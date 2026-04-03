import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, firestore


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
        if not args.keep_document:
            doc_ref.delete()
        print("Conexión a Firebase exitosa y lectura/escritura validada.")
        return 0
    except Exception as exc:
        print(f"Falló la conexión a Firebase: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
