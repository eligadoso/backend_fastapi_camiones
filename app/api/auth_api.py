from fastapi import APIRouter, Depends, HTTPException, Request, status
from google.cloud.firestore_v1.base_query import FieldFilter

from app.api.dependencies import get_current_user
from app.firebase_client import get_firestore_client
from app.models.api_model import LoginRequest
from app.security import verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginRequest, request: Request) -> dict:
    db = get_firestore_client()
    users = list(
        db.collection("usuario")
        .where(filter=FieldFilter("username", "==", payload.username))
        .limit(1)
        .stream()
    )
    if not users:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    user = users[0].to_dict()
    if not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    request.session["user_id"] = user["id_usuario"]
    return {
        "status": "ok",
        "user": {
            "id_usuario": user["id_usuario"],
            "username": user["username"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
        },
    }


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"status": "ok"}


@router.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return {
        "status": "ok",
        "user": {
            "id_usuario": user["id_usuario"],
            "username": user["username"],
            "nombre": user["nombre"],
            "apellido": user["apellido"],
        },
    }
