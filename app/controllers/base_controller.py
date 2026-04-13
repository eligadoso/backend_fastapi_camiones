from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx
from google.cloud.firestore_v1.base_query import FieldFilter

from app.firebase_client import get_firestore_client
from app.models import SensorReading, ThingSpeakWebhookPayload
from app.settings import settings


class WebhookController:
    def __init__(self) -> None:
        self._db = self._build_firestore_client()
        self._last_entry_id: int | None = self._load_last_entry_id()

    def _build_firestore_client(self):
        try:
            return get_firestore_client()
        except Exception:
            return None

    def _load_last_entry_id(self) -> int | None:
        if self._db is None:
            return None
        try:
            docs = (
                self._db.collection(settings.firebase_collection)
                .order_by("received_at", direction="DESCENDING")
                .limit(1)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict()
                raw = data.get("raw_payload", {})
                entry_id = raw.get("entry_id")
                if entry_id is not None:
                    return int(entry_id)
        except Exception:
            pass
        return None

    def _where_eq(self, query, field: str, value):
        return query.where(filter=FieldFilter(field, "==", value))

    async def pull_latest_from_thingspeak(self, channel_id: str) -> dict[str, Any]:
        url, params = self._build_thingspeak_request(channel_id=channel_id)
        async with httpx.AsyncClient(timeout=settings.thingspeak_timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        normalized_payload = self._normalize_thingspeak_payload(payload)
        if normalized_payload is None:
            return {"status": "ok", "source": "thingspeak_pull", "firebase_document_id": None, "data": None}
        reading = self._to_sensor_reading(normalized_payload)
        firebase_id = self._save_to_firebase(reading)
        self._register_rfid_and_reading(reading)
        return {
            "status": "ok",
            "source": "thingspeak_pull",
            "firebase_document_id": firebase_id,
            "data": reading.model_dump(mode="json"),
        }

    async def pull_latest_from_settings(self) -> dict[str, Any]:
        channel_id = settings.thingspeak_channel_id or ""
        return await self.pull_latest_from_thingspeak(channel_id)

    def process_webhook(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        parsed_payload = ThingSpeakWebhookPayload.model_validate(dict(payload))
        reading = self._to_sensor_reading(parsed_payload.model_dump(mode="json"))
        self._register_rfid_and_reading(reading)
        firebase_id = self._save_to_firebase(reading)
        return {
            "status": "ok",
            "source": "thingspeak_webhook",
            "firebase_document_id": firebase_id,
            "data": reading.model_dump(mode="json"),
        }

    def _to_sensor_reading(self, raw_payload: dict[str, Any]) -> SensorReading:
        values = {
            key: value
            for key, value in raw_payload.items()
            if key.startswith("field") and value is not None
        }
        channel_id = raw_payload.get("channel_id")
        return SensorReading(
            source="thingspeak",
            received_at=datetime.now(timezone.utc),
            channel_id=str(channel_id) if channel_id is not None else None,
            values=values,
            raw_payload=raw_payload,
        )

    def _build_thingspeak_request(self, channel_id: str) -> tuple[str, dict[str, str] | None]:
        if settings.thingspeak_field1_url:
            return settings.thingspeak_field1_url, None
        if settings.thingspeak_read_api_key and settings.thingspeak_read_api_key.startswith("http"):
            return settings.thingspeak_read_api_key, None
        effective_channel = channel_id or settings.thingspeak_channel_id
        if not effective_channel:
            raise RuntimeError("Falta THINGSPEAK_CHANNEL_ID para consultar ThingSpeak.")
        url = f"{settings.thingspeak_base_url}/channels/{effective_channel}/feeds.json"
        params = {"results": "1"}
        if settings.thingspeak_read_api_key:
            params["api_key"] = settings.thingspeak_read_api_key
        return url, params

    def _normalize_thingspeak_payload(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        entry_id = payload.get("entry_id")
        if entry_id is not None:
            if self._is_duplicate_entry(entry_id):
                return None
            return payload
        feeds = payload.get("feeds")
        if isinstance(feeds, list) and feeds:
            last_feed = feeds[-1]
            if not isinstance(last_feed, dict):
                return None
            normalized = dict(last_feed)
            channel = payload.get("channel")
            if isinstance(channel, dict):
                channel_id = channel.get("id")
                if channel_id is not None:
                    normalized["channel_id"] = channel_id
            entry_id = normalized.get("entry_id")
            if entry_id is not None and self._is_duplicate_entry(entry_id):
                return None
            return normalized
        return None

    def _is_duplicate_entry(self, entry_id: Any) -> bool:
        try:
            current = int(entry_id)
        except (TypeError, ValueError):
            return False
        if self._last_entry_id is not None and current <= self._last_entry_id:
            return True
        self._last_entry_id = current
        return False

    def _save_to_firebase(self, reading: SensorReading) -> str | None:
        if self._db is None:
            return None
        doc_ref = self._db.collection(settings.firebase_collection).document()
        doc_ref.set(reading.model_dump(mode="json"))
        print(f"[ThingSpeak] Guardado en Firebase colección {settings.firebase_collection}: {doc_ref.id}")
        return doc_ref.id

    def _register_rfid_and_reading(self, reading: SensorReading) -> None:
        if self._db is None:
            return
        uid = reading.values.get("field1")
        esp32_id = reading.values.get("field2")
        if not isinstance(uid, str) or not uid.strip():
            return
        uid = uid.strip()
        tag_id = self._ensure_tag(uid)
        if not isinstance(esp32_id, str) or not esp32_id.strip():
            return
        esp32_id = esp32_id.strip()
        punto_id = self._ensure_punto_control(esp32_id)
        lectura_id = uuid4().hex
        self._db.collection("lectura_rfid").document(lectura_id).set(
            {
                "id_lectura": lectura_id,
                "id_tag": tag_id,
                "id_punto_control": punto_id,
                "fecha_hora_lectura": reading.received_at.isoformat(),
                "resultado": "valida",
                "detalle": "Lectura recibida desde ThingSpeak",
                "raw_data": reading.raw_payload,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        print(
            f"[ThingSpeak] Lectura registrada uid={uid} esp32={esp32_id} punto={punto_id} lectura={lectura_id}"
        )
        self._register_movimiento_desde_lectura(
            id_tag=tag_id,
            id_punto_control=punto_id,
            id_lectura=lectura_id,
            timestamp=reading.received_at.isoformat(),
        )

    def _ensure_tag(self, uid: str) -> str:
        tags = list(self._where_eq(self._db.collection("tag_rfid"), "uid_tag", uid).limit(1).stream())
        if tags:
            return tags[0].to_dict()["id_tag"]
        tag_id = uuid4().hex
        self._db.collection("tag_rfid").document(tag_id).set(
            {
                "id_tag": tag_id,
                "uid_tag": uid,
                "codigo_interno": None,
                "estado": "activo",
                "fecha_alta": datetime.now(timezone.utc).isoformat(),
                "fecha_baja": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return tag_id

    def _ensure_punto_control(self, esp32_id: str) -> str:
        points = list(self._where_eq(self._db.collection("punto_control"), "id_esp32", esp32_id).limit(1).stream())
        if points:
            return points[0].to_dict()["id_punto_control"]
        point_id = uuid4().hex
        self._db.collection("punto_control").document(point_id).set(
            {
                "id_punto_control": point_id,
                "id_zona": None,
                "nombre": f"Punto {esp32_id}",
                "tipo_punto": "checkpoint",
                "id_esp32": esp32_id,
                "ubicacion": None,
                "cordenadas": None,
                "activo": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return point_id

    def _resolve_camion_conductor_para_tag(self, id_tag: str) -> tuple[str | None, str | None]:
        """Devuelve (id_camion, id_conductor) para el tag dado.

        Prioridad:
        1. vinculacion_activa (vínculo operacional explícito)
        2. asignacion_tag   (asignación estática alternativa)
        3. tag_rfid.id_conductor → conductor.id_camion  (cadena principal de la UI)
        """
        # 1) Vínculo operacional explícito
        vinculos = list(
            self._where_eq(
                self._where_eq(self._db.collection("vinculacion_activa"), "id_tag", id_tag),
                "activa",
                True,
            )
            .limit(1)
            .stream()
        )
        if vinculos:
            v = vinculos[0].to_dict()
            return v.get("id_camion"), v.get("id_conductor")

        # 2) asignacion_tag (alternativa explícita)
        asignaciones = list(
            self._where_eq(
                self._where_eq(self._db.collection("asignacion_tag"), "id_tag", id_tag),
                "activa",
                True,
            )
            .limit(1)
            .stream()
        )
        if asignaciones:
            id_camion = asignaciones[0].to_dict().get("id_camion")
            if id_camion:
                camion_snap = self._db.collection("camion").document(id_camion).get()
                id_conductor = camion_snap.to_dict().get("id_conductor") if camion_snap.exists else None
                if not id_conductor:
                    conds = list(
                        self._where_eq(self._db.collection("conductor"), "id_camion", id_camion).limit(1).stream()
                    )
                    if conds:
                        id_conductor = conds[0].to_dict().get("id_conductor")
                return id_camion, id_conductor

        # 3) Cadena principal creada por la UI:
        #    tag_rfid.id_conductor  →  conductor.id_camion
        tag_snap = self._db.collection("tag_rfid").document(id_tag).get()
        if not tag_snap.exists:
            return None, None
        id_conductor = tag_snap.to_dict().get("id_conductor")
        if not id_conductor:
            return None, None

        conductor_snap = self._db.collection("conductor").document(id_conductor).get()
        if not conductor_snap.exists:
            return None, id_conductor
        id_camion = conductor_snap.to_dict().get("id_camion")

        if not id_camion:
            # Búsqueda inversa por si el campo está solo en el camión
            camiones = list(
                self._where_eq(self._db.collection("camion"), "id_conductor", id_conductor).limit(1).stream()
            )
            if camiones:
                id_camion = camiones[0].to_dict().get("id_camion")

        return id_camion, id_conductor

    # ------------------------------------------------------------------
    # Lógica de recorridos (ruta_camion_asignacion)
    # ------------------------------------------------------------------

    def _get_recorrido_en_proceso(self, id_camion: str) -> dict | None:
        """Devuelve el único recorrido en estado 'en_proceso' para el camión dado.

        Prioridad: estado_recorrido == "en_proceso" (campo nuevo).
        Fallback para registros anteriores: activa == True sin estado_recorrido.
        Si existe más de uno (error de datos), se usa el de hora_inicio más reciente y
        se registra un warning.
        """
        # Búsqueda por estado_recorrido (campo nuevo)
        docs_en_proceso = list(
            self._where_eq(
                self._where_eq(
                    self._db.collection("ruta_camion_asignacion"),
                    "id_camion",
                    id_camion,
                ),
                "estado_recorrido",
                "en_proceso",
            )
            .stream()
        )
        if docs_en_proceso:
            if len(docs_en_proceso) > 1:
                print(
                    f"[WARN] Camión {id_camion} tiene {len(docs_en_proceso)} recorridos en_proceso "
                    f"simultáneos. Se usará el de hora_inicio más reciente."
                )
            docs_en_proceso.sort(
                key=lambda d: d.to_dict().get("hora_inicio", ""),
                reverse=True,
            )
            return docs_en_proceso[0].to_dict()

        # Fallback: activa=True sin estado_recorrido (compatibilidad con datos anteriores)
        docs_activos = list(
            self._where_eq(
                self._where_eq(
                    self._db.collection("ruta_camion_asignacion"),
                    "id_camion",
                    id_camion,
                ),
                "activa",
                True,
            )
            .stream()
        )
        # Excluir los que tengan estado_recorrido explícito (ya cubiertos arriba)
        docs_activos = [
            d for d in docs_activos
            if not d.to_dict().get("estado_recorrido")
        ]
        if docs_activos:
            docs_activos.sort(
                key=lambda d: d.to_dict().get("hora_inicio", ""),
                reverse=True,
            )
            return docs_activos[0].to_dict()

        return None

    def _inicializar_puntos_estado(self, puntos_snapshot: list[dict]) -> list[dict]:
        """Construye el estado inicial de puntos (todos pendientes)."""
        return [
            {
                "id_punto_control": p["id_punto_control"],
                "orden": int(p.get("orden", 0)),
                "estado": "pendiente",
                "fecha_hora_paso": None,
                "id_lectura": None,
                "id_movimiento": None,
            }
            for p in sorted(puntos_snapshot, key=lambda x: int(x.get("orden", 0)))
        ]

    def _register_movimiento_desde_lectura(
        self,
        id_tag: str,
        id_punto_control: str,
        id_lectura: str,
        timestamp: str,
    ) -> None:
        """Procesa una lectura RFID contra el recorrido activo del camión.

        Flujo:
        1. UID (tag) → conductor → camión
        2. Camión → recorrido en estado 'en_proceso'
        3. Validar punto recibido contra puntos_snapshot del recorrido
        4. Aplicar lógica de casos A/B/C/D
        5. Persistir puntos_estado y crear movimiento_acceso con link directo al recorrido
        """
        # 1. Resolver camión y conductor a partir del tag
        id_camion, id_conductor = self._resolve_camion_conductor_para_tag(id_tag)
        if not id_camion:
            print(f"[Recorrido] Sin camión resuelto para tag={id_tag}. Lectura ignorada.")
            return
        if not id_conductor:
            print(f"[Recorrido] Tag={id_tag} resuelve camión={id_camion} pero sin conductor. Lectura ignorada.")
            return

        # 2. Obtener recorrido activo (exclusivamente "en_proceso")
        recorrido = self._get_recorrido_en_proceso(id_camion)
        if not recorrido:
            print(
                f"[Recorrido] Camión={id_camion} no tiene recorrido en_proceso. "
                f"Lectura id_lectura={id_lectura} ignorada para rutas."
            )
            return

        id_asignacion_ruta = recorrido["id_asignacion_ruta"]

        # 3. Verificar que el punto pertenece a este recorrido (Caso D)
        puntos_snapshot: list[dict] = sorted(
            recorrido.get("puntos_snapshot") or [],
            key=lambda x: int(x.get("orden", 0)),
        )
        if not puntos_snapshot:
            print(f"[Recorrido] Recorrido={id_asignacion_ruta} no tiene puntos_snapshot. Lectura ignorada.")
            return

        punto_ids_en_ruta = {p["id_punto_control"] for p in puntos_snapshot}
        if id_punto_control not in punto_ids_en_ruta:
            print(
                f"[Recorrido] Punto={id_punto_control} NO pertenece al recorrido={id_asignacion_ruta}. "
                f"Caso D — ignorado."
            )
            return

        # 4. Obtener o inicializar puntos_estado
        puntos_estado: list[dict] = recorrido.get("puntos_estado") or self._inicializar_puntos_estado(
            puntos_snapshot
        )
        puntos_estado.sort(key=lambda x: int(x.get("orden", 0)))

        # Reconciliación defensiva: si hay puntos en puntos_snapshot que no están en
        # puntos_estado (ocurre cuando se agregó un punto al recorrido antes de que
        # llegara la primera lectura RFID, dejando puntos_estado incompleto), se añaden
        # como "pendiente" para que el algoritmo de omisión los procese correctamente.
        ids_en_estado = {p["id_punto_control"] for p in puntos_estado}
        faltantes = [
            {
                "id_punto_control": p["id_punto_control"],
                "orden": int(p.get("orden", 0)),
                "estado": "pendiente",
                "fecha_hora_paso": None,
                "id_lectura": None,
                "id_movimiento": None,
            }
            for p in puntos_snapshot
            if p["id_punto_control"] not in ids_en_estado
        ]
        if faltantes:
            puntos_estado.extend(faltantes)
            puntos_estado.sort(key=lambda x: int(x.get("orden", 0)))
            print(
                f"[Recorrido] Reconciliación: {len(faltantes)} punto(s) agregado(s) a puntos_estado "
                f"del recorrido={id_asignacion_ruta}."
            )

        # Buscar el estado del punto recibido
        punto_estado = next(
            (p for p in puntos_estado if p["id_punto_control"] == id_punto_control),
            None,
        )
        if punto_estado is None:
            # No debería ocurrir si puntos_snapshot y puntos_estado son coherentes
            print(f"[Recorrido] Inconsistencia: punto={id_punto_control} en snapshot pero no en estado.")
            return

        # Caso A: el punto ya fue procesado (pasado u omitido) → idempotencia, ignorar
        if punto_estado["estado"] in ("pasado", "omitido"):
            print(
                f"[Recorrido] Punto={id_punto_control} ya tiene estado='{punto_estado['estado']}' "
                f"en recorrido={id_asignacion_ruta}. Caso A — ignorado."
            )
            return

        # Determinar el próximo pendiente esperado
        pendientes = [p for p in puntos_estado if p["estado"] == "pendiente"]
        if not pendientes:
            # Todos procesados; el recorrido debería haberse completado ya
            print(f"[Recorrido] Recorrido={id_asignacion_ruta} sin pendientes pero llegó lectura. Ignorado.")
            return

        orden_recibido = int(punto_estado.get("orden", 0))
        orden_esperado = int(pendientes[0].get("orden", 0))

        ahora = datetime.now(timezone.utc).isoformat()

        if orden_recibido == orden_esperado:
            # Caso B: es exactamente el siguiente esperado
            punto_estado["estado"] = "pasado"
            punto_estado["fecha_hora_paso"] = timestamp
            punto_estado["id_lectura"] = id_lectura
            print(f"[Recorrido] Caso B — punto={id_punto_control} registrado como pasado.")

        elif orden_recibido > orden_esperado:
            # Caso C: punto adelantado → marcar intermedios como omitido
            omitidos = []
            for p in puntos_estado:
                if p["estado"] == "pendiente" and int(p.get("orden", 0)) < orden_recibido:
                    p["estado"] = "omitido"
                    omitidos.append(p["id_punto_control"])
            punto_estado["estado"] = "pasado"
            punto_estado["fecha_hora_paso"] = timestamp
            punto_estado["id_lectura"] = id_lectura
            print(
                f"[Recorrido] Caso C — punto={id_punto_control} adelantado. "
                f"Omitidos: {omitidos}. Registrado como pasado."
            )

        else:
            # orden_recibido < orden_esperado y estado == "pendiente"
            # Solo ocurre si puntos_estado está corrupto; ignorar de forma segura
            print(
                f"[Recorrido] Punto={id_punto_control} con orden={orden_recibido} < esperado={orden_esperado} "
                f"y aún pendiente. Estado inconsistente — ignorado."
            )
            return

        # 5. Crear movimiento_acceso con link directo al recorrido
        movimiento_id = uuid4().hex
        punto_estado["id_movimiento"] = movimiento_id

        # Intentar vincular a visita abierta (compatibilidad con módulo de planta)
        visitas_ref = self._db.collection("visita")
        abiertas = list(
            self._where_eq(
                self._where_eq(visitas_ref, "id_camion", id_camion),
                "estado_visita",
                "en_planta",
            )
            .limit(1)
            .stream()
        )
        id_visita = abiertas[0].to_dict().get("id_visita") if abiertas else None

        # Obtener coordenadas del punto de control para el mapa del dashboard.
        # Se guardan directamente en el movimiento para que dashboard_ubicacion_tiempo_real
        # pueda resolverlas sin depender de id_visita (que es null en recorridos de ruta).
        try:
            punto_doc = self._db.collection("punto_control").document(id_punto_control).get()
            cordenadas_punto = punto_doc.to_dict().get("cordenadas") if punto_doc.exists else None
        except Exception:
            cordenadas_punto = None

        self._db.collection("movimiento_acceso").document(movimiento_id).set(
            {
                "id_movimiento": movimiento_id,
                "id_asignacion_ruta": id_asignacion_ruta,   # link directo al recorrido
                "id_visita": id_visita,                      # null si no hay visita de planta abierta
                "id_camion": id_camion,                      # copia directa → dashboard sin id_visita
                "id_conductor": id_conductor,                # copia directa → dashboard sin id_visita
                "id_lectura": id_lectura,
                "tipo_movimiento": "paso_punto",
                "fecha_hora_movimiento": timestamp,
                "id_punto_control": id_punto_control,
                "cordenadas": cordenadas_punto,              # coords del punto → mapa en tiempo real
                "validado": True,
                "observacion": f"Punto {punto_estado['estado']} en recorrido {id_asignacion_ruta}",
                "created_at": ahora,
            }
        )

        # 6. Persistir puntos_estado actualizado en el recorrido
        recorrido_ref = self._db.collection("ruta_camion_asignacion").document(id_asignacion_ruta)
        actualizacion: dict = {
            "puntos_estado": puntos_estado,
            "updated_at": ahora,
        }

        # 7. Verificar si el recorrido queda completo
        todos_procesados = all(p["estado"] in ("pasado", "omitido") for p in puntos_estado)
        if todos_procesados:
            actualizacion["estado_recorrido"] = "finalizado"
            actualizacion["activa"] = False
            actualizacion["fecha_fin"] = timestamp
            print(f"[Recorrido] Recorrido={id_asignacion_ruta} FINALIZADO automáticamente.")

        recorrido_ref.update(actualizacion)
        print(
            f"[Recorrido] Movimiento={movimiento_id} registrado. "
            f"Recorrido={id_asignacion_ruta} camion={id_camion} punto={id_punto_control}"
        )

        # 8. Si el recorrido se finalizó, activar el siguiente recorrido agendado del camión
        if todos_procesados:
            self._activar_siguiente_agendado(id_camion, timestamp)


    def _activar_siguiente_agendado(self, id_camion: str, timestamp: str) -> None:
        """Activa el siguiente recorrido agendado del camión, si existe.

        Regla: solo un recorrido puede estar 'en_proceso' por camión.
        Cuando el actual finaliza, se busca el próximo 'agendado' ordenado
        por hora_inicio ascendente y se transiciona a 'en_proceso'.
        """
        agendados = list(
            self._where_eq(
                self._where_eq(
                    self._db.collection("ruta_camion_asignacion"),
                    "id_camion",
                    id_camion,
                ),
                "estado_recorrido",
                "agendado",
            )
            .stream()
        )
        if not agendados:
            print(f"[Recorrido] Camión={id_camion} sin recorridos agendados. Nada que activar.")
            return

        # Ordenar por hora_inicio ascendente: el más próximo primero
        agendados.sort(key=lambda d: d.to_dict().get("hora_inicio", ""))
        siguiente = agendados[0]
        siguiente_id = siguiente.to_dict().get("id_asignacion_ruta") or siguiente.id

        siguiente.reference.update({
            "estado_recorrido": "en_proceso",
            "activa": True,
            "updated_at": timestamp,
        })
        print(
            f"[Recorrido] Recorrido={siguiente_id} activado automáticamente "
            f"para camión={id_camion}."
        )


webhook_controller = WebhookController()
