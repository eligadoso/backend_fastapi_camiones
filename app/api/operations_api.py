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
    RutaCamionAsignacionCreate,
    RutaCreate,
    RutaUpdate,
    TagCreate,
    TagUpdate,
    VinculacionCreate,
)

router = APIRouter(prefix="/api", tags=["operaciones"])


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
        "cordenadas": payload.cordenadas,
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
    if payload.cordenadas is not None:
        update_data["cordenadas"] = payload.cordenadas
    if payload.activo is not None:
        update_data["activo"] = payload.activo
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        ref.update(update_data)
    merged = {**current, **update_data}
    return {"status": "ok", "data": merged}


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


@router.post("/seguimiento-rutas/asignaciones")
def create_ruta_asignacion(payload: RutaCamionAsignacionCreate, user: dict = Depends(get_current_user)) -> dict:
    db = get_firestore_client()
    ruta = db.collection("ruta").document(payload.id_ruta).get()
    if not ruta.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    camion = db.collection("camion").document(payload.id_camion).get()
    if not camion.exists:
        raise HTTPException(status_code=404, detail="Camión no encontrado")
    ref = db.collection("ruta_camion_asignacion")
    now = datetime.now(timezone.utc).isoformat()
    active = list(
        ref.where("id_camion", "==", payload.id_camion).where("activa", "==", True).stream()
    )
    for doc in active:
        doc.reference.update({"activa": False, "fecha_fin": now})
    id_asignacion_ruta = uuid4().hex
    record = {
        "id_asignacion_ruta": id_asignacion_ruta,
        "id_ruta": payload.id_ruta,
        "id_camion": payload.id_camion,
        "hora_inicio": payload.hora_inicio.astimezone(timezone.utc).isoformat(),
        "activa": True,
        "fecha_fin": None,
        "created_at": now,
    }
    ref.document(id_asignacion_ruta).set(record)
    return {"status": "ok", "data": record}


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
    for item in items:
        camion = camiones.get(item.get("id_camion"), {})
        item["patente"] = camion.get("patente")
    return {"status": "ok", "data": items}


