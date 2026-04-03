from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from app.settings import settings


def _init_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass
    if not settings.firebase_credentials_path:
        raise RuntimeError("FIREBASE_CREDENTIALS_PATH no configurado.")
    creds_path = Path(settings.firebase_credentials_path)
    if not creds_path.exists():
        raise RuntimeError(f"No existe archivo de credenciales Firebase: {creds_path}")
    options = {}
    if settings.firebase_realtime_db_url:
        options["databaseURL"] = settings.firebase_realtime_db_url
    return firebase_admin.initialize_app(credentials.Certificate(str(creds_path)), options=options)


def get_firestore_client():
    _init_firebase_app()
    return firestore.client()
