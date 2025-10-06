"""
Workflow Service for Multi-level Approval System

Handles workflow creation, approval routing, state management, and notifications
for SEC compliance report approval process.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.workflow import (
    ApprovalRequest,
    NotificationQueue,
    Workflow,
    WorkflowHistory,
    WorkflowTemplate
)
from app.models.workflow import WorkflowState, ApprovalAction, UserRole
from app.schemas.workflow import (
    ApprovalActionRequest,
    ApprovalRequestCreate,
    ApprovalRequestResponse,
    WorkflowCreate,
    WorkflowMetrics,
    WorkflowResponse,
    WorkflowSearchRequest,
    WorkflowSummary
)

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for managing multi-level approval workflows"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_workflow(self, workflow_data: WorkflowCreate, initiator_id: UUID) -> WorkflowResponse:
        """Create a new workflow instance"""
        try:
            # Validate template exists and is active
            template = self.db.query(WorkflowTemplate).filter(
                and_(
                    WorkflowTemplate.id == workflow_data.template_id,
                    WorkflowTemplate.is_active == True
                )
            ).first()
            
            if not template:
                raise HTTPException(
                    status_code=404,
                    detail="Workflow template not found or inactive"
                )
            
            # Check if workflow already exists for this subject
            existing_workflow = self.db.query(Workflow).filter(
                and_(
                    Workflow.subject_type == workflow_data.subject_type,
                    Workflow.subject_id == workflow_data.subject_id,
                    Workflow.current_state.in_([
                        WorkflowState.PENDING_FINANCE_APPROVAL,
                        WorkflowState.PENDING_LEGAL_APPROVAL,
                        WorkflowState.PENDING_CFO_APPROVAL
                    ])
                )
            ).first()
            
            if existing_workflow:
                raise HTTPException(
                    status_code=409,
                    detail="Active workflow already exists for this subject"
                )
            
            # Create workflow
            workflow = Workflow(
                template_id=workflow_data.template_id,
                subject_type=workflow_data.subject_type,
                subject_id=workflow_data.subject_id,
                current_state=WorkflowState.DRAFT,
                initiated_by=initiator_id,
                priority=workflow_data.priority,
                due_date=workflow_data.due_date,
                workflow_metadata=workflow_data.metadata or {}
            )
            
            self.db.add(workflow)
            self.db.commit()
            self.db.refresh(workflow)
            
            # Create workflow history entry
            await self._log_workflow_history(
                workflow_id=workflow.id,
                from_state=None,
                to_state=WorkflowState.DRAFT,
                action="workflow_created",
                actor_id=initiator_id,
                actor_role="submitter",
                comments="Workflow created"
            )
            
            logger.info(f"Created workflow {workflow.id} for {workflow_data.subject_type}:{workflow_data.subject_id}")
            
            # Map workflow_metadata to metadata for response
            workflow_dict = {
                'id': workflow.id,
                'template_id': workflow.template_id,
                'subject_type': workflow.subject_type,
                'subject_id': workflow.subject_id,
                'current_state': workflow.current_state,
                'current_step': workflow.current_step,
                'initiated_by': workflow.initiated_by,
                'initiated_at': workflow.initiated_at,
                'completed_at': workflow.completed_at,
                'priority': workflow.priority,
                'due_date': workflow.due_date,
                'metadata': workflow.workflow_metadata
            }
            return WorkflowResponse(**workflow_dict)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating workflow: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to create workflow"
            )
    
    async def submit_for_approval(self, workflow_id: UUID, submitter_id: UUID) -> WorkflowResponse:
        """Submit workflow for approval, creating approval requests"""
        try:
            workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
            
            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            if workflow.current_state != WorkflowState.DRAFT:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot submit workflow in state: {workflow.current_state}"
                )
            
            # Get template configuration
            template = workflow.template
            steps_config = template.steps_config
            
            if not steps_config:
                raise HTTPException(
                    status_code=400,
                    detail="Workflow template has no steps configured"
                )
            
            # Create approval requests for all steps
            approval_requests = []
            for step_config in steps_config:
                # Find user with required role (simplified - in real implementation, 
                # you'd have a more sophisticated user assignment logic)
                assignee = await self._find_assignee_for_role(step_config["required_role"])
                
                if not assignee:
                    raise HTTPException(
                        status_code=400,
                        detail=f"No user found with role: {step_config['required_role']}"
                    )
                
                # Calculate due date for this step
                due_date = None
                if step_config.get("timeout_hours"):
                    due_date = datetime.utcnow() + timedelta(hours=step_config["timeout_hours"])
                
                approval_request = ApprovalRequest(
                    workflow_id=workflow.id,
                    step_name=step_config["step_name"],
                    sequence_order=step_config["sequence_order"],
                    assigned_to=assignee,
                    assigned_role=UserRole(step_config["required_role"]),
                    due_date=due_date,
                    status="pending"
                )
                
                approval_requests.append(approval_request)
                self.db.add(approval_request)
            
            # Update workflow state to first approval step
            first_step = min(steps_config, key=lambda x: x["sequence_order"])
            new_state = self._get_state_for_step(first_step["step_name"])
            
            workflow.current_state = new_state
            workflow.current_step = first_step["step_name"]
            
            self.db.commit()
            
            # Create history entry
            await self._log_workflow_history(
                workflow_id=workflow.id,
                from_state=WorkflowState.DRAFT,
                to_state=new_state,
                action="submitted_for_approval",
                actor_id=submitter_id,
                actor_role="submitter",
                comments="Workflow submitted for approval"
            )
            
            # Send notifications to first step approvers
            await self._send_approval_notifications(workflow.id, first_step["step_name"])
            
            logger.info(f"Submitted workflow {workflow_id} for approval")
            
            self.db.refresh(workflow)
            # Map workflow_metadata to metadata for response
            workflow_dict = {
                'id': workflow.id,
                'template_id': workflow.template_id,
                'subject_type': workflow.subject_type,
                'subject_id': workflow.subject_id,
                'current_state': workflow.current_state,
                'current_step': workflow.current_step,
                'initiated_by': workflow.initiated_by,
                'initiated_at': workflow.initiated_at,
                'completed_at': workflow.completed_at,
                'priority': workflow.priority,
                'due_date': workflow.due_date,
                'metadata': workflow.workflow_metadata
            }
            return WorkflowResponse(**workflow_dict)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error submitting workflow for approval: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to submit workflow for approval"
            )
    
    async def process_approval_action(
        self, 
        approval_request_id: UUID, 
        action_data: ApprovalActionRequest, 
        actor_id: UUID
    ) -> ApprovalRequestResponse:
        """Process an approval action (approve, reject, delegate, etc.)"""
        try:
            approval_request = self.db.query(ApprovalRequest).filter(
                ApprovalRequest.id == approval_request_id
            ).first()
            
            if not approval_request:
                raise HTTPException(status_code=404, detail="Approval request not found")
            
            if approval_request.status != "pending":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot act on approval request with status: {approval_request.status}"
                )
            
            # Validate actor has permission
            if approval_request.assigned_to != actor_id and approval_request.delegated_to != actor_id:
                raise HTTPException(
                    status_code=403,
                    detail="Not authorized to act on this approval request"
                )
            
            # Process the action
            approval_request.action_taken = action_data.action
            approval_request.responded_at = datetime.utcnow()
            approval_request.comments = action_data.comments
            approval_request.response_metadata = action_data.metadata or {}
            
            if action_data.action == ApprovalAction.APPROVE:
                approval_request.status = "approved"
                await self._handle_approval(approval_request, actor_id)
                
            elif action_data.action == ApprovalAction.REJECT:
                approval_request.status = "rejected"
                await self._handle_rejection(approval_request, actor_id)
                
            elif action_data.action == ApprovalAction.REQUEST_CHANGES:
                approval_request.status = "changes_requested"
                await self._handle_change_request(approval_request, actor_id)
                
            elif action_data.action == ApprovalAction.DELEGATE:
                if not action_data.delegate_to:
                    raise HTTPException(
                        status_code=400,
                        detail="delegate_to is required for delegation action"
                    )
                approval_request.status = "delegated"
                approval_request.delegated_to = action_data.delegate_to
                approval_request.delegation_reason = action_data.delegation_reason
                await self._handle_delegation(approval_request, actor_id)
            
            self.db.commit()
            self.db.refresh(approval_request)
            
            logger.info(f"Processed approval action {action_data.action} for request {approval_request_id}")
            
            return ApprovalRequestResponse.model_validate(approval_request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error processing approval action: {str(e)}")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Failed to process approval action"
            )
    
    async def get_pending_approvals(self, user_id: UUID) -> List[ApprovalRequestResponse]:
        """Get pending approval requests for a user"""
        try:
            pending_requests = self.db.query(ApprovalRequest).filter(
                and_(
                    or_(
                        ApprovalRequest.assigned_to == user_id,
                        ApprovalRequest.delegated_to == user_id
                    ),
                    ApprovalRequest.status == "pending"
                )
            ).order_by(desc(ApprovalRequest.assigned_at)).all()
            
            return [ApprovalRequestResponse.model_validate(req) for req in pending_requests]
            
        except Exception as e:
            logger.error(f"Error getting pending approvals: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get pending approvals"
            )
    
    async def get_workflow_summary(self, workflow_id: UUID) -> WorkflowSummary:
        """Get workflow summary with current status"""
        try:
            workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
            
            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found")
            
            # Get approval requests statistics
            approval_requests = self.db.query(ApprovalRequest).filter(
                ApprovalRequest.workflow_id == workflow_id
            ).all()
            
            total_steps = len(approval_requests)
            completed_steps = len([req for req in approval_requests if req.status in ["approved", "rejected"]])
            pending_steps = len([req for req in approval_requests if req.status == "pending"])
            overdue_steps = len([
                req for req in approval_requests 
                if req.status == "pending" and req.due_date and req.due_date < datetime.utcnow()
            ])
            
            # Get current pending approvals
            pending_approvals = [
                ApprovalRequestResponse.model_validate(req) 
                for req in approval_requests 
                if req.status == "pending"
            ]
            
            summary = WorkflowSummary(
                id=workflow.id,
                subject_type=workflow.subject_type,
                subject_id=workflow.subject_id,
                current_state=workflow.current_state,
                current_step=workflow.current_step,
                initiated_by=workflow.initiated_by,
                initiated_at=workflow.initiated_at,
                priority=workflow.priority,
                due_date=workflow.due_date,
                total_steps=total_steps,
                completed_steps=completed_steps,
                pending_steps=pending_steps,
                overdue_steps=overdue_steps,
                pending_approvals=pending_approvals
            )
            
            return summary
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting workflow summary: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get workflow summary"
            )
    
    async def get_workflow_history(self, workflow_id: UUID) -> List[Dict]:
        """Get workflow history/audit trail"""
        try:
            history_entries = self.db.query(WorkflowHistory).filter(
                WorkflowHistory.workflow_id == workflow_id
            ).order_by(desc(WorkflowHistory.change_timestamp)).all()
            
            return [
                {
                    "id": entry.id,
                    "from_state": entry.from_state.value if entry.from_state else None,
                    "to_state": entry.to_state.value,
                    "action": entry.action,
                    "actor_id": entry.actor_id,
                    "actor_role": entry.actor_role.value,
                    "change_timestamp": entry.change_timestamp,
                    "comments": entry.comments,
                    "change_metadata": entry.change_metadata
                }
                for entry in history_entries
            ]
            
        except Exception as e:
            logger.error(f"Error getting workflow history: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Failed to get workflow history"
            )
    
    # Private helper methods
    
    async def _handle_approval(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle approval action - advance workflow if all steps in current stage are complete"""
        workflow = approval_request.workflow
        
        # Check if this was the last pending request for current step
        pending_requests = self.db.query(ApprovalRequest).filter(
            and_(
                ApprovalRequest.workflow_id == workflow.id,
                ApprovalRequest.step_name == approval_request.step_name,
                ApprovalRequest.status == "pending"
            )
        ).count()
        
        if pending_requests == 0:
            # All approvals for this step are complete, advance workflow
            await self._advance_workflow(workflow, actor_id)
    
    async def _handle_rejection(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle rejection action - set workflow to rejected state"""
        workflow = approval_request.workflow
        workflow.current_state = WorkflowState.REJECTED
        workflow.completed_at = datetime.utcnow()
        
        await self._create_history_entry(
            workflow_id=workflow.id,
            from_state=workflow.current_state,
            to_state=WorkflowState.REJECTED,
            action="workflow_rejected",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role,
            comments=approval_request.comments
        )
    
    async def _handle_change_request(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle change request - send workflow back to draft"""
        workflow = approval_request.workflow
        workflow.current_state = WorkflowState.DRAFT
        workflow.current_step = None
        
        await self._create_history_entry(
            workflow_id=workflow.id,
            from_state=workflow.current_state,
            to_state=WorkflowState.DRAFT,
            action="changes_requested",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role,
            comments=approval_request.comments
        )
    
    async def _handle_delegation(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle delegation action"""
        await self._create_history_entry(
            workflow_id=approval_request.workflow_id,
            from_state=None,
            to_state=None,
            action="approval_delegated",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role,
            comments=f"Delegated to user {approval_request.delegated_to}: {approval_request.delegation_reason}"
        )
        
        # Send notification to delegate
        await self._send_delegation_notification(approval_request)
    
    async def _advance_workflow(self, workflow: Workflow, actor_id: UUID):
        """Advance workflow to next step or complete it"""
        template = workflow.template
        steps_config = template.steps_config
        
        # Find current step and next step
        current_step_config = next(
            (step for step in steps_config if step["step_name"] == workflow.current_step),
            None
        )
        
        if not current_step_config:
            logger.error(f"Current step {workflow.current_step} not found in template")
            return
        
        # Find next step
        next_step_config = next(
            (step for step in steps_config 
             if step["sequence_order"] > current_step_config["sequence_order"]),
            None
        )
        
        if next_step_config:
            # Advance to next step
            new_state = self._get_state_for_step(next_step_config["step_name"])
            old_state = workflow.current_state
            
            workflow.current_state = new_state
            workflow.current_step = next_step_config["step_name"]
            
            await self._create_history_entry(
                workflow_id=workflow.id,
                from_state=old_state,
                to_state=new_state,
                action="workflow_advanced",
                actor_id=actor_id,
                actor_role=UserRole.ADMIN,  # System action
                comments=f"Advanced to step: {next_step_config['step_name']}"
            )
            
            # Send notifications for next step
            await self._send_approval_notifications(workflow.id, next_step_config["step_name"])
        else:
            # Workflow complete
            old_state = workflow.current_state
            workflow.current_state = WorkflowState.APPROVED
            workflow.current_step = None
            workflow.completed_at = datetime.utcnow()
            
            await self._create_history_entry(
                workflow_id=workflow.id,
                from_state=old_state,
                to_state=WorkflowState.APPROVED,
                action="workflow_completed",
                actor_id=actor_id,
                actor_role=UserRole.ADMIN,
                comments="Workflow completed successfully"
            )
    
    async def _create_history_entry(
        self, 
        workflow_id: UUID, 
        from_state: Optional[WorkflowState], 
        to_state: WorkflowState,
        action: str,
        actor_id: UUID,
        actor_role: UserRole,
        comments: Optional[str] = None
    ):
        """Create workflow history entry"""
        history_entry = WorkflowHistory(
            workflow_id=workflow_id,
            from_state=from_state,
            to_state=to_state,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            comments=comments
        )
        
        self.db.add(history_entry)
    
    async def _find_assignee_for_role(self, role: str) -> Optional[UUID]:
        """Find a user with the specified role (simplified implementation)"""
        # In a real implementation, this would query the users table
        # For now, return a mock UUID based on role
        role_to_uuid = {
            "finance_team": UUID("11111111-1111-1111-1111-111111111111"),
            "general_counsel": UUID("22222222-2222-2222-2222-222222222222"),
            "cfo": UUID("33333333-3333-3333-3333-333333333333")
        }
        return role_to_uuid.get(role)
    
    def _get_state_for_step(self, step_name: str) -> WorkflowState:
        """Map step name to workflow state"""
        step_to_state = {
            "finance_approval": WorkflowState.PENDING_FINANCE_APPROVAL,
            "legal_approval": WorkflowState.PENDING_LEGAL_APPROVAL,
            "cfo_approval": WorkflowState.PENDING_CFO_APPROVAL
        }
        return step_to_state.get(step_name, WorkflowState.PENDING_FINANCE_APPROVAL)
    
    async def _send_approval_notifications(self, workflow_id: UUID, step_name: str):
        """Send notifications to approvers for a specific step"""
        # Get pending approval requests for this step
        pending_requests = self.db.query(ApprovalRequest).filter(
            and_(
                ApprovalRequest.workflow_id == workflow_id,
                ApprovalRequest.step_name == step_name,
                ApprovalRequest.status == "pending"
            )
        ).all()
        
        for request in pending_requests:
            notification = NotificationQueue(
                workflow_id=workflow_id,
                recipient_id=request.assigned_to,
                notification_type="approval_request",
                subject=f"Approval Required: {step_name}",
                message=f"You have a pending approval request for workflow {workflow_id}",
                delivery_method="email"
            )
            self.db.add(notification)
    
    async def _send_delegation_notification(self, approval_request: ApprovalRequest):
        """Send notification about delegation"""
        notification = NotificationQueue(
            workflow_id=approval_request.workflow_id,
            recipient_id=approval_request.delegated_to,
            notification_type="delegation",
            subject="Approval Delegated to You",
            message=f"An approval has been delegated to you: {approval_request.step_name}",
            delivery_method="email"
        )
        self.db.add(notification)
    
    async def _log_workflow_history(
        self,
        workflow_id: UUID,
        from_state: WorkflowState,
        to_state: WorkflowState,
        action: str,
        actor_id: UUID,
        actor_role: str,
        comments: str = None,
        metadata: dict = None
    ):
        """Log workflow state change to history"""
        from app.models.workflow import WorkflowHistory
        
        from app.models.workflow import UserRole as ModelUserRole
        
        # Convert string role to enum if needed
        if isinstance(actor_role, str):
            role_mapping = {
                "submitter": ModelUserRole.SUBMITTER,
                "finance_team": ModelUserRole.FINANCE_TEAM,
                "legal_team": ModelUserRole.LEGAL_TEAM,
                "cfo": ModelUserRole.CFO,
                "admin": ModelUserRole.ADMIN
            }
            actor_role_enum = role_mapping.get(actor_role, ModelUserRole.SUBMITTER)
        else:
            actor_role_enum = actor_role
        
        history_entry = WorkflowHistory(
            id=uuid4(),
            workflow_id=workflow_id,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role_enum,
            comments=comments,
            change_metadata=metadata or {}
        )
        
        self.db.add(history_entry)
    
    async def _send_approval_notification(
        self,
        workflow_id: UUID,
        recipient_id: UUID,
        notification_type: str,
        subject: str,
        message: str
    ):
        """Send approval notification to recipient"""
        from app.models.workflow import NotificationQueue
        
        notification = NotificationQueue(
            id=uuid4(),
            workflow_id=workflow_id,
            recipient_id=recipient_id,
            notification_type=notification_type,
            subject=subject,
            message=message,
            delivery_method="email",
            status="pending",
            created_at=datetime.utcnow()
        )
        
        self.db.add(notification)
    
    async def _handle_approval(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle approval action"""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == approval_request.workflow_id
        ).first()
        
        if not workflow:
            return
        
        # Log history
        await self._log_workflow_history(
            workflow_id=workflow.id,
            from_state=workflow.current_state,
            to_state=workflow.current_state,  # Will be updated by next step logic
            action="approved",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role.value,
            comments=approval_request.comments
        )
        
        # Check if this was the final approval step
        if approval_request.step_name == "cfo_approval":
            workflow.current_state = WorkflowState.APPROVED
            workflow.current_step = "completed"
            workflow.completed_at = datetime.utcnow()
        else:
            # Move to next approval step
            await self._advance_to_next_step(workflow, approval_request.step_name)
    
    async def _handle_rejection(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle rejection action"""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == approval_request.workflow_id
        ).first()
        
        if not workflow:
            return
        
        # Update workflow state to rejected
        workflow.current_state = WorkflowState.REJECTED
        workflow.current_step = "rejected"
        workflow.completed_at = datetime.utcnow()
        
        # Log history
        await self._log_workflow_history(
            workflow_id=workflow.id,
            from_state=workflow.current_state,
            to_state=WorkflowState.REJECTED,
            action="rejected",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role.value,
            comments=approval_request.comments
        )
    
    async def _handle_change_request(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle change request action"""
        workflow = self.db.query(Workflow).filter(
            Workflow.id == approval_request.workflow_id
        ).first()
        
        if not workflow:
            return
        
        # Update workflow state to changes requested
        workflow.current_state = WorkflowState.CHANGES_REQUESTED
        workflow.current_step = "changes_requested"
        
        # Log history
        await self._log_workflow_history(
            workflow_id=workflow.id,
            from_state=workflow.current_state,
            to_state=WorkflowState.CHANGES_REQUESTED,
            action="changes_requested",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role.value,
            comments=approval_request.comments
        )
    
    async def _handle_delegation(self, approval_request: ApprovalRequest, actor_id: UUID):
        """Handle delegation action"""
        # Send notification to delegated user
        await self._send_delegation_notification(approval_request)
        
        # Log history
        await self._log_workflow_history(
            workflow_id=approval_request.workflow_id,
            from_state=None,  # No state change for delegation
            to_state=None,
            action="delegated",
            actor_id=actor_id,
            actor_role=approval_request.assigned_role.value,
            comments=f"Delegated to user {approval_request.delegated_to}: {approval_request.delegation_reason}"
        )
    
    async def _advance_to_next_step(self, workflow: Workflow, current_step: str):
        """Advance workflow to next approval step"""
        step_sequence = {
            "finance_approval": ("legal_approval", WorkflowState.PENDING_LEGAL_APPROVAL),
            "legal_approval": ("cfo_approval", WorkflowState.PENDING_CFO_APPROVAL)
        }
        
        if current_step in step_sequence:
            next_step, next_state = step_sequence[current_step]
            workflow.current_step = next_step
            workflow.current_state = next_state
            
            # Create next approval request
            assignee = await self._find_assignee_for_role(
                "legal_team" if next_step == "legal_approval" else "cfo"
            )
            
            if assignee:
                next_approval = ApprovalRequest(
                    id=uuid4(),
                    workflow_id=workflow.id,
                    step_name=next_step,
                    sequence_order=2 if next_step == "legal_approval" else 3,
                    assigned_to=assignee,
                    assigned_role=UserRole.LEGAL_TEAM if next_step == "legal_approval" else UserRole.CFO,
                    status="pending",
                    assigned_at=datetime.utcnow(),
                    due_date=datetime.utcnow() + timedelta(days=3)
                )
                self.db.add(next_approval)
                
                # Send notification
                await self._send_approval_notification(
                    workflow_id=workflow.id,
                    recipient_id=assignee,
                    notification_type="approval_request",
                    subject=f"Approval Required: {next_step}",
                    message=f"A workflow requires your approval at step: {next_step}"
                )