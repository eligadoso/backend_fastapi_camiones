import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from google.cloud.firestore_v1.base_query import FieldFilter
from starlette.middleware.sessions import SessionMiddleware
from uuid import uuid4

from app.controllers import webhook_controller
from app.firebase_client import get_firestore_client
from app.security import hash_password
from app.api import router as api_router
from app.settings import settings

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret, same_site="lax")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


def ensure_admin_user() -> None:
    try:
        db = get_firestore_client()
        users = db.collection("usuario")
        exists = list(users.where(filter=FieldFilter("username", "==", "admin")).limit(1).stream())
        if exists:
            return
        doc_id = uuid4().hex
        users.document(doc_id).set(
            {
                "id_usuario": doc_id,
                "nombre": "Administrador",
                "apellido": "SyncTruck",
                "correo": "admin@synctruck.local",
                "username": "admin",
                "password_hash": hash_password("admin123"),
                "estado": "activo",
            }
        )
    except Exception:
        return


ensure_admin_user()


async def thingspeak_poll_loop() -> None:
    while True:
        try:
            result = await webhook_controller.pull_latest_from_settings()
            if result.get("data") is not None:
                print("[ThingSpeak] Sincronización OK")
        except Exception as exc:
            print(f"[ThingSpeak] Error de sincronización: {exc}")
        await asyncio.sleep(max(3, settings.thingspeak_poll_seconds))


@app.on_event("startup")
async def startup_event() -> None:
    ensure_admin_user()
    if settings.thingspeak_poll_enabled:
        asyncio.create_task(thingspeak_poll_loop())
