import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.core.logging import logger
from app.db.models.audit import AuditEvent
from app.services.base_service import BaseService


class AuditService(BaseService):
    """Append-only audit service ensuring all sensitive actions are traceable."""

    def record_event(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        request_id: str,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: str = "system",
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and persist an append-only audit event record."""
        # Sanitize payload: never persist passwords or raw secret tokens
        sanitized_payload = {}
        if payload:
            for k, v in payload.items():
                if any(secret_term in k.lower() for secret_term in ("password", "token", "secret", "auth")):
                    sanitized_payload[k] = "[REDACTED]"
                else:
                    sanitized_payload[k] = v

        event = AuditEvent(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            request_id=request_id,
            payload_json=sanitized_payload,
        )
        self.db.add(event)
        self.db.flush()

        logger.info(
            f"Audit event recorded: {action} on {entity_type}:{entity_id}",
            extra={
                "request_id": request_id,
                "actor_id": str(actor_id) if actor_id else None,
                "actor_role": actor_role,
                "entity_type": entity_type,
                "entity_id": str(entity_id),
            },
        )
        return event
