"""
Background Task Processing Service
Handles asynchronous job processing for heavy calculations and long-running tasks
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.models.user import User
from app.services.scope1_calculator import Scope1EmissionsCalculator
from app.services.scope2_calculator import Scope2EmissionsCalculator

logger = logging.getLogger(__name__)


class BackgroundTaskService:
    """Service for managing background tasks and job processing"""

    def __init__(self, db: Optional[Session] = None):
        self.db = db or next(get_db())
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg_task")
        self.active_tasks: Dict[str, asyncio.Task] = {}

    async def submit_emissions_calculation(
        self,
        calculation_type: str,  # "scope1" or "scope2"
        calculation_data: Dict[str, Any],
        user_id: str,
        priority: str = "normal",  # "low", "normal", "high"
    ) -> str:
        """
        Submit emissions calculation for background processing

        Args:
            calculation_type: Type of calculation ("scope1" or "scope2")
            calculation_data: Calculation input data
            user_id: User who initiated the calculation
            priority: Task priority level

        Returns:
            Task ID for tracking
        """
        task_id = f"calc_{calculation_type}_{UUID().hex[:8]}"

        # Create background task
        task = asyncio.create_task(
            self._process_emissions_calculation(
                task_id, calculation_type, calculation_data, user_id
            )
        )

        self.active_tasks[task_id] = task

        # Clean up completed tasks
        task.add_done_callback(lambda t: self.active_tasks.pop(task_id, None))

        logger.info(f"Submitted background calculation task: {task_id}")
        return task_id

    async def _process_emissions_calculation(
        self,
        task_id: str,
        calculation_type: str,
        calculation_data: Dict[str, Any],
        user_id: str,
    ) -> Dict[str, Any]:
        """Process emissions calculation in background"""
        try:
            logger.info(f"Starting background calculation: {task_id}")

            # Get fresh database session for this task
            db = next(get_db())

            try:
                if calculation_type == "scope1":
                    calculator = Scope1EmissionsCalculator(db)
                    result = await calculator.calculate_scope1_emissions(
                        calculation_data, user_id
                    )
                elif calculation_type == "scope2":
                    calculator = Scope2EmissionsCalculator(db)
                    result = await calculator.calculate_scope2_emissions(
                        calculation_data, user_id
                    )
                else:
                    raise ValueError(f"Unknown calculation type: {calculation_type}")

                logger.info(f"Completed background calculation: {task_id}")
                return {
                    "task_id": task_id,
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.utcnow().isoformat(),
                }

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Background calculation failed: {task_id} - {str(e)}")
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            }

    async def submit_bulk_calculation(
        self, calculations: List[Dict[str, Any]], user_id: str, batch_size: int = 10
    ) -> str:
        """
        Submit bulk calculations for background processing

        Args:
            calculations: List of calculation requests
            user_id: User who initiated the calculations
            batch_size: Number of calculations to process in parallel

        Returns:
            Batch task ID
        """
        batch_task_id = f"batch_calc_{UUID().hex[:8]}"

        task = asyncio.create_task(
            self._process_bulk_calculations(
                batch_task_id, calculations, user_id, batch_size
            )
        )

        self.active_tasks[batch_task_id] = task
        task.add_done_callback(lambda t: self.active_tasks.pop(batch_task_id, None))

        logger.info(f"Submitted bulk calculation batch: {batch_task_id}")
        return batch_task_id

    async def _process_bulk_calculations(
        self,
        batch_task_id: str,
        calculations: List[Dict[str, Any]],
        user_id: str,
        batch_size: int,
    ) -> Dict[str, Any]:
        """Process bulk calculations in batches"""
        try:
            logger.info(f"Starting bulk calculation batch: {batch_task_id}")

            results = []
            total_calculations = len(calculations)

            # Process in batches
            for i in range(0, total_calculations, batch_size):
                batch = calculations[i : i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} of {batch_task_id}")

                # Process batch in parallel
                batch_tasks = []
                for calc_data in batch:
                    calc_type = calc_data.get("scope", "scope1").replace("scope_", "")
                    task = self.submit_emissions_calculation(
                        calc_type, calc_data, user_id
                    )
                    batch_tasks.append(task)

                # Wait for batch to complete
                batch_results = await asyncio.gather(
                    *batch_tasks, return_exceptions=True
                )
                results.extend(batch_results)

                # Small delay between batches to prevent overwhelming the system
                await asyncio.sleep(0.1)

            successful = sum(
                1
                for r in results
                if isinstance(r, dict) and r.get("status") == "completed"
            )
            failed = len(results) - successful

            logger.info(
                f"Completed bulk calculation batch: {batch_task_id} - {successful}/{total_calculations} successful"
            )

            return {
                "batch_task_id": batch_task_id,
                "status": "completed",
                "total_calculations": total_calculations,
                "successful": successful,
                "failed": failed,
                "results": results,
                "completed_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Bulk calculation batch failed: {batch_task_id} - {str(e)}")
            return {
                "batch_task_id": batch_task_id,
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.utcnow().isoformat(),
            }

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a background task"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if task.done():
                try:
                    return task.result()
                except Exception as e:
                    return {"task_id": task_id, "status": "failed", "error": str(e)}
            else:
                return {"task_id": task_id, "status": "running"}
        else:
            return {"task_id": task_id, "status": "not_found"}

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running background task"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return True
        return False

    async def get_active_tasks(self) -> List[Dict[str, Any]]:
        """Get list of currently active tasks"""
        active = []
        for task_id, task in self.active_tasks.items():
            if not task.done():
                active.append({"task_id": task_id, "status": "running"})
        return active

    def cleanup(self):
        """Clean up resources"""
        self.executor.shutdown(wait=False)
        # Cancel all active tasks
        for task in self.active_tasks.values():
            if not task.done():
                task.cancel()


# Global background task service instance
background_task_service = BackgroundTaskService()
