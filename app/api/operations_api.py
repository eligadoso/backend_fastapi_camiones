from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore_v1.base_query import FieldFilter

from app.api.dependencies import get_current_user
from app.firebase_client import get_firestore_client
from app.models.api_model import (
    AgregarPuntoRecorridoPayload,
    AsignacionTagCreate,
    CamionConductorAsignacion,
    CamionCreate,
    CamionUpdate,
    ConductorCreate,
    ConductorCamionAsignacion,
    ConductorUpdate,
    DashboardMovimiento,
    DashboardSummary,
    PuntoControlCreate,
    PuntoControlUpdate,
    RutaCamionAsignacionCreate,
    RutaCreate,
    RutaUpdate,
    TagConductorAsignacion,
    TagCreate,
    TagUpdate,
    TipoPuntoCreate,
    TipoPuntoUpdate,
    VinculacionCreate,
)

router = APIRouter(prefix="/api", tags=["operaciones"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _where_eq(query, field: str, value):
    return query.where(filter=FieldFilter(field, "==", value))


def _parse_coords(value) -> dict[str, float] | None:
    if not value:
        return None
    if isinstance(value, dict):
        lat = value.get("lat", value.get("latitude"))
        lng = value.get("lng", value.get("longitude"))
        if lat is not None and lng is not None:
            try:
                return {"lat": float(lat), "lng": float(lng)}
            except (TypeError, ValueError):
                return None
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return {"lat": float(value[0]), "lng": float(value[1])}
        except (TypeError, ValueError):
            return None
    parts = [part.strip() for part in str(value).split(",")]
    if len(parts) != 2:
        return None
    try:
        return {"lat": float(parts[0]), "lng": float(parts[1])}
    except ValueError:
        return None


def _load_camiones(db) -> dict[str, dict]:
    return {
        doc.to_dict().get("id_camion"): doc.to_dict()
        for doc in db.collection("camion").stream()
        if doc.to_dict().get("id_camion")
    }


def _load_conductores(db) -> dict[str, dict]:
    return {
        doc.to_dict().get("id_conductor"): doc.to_dict()
        for doc in db.collection("conductor").stream()
        if doc.to_dict().get("id_conductor")
    }


def _camion_summary(camion: dict | None) -> dict | None:
    if not camion:
        return None
    return {
        "id_camion": camion.get("id_camion"),
        "patente": camion.get("patente"),
        "marca": camion.get("marca"),
        "modelo": camion.get("modelo"),
        "color": camion.get("color"),
        "estado": camion.get("estado"),
    }


def _conductor_summary(conductor: dict | None) -> dict | None:
    if not conductor:
        return None
    return {
        "id_conductor": conductor.get("id_conductor"),
        "rut": conductor.get("rut"),
        "nombre": conductor.get("nombre"),
        "apellido": conductor.get("apellido"),
        "telefono": conductor.get("telefono"),
        "licencia": conductor.get("licencia"),
        "estado": conductor.get("estado"),
    }


def _enrich_camion_conductor_relationships(db, camiones: list[dict], conductores: list[dict]) -> None:
    conductores_by_id = {item.get("id_conductor"): item for item in conductores if item.get("id_conductor")}
    camiones_by_id = {item.get("id_camion"): item for item in camiones if item.get("id_camion")}

    camion_to_conductor: dict[str, str] = {}
    conductor_to_camion: dict[str, str] = {}

    for camion in camiones:
        id_camion = camion.get("id_camion")
        id_conductor = camion.get("id_conductor")
        if id_camion and id_conductor:
            camion_to_conductor[id_camion] = id_conductor
            conductor_to_camion.setdefault(id_conductor, id_camion)

    for conductor in conductores:
        id_conductor = conductor.get("id_conductor")
        id_camion = conductor.get("id_camion")
        if id_conductor and id_camion:
            conductor_to_camion[id_conductor] = id_camion
            camion_to_conductor.setdefault(id_camion, id_conductor)

    for camion in camiones:
        id_camion = camion.get("id_camion")
        id_conductor = camion_to_conductor.get(id_camion)
        camion["id_conductor"] = id_conductor
        camion["conductor"] = _conductor_summary(conductores_by_id.get(id_conductor)) if id_conductor else None

    for conductor in conductores:
        id_conductor = conductor.get("id_conductor")
        id_camion = conductor_to_camion.get(id_conductor)
        conductor["id_camion"] = id_camion
        conductor["camion"] = _camion_summary(camiones_by_id.get(id_camion)) if id_camion else None


def _set_camion_conductor_assignment(db, id_camion: str, id_conductor: str) -> None:
    camion_ref = db.collection("camion").document(id_camion)
    conductor_ref = db.collection("conductor").document(id_conductor)
    camion_snap = camion_ref.get()
    conductor_snap = conductor_ref.get()
    if not camion_snap.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    if not conductor_snap.exists:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")

    camion_data = camion_snap.to_dict()
    conductor_data = conductor_snap.to_dict()
    camion_actual = camion_data.get("id_conductor")
    conductor_actual = conductor_data.get("id_camion")

    if camion_actual and camion_actual != id_conductor:
        raise HTTPException(status_code=409, detail="El camión ya tiene un conductor asignado")
    if conductor_actual and conductor_actual != id_camion:
        raise HTTPException(status_code=409, detail="El conductor ya tiene un camión asignado")

    otros_camiones = list(_where_eq(db.collection("camion"), "id_conductor", id_conductor).limit(2).stream())
    if any(doc.id != id_camion for doc in otros_camiones):
        raise HTTPException(status_code=409, detail="El conductor ya tiene un camión asignado")

    otros_conductores = list(
        _where_eq(db.collection("conductor"), "id_camion", id_camion).limit(2).stream()
    )
    if any(doc.id != id_conductor for doc in otros_conductores):
        raise HTTPException(status_code=409, detail="El camión ya tiene un conductor asignado")

    now = datetime.now(timezone.utc).isoformat()
    camion_ref.update({"id_conductor": id_conductor, "updated_at": now})
    conductor_ref.update({"id_camion": id_camion, "updated_at": now})


def _clear_camion_conductor_assignment(db, id_camion: str | None = None, id_conductor: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    camion_ref = db.collection("camion").document(id_camion) if id_camion else None
    conductor_ref = db.collection("conductor").document(id_conductor) if id_conductor else None

    camion_snap = camion_ref.get() if camion_ref else None
    conductor_snap = conductor_ref.get() if conductor_ref else None
    camion_data = camion_snap.to_dict() if camion_snap and camion_snap.exists else None
    conductor_data = conductor_snap.to_dict() if conductor_snap and conductor_snap.exists else None

    if camion_data is None and conductor_data is None:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")

    resolved_camion_id = id_camion or conductor_data.get("id_camion")
    resolved_conductor_id = id_conductor or camion_data.get("id_conductor")
    if resolved_conductor_id is None and resolved_camion_id:
        conductor_docs = list(
            _where_eq(db.collection("conductor"), "id_camion", resolved_camion_id).limit(1).stream()
        )
        if conductor_docs:
            resolved_conductor_id = conductor_docs[0].to_dict().get("id_conductor")
    if resolved_camion_id is None and resolved_conductor_id:
        camion_docs = list(
            _where_eq(db.collection("camion"), "id_conductor", resolved_conductor_id).limit(1).stream()
        )
        if camion_docs:
            resolved_camion_id = camion_docs[0].to_dict().get("id_camion")

    if resolved_camion_id:
        db.collection("camion").document(resolved_camion_id).update(
            {"id_conductor": None, "updated_at": now}
        )
    if resolved_conductor_id:
        db.collection("conductor").document(resolved_conductor_id).update(
            {"id_camion": None, "updated_at": now}
        )


def _load_tag_a_camion(db) -> dict[str, str]:
    """Devuelve un mapa {id_tag -> id_camion} desde todas las fuentes de asignación.

    Prioridad:
    1. vinculacion_activa (vínculo operacional explícito)
    2. asignacion_tag    (asignación estática alternativa)
    3. tag_rfid.id_conductor → conductor.id_camion  (cadena principal de la UI)
    """
    result: dict[str, str] = {}

    # 1) vinculacion_activa
    for doc in db.collection("vinculacion_activa").stream():
        data = doc.to_dict()
        if data.get("activa") and data.get("id_tag") and data.get("id_camion"):
            result[data["id_tag"]] = data["id_camion"]

    # 2) asignacion_tag
    for doc in db.collection("asignacion_tag").stream():
        data = doc.to_dict()
        if data.get("activa") and data.get("id_tag") and data.get("id_camion"):
            result.setdefault(data["id_tag"], data["id_camion"])

    # 3) Cadena principal de la UI: tag_rfid.id_conductor → conductor.id_camion
    conductores_by_id = {
        doc.to_dict().get("id_conductor"): doc.to_dict()
        for doc in db.collection("conductor").stream()
        if doc.to_dict().get("id_conductor")
    }
    for doc in db.collection("tag_rfid").stream():
        data = doc.to_dict()
        id_tag = data.get("id_tag")
        id_conductor = data.get("id_conductor")
        if not id_tag or not id_conductor or id_tag in result:
            continue
        conductor = conductores_by_id.get(id_conductor, {})
        id_camion = conductor.get("id_camion")
        if id_camion:
            result[id_tag] = id_camion

    return result


def _load_movimientos_por_camion(db) -> dict[str, list[dict]]:
    visitas_by_id = {
        doc.to_dict().get("id_visita"): doc.to_dict()
        for doc in db.collection("visita").stream()
        if doc.to_dict().get("id_visita")
    }
    movimientos_por_camion: dict[str, list[dict]] = {}

    # Fuente primaria: movimiento_acceso (datos normales / futuros)
    for doc in db.collection("movimiento_acceso").stream():
        mov = doc.to_dict()
        visita = visitas_by_id.get(mov.get("id_visita"))
        if not visita:
            continue
        id_camion = visita.get("id_camion")
        timestamp = _parse_iso_datetime(mov.get("fecha_hora_movimiento"))
        if not id_camion or timestamp is None:
            continue
        movimientos_por_camion.setdefault(id_camion, []).append({**mov, "_dt": timestamp})

    # Fuente de respaldo: lectura_rfid (cubre lecturas históricas sin movimiento_acceso)
    # Solo se usa cuando no hay ya un movimiento_acceso para esa lectura.
    lecturas_ya_en_movimiento = {
        mov.get("id_lectura")
        for movs in movimientos_por_camion.values()
        for mov in movs
        if mov.get("id_lectura")
    }
    tag_a_camion = _load_tag_a_camion(db)
    for doc in db.collection("lectura_rfid").stream():
        lectura = doc.to_dict()
        id_lectura = lectura.get("id_lectura")
        if id_lectura in lecturas_ya_en_movimiento:
            continue
        id_tag = lectura.get("id_tag")
        id_camion = tag_a_camion.get(id_tag)
        if not id_camion:
            continue
        timestamp = _parse_iso_datetime(lectura.get("fecha_hora_lectura"))
        if timestamp is None:
            continue
        mov_sintetico = {
            "id_movimiento": None,
            "id_visita": None,
            "id_lectura": id_lectura,
            "id_punto_control": lectura.get("id_punto_control"),
            "tipo_movimiento": "paso_punto",
            "fecha_hora_movimiento": lectura.get("fecha_hora_lectura"),
            "_dt": timestamp,
            "_sintetico": True,
        }
        movimientos_por_camion.setdefault(id_camion, []).append(mov_sintetico)

    for id_camion in movimientos_por_camion:
        movimientos_por_camion[id_camion].sort(key=lambda item: item["_dt"])
    return movimientos_por_camion


def _filter_movimientos_en_ventana(
    movimientos: list[dict],
    inicio: datetime | None,
    fin: datetime | None = None,
) -> list[dict]:
    if inicio is None:
        return []
    salida = []
    for mov in movimientos:
        timestamp = mov.get("_dt")
        if timestamp is None or timestamp < inicio:
            continue
        if fin is not None and timestamp > fin:
            continue
        salida.append(mov)
    return salida


@router.post("/camiones")
def create_camion(payload: CamionCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    camion_ref = db.collection("camion")
    exists = list(_where_eq(camion_ref, "patente", payload.patente).limit(1).stream())
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patente ya registrada")
    id_camion = uuid4().hex
    camion_ref.document(id_camion).set(
        {
            "id_camion": id_camion,
            "patente": payload.patente,
            "id_empresa": payload.id_empresa,
            "marca": payload.marca,
            "modelo": payload.modelo,
            "color": payload.color,
            "estado": "activo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"status": "ok", "data": {"id_camion": id_camion, "patente": payload.patente}}


@router.get("/camiones")
def list_camiones(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("camion").stream()]
    data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    conductores = [doc.to_dict() for doc in db.collection("conductor").stream()]
    _enrich_camion_conductor_relationships(db, data, conductores)
    return {"status": "ok", "data": data}


@router.get("/camiones/{id_camion}")
def get_camion(id_camion: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    snap = db.collection("camion").document(id_camion).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    camiones = [snap.to_dict()]
    conductores = [doc.to_dict() for doc in db.collection("conductor").stream()]
    _enrich_camion_conductor_relationships(db, camiones, conductores)
    return {"status": "ok", "data": camiones[0]}


@router.put("/camiones/{id_camion}")
def update_camion(id_camion: str, payload: CamionUpdate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("camion").document(id_camion)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    current = snap.to_dict()
    update_data: dict = {}
    for field in ("patente", "marca", "modelo", "color", "estado"):
        val = getattr(payload, field)
        if val is not None:
            update_data[field] = val
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    return {"status": "ok", "data": {**current, **update_data}}


@router.delete("/camiones/{id_camion}")
def delete_camion(id_camion: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("camion").document(id_camion)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    conductor_id = snap.to_dict().get("id_conductor")
    if conductor_id:
        conductor_ref = db.collection("conductor").document(conductor_id)
        conductor_snap = conductor_ref.get()
        if conductor_snap.exists and conductor_snap.to_dict().get("id_camion") == id_camion:
            conductor_ref.update({"id_camion": None, "updated_at": datetime.now(timezone.utc).isoformat()})
    ref.delete()
    return {"status": "ok"}


@router.post("/conductores")
def create_conductor(payload: ConductorCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("conductor")
    exists = list(_where_eq(ref, "rut", payload.rut).limit(1).stream())
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RUT ya registrado")
    id_conductor = uuid4().hex
    ref.document(id_conductor).set(
        {
            "id_conductor": id_conductor,
            "rut": payload.rut,
            "nombre": payload.nombre,
            "apellido": payload.apellido,
            "telefono": payload.telefono,
            "licencia": payload.licencia,
            "estado": "activo",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"status": "ok", "data": {"id_conductor": id_conductor, "rut": payload.rut}}


@router.get("/conductores")
def list_conductores(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("conductor").stream()]
    data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    # Enrich with tag info (find tag where id_conductor == this conductor)
    tags_by_conductor: dict[str, dict] = {}
    for tag_doc in db.collection("tag_rfid").stream():
        tag = tag_doc.to_dict()
        id_c = tag.get("id_conductor")
        if id_c:
            tags_by_conductor[id_c] = tag
    for conductor in data:
        conductor["tag"] = tags_by_conductor.get(conductor["id_conductor"])
    camiones = [doc.to_dict() for doc in db.collection("camion").stream()]
    _enrich_camion_conductor_relationships(db, camiones, data)
    return {"status": "ok", "data": data}


@router.put("/conductores/{id_conductor}")
def update_conductor(id_conductor: str, payload: ConductorUpdate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("conductor").document(id_conductor)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    current = snap.to_dict()
    update_data: dict = {}
    for field in ("nombre", "apellido", "telefono", "licencia", "estado"):
        val = getattr(payload, field)
        if val is not None:
            update_data[field] = val
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    return {"status": "ok", "data": {**current, **update_data}}


@router.get("/conductores/{id_conductor}")
def get_conductor(id_conductor: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    snap = db.collection("conductor").document(id_conductor).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    conductor = snap.to_dict()
    tags_by_conductor: dict[str, dict] = {}
    for tag_doc in db.collection("tag_rfid").stream():
        tag = tag_doc.to_dict()
        linked_id = tag.get("id_conductor")
        if linked_id:
            tags_by_conductor[linked_id] = tag
    conductor["tag"] = tags_by_conductor.get(id_conductor)
    conductores = [conductor]
    camiones = [doc.to_dict() for doc in db.collection("camion").stream()]
    _enrich_camion_conductor_relationships(db, camiones, conductores)
    return {"status": "ok", "data": conductores[0]}


@router.delete("/conductores/{id_conductor}")
def delete_conductor(id_conductor: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("conductor").document(id_conductor)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
    camion_id = snap.to_dict().get("id_camion")
    if camion_id:
        camion_ref = db.collection("camion").document(camion_id)
        camion_snap = camion_ref.get()
        if camion_snap.exists and camion_snap.to_dict().get("id_conductor") == id_conductor:
            camion_ref.update({"id_conductor": None, "updated_at": datetime.now(timezone.utc).isoformat()})
    ref.delete()
    return {"status": "ok"}


@router.put("/camiones/{id_camion}/asignar-conductor")
def asignar_conductor_a_camion(
    id_camion: str,
    payload: CamionConductorAsignacion,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    _set_camion_conductor_assignment(db, id_camion, payload.id_conductor)
    return {"status": "ok"}


@router.delete("/camiones/{id_camion}/asignar-conductor")
def desasignar_conductor_de_camion(id_camion: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    _clear_camion_conductor_assignment(db, id_camion=id_camion)
    return {"status": "ok"}


@router.put("/conductores/{id_conductor}/asignar-camion")
def asignar_camion_a_conductor(
    id_conductor: str,
    payload: ConductorCamionAsignacion,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    _set_camion_conductor_assignment(db, payload.id_camion, id_conductor)
    return {"status": "ok"}


@router.delete("/conductores/{id_conductor}/asignar-camion")
def desasignar_camion_de_conductor(
    id_conductor: str,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    _clear_camion_conductor_assignment(db, id_conductor=id_conductor)
    return {"status": "ok"}


@router.post("/rfid/tags")
def create_tag(payload: TagCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tag_rfid")
    exists = list(_where_eq(ref, "uid_tag", payload.uid_tag).limit(1).stream())
    if exists:
        return {"status": "ok", "data": exists[0].to_dict()}
    id_tag = uuid4().hex
    record = {
        "id_tag": id_tag,
        "uid_tag": payload.uid_tag,
        "codigo_interno": payload.codigo_interno,
        "estado": "activo",
        "fecha_alta": datetime.now(timezone.utc).isoformat(),
        "fecha_baja": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ref.document(id_tag).set(record)
    return {"status": "ok", "data": record}


@router.get("/rfid/tags")
def list_tags(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("tag_rfid").stream()]
    data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    # Enrich with conductor info
    conductores = {doc.id: doc.to_dict() for doc in db.collection("conductor").stream()}
    for tag in data:
        id_c = tag.get("id_conductor")
        tag["conductor"] = conductores.get(id_c) if id_c else None
    return {"status": "ok", "data": data}


@router.put("/rfid/tags/{id_tag}")
def update_tag(id_tag: str, payload: TagUpdate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tag_rfid").document(id_tag)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    current = snap.to_dict()
    update_data: dict = {}
    if payload.codigo_interno is not None:
        update_data["codigo_interno"] = payload.codigo_interno
    if payload.estado is not None:
        update_data["estado"] = payload.estado
    if payload.fecha_baja is not None:
        update_data["fecha_baja"] = payload.fecha_baja.isoformat()
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    merged = {**current, **update_data}
    return {"status": "ok", "data": merged}


@router.delete("/rfid/tags/{id_tag}")
def delete_tag(id_tag: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tag_rfid").document(id_tag)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    ref.delete()
    return {"status": "ok"}


@router.put("/rfid/tags/{id_tag}/asignar-conductor")
def asignar_conductor_a_tag(
    id_tag: str, payload: TagConductorAsignacion, user: dict = Depends(get_current_user)
) -> dict:
    """Assigns a conductor to a tag (one-to-one). Raises 409 if either already has an assignment."""
    db = get_firestore_client()
    tag_ref = db.collection("tag_rfid").document(id_tag)
    tag_snap = tag_ref.get()
    if not tag_snap.exists:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    tag_data = tag_snap.to_dict()

    if tag_data.get("id_conductor") and tag_data["id_conductor"] != payload.id_conductor:
        raise HTTPException(status_code=409, detail="El tag ya tiene un conductor asignado")

    # Check no other tag already has this conductor
    existing = list(
        _where_eq(db.collection("tag_rfid"), "id_conductor", payload.id_conductor).limit(1).stream()
    )
    if existing and existing[0].id != id_tag:
        raise HTTPException(status_code=409, detail="El conductor ya tiene un tag asignado")

    tag_ref.update({"id_conductor": payload.id_conductor, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"status": "ok"}


@router.delete("/rfid/tags/{id_tag}/asignar-conductor")
def desasignar_conductor_de_tag(id_tag: str, user: dict = Depends(get_current_user)) -> dict:
    """Removes the conductor assignment from a tag."""
    db = get_firestore_client()
    ref = db.collection("tag_rfid").document(id_tag)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Tag no encontrado")
    ref.update({"id_conductor": None, "updated_at": datetime.now(timezone.utc).isoformat()})
    return {"status": "ok"}


@router.post("/puntos-control")
def create_punto_control(payload: PuntoControlCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("punto_control")
    exists = list(_where_eq(ref, "id_esp32", payload.id_esp32).limit(1).stream())
    if exists:
        return {"status": "ok", "data": exists[0].to_dict()}
    id_punto_control = uuid4().hex
    record = {
        "id_punto_control": id_punto_control,
        "id_zona": payload.id_zona,
        "nombre": payload.nombre,
        "tipo_punto": payload.tipo_punto,
        "id_esp32": payload.id_esp32,
        "ubicacion": payload.ubicacion,
        "cordenadas": payload.cordenadas,
        "activo": payload.activo,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ref.document(id_punto_control).set(record)
    return {"status": "ok", "data": record}


@router.get("/puntos-control")
def list_puntos_control(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("punto_control").stream()]
    data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"status": "ok", "data": data}


@router.put("/puntos-control/{id_punto_control}")
def update_punto_control(
    id_punto_control: str,
    payload: PuntoControlUpdate,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    ref = db.collection("punto_control").document(id_punto_control)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Punto de control no encontrado")
    current = snap.to_dict()
    update_data: dict = {}
    if payload.nombre is not None:
        update_data["nombre"] = payload.nombre
    if payload.tipo_punto is not None:
        update_data["tipo_punto"] = payload.tipo_punto
    if payload.id_zona is not None:
        update_data["id_zona"] = payload.id_zona
    if payload.ubicacion is not None:
        update_data["ubicacion"] = payload.ubicacion
    if payload.cordenadas is not None:
        update_data["cordenadas"] = payload.cordenadas
    if payload.activo is not None:
        update_data["activo"] = payload.activo
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    merged = {**current, **update_data}
    return {"status": "ok", "data": merged}


@router.delete("/puntos-control/{id_punto_control}")
def delete_punto_control(id_punto_control: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("punto_control").document(id_punto_control)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Punto de control no encontrado")

    rutas_en_uso = []
    for ruta_doc in db.collection("ruta").stream():
        ruta = ruta_doc.to_dict()
        if any(item.get("id_punto_control") == id_punto_control for item in ruta.get("puntos", [])):
            rutas_en_uso.append(ruta.get("nombre") or ruta.get("id_ruta"))
    if rutas_en_uso:
        raise HTTPException(
            status_code=409,
            detail="No se puede eliminar el punto porque está asignado a una ruta",
        )

    ref.delete()
    return {"status": "ok"}


@router.post("/rutas")
def create_ruta(payload: RutaCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    id_ruta = uuid4().hex
    puntos = sorted(
        [{"id_punto_control": p.id_punto_control, "orden": p.orden} for p in payload.puntos],
        key=lambda x: x["orden"],
    )
    record = {
        "id_ruta": id_ruta,
        "nombre": payload.nombre,
        "descripcion": payload.descripcion,
        "activa": payload.activa,
        "puntos": puntos,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db.collection("ruta").document(id_ruta).set(record)
    return {"status": "ok", "data": record}


@router.get("/rutas")
def list_rutas(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    rutas = [doc.to_dict() for doc in db.collection("ruta").stream()]
    rutas.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    puntos = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    for ruta in rutas:
        enriched = []
        for p in ruta.get("puntos", []):
            punto = puntos.get(p.get("id_punto_control"), {})
            enriched.append(
                {
                    "id_punto_control": p.get("id_punto_control"),
                    "orden": p.get("orden"),
                    "nombre_punto": punto.get("nombre"),
                    "tipo_punto": punto.get("tipo_punto"),
                    "ubicacion": punto.get("ubicacion"),
                    "cordenadas": punto.get("cordenadas"),
                    "activo": punto.get("activo", True),
                }
            )
        ruta["puntos"] = sorted(enriched, key=lambda x: x.get("orden", 0))
    return {"status": "ok", "data": rutas}


@router.get("/rutas/{id_ruta}")
def get_ruta(id_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    snap = db.collection("ruta").document(id_ruta).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return {"status": "ok", "data": snap.to_dict()}


@router.put("/rutas/{id_ruta}")
def update_ruta(id_ruta: str, payload: RutaUpdate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("ruta").document(id_ruta)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    current = snap.to_dict()
    update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if payload.nombre is not None:
        update_data["nombre"] = payload.nombre
    if payload.descripcion is not None:
        update_data["descripcion"] = payload.descripcion
    if payload.activa is not None:
        update_data["activa"] = payload.activa
    if payload.puntos is not None:
        update_data["puntos"] = sorted(
            [{"id_punto_control": p.id_punto_control, "orden": p.orden} for p in payload.puntos],
            key=lambda x: x["orden"],
        )
    ref.update(update_data)
    return {"status": "ok", "data": {**current, **update_data}}


@router.delete("/rutas/{id_ruta}")
def delete_ruta(id_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("ruta").document(id_ruta)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    ref.delete()
    return {"status": "ok", "message": "Ruta eliminada"}


def _hay_recorrido_en_proceso(db, id_camion: str) -> bool:
    """Devuelve True si el camión ya tiene un recorrido en estado 'en_proceso'."""
    # Campo nuevo con estado explícito
    docs = list(
        _where_eq(
            _where_eq(db.collection("ruta_camion_asignacion"), "id_camion", id_camion),
            "estado_recorrido",
            "en_proceso",
        )
        .limit(1)
        .stream()
    )
    if docs:
        return True
    # Fallback: activa=True sin estado_recorrido (registros legacy)
    docs_legacy = list(
        _where_eq(
            _where_eq(db.collection("ruta_camion_asignacion"), "id_camion", id_camion),
            "activa",
            True,
        )
        .limit(1)
        .stream()
    )
    return any(
        not d.to_dict().get("estado_recorrido")  # sin campo → legacy activo
        for d in docs_legacy
    )


@router.post("/seguimiento-rutas/asignaciones")
def create_ruta_asignacion(payload: RutaCamionAsignacionCreate, user: dict = Depends(get_current_user)) -> dict:
    """Crea un nuevo recorrido para un camión en una ruta.

    Reglas de estado inicial:
    - Si el camión ya tiene un recorrido "en_proceso" → nuevo recorrido = "agendado"
    - Si no hay recorrido "en_proceso":
        - hora_inicio <= ahora + 5min → "en_proceso"
        - hora_inicio > ahora + 5min  → "agendado"
    - Un recorrido nuevo NUNCA se crea como "finalizado".

    La ruta se aísla mediante snapshot: editar la ruta maestra no altera este recorrido.
    """
    from datetime import timedelta

    db = get_firestore_client()
    ruta_snap = db.collection("ruta").document(payload.id_ruta).get()
    if not ruta_snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    camion = db.collection("camion").document(payload.id_camion).get()
    if not camion.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    hora_inicio_utc = payload.hora_inicio.astimezone(timezone.utc)

    # Determinar estado inicial sin tocar recorridos existentes
    ya_en_proceso = _hay_recorrido_en_proceso(db, payload.id_camion)
    if ya_en_proceso:
        # El camión ya está ejecutando un recorrido → el nuevo queda en espera
        estado_recorrido = "agendado"
    else:
        margen = timedelta(minutes=5)
        estado_recorrido = (
            "en_proceso"
            if hora_inicio_utc <= now_dt + margen
            else "agendado"
        )

    # Snapshot inmutable de los puntos de la ruta maestra en este instante.
    # Garantiza que editar la ruta maestra después NO altera este recorrido.
    puntos_snapshot = sorted(
        ruta_snap.to_dict().get("puntos", []),
        key=lambda x: int(x.get("orden", 0)),
    )

    id_asignacion_ruta = uuid4().hex
    record = {
        "id_asignacion_ruta": id_asignacion_ruta,
        "id_ruta": payload.id_ruta,
        "id_camion": payload.id_camion,
        "hora_inicio": hora_inicio_utc.isoformat(),
        "activa": estado_recorrido == "en_proceso",
        "estado_recorrido": estado_recorrido,
        "fecha_fin": None,
        "puntos_snapshot": puntos_snapshot,
        "puntos_estado": [],  # se construye al llegar la primera lectura RFID
        "created_at": now,
    }
    db.collection("ruta_camion_asignacion").document(id_asignacion_ruta).set(record)
    return {"status": "ok", "data": record}


@router.post("/seguimiento-rutas/asignaciones/{id_asignacion_ruta}/iniciar")
def iniciar_recorrido(id_asignacion_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    """Transiciona un recorrido de 'agendado' a 'en_proceso'.

    Guarda de unicidad: si el camión ya tiene otro recorrido 'en_proceso', rechaza la operación.
    """
    db = get_firestore_client()
    doc_ref = db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    data = snap.to_dict()
    estado_actual = data.get("estado_recorrido")

    if estado_actual == "en_proceso":
        return {"status": "ok", "message": "El recorrido ya está en proceso", "data": data}
    if estado_actual in ("finalizado", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede iniciar un recorrido en estado '{estado_actual}'",
        )

    # Guarda de unicidad: no puede haber dos recorridos en_proceso para el mismo camión
    id_camion = data.get("id_camion")
    if id_camion and _hay_recorrido_en_proceso(db, id_camion):
        raise HTTPException(
            status_code=409,
            detail="El camión ya tiene un recorrido 'en_proceso'. Finalízalo antes de iniciar otro.",
        )

    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "estado_recorrido": "en_proceso",
        "activa": True,
        "updated_at": now,
    })
    return {"status": "ok", "message": "Recorrido iniciado", "data": {**data, "estado_recorrido": "en_proceso"}}


@router.post("/seguimiento-rutas/asignaciones/{id_asignacion_ruta}/finalizar")
def finalizar_recorrido(id_asignacion_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    """Finaliza manualmente un recorrido en_proceso.

    Tras finalizar, activa automáticamente el siguiente recorrido agendado del camión
    (ordenado por hora_inicio ascendente).
    """
    db = get_firestore_client()
    doc_ref = db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    data = snap.to_dict()
    estado_actual = data.get("estado_recorrido")

    if estado_actual == "finalizado":
        return {"status": "ok", "message": "El recorrido ya está finalizado", "data": data}
    if estado_actual in ("agendado", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se puede finalizar un recorrido 'en_proceso', no uno en estado '{estado_actual}'",
        )

    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "estado_recorrido": "finalizado",
        "activa": False,
        "fecha_fin": now,
        "updated_at": now,
    })

    # Activar el siguiente recorrido agendado del camión
    id_camion = data.get("id_camion")
    siguiente_activado = None
    if id_camion:
        agendados = list(
            _where_eq(
                _where_eq(db.collection("ruta_camion_asignacion"), "id_camion", id_camion),
                "estado_recorrido",
                "agendado",
            )
            .stream()
        )
        if agendados:
            agendados.sort(key=lambda d: d.to_dict().get("hora_inicio", ""))
            siguiente = agendados[0]
            siguiente_data = siguiente.to_dict()
            siguiente.reference.update({
                "estado_recorrido": "en_proceso",
                "activa": True,
                "updated_at": now,
            })
            siguiente_activado = siguiente_data.get("id_asignacion_ruta") or siguiente.id

    return {
        "status": "ok",
        "message": "Recorrido finalizado",
        "siguiente_activado": siguiente_activado,
    }


@router.post("/seguimiento-rutas/asignaciones/{id_asignacion_ruta}/cancelar")
def cancelar_recorrido(id_asignacion_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    """Cancela un recorrido agendado o en_proceso."""
    db = get_firestore_client()
    doc_ref = db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    data = snap.to_dict()
    estado_actual = data.get("estado_recorrido")
    if estado_actual in ("finalizado", "cancelado"):
        raise HTTPException(
            status_code=400,
            detail=f"El recorrido ya está en estado '{estado_actual}'",
        )
    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "estado_recorrido": "cancelado",
        "activa": False,
        "fecha_fin": now,
        "updated_at": now,
    })
    return {"status": "ok", "message": "Recorrido cancelado"}


# ---------------------------------------------------------------------------
# Gestión de puntos dentro de un recorrido
# ---------------------------------------------------------------------------

def _estados_interactuados() -> frozenset[str]:
    """Estados de punto que se consideran inamovibles (ya ejecutados)."""
    return frozenset({"pasado", "omitido"})


@router.post("/seguimiento-rutas/asignaciones/{id_asignacion_ruta}/puntos")
def agregar_punto_recorrido(
    id_asignacion_ruta: str,
    payload: AgregarPuntoRecorridoPayload,
    user: dict = Depends(get_current_user),
) -> dict:
    """Añade un punto de control adicional al snapshot de un recorrido.

    Reglas:
    - Solo disponible para recorridos en estado 'en_proceso' o 'agendado'.
    - El punto no debe existir ya en el snapshot del recorrido.
    - Si se proporciona `orden`, debe ser posterior al último punto interactuado.
    - Sin `orden`: se asigna automáticamente al final del snapshot.
    """
    db = get_firestore_client()
    doc_ref = db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    recorrido = snap.to_dict()

    estado = recorrido.get("estado_recorrido")
    if estado not in ("en_proceso", "agendado"):
        raise HTTPException(
            status_code=400,
            detail=f"No se puede modificar un recorrido en estado '{estado}'. Solo 'en_proceso' o 'agendado'.",
        )

    # Verificar que el punto existe en la BD
    punto_snap = db.collection("punto_control").document(payload.id_punto_control).get()
    if not punto_snap.exists:
        raise HTTPException(status_code=404, detail="Punto de control no encontrado")

    puntos_snapshot: list[dict] = recorrido.get("puntos_snapshot") or []
    _pe_raw: list[dict] = recorrido.get("puntos_estado") or []
    if not _pe_raw and puntos_snapshot:
        # puntos_estado aún no fue inicializado (ninguna lectura RFID llegó todavía).
        # Si se agrega un punto directamente a la lista vacía, se perderían los puntos
        # originales del snapshot. Se inicializan todos como "pendiente" antes de añadir el nuevo.
        _pe_raw = [
            {
                "id_punto_control": p["id_punto_control"],
                "orden": int(p.get("orden", 0)),
                "estado": "pendiente",
                "fecha_hora_paso": None,
                "id_lectura": None,
                "id_movimiento": None,
            }
            for p in puntos_snapshot
        ]
    puntos_estado: list[dict] = _pe_raw

    # El punto no debe estar ya en el snapshot
    ids_en_snapshot = {p["id_punto_control"] for p in puntos_snapshot}
    if payload.id_punto_control in ids_en_snapshot:
        raise HTTPException(status_code=409, detail="El punto de control ya existe en este recorrido")

    # Calcular el máximo orden de puntos ya interactuados
    interacted_ordenes = [
        int(p.get("orden", 0))
        for p in puntos_estado
        if p.get("estado") in _estados_interactuados()
    ]
    max_interacted_orden = max(interacted_ordenes, default=0)
    max_snapshot_orden = max((int(p.get("orden", 0)) for p in puntos_snapshot), default=0)

    if payload.orden is not None:
        if payload.orden <= max_interacted_orden:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"El orden {payload.orden} es anterior o igual al último punto ejecutado "
                    f"(orden {max_interacted_orden}). Solo se pueden insertar puntos futuros."
                ),
            )
        orden = payload.orden
    else:
        orden = max_snapshot_orden + 1

    nuevo_snap = {"id_punto_control": payload.id_punto_control, "orden": orden}
    nuevo_estado_item = {
        "id_punto_control": payload.id_punto_control,
        "orden": orden,
        "estado": "pendiente",
        "fecha_hora_paso": None,
        "id_lectura": None,
        "id_movimiento": None,
    }

    nuevo_snapshot = sorted(puntos_snapshot + [nuevo_snap], key=lambda x: int(x.get("orden", 0)))
    nuevo_estado_lista = sorted(puntos_estado + [nuevo_estado_item], key=lambda x: int(x.get("orden", 0)))

    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "puntos_snapshot": nuevo_snapshot,
        "puntos_estado": nuevo_estado_lista,
        "updated_at": now,
    })

    nombre_punto = punto_snap.to_dict().get("nombre", payload.id_punto_control)
    return {
        "status": "ok",
        "punto_agregado": {**nuevo_snap, "nombre": nombre_punto},
        "total_puntos": len(nuevo_snapshot),
    }


@router.post("/seguimiento-rutas/asignaciones/{id_asignacion_ruta}/recargar-ruta")
def recargar_ruta_recorrido(
    id_asignacion_ruta: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Sincroniza los puntos futuros no interactuados del recorrido con la ruta maestra actual.

    Algoritmo de recarga segura:
    1. Puntos interactuados (pasado/omitido) → inmutables, nunca se tocan.
    2. Identificar puntos futuros en el snapshot actual y en la nueva ruta.
    3. Si hay puntos futuros que serían ELIMINADOS o que cambiarían de ORDEN RELATIVO → AMBIGUO.
    4. Si solo hay adiciones puras (nuevos puntos en ruta no presentes en snapshot) → SEGURO.
    5. En caso ambiguo: retornar descripción del conflicto sin modificar nada.
    """
    db = get_firestore_client()
    doc_ref = db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
    snap = doc_ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    recorrido = snap.to_dict()

    estado = recorrido.get("estado_recorrido")
    if estado not in ("en_proceso", "agendado"):
        raise HTTPException(
            status_code=400,
            detail=f"La recarga de ruta solo está disponible para recorridos 'en_proceso' o 'agendado'.",
        )

    id_ruta = recorrido.get("id_ruta")
    ruta_snap = db.collection("ruta").document(id_ruta).get()
    if not ruta_snap.exists:
        raise HTTPException(status_code=404, detail="Ruta maestra no encontrada")

    ruta_puntos_nuevos = sorted(ruta_snap.to_dict().get("puntos", []), key=lambda x: int(x.get("orden", 0)))

    puntos_snapshot: list[dict] = sorted(
        recorrido.get("puntos_snapshot") or [],
        key=lambda x: int(x.get("orden", 0)),
    )
    puntos_estado: list[dict] = recorrido.get("puntos_estado") or []

    # Conjuntos de IDs
    interacted_ids = {
        p["id_punto_control"]
        for p in puntos_estado
        if p.get("estado") in _estados_interactuados()
    }
    snapshot_ids = {p["id_punto_control"] for p in puntos_snapshot}

    # Puntos futuros del snapshot (pendientes)
    future_snapshot = [p for p in puntos_snapshot if p["id_punto_control"] not in interacted_ids]
    future_ids = {p["id_punto_control"] for p in future_snapshot}

    nueva_ruta_ids = {p["id_punto_control"] for p in ruta_puntos_nuevos}

    # Puntos completamente nuevos (en nueva ruta, NOT en snapshot completo)
    puntos_solo_nuevos = [p for p in ruta_puntos_nuevos if p["id_punto_control"] not in snapshot_ids]

    # Futuros que serían eliminados
    futuros_eliminados = [p for p in future_snapshot if p["id_punto_control"] not in nueva_ruta_ids]

    # Verificar si el orden relativo de los futuros comunes cambiaría
    common_order_snapshot = [p["id_punto_control"] for p in future_snapshot if p["id_punto_control"] in nueva_ruta_ids]
    common_order_nueva = [p["id_punto_control"] for p in ruta_puntos_nuevos if p["id_punto_control"] in future_ids]
    orden_relativo_cambio = common_order_snapshot != common_order_nueva

    # ── Detectar ambigüedad ──────────────────────────────────────────
    if futuros_eliminados or orden_relativo_cambio:
        motivos = []
        if futuros_eliminados:
            ids_elim = [p["id_punto_control"] for p in futuros_eliminados]
            motivos.append(
                f"{len(futuros_eliminados)} punto(s) futuro(s) serían eliminados del recorrido: {ids_elim}"
            )
        if orden_relativo_cambio:
            motivos.append(
                "El orden relativo de los puntos futuros existentes cambiaría, "
                "lo que no puede reinterpretarse de forma segura automáticamente."
            )
        return {
            "status": "ok",
            "resultado": "ambiguo",
            "mensaje": (
                "La recarga no es segura: los cambios en la ruta afectan puntos futuros "
                "ya registrados en el recorrido. Usa 'Añadir punto adicional' para incorporar "
                "nuevos puntos manualmente sin riesgo de alterar el historial."
            ),
            "motivos": motivos,
            "puntos_agregados": [],
        }

    # ── Sin cambios ──────────────────────────────────────────────────
    if not puntos_solo_nuevos:
        return {
            "status": "ok",
            "resultado": "sin_cambios",
            "mensaje": "La ruta maestra no tiene puntos nuevos respecto al recorrido actual. No hay nada que sincronizar.",
            "puntos_agregados": [],
        }

    # ── Adición pura — seguro ────────────────────────────────────────
    max_orden_actual = max((int(p.get("orden", 0)) for p in puntos_snapshot), default=0)
    nuevos_con_orden: list[dict] = []
    for i, p in enumerate(puntos_solo_nuevos):
        nuevos_con_orden.append({
            "id_punto_control": p["id_punto_control"],
            "orden": max_orden_actual + i + 1,
        })

    nuevo_snapshot = sorted(
        puntos_snapshot + nuevos_con_orden,
        key=lambda x: int(x.get("orden", 0)),
    )
    nuevos_estado_items = [
        {
            "id_punto_control": p["id_punto_control"],
            "orden": p["orden"],
            "estado": "pendiente",
            "fecha_hora_paso": None,
            "id_lectura": None,
            "id_movimiento": None,
        }
        for p in nuevos_con_orden
    ]
    nuevo_estado_completo = sorted(
        puntos_estado + nuevos_estado_items,
        key=lambda x: int(x.get("orden", 0)),
    )

    now = datetime.now(timezone.utc).isoformat()
    doc_ref.update({
        "puntos_snapshot": nuevo_snapshot,
        "puntos_estado": nuevo_estado_completo,
        "updated_at": now,
    })

    return {
        "status": "ok",
        "resultado": "ok",
        "mensaje": f"Se agregaron {len(nuevos_con_orden)} punto(s) nuevo(s) al recorrido.",
        "puntos_agregados": nuevos_con_orden,
    }


@router.get("/seguimiento-rutas/asignaciones")
def list_ruta_asignaciones(id_ruta: str | None = None, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    items = [doc.to_dict() for doc in db.collection("ruta_camion_asignacion").stream()]
    if id_ruta:
        items = [item for item in items if item.get("id_ruta") == id_ruta]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    camiones = {
        doc.to_dict().get("id_camion"): doc.to_dict()
        for doc in db.collection("camion").stream()
    }
    conductores = {
        doc.to_dict().get("id_conductor"): doc.to_dict()
        for doc in db.collection("conductor").stream()
    }
    for item in items:
        camion = camiones.get(item.get("id_camion"), {})
        item["patente"] = camion.get("patente")
        id_conductor = camion.get("id_conductor")
        conductor = conductores.get(id_conductor, {}) if id_conductor else {}
        item["conductor_nombre"] = (
            f"{conductor.get('nombre', '')} {conductor.get('apellido', '')}".strip()
            if conductor else None
        )
        item["id_conductor"] = id_conductor
        # Normalizar estado_recorrido para registros legacy sin campo explícito.
        # Garantiza que el frontend siempre recibe un valor canónico.
        if not item.get("estado_recorrido"):
            item["estado_recorrido"] = (
                "finalizado" if not item.get("activa") else "en_proceso"
            )
    return {"status": "ok", "data": items}


@router.get("/seguimiento-rutas")
def get_seguimiento_ruta(
    id_ruta: str,
    id_camion: str,
    id_asignacion_ruta: str | None = None,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    ruta_snap = db.collection("ruta").document(id_ruta).get()
    if not ruta_snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    puntos_lookup = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    asignaciones = [
        doc.to_dict()
        for doc in _where_eq(
            _where_eq(db.collection("ruta_camion_asignacion"), "id_ruta", id_ruta),
            "id_camion",
            id_camion,
        ).stream()
    ]
    if not asignaciones:
        return {"status": "ok", "data": {"id_ruta": id_ruta, "id_camion": id_camion, "puntos": []}}
    asignaciones.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    if id_asignacion_ruta:
        asignacion = next(
            (item for item in asignaciones if item.get("id_asignacion_ruta") == id_asignacion_ruta),
            None,
        )
        if asignacion is None:
            raise HTTPException(status_code=404, detail="Recorrido no encontrado")
    else:
        # Prioridad: en_proceso > agendado > más reciente (para lectura histórica)
        asignacion = (
            next((a for a in asignaciones if a.get("estado_recorrido") == "en_proceso"), None)
            or next((a for a in asignaciones if a.get("estado_recorrido") == "agendado"), None)
            or next((a for a in asignaciones if a.get("activa")), None)  # legacy
            or asignaciones[0]
        )

    # Usar el snapshot de puntos guardado al crear el recorrido.
    # Garantiza que editar la ruta maestra no altera recorridos ya registrados.
    puntos_ruta = sorted(
        asignacion.get("puntos_snapshot") or ruta_snap.to_dict().get("puntos", []),
        key=lambda x: int(x.get("orden", 0)),
    )

    hora_inicio = _parse_iso_datetime(asignacion.get("hora_inicio"))
    if hora_inicio is None:
        return {"status": "ok", "data": {"id_ruta": id_ruta, "id_camion": id_camion, "puntos": []}}
    hora_fin = _parse_iso_datetime(asignacion.get("fecha_fin"))
    now = datetime.now(timezone.utc)

    # ----------------------------------------------------------------
    # Fuente de estados: puntos_estado persistido (write-time)
    # Fallback: movimientos filtrados por ventana (legacy / compatibilidad)
    # ----------------------------------------------------------------
    puntos_estado_persistido: list[dict] = asignacion.get("puntos_estado") or []

    if puntos_estado_persistido:
        # Ruta nueva: leer del estado persistido en escritura
        estado_por_punto = {
            p["id_punto_control"]: p for p in puntos_estado_persistido
        }
        salida = []
        for p in puntos_ruta:
            pid = p.get("id_punto_control")
            orden = int(p.get("orden", 0))
            punto = puntos_lookup.get(pid, {})
            ep = estado_por_punto.get(pid, {})
            estado = ep.get("estado", "pendiente")
            fecha_hora = ep.get("fecha_hora_paso")
            salida.append(
                {
                    "id_punto_control": pid,
                    "nombre_punto": punto.get("nombre"),
                    "orden": orden,
                    "estado": estado,
                    "fecha_hora_paso": fecha_hora,
                    "tiempo_en_punto": None,
                    "referencia_tiempo_en_punto": None,
                    "id_movimiento": ep.get("id_movimiento"),
                }
            )
    else:
        # Fallback legacy: calcular desde movimientos por ventana de tiempo
        movimientos_por_camion = _load_movimientos_por_camion(db)
        movs_camion = _filter_movimientos_en_ventana(
            movimientos_por_camion.get(id_camion, []),
            hora_inicio,
            hora_fin,
        )
        pass_map: dict[str, datetime] = {}
        for mov in movs_camion:
            pid = mov.get("id_punto_control")
            if pid and pid not in pass_map:
                pass_map[pid] = mov["_dt"]
        ordenes_pasadas = [
            int(p.get("orden", 0))
            for p in puntos_ruta
            if p.get("id_punto_control") in pass_map
        ]
        started = len(ordenes_pasadas) > 0
        max_orden_pasada = max(ordenes_pasadas) if ordenes_pasadas else 0
        salida = []
        for p in puntos_ruta:
            pid = p.get("id_punto_control")
            orden = int(p.get("orden", 0))
            punto = puntos_lookup.get(pid, {})
            marca = pass_map.get(pid)
            if marca:
                estado = "pasado"
                fecha_hora = marca.isoformat()
            else:
                estado = "omitido" if (started and orden < max_orden_pasada) else "pendiente"
                fecha_hora = None
            salida.append(
                {
                    "id_punto_control": pid,
                    "nombre_punto": punto.get("nombre"),
                    "orden": orden,
                    "estado": estado,
                    "fecha_hora_paso": fecha_hora,
                    "tiempo_en_punto": None,
                    "referencia_tiempo_en_punto": None,
                    "id_movimiento": None,
                }
            )

    salida.sort(key=lambda x: x["orden"])

    # Lógica de "en_punto": el primer pendiente después de un punto pasado
    if salida:
        pendientes = [item for item in salida if item["estado"] == "pendiente"]
        if pendientes:
            actual = pendientes[0]
            indice_actual = salida.index(actual)
            if indice_actual > 0:
                previo = salida[indice_actual - 1]
                previo_dt = _parse_iso_datetime(previo.get("fecha_hora_paso"))
                if previo_dt:
                    actual["estado"] = "en_punto"
                    elapsed = now - previo_dt
                    minutes = int(elapsed.total_seconds() // 60)
                    actual["tiempo_en_punto"] = f"{minutes // 60:02d}:{minutes % 60:02d}"
                    actual["referencia_tiempo_en_punto"] = previo_dt.isoformat()

    # Auto-completar solo para rutas legacy (sin puntos_estado): las nuevas
    # se completan en escritura dentro de _register_movimiento_desde_lectura.
    auto_completado = False
    if not puntos_estado_persistido:
        todos_pasados = salida and all(p["estado"] in ("pasado", "omitido") for p in salida)
        if todos_pasados and asignacion.get("activa"):
            ultimo_paso = max(
                (_parse_iso_datetime(p["fecha_hora_paso"]) for p in salida if p.get("fecha_hora_paso")),
                default=now,
            )
            db.collection("ruta_camion_asignacion").document(
                asignacion["id_asignacion_ruta"]
            ).update({
                "estado_recorrido": "finalizado",
                "activa": False,
                "fecha_fin": ultimo_paso.isoformat(),
                "updated_at": now.isoformat(),
            })
            hora_fin = ultimo_paso
            auto_completado = True

    # Inferir estado_recorrido para registros legacy sin campo explícito
    estado_recorrido = asignacion.get("estado_recorrido") or (
        "finalizado" if not asignacion.get("activa") else "en_proceso"
    )
    if auto_completado:
        estado_recorrido = "finalizado"

    return {
        "status": "ok",
        "data": {
            "id_ruta": id_ruta,
            "id_camion": id_camion,
            "id_asignacion_ruta": asignacion.get("id_asignacion_ruta"),
            "hora_inicio": hora_inicio.isoformat(),
            "fecha_fin": hora_fin.isoformat() if hora_fin else None,
            "estado_recorrido": estado_recorrido,
            "activa": asignacion.get("activa", False) and not auto_completado,
            "auto_completado": auto_completado,
            "puntos": salida,
        },
    }


@router.get("/metricas-rutas")
def get_metricas_rutas(id_ruta: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ruta_snap = db.collection("ruta").document(id_ruta).get()
    if not ruta_snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    ruta = ruta_snap.to_dict()
    puntos_ruta = sorted(ruta.get("puntos", []), key=lambda x: x.get("orden", 0))
    if len(puntos_ruta) < 2:
        return {"status": "ok", "data": {"id_ruta": id_ruta, "puntos": []}}
    puntos_lookup = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    camiones = _load_camiones(db)
    movimientos_por_camion = _load_movimientos_por_camion(db)
    asignaciones = [
        doc.to_dict()
        for doc in _where_eq(db.collection("ruta_camion_asignacion"), "id_ruta", id_ruta).stream()
    ]
    puntos_metricas = []
    for index in range(1, len(puntos_ruta)):
        punto_anterior = puntos_ruta[index - 1]
        punto_actual = puntos_ruta[index]
        prev_pid = punto_anterior.get("id_punto_control")
        curr_pid = punto_actual.get("id_punto_control")
        prev_nombre = puntos_lookup.get(prev_pid, {}).get("nombre") or prev_pid
        curr_nombre = puntos_lookup.get(curr_pid, {}).get("nombre") or curr_pid
        registros = []
        for asignacion in asignaciones:
            cid = asignacion.get("id_camion")
            if not cid:
                continue
            hora_inicio = _parse_iso_datetime(asignacion.get("hora_inicio"))
            if hora_inicio is None:
                continue
            hora_fin = _parse_iso_datetime(asignacion.get("fecha_fin"))
            movs = _filter_movimientos_en_ventana(
                movimientos_por_camion.get(cid, []),
                hora_inicio,
                hora_fin,
            )
            t_prev = None
            t_curr = None
            for mov in movs:
                pid = mov.get("id_punto_control")
                if pid == prev_pid and t_prev is None:
                    t_prev = mov["_dt"]
                    continue
                if pid == curr_pid and t_prev is not None and t_curr is None:
                    t_curr = mov["_dt"]
                if t_prev and t_curr:
                    break
            if t_prev and t_curr and t_curr >= t_prev:
                dur_min = (t_curr - t_prev).total_seconds() / 60
                cam = camiones.get(cid, {})
                registros.append(
                    {
                        "id_camion": cid,
                        "patente": cam.get("patente"),
                        "id_asignacion_ruta": asignacion.get("id_asignacion_ruta"),
                        "fecha_hora": t_curr.isoformat(),
                        "fecha_hora_desde": t_prev.isoformat(),
                        "fecha_hora_hasta": t_curr.isoformat(),
                        "duracion_min": round(dur_min, 2),
                    }
                )
        if registros:
            ordenados = sorted(registros, key=lambda x: x["duracion_min"])
            min_item = ordenados[0]
            max_item = ordenados[-1]
            avg = round(sum(x["duracion_min"] for x in registros) / len(registros), 2)
        else:
            min_item = None
            max_item = None
            avg = None
        puntos_metricas.append(
            {
                "id_segmento": f"{prev_pid}__{curr_pid}",
                "desde": {
                    "id_punto_control": prev_pid,
                    "nombre_punto": prev_nombre,
                    "orden": int(punto_anterior.get("orden", index)),
                },
                "hasta": {
                    "id_punto_control": curr_pid,
                    "nombre_punto": curr_nombre,
                    "orden": int(punto_actual.get("orden", index + 1)),
                },
                "id_punto_control": curr_pid,
                "nombre_punto": curr_nombre,
                "nombre_punto_anterior": prev_nombre,
                "orden": int(punto_actual.get("orden", index + 1)),
                "transicion_desde_orden": int(punto_anterior.get("orden", index)),
                "registros": registros,
                "resumen": {
                    "tiempo_mas_alto": max_item,
                    "tiempo_mas_bajo": min_item,
                    "tiempo_promedio_min": avg,
                    "tiempo_estimado_min": avg,
                },
            }
        )
    return {"status": "ok", "data": {"id_ruta": id_ruta, "puntos": puntos_metricas}}


@router.get("/lecturas-rfid")
def list_lecturas_rfid(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("lectura_rfid").stream()]
    data.sort(key=lambda x: x.get("fecha_hora_lectura", ""), reverse=True)
    return {"status": "ok", "data": data[:100]}


@router.post("/vinculaciones")
def create_vinculacion(payload: VinculacionCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    active_ref = db.collection("vinculacion_activa")
    active_docs = list(_where_eq(active_ref, "activa", True).stream())
    now = datetime.now(timezone.utc).isoformat()
    for doc in active_docs:
        item = doc.to_dict()
        if (
            item.get("id_tag") == payload.id_tag
            or item.get("id_camion") == payload.id_camion
            or item.get("id_conductor") == payload.id_conductor
        ):
            doc.reference.update({"activa": False, "fecha_fin": now})
    id_vinculacion = uuid4().hex
    record = {
        "id_vinculacion": id_vinculacion,
        "id_tag": payload.id_tag,
        "id_camion": payload.id_camion,
        "id_conductor": payload.id_conductor,
        "activa": True,
        "fecha_inicio": now,
        "fecha_fin": None,
        "created_at": now,
    }
    active_ref.document(id_vinculacion).set(record)
    return {"status": "ok", "data": record}


@router.get("/vinculaciones")
def list_vinculaciones(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("vinculacion_activa").stream()]
    data.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"status": "ok", "data": data}


@router.get("/movimientos-acceso")
def list_movimientos_acceso(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("movimiento_acceso").stream()]
    visitas = {
        doc.to_dict().get("id_visita"): doc.to_dict()
        for doc in db.collection("visita").stream()
    }
    camiones = {
        doc.to_dict().get("id_camion"): doc.to_dict()
        for doc in db.collection("camion").stream()
    }
    conductores = {
        doc.to_dict().get("id_conductor"): doc.to_dict()
        for doc in db.collection("conductor").stream()
    }
    puntos = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    data.sort(key=lambda x: x.get("fecha_hora_movimiento", ""), reverse=True)
    for item in data:
        punto = puntos.get(item.get("id_punto_control"), {})
        visita = visitas.get(item.get("id_visita"), {})
        camion = camiones.get(visita.get("id_camion"), {})
        conductor = conductores.get(visita.get("id_conductor"), {})
        item["evento"] = "pasó por punto de control"
        item["punto_control_nombre"] = punto.get("nombre")
        item["movil"] = camion.get("patente")
        item["chofer"] = (
            f"{conductor.get('nombre', '')} {conductor.get('apellido', '')}".strip()
            if conductor
            else None
        )
    return {"status": "ok", "data": data[:200]}


@router.post("/rfid/asignaciones")
def assign_tag(payload: AsignacionTagCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("asignacion_tag")
    active_assignment = list(
        _where_eq(_where_eq(ref, "id_tag", payload.id_tag), "activa", True).limit(1).stream()
    )
    if active_assignment:
        active_doc = active_assignment[0]
        active_doc.reference.update(
            {"activa": False, "fecha_fin": datetime.now(timezone.utc).isoformat()}
        )
    id_asignacion = uuid4().hex
    record = {
        "id_asignacion": id_asignacion,
        "id_tag": payload.id_tag,
        "id_camion": payload.id_camion,
        "fecha_inicio": datetime.now(timezone.utc).isoformat(),
        "fecha_fin": None,
        "activa": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    ref.document(id_asignacion).set(record)
    return {"status": "ok", "data": {"id_asignacion": id_asignacion}}


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(user: dict = Depends(get_current_user)) -> DashboardSummary:
    db = get_firestore_client()
    visitas = [doc.to_dict() for doc in db.collection("visita").stream()]
    movimientos = [doc.to_dict() for doc in db.collection("movimiento_acceso").stream()]
    camiones_en_planta = sum(
        1
        for item in visitas
        if item.get("estado_visita") == "en_planta" and item.get("fecha_hora_salida") in (None, "")
    )
    start_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    ingresos_hoy = 0
    for mov in movimientos:
        timestamp = mov.get("fecha_hora_movimiento")
        if not timestamp:
            continue
        mov_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if mov_dt >= start_day:
            ingresos_hoy += 1
    duraciones = []
    for visita in visitas:
        ingreso = visita.get("fecha_hora_ingreso")
        salida = visita.get("fecha_hora_salida")
        if not ingreso or not salida:
            continue
        ingreso_dt = datetime.fromisoformat(ingreso.replace("Z", "+00:00"))
        salida_dt = datetime.fromisoformat(salida.replace("Z", "+00:00"))
        duraciones.append((salida_dt - ingreso_dt).total_seconds() / 60)
    promedio = int(sum(duraciones) / len(duraciones)) if duraciones else 0
    return DashboardSummary(
        camiones_en_planta=camiones_en_planta,
        ingresos_hoy=ingresos_hoy,
        tiempo_promedio_estadia_min=promedio,
    )


@router.get("/dashboard/ubicacion-tiempo-real")
def dashboard_ubicacion_tiempo_real(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    visitas = [doc.to_dict() for doc in db.collection("visita").stream()]
    visitas_activas = [
        item
        for item in visitas
        if item.get("estado_visita") == "en_planta" and item.get("fecha_hora_salida") in (None, "")
    ]
    if not visitas_activas:
        return {"status": "ok", "data": []}

    visita_activa_por_camion: dict[str, dict] = {}
    for visita in visitas_activas:
        id_camion = visita.get("id_camion")
        if not id_camion:
            continue
        actual = visita_activa_por_camion.get(id_camion)
        ingreso_actual = _parse_iso_datetime(actual.get("fecha_hora_ingreso")) if actual else None
        ingreso_visita = _parse_iso_datetime(visita.get("fecha_hora_ingreso"))
        if actual is None or (
            ingreso_visita is not None and (ingreso_actual is None or ingreso_visita > ingreso_actual)
        ):
            visita_activa_por_camion[id_camion] = visita

    visitas_por_id = {
        visita.get("id_visita"): visita
        for visita in visita_activa_por_camion.values()
        if visita.get("id_visita")
    }

    puntos = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    camiones = _load_camiones(db)
    conductores = _load_conductores(db)

    # Recorre todos los movimientos y mantiene el más reciente por camión.
    # Acepta dos fuentes de identidad del camión:
    #   a) id_visita → visita activa → id_camion  (módulo de planta)
    #   b) id_camion directo en el movimiento      (módulo de rutas, id_visita=null)
    ultimos_movimientos: dict[str, dict] = {}
    for doc in db.collection("movimiento_acceso").stream():
        movimiento = doc.to_dict()
        timestamp = _parse_iso_datetime(movimiento.get("fecha_hora_movimiento"))
        if timestamp is None:
            continue

        # Fuente a: visita de planta activa
        id_camion = None
        id_conductor_mov = None
        visita = visitas_por_id.get(movimiento.get("id_visita"))
        if visita:
            id_camion = visita.get("id_camion")
            id_conductor_mov = visita.get("id_conductor")

        # Fuente b: campos directos en el movimiento (rutas sin visita de planta)
        if not id_camion:
            id_camion = movimiento.get("id_camion")
            id_conductor_mov = movimiento.get("id_conductor")

        if not id_camion:
            continue

        actual = ultimos_movimientos.get(id_camion)
        if actual is None or timestamp > actual["_dt"]:
            ultimos_movimientos[id_camion] = {
                **movimiento,
                "_dt": timestamp,
                "_id_conductor": id_conductor_mov,
            }

    markers = []
    for id_camion, movimiento in ultimos_movimientos.items():
        punto = puntos.get(movimiento.get("id_punto_control"), {})
        # Prioridad coordenadas: campo directo en movimiento → campo en punto_control
        coords = _parse_coords(movimiento.get("cordenadas")) or _parse_coords(punto.get("cordenadas"))
        if coords is None:
            continue
        camion = camiones.get(id_camion, {})
        id_conductor = movimiento.get("_id_conductor")
        conductor = conductores.get(id_conductor, {}) if id_conductor else {}
        nombre_conductor = f"{conductor.get('nombre', '')} {conductor.get('apellido', '')}".strip() or "-"
        markers.append(
            {
                "id_camion": id_camion,
                "patente": camion.get("patente") or id_camion,
                "id_conductor": id_conductor,
                "conductor": nombre_conductor,
                "id_punto_control": movimiento.get("id_punto_control"),
                "punto_control": punto.get("nombre") or movimiento.get("id_punto_control"),
                "cordenadas": coords,
                "fecha_hora_movimiento": movimiento["_dt"].isoformat(),
            }
        )

    markers.sort(key=lambda item: item.get("fecha_hora_movimiento", ""), reverse=True)
    return {"status": "ok", "data": markers}


@router.get("/tipos-punto-control")
def list_tipos_punto_control(user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    data = [doc.to_dict() for doc in db.collection("tipo_punto_control").stream()]
    if not data:
        # Seed defaults on first request
        defaults = [
            {"nombre": "checkpoint", "descripcion": "Punto de control genérico"},
            {"nombre": "porton_entrada", "descripcion": "Portón de entrada a la planta"},
            {"nombre": "porton_salida", "descripcion": "Portón de salida de la planta"},
        ]
        now = datetime.now(timezone.utc).isoformat()
        for t in defaults:
            id_tipo = uuid4().hex
            record = {"id_tipo": id_tipo, "nombre": t["nombre"], "descripcion": t["descripcion"], "created_at": now}
            db.collection("tipo_punto_control").document(id_tipo).set(record)
            data.append(record)
    data.sort(key=lambda x: x.get("created_at", ""))
    return {"status": "ok", "data": data}


@router.post("/tipos-punto-control")
def create_tipo_punto_control(payload: TipoPuntoCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    existing = list(_where_eq(db.collection("tipo_punto_control"), "nombre", payload.nombre).limit(1).stream())
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un tipo con ese nombre")
    id_tipo = uuid4().hex
    record = {"id_tipo": id_tipo, "nombre": payload.nombre, "descripcion": payload.descripcion, "created_at": datetime.now(timezone.utc).isoformat()}
    db.collection("tipo_punto_control").document(id_tipo).set(record)
    return {"status": "ok", "data": record}


@router.put("/tipos-punto-control/{id_tipo}")
def update_tipo_punto_control(id_tipo: str, payload: TipoPuntoUpdate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tipo_punto_control").document(id_tipo)
    snap = ref.get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Tipo no encontrado")
    update_data: dict = {}
    if payload.nombre is not None:
        update_data["nombre"] = payload.nombre
    if payload.descripcion is not None:
        update_data["descripcion"] = payload.descripcion
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    return {"status": "ok", "data": {**snap.to_dict(), **update_data}}


@router.delete("/tipos-punto-control/{id_tipo}")
def delete_tipo_punto_control(id_tipo: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tipo_punto_control").document(id_tipo)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Tipo no encontrado")
    ref.delete()
    return {"status": "ok"}


@router.get("/dashboard/movimientos", response_model=list[DashboardMovimiento])
def dashboard_movimientos(user: dict = Depends(get_current_user)) -> list[DashboardMovimiento]:
    db = get_firestore_client()
    movimientos = [doc.to_dict() for doc in db.collection("movimiento_acceso").stream()]
    movimientos.sort(key=lambda x: x.get("fecha_hora_movimiento", ""), reverse=True)
    movimientos = movimientos[:10]
    visitas = {
        doc.to_dict().get("id_visita"): doc.to_dict()
        for doc in db.collection("visita").stream()
    }
    camiones = {
        doc.to_dict().get("id_camion"): doc.to_dict()
        for doc in db.collection("camion").stream()
    }
    conductores = {
        doc.to_dict().get("id_conductor"): doc.to_dict()
        for doc in db.collection("conductor").stream()
    }
    puntos = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    result = []
    for mov in movimientos:
        timestamp = mov.get("fecha_hora_movimiento")
        if not timestamp:
            continue
        mov_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        visita = visitas.get(mov.get("id_visita"), {})
        # Fallback para movimientos de ruta sin visita de planta (id_visita=null):
        # usar id_camion e id_conductor almacenados directamente en el movimiento.
        id_camion_mov = visita.get("id_camion") or mov.get("id_camion")
        id_conductor_mov = visita.get("id_conductor") or mov.get("id_conductor")
        camion = camiones.get(id_camion_mov, {})
        conductor = conductores.get(id_conductor_mov, {})
        punto = puntos.get(mov.get("id_punto_control"), {})
        result.append(
            DashboardMovimiento(
                estado="pasó por punto",
                hora=mov_dt.strftime("%I:%M %p"),
                patente=camion.get("patente", "-"),
                conductor=f"{conductor.get('nombre', '')} {conductor.get('apellido', '')}".strip() or "-",
                punto_control=punto.get("nombre"),
                timestamp=mov_dt,
            )
        )
    return result
