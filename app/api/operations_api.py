from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_current_user
from app.firebase_client import get_firestore_client
from app.models.api_model import (
    AsignacionTagCreate,
    CamionCreate,
    ConductorCreate,
    DashboardMovimiento,
    DashboardSummary,
    PuntoControlCreate,
    PuntoControlUpdate,
    TagCreate,
    TagUpdate,
    VinculacionCreate,
)

router = APIRouter(prefix="/api", tags=["operaciones"])


@router.post("/camiones")
def create_camion(payload: CamionCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    camion_ref = db.collection("camion")
    exists = list(camion_ref.where("patente", "==", payload.patente).limit(1).stream())
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
    return {"status": "ok", "data": data}


@router.get("/camiones/{id_camion}")
def get_camion(id_camion: str, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    snap = db.collection("camion").document(id_camion).get()
    if not snap.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    return {"status": "ok", "data": snap.to_dict()}


@router.post("/conductores")
def create_conductor(payload: ConductorCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("conductor")
    exists = list(ref.where("rut", "==", payload.rut).limit(1).stream())
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
    return {"status": "ok", "data": data}


@router.post("/rfid/tags")
def create_tag(payload: TagCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("tag_rfid")
    exists = list(ref.where("uid_tag", "==", payload.uid_tag).limit(1).stream())
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


@router.post("/puntos-control")
def create_punto_control(payload: PuntoControlCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ref = db.collection("punto_control")
    exists = list(ref.where("id_esp32", "==", payload.id_esp32).limit(1).stream())
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
        "activo": True,
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
    if payload.activo is not None:
        update_data["activo"] = payload.activo
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    merged = {**current, **update_data}
    return {"status": "ok", "data": merged}


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
    active_docs = list(active_ref.where("activa", "==", True).stream())
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
        ref.where("id_tag", "==", payload.id_tag).where("activa", "==", True).limit(1).stream()
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
        camion = camiones.get(visita.get("id_camion"), {})
        conductor = conductores.get(visita.get("id_conductor"), {})
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
