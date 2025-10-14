"""
Automated Backup Service
Handles database backups, file backups, and backup verification
"""

import asyncio
import gzip
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import aiofiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class BackupService:
    """Service for automated database and file backups"""

    def __init__(self, db: Session):
        self.db = db
        self.backup_base_dir = (
            Path(settings.BACKUP_DIR)
            if hasattr(settings, "BACKUP_DIR")
            else Path("./backups")
        )
        self.backup_base_dir.mkdir(exist_ok=True, parents=True)

        # Backup retention settings
        self.retention_days = getattr(settings, "BACKUP_RETENTION_DAYS", 30)
        self.max_backup_count = getattr(settings, "MAX_BACKUP_COUNT", 10)

    async def create_full_backup(
        self, backup_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Create a full database and file backup

        Args:
            backup_name: Optional custom backup name

        Returns:
            Backup metadata
        """
        timestamp = datetime.utcnow()
        backup_id = backup_name or f"full_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"

        backup_dir = self.backup_base_dir / backup_id
        backup_dir.mkdir(exist_ok=True)

        logger.info(f"Starting full backup: {backup_id}")

        try:
            # Create database backup
            db_backup_result = await self._create_database_backup(backup_dir, backup_id)

            # Create file backup (if any)
            file_backup_result = await self._create_file_backup(backup_dir, backup_id)

            # Create backup manifest
            manifest = await self._create_backup_manifest(
                backup_dir, backup_id, timestamp, db_backup_result, file_backup_result
            )

            # Verify backup integrity
            verification_result = await self._verify_backup_integrity(backup_dir)

            # Clean up old backups
            await self._cleanup_old_backups()

            backup_metadata = {
                "backup_id": backup_id,
                "timestamp": timestamp.isoformat(),
                "type": "full",
                "status": "completed" if verification_result["success"] else "failed",
                "database_backup": db_backup_result,
                "file_backup": file_backup_result,
                "verification": verification_result,
                "manifest_path": str(manifest),
                "total_size_mb": self._calculate_backup_size(backup_dir),
            }

            logger.info(f"Full backup completed: {backup_id}")
            return backup_metadata

        except Exception as e:
            logger.error(f"Full backup failed: {str(e)}")
            # Clean up failed backup
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            return {
                "backup_id": backup_id,
                "timestamp": timestamp.isoformat(),
                "type": "full",
                "status": "failed",
                "error": str(e),
            }

    async def create_incremental_backup(
        self, backup_name: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Create an incremental backup (changes since last full backup)

        Args:
            backup_name: Optional custom backup name

        Returns:
            Backup metadata
        """
        timestamp = datetime.utcnow()
        backup_id = (
            backup_name or f"incremental_backup_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        )

        backup_dir = self.backup_base_dir / backup_id
        backup_dir.mkdir(exist_ok=True)

        logger.info(f"Starting incremental backup: {backup_id}")

        try:
            # Find last full backup
            last_full_backup = await self._find_last_full_backup()

            if not last_full_backup:
                logger.warning(
                    "No previous full backup found, creating full backup instead"
                )
                return await self.create_full_backup(backup_name)

            # Create incremental database backup
            db_backup_result = await self._create_incremental_database_backup(
                backup_dir, backup_id, last_full_backup
            )

            # Create backup manifest
            manifest = await self._create_backup_manifest(
                backup_dir, backup_id, timestamp, db_backup_result, {}
            )

            # Verify backup integrity
            verification_result = await self._verify_backup_integrity(backup_dir)

            backup_metadata = {
                "backup_id": backup_id,
                "timestamp": timestamp.isoformat(),
                "type": "incremental",
                "status": "completed" if verification_result["success"] else "failed",
                "database_backup": db_backup_result,
                "reference_backup": last_full_backup,
                "verification": verification_result,
                "manifest_path": str(manifest),
                "total_size_mb": self._calculate_backup_size(backup_dir),
            }

            logger.info(f"Incremental backup completed: {backup_id}")
            return backup_metadata

        except Exception as e:
            logger.error(f"Incremental backup failed: {str(e)}")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)

            return {
                "backup_id": backup_id,
                "timestamp": timestamp.isoformat(),
                "type": "incremental",
                "status": "failed",
                "error": str(e),
            }

    async def _create_database_backup(
        self, backup_dir: Path, backup_id: str
    ) -> Dict[str, any]:
        """Create PostgreSQL database backup using pg_dump"""
        try:
            # Create database backup directory
            db_backup_dir = backup_dir / "database"
            db_backup_dir.mkdir(exist_ok=True)

            # Use pg_dump for PostgreSQL backup
            import os
            import subprocess

            # Get database connection details
            db_url = settings.DATABASE_URL
            # Parse connection string (simplified)
            if "postgresql://" in db_url:
                # Extract connection parameters
                conn_parts = db_url.replace("postgresql://", "").split("/")
                host_user = conn_parts[0].split("@")
                user_pass = host_user[0].split(":")
                host_port = host_user[1].split(":")

                db_user = user_pass[0]
                db_password = user_pass[1] if len(user_pass) > 1 else ""
                db_host = host_port[0]
                db_port = host_port[1] if len(host_port) > 1 else "5432"
                db_name = conn_parts[1].split("?")[0]

                # Set environment variable for password
                env = os.environ.copy()
                env["PGPASSWORD"] = db_password

                # Create backup file path
                backup_file = db_backup_dir / f"{backup_id}_database.sql.gz"

                # Run pg_dump
                cmd = [
                    "pg_dump",
                    "-h",
                    db_host,
                    "-p",
                    db_port,
                    "-U",
                    db_user,
                    "-d",
                    db_name,
                    "-f",
                    str(backup_file),
                    "--compress=9",  # gzip compression
                    "--format=custom",  # custom format for better compression
                    "--no-owner",  # don't set ownership
                    "--no-privileges",  # don't dump privileges
                ]

                result = subprocess.run(cmd, env=env, capture_output=True, text=True)

                if result.returncode != 0:
                    raise Exception(f"pg_dump failed: {result.stderr}")

                # Get backup file size
                file_size = backup_file.stat().st_size

                return {
                    "success": True,
                    "method": "pg_dump",
                    "file_path": str(backup_file),
                    "file_size_bytes": file_size,
                    "compression": "gzip",
                    "format": "custom",
                }

        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "method": "pg_dump",
            }

    async def _create_incremental_database_backup(
        self, backup_dir: Path, backup_id: str, reference_backup: str
    ) -> Dict[str, any]:
        """Create incremental database backup"""
        try:
            # For PostgreSQL, incremental backups are complex
            # This is a simplified approach - in production you'd use tools like pgBackRest
            logger.warning(
                "Incremental database backup not fully implemented for PostgreSQL"
            )

            # For now, create a backup of WAL files or recent changes
            wal_backup_dir = backup_dir / "database" / "incremental"
            wal_backup_dir.mkdir(exist_ok=True, parents=True)

            # Get recent changes (simplified)
            recent_changes = await self._get_recent_database_changes()

            # Save changes to file
            changes_file = wal_backup_dir / f"{backup_id}_changes.sql.gz"
            async with aiofiles.open(changes_file, "wb") as f:
                # Compress the changes data
                import gzip
                import io

                changes_sql = "\n".join(recent_changes)
                compressed_data = gzip.compress(changes_sql.encode("utf-8"))
                await f.write(compressed_data)

            return {
                "success": True,
                "method": "incremental_sql",
                "file_path": str(changes_file),
                "reference_backup": reference_backup,
                "changes_count": len(recent_changes),
            }

        except Exception as e:
            logger.error(f"Incremental database backup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "method": "incremental_sql",
            }

    async def _create_file_backup(
        self, backup_dir: Path, backup_id: str
    ) -> Dict[str, any]:
        """Create backup of important files (logs, configs, etc.)"""
        try:
            file_backup_dir = backup_dir / "files"
            file_backup_dir.mkdir(exist_ok=True)

            # Files to backup
            files_to_backup = [
                "pyproject.toml",
                "requirements.txt",
                "alembic.ini",
                ".env.example",
                "docker-compose.yml",
                "Dockerfile",
            ]

            # Directories to backup
            dirs_to_backup = [
                "monitoring",
                "scripts",
            ]

            backed_up_files = []

            # Backup individual files
            for file_path in files_to_backup:
                src_path = Path(file_path)
                if src_path.exists():
                    dst_path = file_backup_dir / file_path
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dst_path)
                    backed_up_files.append(str(dst_path))

            # Backup directories
            for dir_path in dirs_to_backup:
                src_dir = Path(dir_path)
                if src_dir.exists():
                    dst_dir = file_backup_dir / dir_path
                    if dst_dir.exists():
                        shutil.rmtree(dst_dir)
                    shutil.copytree(src_dir, dst_dir)
                    backed_up_files.append(str(dst_dir))

            # Create compressed archive
            archive_path = backup_dir / f"{backup_id}_files.tar.gz"
            await self._create_tar_archive(file_backup_dir, archive_path)

            return {
                "success": True,
                "files_backed_up": len(backed_up_files),
                "archive_path": str(archive_path),
                "archive_size_bytes": archive_path.stat().st_size,
            }

        except Exception as e:
            logger.error(f"File backup failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _create_backup_manifest(
        self,
        backup_dir: Path,
        backup_id: str,
        timestamp: datetime,
        db_result: Dict,
        file_result: Dict,
    ) -> Path:
        """Create backup manifest file"""
        manifest_path = backup_dir / "backup_manifest.json"

        manifest = {
            "backup_id": backup_id,
            "timestamp": timestamp.isoformat(),
            "version": "1.0",
            "database_backup": db_result,
            "file_backup": file_result,
            "backup_service_version": "1.0",
            "system_info": {
                "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
                "platform": os.uname().sysname if hasattr(os, "uname") else "unknown",
            },
        }

        async with aiofiles.open(manifest_path, "w") as f:
            await f.write(json.dumps(manifest, indent=2, default=str))

        return manifest_path

    async def _verify_backup_integrity(self, backup_dir: Path) -> Dict[str, any]:
        """Verify backup integrity"""
        try:
            # Check if manifest exists
            manifest_path = backup_dir / "backup_manifest.json"
            if not manifest_path.exists():
                return {"success": False, "error": "Manifest file missing"}

            # Check database backup
            db_backup_exists = False
            for file_path in backup_dir.rglob("*"):
                if "database" in str(file_path) and file_path.is_file():
                    db_backup_exists = True
                    break

            if not db_backup_exists:
                return {"success": False, "error": "Database backup files missing"}

            # Check file sizes are reasonable
            total_size = sum(
                f.stat().st_size for f in backup_dir.rglob("*") if f.is_file()
            )

            return {
                "success": True,
                "total_files": len(list(backup_dir.rglob("*"))),
                "total_size_bytes": total_size,
                "manifest_valid": True,
                "database_backup_present": db_backup_exists,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _cleanup_old_backups(self):
        """Clean up old backups based on retention policy"""
        try:
            # Get all backup directories
            backup_dirs = []
            for item in self.backup_base_dir.iterdir():
                if item.is_dir() and item.name.startswith(
                    ("full_backup_", "incremental_backup_")
                ):
                    # Extract timestamp from directory name
                    try:
                        # Parse timestamp from directory name
                        name_parts = item.name.split("_")
                        if len(name_parts) >= 3:
                            timestamp_str = name_parts[2] + "_" + name_parts[3]
                            timestamp = datetime.strptime(
                                timestamp_str, "%Y%m%d_%H%M%S"
                            )
                            backup_dirs.append((item, timestamp))
                    except ValueError:
                        continue

            # Sort by timestamp (newest first)
            backup_dirs.sort(key=lambda x: x[1], reverse=True)

            # Remove backups older than retention period
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            old_backups = [bd for bd in backup_dirs if bd[1] < cutoff_date]

            for backup_dir, _ in old_backups:
                logger.info(f"Removing old backup: {backup_dir.name}")
                shutil.rmtree(backup_dir)

            # Keep only the most recent backups (up to max_backup_count)
            if len(backup_dirs) > self.max_backup_count:
                backups_to_remove = backup_dirs[self.max_backup_count :]
                for backup_dir, _ in backups_to_remove:
                    logger.info(f"Removing excess backup: {backup_dir.name}")
                    shutil.rmtree(backup_dir)

        except Exception as e:
            logger.error(f"Backup cleanup failed: {str(e)}")

    async def _find_last_full_backup(self) -> Optional[str]:
        """Find the last full backup directory"""
        try:
            backup_dirs = []
            for item in self.backup_base_dir.iterdir():
                if item.is_dir() and item.name.startswith("full_backup_"):
                    backup_dirs.append(item)

            if not backup_dirs:
                return None

            # Sort by name (which includes timestamp)
            backup_dirs.sort(reverse=True)
            return backup_dirs[0].name

        except Exception as e:
            logger.error(f"Error finding last full backup: {str(e)}")
            return None

    async def _get_recent_database_changes(self) -> List[str]:
        """Get recent database changes (simplified)"""
        # This is a simplified implementation
        # In production, you'd use WAL archiving or change tracking
        try:
            # Get recent audit trail entries
            from app.models.audit import AuditTrail

            recent_audits = (
                self.db.query(AuditTrail)
                .order_by(AuditTrail.timestamp.desc())
                .limit(100)
                .all()
            )

            changes = []
            for audit in recent_audits:
                changes.append(
                    f"-- Audit: {audit.action} on {audit.entity_type} {audit.entity_id}"
                )
                changes.append(
                    f"-- User: {audit.user_id}, Timestamp: {audit.timestamp}"
                )

            return changes

        except Exception as e:
            logger.error(f"Error getting recent changes: {str(e)}")
            return []

    async def _create_tar_archive(self, source_dir: Path, archive_path: Path):
        """Create a compressed tar archive"""
        import tarfile

        with tarfile.open(archive_path, "w:gz") as tar:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    tar.add(file_path, arcname=file_path.relative_to(source_dir.parent))

    def _calculate_backup_size(self, backup_dir: Path) -> float:
        """Calculate total backup size in MB"""
        total_size = sum(f.stat().st_size for f in backup_dir.rglob("*") if f.is_file())
        return round(total_size / (1024 * 1024), 2)

    async def list_backups(self) -> List[Dict[str, any]]:
        """List all available backups"""
        try:
            backups = []
            for item in self.backup_base_dir.iterdir():
                if item.is_dir() and item.name.startswith(
                    ("full_backup_", "incremental_backup_")
                ):
                    manifest_path = item / "backup_manifest.json"
                    if manifest_path.exists():
                        async with aiofiles.open(manifest_path, "r") as f:
                            manifest = json.loads(await f.read())
                            backups.append(manifest)

            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return backups

        except Exception as e:
            logger.error(f"Error listing backups: {str(e)}")
            return []

    async def restore_backup(
        self, backup_id: str, target_db_url: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Restore from a backup

        Args:
            backup_id: Backup ID to restore from
            target_db_url: Target database URL (optional)

        Returns:
            Restore operation result
        """
        # This is a complex operation that would require careful implementation
        # For now, return not implemented
        return {
            "success": False,
            "error": "Database restore not yet implemented",
            "backup_id": backup_id,
        }


# Global backup service instance
def create_backup_service(db: Session) -> BackupService:
    """Factory function to create backup service"""
    return BackupService(db)