@router.get("/seguimiento-rutas")
def get_seguimiento_ruta(
    id_ruta: str,
    id_camion: str,
    user: dict = Depends(get_current_user),
) -> dict:
    db = get_firestore_client()
    ruta_snap = db.collection("ruta").document(id_ruta).get()
    if not ruta_snap.exists:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    ruta = ruta_snap.to_dict()
    puntos_ruta = sorted(ruta.get("puntos", []), key=lambda x: x.get("orden", 0))
    puntos_lookup = {
        doc.to_dict().get("id_punto_control"): doc.to_dict()
        for doc in db.collection("punto_control").stream()
    }
    asignaciones = [
        doc.to_dict()
        for doc in db.collection("ruta_camion_asignacion")
        .where("id_ruta", "==", id_ruta)
        .where("id_camion", "==", id_camion)
        .stream()
    ]
    if not asignaciones:
        return {"status": "ok", "data": {"id_ruta": id_ruta, "id_camion": id_camion, "puntos": []}}
    asignaciones.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    asignacion = asignaciones[0]
    hora_inicio = _parse_iso_datetime(asignacion.get("hora_inicio"))
    if hora_inicio is None:
        return {"status": "ok", "data": {"id_ruta": id_ruta, "id_camion": id_camion, "puntos": []}}
    movimientos = [doc.to_dict() for doc in db.collection("movimiento_acceso").stream()]
    visitas = [doc.to_dict() for doc in db.collection("visita").where("id_camion", "==", id_camion).stream()]
    ids_visita = {v.get("id_visita") for v in visitas}
    movs_camion = []
    for mov in movimientos:
        if mov.get("id_visita") not in ids_visita:
            continue
        ts = _parse_iso_datetime(mov.get("fecha_hora_movimiento"))
        if ts is None or ts < hora_inicio:
            continue
        movs_camion.append({**mov, "_dt": ts})
    movs_camion.sort(key=lambda x: x["_dt"])
    pass_map: dict[str, datetime] = {}
    for mov in movs_camion:
        pid = mov.get("id_punto_control")
        if pid and pid not in pass_map:
            pass_map[pid] = mov["_dt"]
    ordenes_pasadas = []
    for p in puntos_ruta:
        pid = p.get("id_punto_control")
        if pid in pass_map:
            ordenes_pasadas.append(int(p.get("orden", 0)))
    started = len(ordenes_pasadas) > 0
    max_orden_pasada = max(ordenes_pasadas) if ordenes_pasadas else 0
    now = datetime.now(timezone.utc)
    salida = []
    for p in puntos_ruta:
        pid = p.get("id_punto_control")
        orden = int(p.get("orden", 0))
        punto = puntos_lookup.get(pid, {})
        marca = pass_map.get(pid)
        if marca:
            estado = "pasado"
            fecha_hora = marca.isoformat()
            tiempo_en_punto = None
        else:
            if started and orden < max_orden_pasada:
                estado = "omitido"
            else:
                estado = "pendiente"
            fecha_hora = None
            tiempo_en_punto = None
        salida.append(
            {
                "id_punto_control": pid,
                "nombre_punto": punto.get("nombre"),
                "orden": orden,
                "estado": estado,
                "fecha_hora_paso": fecha_hora,
                "tiempo_en_punto": tiempo_en_punto,
                "referencia_tiempo_en_punto": None,
            }
        )
    salida.sort(key=lambda x: x["orden"])
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
                    hours = minutes // 60
                    mins = minutes % 60
                    actual["tiempo_en_punto"] = f"{hours:02d}:{mins:02d}"
                    actual["referencia_tiempo_en_punto"] = previo_dt.isoformat()
    for item in salida:
        if item["fecha_hora_paso"] is None:
            item["fecha_hora_paso"] = "--:--; --/--"
    return {
        "status": "ok",
        "data": {
            "id_ruta": id_ruta,
            "id_camion": id_camion,
            "hora_inicio": hora_inicio.isoformat(),
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
    camiones = {
        doc.to_dict().get("id_camion"): doc.to_dict()
        for doc in db.collection("camion").stream()
    }
    visitas = [doc.to_dict() for doc in db.collection("visita").stream()]
    visita_por_camion: dict[str, set[str]] = {}
    for v in visitas:
        cid = v.get("id_camion")
        vid = v.get("id_visita")
        if cid and vid:
            visita_por_camion.setdefault(cid, set()).add(vid)
    movimientos = [doc.to_dict() for doc in db.collection("movimiento_acceso").stream()]
    asignaciones = [
        doc.to_dict()
        for doc in db.collection("ruta_camion_asignacion")
        .where("id_ruta", "==", id_ruta)
        .stream()
    ]
    puntos_metricas = []
    for index in range(1, len(puntos_ruta)):
        prev_pid = puntos_ruta[index - 1].get("id_punto_control")
        curr_pid = puntos_ruta[index].get("id_punto_control")
        curr_nombre = puntos_lookup.get(curr_pid, {}).get("nombre")
        registros = []
        for asignacion in asignaciones:
            cid = asignacion.get("id_camion")
            if not cid:
                continue
            hora_inicio = _parse_iso_datetime(asignacion.get("hora_inicio"))
            if hora_inicio is None:
                continue
            ids_visita = visita_por_camion.get(cid, set())
            movs = []
            for mov in movimientos:
                if mov.get("id_visita") not in ids_visita:
                    continue
                dt = _parse_iso_datetime(mov.get("fecha_hora_movimiento"))
                if dt is None or dt < hora_inicio:
                    continue
                movs.append({**mov, "_dt": dt})
            movs.sort(key=lambda x: x["_dt"])
            t_prev = None
            t_curr = None
            for mov in movs:
                pid = mov.get("id_punto_control")
                if pid == prev_pid and t_prev is None:
                    t_prev = mov["_dt"]
                if pid == curr_pid and t_curr is None:
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
                        "fecha_hora": t_curr.isoformat(),
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
                "id_punto_control": curr_pid,
                "nombre_punto": curr_nombre,
                "orden": int(puntos_ruta[index].get("orden", index + 1)),
                "transicion_desde_orden": int(puntos_ruta[index - 1].get("orden", index)),
                "registros": registros,
                "resumen": {
                    "tiempo_mas_alto": max_item,
                    "tiempo_mas_bajo": min_item,
                    "tiempo_promedio_min": avg,
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
