from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.controllers import webhook_controller

router = APIRouter(prefix="/api", tags=["webhooks"])


@router.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/webhooks/thingspeak")
def receive_thingspeak_webhook(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return webhook_controller.process_webhook(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhooks/thingspeak/pull/{channel_id}")
async def pull_from_thingspeak(channel_id: str) -> dict[str, Any]:
    try:
        return await webhook_controller.pull_latest_from_thingspeak(channel_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
