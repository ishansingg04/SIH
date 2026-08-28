import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_role: str
    action: str
    entity_type: str
    entity_id: str
    request_id: str
    payload_json: Dict[str, Any]
    created_at: datetime
