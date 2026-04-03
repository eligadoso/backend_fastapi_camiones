from fastapi import HTTPException, Request, status

from app.firebase_client import get_firestore_client


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    db = get_firestore_client()
    snap = db.collection("usuario").document(user_id).get()
    if not snap.exists:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión inválida")
    return snap.to_dict()
