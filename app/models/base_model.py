from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ThingSpeakWebhookPayload(BaseModel):
    channel_id: str | int | None = None
    field1: str | float | int | None = None
    field2: str | float | int | None = None
    field3: str | float | int | None = None
    field4: str | float | int | None = None
    field5: str | float | int | None = None
    field6: str | float | int | None = None
    field7: str | float | int | None = None
    field8: str | float | int | None = None
    created_at: datetime | None = None


class SensorReading(BaseModel):
    source: str = Field(default="thingspeak")
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channel_id: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)
    raw_payload: dict[str, Any] = Field(default_factory=dict)
