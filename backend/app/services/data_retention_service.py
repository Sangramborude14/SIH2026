"""
Data Retention Policy and Maintenance Service.

RETENTION POLICY SPECIFICATION:
1. RAW TELEMETRY & ML DATA:
   - `weather_observations`: Indefinite retention. Essential ground truth for retraining ML and climate baselines.
   - `weather_forecast_snapshots`: Indefinite retention.
   - `landslide_forecast_records`: Indefinite retention.
   - `landslide_events`: Indefinite retention (GSI / NASA National Ground Truth).

2. OPERATIONAL AUDIT & SESSION LOGS:
   - `refresh_tokens`: Prune revoked or expired tokens older than 7 days.
   - `ai_audit_logs`: Retain for 90 days.
   - `notification_dispatch_logs`: Retain for 180 days.
   - `public_alert_acknowledgments`: Retain for 90 days.

3. CACHE TIERS:
   - Redis / Memory: TTL-based automatic expiration (30s to 24h).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from sqlalchemy import delete, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import RefreshToken
from backend.app.models.audit import AIAuditLog
from backend.app.models.alerting import NotificationDispatchLog
from backend.app.models.public import PublicAlertAcknowledgment
from backend.app.core.logging import logger


class DataRetentionService:
    """Automated and on-demand maintenance service executing policy retention pruning."""

    @staticmethod
    async def prune_expired_refresh_tokens(session: AsyncSession, days_threshold: int = 7) -> int:
        """Prunes revoked or expired refresh tokens older than the grace period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        stmt = delete(RefreshToken).where(
            and_(
                RefreshToken.expires_at < cutoff,
                RefreshToken.revoked_at.is_not(None)
            )
        )
        res = await session.execute(stmt)
        count = res.rowcount or 0
        if count > 0:
            logger.info(f"DataRetentionService: Pruned {count} expired/revoked refresh tokens.")
        return count

    @staticmethod
    async def prune_stale_audit_logs(session: AsyncSession, days_threshold: int = 90) -> int:
        """Prunes historical AI audit logs older than retention threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        stmt = delete(AIAuditLog).where(AIAuditLog.timestamp < cutoff)
        res = await session.execute(stmt)
        count = res.rowcount or 0
        if count > 0:
            logger.info(f"DataRetentionService: Pruned {count} stale AI audit logs.")
        return count

    @staticmethod
    async def prune_stale_dispatch_logs(session: AsyncSession, days_threshold: int = 180) -> int:
        """Prunes notification dispatch logs older than retention threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        stmt = delete(NotificationDispatchLog).where(NotificationDispatchLog.created_at < cutoff)
        res = await session.execute(stmt)
        count = res.rowcount or 0
        if count > 0:
            logger.info(f"DataRetentionService: Pruned {count} old notification dispatch logs.")
        return count

    @staticmethod
    async def prune_stale_acknowledgments(session: AsyncSession, days_threshold: int = 90) -> int:
        """Prunes public alert acknowledgments older than retention threshold."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
        stmt = delete(PublicAlertAcknowledgment).where(PublicAlertAcknowledgment.timestamp < cutoff)
        res = await session.execute(stmt)
        count = res.rowcount or 0
        if count > 0:
            logger.info(f"DataRetentionService: Pruned {count} old alert acknowledgments.")
        return count

    @classmethod
    async def execute_retention_policy(cls, session: AsyncSession) -> Dict[str, int]:
        """Executes all automated retention policy maintenance cleanups."""
        pruned_tokens = await cls.prune_expired_refresh_tokens(session)
        pruned_logs = await cls.prune_stale_audit_logs(session)
        pruned_dispatches = await cls.prune_stale_dispatch_logs(session)
        pruned_acks = await cls.prune_stale_acknowledgments(session)
        await session.commit()
        return {
            "pruned_refresh_tokens": pruned_tokens,
            "pruned_ai_audit_logs": pruned_logs,
            "pruned_dispatch_logs": pruned_dispatches,
            "pruned_acknowledgments": pruned_acks,
        }


data_retention_service = DataRetentionService()
