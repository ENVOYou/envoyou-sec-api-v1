"""
Unit tests for Workflow Service
Tests multi-level approval workflow functionality
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from app.services.workflow_service import WorkflowService
from app.schemas.workflow import (
    WorkflowCreate,
    ApprovalActionRequest,
    ApprovalAction,
    UserRole
)
from app.models.workflow import (
    Workflow,
    WorkflowTemplate,
    ApprovalRequest,
    WorkflowHistory,
    WorkflowState
)


class TestWorkflowService:
    """Test workflow service functionality"""
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def sample_template(self):
        """Sample workflow template"""
        return WorkflowTemplate(
            id=uuid4(),
            name="Report Approval Workflow",
            workflow_type="report_approval",
            is_active=True,
            steps_config=[
                {
                    "step_name": "finance_approval",
                    "required_role": "finance_team",
                    "sequence_order": 1,
                    "timeout_hours": 48
                },
                {
                    "step_name": "legal_approval", 
                    "required_role": "general_counsel",
                    "sequence_order": 2,
                    "timeout_hours": 24
                },
                {
                    "step_name": "cfo_approval",
                    "required_role": "cfo", 
                    "sequence_order": 3,
                    "timeout_hours": 24
                }
            ]
        )
    
    @pytest.fixture
    def sample_workflow_data(self, sample_template):
        """Sample workflow creation data"""
        return WorkflowCreate(
            template_id=sample_template.id,
            subject_type="consolidated_emissions",
            subject_id=uuid4(),
            priority="normal"
        )
    
    @pytest.mark.asyncio
    async def test_create_workflow_success(self, mock_db, sample_template, sample_workflow_data):
        """Test successful workflow creation"""
        # Mock template query
        mock_db.query.return_value.filter.return_value.first.return_value = sample_template
        
        # Mock existing workflow check (none found)
        mock_db.query.return_value.filter.return_value.first.side_effect = [sample_template, None]
        
        # Mock workflow creation
        created_workflow = Workflow(
            id=uuid4(),
            template_id=sample_workflow_data.template_id,
            subject_type=sample_workflow_data.subject_type,
            subject_id=sample_workflow_data.subject_id,
            current_state=WorkflowState.DRAFT,
            initiated_by=uuid4(),
            priority=sample_workflow_data.priority,
            initiated_at=datetime.utcnow(),
            workflow_metadata={}
        )
        
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock(side_effect=lambda obj: [
            setattr(obj, 'id', created_workflow.id),
            setattr(obj, 'initiated_at', created_workflow.initiated_at),
            setattr(obj, 'workflow_metadata', created_workflow.workflow_metadata)
        ])
        
        service = WorkflowService(mock_db)
        service._log_workflow_history = AsyncMock()  # Mock the history logging method
        initiator_id = uuid4()
        
        result = await service.create_workflow(sample_workflow_data, initiator_id)
        
        # Verify workflow was created
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        assert result.subject_type == sample_workflow_data.subject_type
        assert result.current_state.value == WorkflowState.DRAFT.value
    
    @pytest.mark.asyncio
    async def test_create_workflow_template_not_found(self, mock_db, sample_workflow_data):
        """Test workflow creation with invalid template"""
        # Mock template not found
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = WorkflowService(mock_db)
        initiator_id = uuid4()
        
        with pytest.raises(Exception) as exc_info:
            await service.create_workflow(sample_workflow_data, initiator_id)
        
        assert "template not found" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_submit_for_approval_success(self, mock_db, sample_template):
        """Test successful workflow submission for approval"""
        workflow_id = uuid4()
        submitter_id = uuid4()
        
        # Mock workflow
        workflow = Workflow(
            id=workflow_id,
            template_id=sample_template.id,
            current_state=WorkflowState.DRAFT,
            template=sample_template
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = workflow
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = WorkflowService(mock_db)
        
        # Mock _find_assignee_for_role method
        service._find_assignee_for_role = AsyncMock(return_value=uuid4())
        service._send_approval_notifications = AsyncMock()
        service._create_history_entry = AsyncMock()
        
        result = await service.submit_for_approval(workflow_id, submitter_id)
        
        # Verify approval requests were created
        assert mock_db.add.call_count >= 3  # 3 approval steps
        mock_db.commit.assert_called_once()
        
        # Verify notifications were sent
        service._send_approval_notifications.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_submit_for_approval_invalid_state(self, mock_db):
        """Test workflow submission with invalid state"""
        workflow_id = uuid4()
        submitter_id = uuid4()
        
        # Mock workflow in wrong state
        workflow = Workflow(
            id=workflow_id,
            current_state=WorkflowState.APPROVED
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = workflow
        
        service = WorkflowService(mock_db)
        
        with pytest.raises(Exception) as exc_info:
            await service.submit_for_approval(workflow_id, submitter_id)
        
        assert "cannot submit" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_process_approval_action_approve(self, mock_db):
        """Test processing approval action - approve"""
        approval_request_id = uuid4()
        actor_id = uuid4()
        
        # Mock approval request
        approval_request = ApprovalRequest(
            id=approval_request_id,
            workflow_id=uuid4(),
            assigned_to=actor_id,
            status="pending",
            assigned_role=UserRole.FINANCE_TEAM,
            step_name="finance_approval"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval_request
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = WorkflowService(mock_db)
        service._handle_approval = AsyncMock()
        
        action_data = ApprovalActionRequest(
            action=ApprovalAction.APPROVE,
            comments="Looks good to me"
        )
        
        result = await service.process_approval_action(approval_request_id, action_data, actor_id)
        
        # Verify approval was processed
        assert approval_request.action_taken == ApprovalAction.APPROVE
        assert approval_request.status == "approved"
        assert approval_request.comments == "Looks good to me"
        service._handle_approval.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_approval_action_reject(self, mock_db):
        """Test processing approval action - reject"""
        approval_request_id = uuid4()
        actor_id = uuid4()
        
        # Mock approval request
        approval_request = ApprovalRequest(
            id=approval_request_id,
            workflow_id=uuid4(),
            assigned_to=actor_id,
            status="pending",
            assigned_role=UserRole.FINANCE_TEAM,
            step_name="finance_approval"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval_request
        mock_db.commit = Mock()
        mock_db.refresh = Mock()
        
        service = WorkflowService(mock_db)
        service._handle_rejection = AsyncMock()
        
        action_data = ApprovalActionRequest(
            action=ApprovalAction.REJECT,
            comments="Needs more work"
        )
        
        result = await service.process_approval_action(approval_request_id, action_data, actor_id)
        
        # Verify rejection was processed
        assert approval_request.action_taken == ApprovalAction.REJECT
        assert approval_request.status == "rejected"
        assert approval_request.comments == "Needs more work"
        service._handle_rejection.assert_called_once()
        mock_db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_approval_action_unauthorized(self, mock_db):
        """Test processing approval action by unauthorized user"""
        approval_request_id = uuid4()
        actor_id = uuid4()
        different_user_id = uuid4()
        
        # Mock approval request assigned to different user
        approval_request = ApprovalRequest(
            id=approval_request_id,
            assigned_to=different_user_id,  # Different user
            status="pending"
        )
        
        mock_db.query.return_value.filter.return_value.first.return_value = approval_request
        
        service = WorkflowService(mock_db)
        
        action_data = ApprovalActionRequest(action=ApprovalAction.APPROVE)
        
        with pytest.raises(Exception) as exc_info:
            await service.process_approval_action(approval_request_id, action_data, actor_id)
        
        assert "not authorized" in str(exc_info.value.detail).lower()
    
    @pytest.mark.asyncio
    async def test_get_pending_approvals(self, mock_db):
        """Test getting pending approvals for a user"""
        user_id = uuid4()
        
        # Mock pending approval requests
        pending_requests = [
            ApprovalRequest(
                id=uuid4(),
                workflow_id=uuid4(),
                assigned_to=user_id,
                status="pending",
                step_name="finance_approval",
                assigned_role=UserRole.FINANCE_TEAM,
                assigned_at=datetime.utcnow()
            ),
            ApprovalRequest(
                id=uuid4(),
                workflow_id=uuid4(),
                assigned_to=user_id,
                status="pending",
                step_name="legal_approval",
                assigned_role=UserRole.GENERAL_COUNSEL,
                assigned_at=datetime.utcnow()
            )
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = pending_requests
        
        service = WorkflowService(mock_db)
        
        result = await service.get_pending_approvals(user_id)
        
        # Verify pending approvals returned
        assert len(result) == 2
        assert all(req.status == "pending" for req in result)
    
    @pytest.mark.asyncio
    async def test_get_workflow_summary(self, mock_db):
        """Test getting workflow summary"""
        workflow_id = uuid4()
        
        # Mock workflow
        workflow = Workflow(
            id=workflow_id,
            subject_type="consolidated_emissions",
            subject_id=uuid4(),
            current_state=WorkflowState.PENDING_FINANCE_APPROVAL,
            current_step="finance_approval",
            initiated_by=uuid4(),
            initiated_at=datetime.utcnow(),
            priority="normal"
        )
        
        # Mock approval requests
        approval_requests = [
            Mock(status="approved"),
            Mock(status="pending", due_date=datetime.utcnow() + timedelta(hours=1)),
            Mock(status="pending", due_date=datetime.utcnow() - timedelta(hours=1))  # Overdue
        ]
        
        mock_db.query.return_value.filter.return_value.first.return_value = workflow
        mock_db.query.return_value.filter.return_value.all.return_value = approval_requests
        
        service = WorkflowService(mock_db)
        
        result = await service.get_workflow_summary(workflow_id)
        
        # Verify summary statistics
        assert result.id == workflow_id
        assert result.current_state == WorkflowState.PENDING_FINANCE_APPROVAL
        assert result.total_steps == 3
        assert result.completed_steps == 1
        assert result.pending_steps == 2
        assert result.overdue_steps == 1
    
    @pytest.mark.asyncio
    async def test_get_workflow_history(self, mock_db):
        """Test getting workflow history"""
        workflow_id = uuid4()
        
        # Mock history entries
        history_entries = [
            WorkflowHistory(
                id=uuid4(),
                workflow_id=workflow_id,
                from_state=None,
                to_state=WorkflowState.DRAFT,
                action="workflow_created",
                actor_id=uuid4(),
                actor_role=UserRole.SUBMITTER,
                change_timestamp=datetime.utcnow(),
                comments="Workflow created"
            ),
            WorkflowHistory(
                id=uuid4(),
                workflow_id=workflow_id,
                from_state=WorkflowState.DRAFT,
                to_state=WorkflowState.PENDING_FINANCE_APPROVAL,
                action="submitted_for_approval",
                actor_id=uuid4(),
                actor_role=UserRole.SUBMITTER,
                change_timestamp=datetime.utcnow(),
                comments="Submitted for approval"
            )
        ]
        
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = history_entries
        
        service = WorkflowService(mock_db)
        
        result = await service.get_workflow_history(workflow_id)
        
        # Verify history entries returned
        assert len(result) == 2
        assert result[0]["action"] == "workflow_created"
        assert result[1]["action"] == "submitted_for_approval"
    
    def test_get_state_for_step(self, mock_db):
        """Test mapping step names to workflow states"""
        service = WorkflowService(mock_db)
        
        assert service._get_state_for_step("finance_approval") == WorkflowState.PENDING_FINANCE_APPROVAL
        assert service._get_state_for_step("legal_approval") == WorkflowState.PENDING_LEGAL_APPROVAL
        assert service._get_state_for_step("cfo_approval") == WorkflowState.PENDING_CFO_APPROVAL
        assert service._get_state_for_step("unknown_step") == WorkflowState.PENDING_FINANCE_APPROVAL  # Default
    
    @pytest.mark.asyncio
    async def test_find_assignee_for_role(self, mock_db):
        """Test finding assignee for role"""
        service = WorkflowService(mock_db)
        
        # Test role mappings
        finance_assignee = await service._find_assignee_for_role("finance_team")
        legal_assignee = await service._find_assignee_for_role("general_counsel")
        cfo_assignee = await service._find_assignee_for_role("cfo")
        unknown_assignee = await service._find_assignee_for_role("unknown_role")
        
        assert finance_assignee is not None
        assert legal_assignee is not None
        assert cfo_assignee is not None
        assert unknown_assignee is None