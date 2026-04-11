import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica conexión a Firebase Firestore.")
    parser.add_argument(
        "--credentials-path",
        default=os.getenv("FIREBASE_CREDENTIALS_PATH", "caminesproyecto.json"),
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("FIREBASE_COLLECTION", "sensor_readings"),
    )
    parser.add_argument("--keep-document", action="store_true", default=False)
    return parser.parse_args()


def build_firestore_client(credentials_path: str):
    path = Path(credentials_path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de credenciales: {credentials_path}")
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(path)))
    return firestore.client()


def ensure_admin_user(db) -> tuple[bool, str]:
    users = db.collection("usuario")
    exists = list(users.where(filter=FieldFilter("username", "==", "admin")).limit(1).stream())
    if exists:
        current = exists[0].to_dict() or {}
        return False, current.get("id_usuario", exists[0].id)

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
    return True, doc_id


def main() -> int:
    args = parse_args()
    try:
        db = build_firestore_client(args.credentials_path)
        doc_id = f"firebase-probe-{uuid4().hex[:8]}"
        doc_ref = db.collection(args.collection).document(doc_id)
        payload = {
            "probe": True,
            "source": "firebase_connection_test",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        doc_ref.set(payload)
        saved_data = doc_ref.get().to_dict()
        if not saved_data or not saved_data.get("probe"):
            print("Conectó a Firebase, pero no se pudo validar lectura/escritura.")
            return 1
        created_admin, admin_id = ensure_admin_user(db)
        if not args.keep_document:
            doc_ref.delete()
        print("Conexión a Firebase exitosa y lectura/escritura validada.")
        if created_admin:
            print(f'Usuario admin creado correctamente (id={admin_id}, username="admin").')
        else:
            print(f'Usuario admin ya existía (id={admin_id}, username="admin").')
        return 0
    except Exception as exc:
        print(f"Falló la conexión a Firebase: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
