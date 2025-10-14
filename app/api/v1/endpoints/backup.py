"""
Backup Management Endpoints
API endpoints for backup operations and management
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_active_user, require_admin
from app.db.database import get_db
from app.models.user import User
from app.services.backup_service import create_backup_service

router = APIRouter()


@router.post("/create")
async def create_backup(
    backup_type: str = Query("full", description="Backup type: full or incremental"),
    backup_name: Optional[str] = Query(None, description="Custom backup name"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Create a new backup

    Requires admin privileges.
    """
    backup_service = create_backup_service(db)

    try:
        if backup_type == "full":
            result = await backup_service.create_full_backup(backup_name)
        elif backup_type == "incremental":
            result = await backup_service.create_incremental_backup(backup_name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid backup type: {backup_type}. Must be 'full' or 'incremental'",
            )

        if result["status"] == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Backup failed: {result.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup creation failed: {str(e)}",
        )


@router.get("/list")
async def list_backups(
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of backups to return"
    ),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    List all available backups

    Requires admin privileges.
    """
    backup_service = create_backup_service(db)

    try:
        backups = await backup_service.list_backups()
        return {
            "backups": backups[:limit],
            "total_count": len(backups),
            "returned_count": min(len(backups), limit),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list backups: {str(e)}",
        )


@router.get("/{backup_id}")
async def get_backup_details(
    backup_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get detailed information about a specific backup

    Requires admin privileges.
    """
    backup_service = create_backup_service(db)

    try:
        backups = await backup_service.list_backups()
        backup = next((b for b in backups if b["backup_id"] == backup_id), None)

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found",
            )

        return backup

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get backup details: {str(e)}",
        )


@router.post("/{backup_id}/restore")
async def restore_backup(
    backup_id: str,
    target_database: Optional[str] = Query(
        None, description="Target database URL (optional)"
    ),
    dry_run: bool = Query(True, description="Perform dry run (no actual restore)"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Restore from a backup

    Requires admin privileges.
    WARNING: This operation can be destructive!
    """
    backup_service = create_backup_service(db)

    try:
        # Verify backup exists
        backups = await backup_service.list_backups()
        backup = next((b for b in backups if b["backup_id"] == backup_id), None)

        if not backup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found",
            )

        if backup["status"] != "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Backup {backup_id} is not in completed status",
            )

        if dry_run:
            return {
                "message": "Dry run completed successfully",
                "backup_id": backup_id,
                "backup_type": backup["type"],
                "backup_timestamp": backup["timestamp"],
                "would_restore_to": target_database or "current_database",
                "dry_run": True,
            }

        # Perform actual restore
        result = await backup_service.restore_backup(backup_id, target_database)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Restore failed: {result.get('error', 'Unknown error')}",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore operation failed: {str(e)}",
        )


@router.delete("/{backup_id}")
async def delete_backup(
    backup_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Delete a backup

    Requires admin privileges.
    """
    import shutil
    from pathlib import Path

    from app.core.config import settings

    try:
        backup_dir = Path(settings.BACKUP_DIR) / backup_id

        if not backup_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Backup {backup_id} not found",
            )

        # Delete the backup directory
        shutil.rmtree(backup_dir)

        return {
            "message": f"Backup {backup_id} deleted successfully",
            "backup_id": backup_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete backup: {str(e)}",
        )


@router.get("/status")
async def get_backup_status(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Get backup system status and statistics

    Requires admin privileges.
    """
    import os
    from pathlib import Path

    from app.core.config import settings

    try:
        backup_service = create_backup_service(db)
        backups = await backup_service.list_backups()

        # Calculate statistics
        total_backups = len(backups)
        full_backups = len([b for b in backups if b.get("type") == "full"])
        incremental_backups = len(
            [b for b in backups if b.get("type") == "incremental"]
        )
        successful_backups = len([b for b in backups if b.get("status") == "completed"])
        failed_backups = len([b for b in backups if b.get("status") == "failed"])

        # Calculate total backup size
        backup_base_dir = Path(settings.BACKUP_DIR)
        total_size_bytes = 0
        if backup_base_dir.exists():
            for backup_dir in backup_base_dir.iterdir():
                if backup_dir.is_dir():
                    total_size_bytes += sum(
                        f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
                    )

        # Get disk space information
        disk_stats = {}
        try:
            stat = os.statvfs(settings.BACKUP_DIR)
            disk_stats = {
                "total_space_gb": round((stat.f_blocks * stat.f_frsize) / (1024**3), 2),
                "available_space_gb": round(
                    (stat.f_available * stat.f_frsize) / (1024**3), 2
                ),
                "used_space_gb": round(
                    ((stat.f_blocks - stat.f_available) * stat.f_frsize) / (1024**3), 2
                ),
            }
        except Exception:
            disk_stats = {"error": "Unable to get disk statistics"}

        return {
            "backup_system_status": "operational",
            "statistics": {
                "total_backups": total_backups,
                "full_backups": full_backups,
                "incremental_backups": incremental_backups,
                "successful_backups": successful_backups,
                "failed_backups": failed_backups,
                "success_rate_percent": round(
                    (
                        (successful_backups / total_backups * 100)
                        if total_backups > 0
                        else 0
                    ),
                    1,
                ),
            },
            "storage": {
                "backup_directory": settings.BACKUP_DIR,
                "total_backup_size_gb": round(total_size_bytes / (1024**3), 2),
                "retention_days": settings.BACKUP_RETENTION_DAYS,
                "max_backup_count": settings.MAX_BACKUP_COUNT,
                "disk_space": disk_stats,
            },
            "recent_backups": backups[:5],  # Last 5 backups
        }

    except Exception as e:
        return {
            "backup_system_status": "error",
            "error": str(e),
        }
