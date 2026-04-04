from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import httpx

from app.firebase_client import get_firestore_client
from app.models import SensorReading, ThingSpeakWebhookPayload
from app.settings import settings


class WebhookController:
    def __init__(self) -> None:
        self._db = self._build_firestore_client()
        self._last_entry_id: int | None = None

    def _build_firestore_client(self):
        try:
            return get_firestore_client()
        except Exception:
            return None

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
        tags = list(self._db.collection("tag_rfid").where("uid_tag", "==", uid).limit(1).stream())
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
        points = list(self._db.collection("punto_control").where("id_esp32", "==", esp32_id).limit(1).stream())
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

    def _register_movimiento_desde_lectura(
        self,
        id_tag: str,
        id_punto_control: str,
        id_lectura: str,
        timestamp: str,
    ) -> None:
        vinculos = list(
            self._db.collection("vinculacion_activa")
            .where("id_tag", "==", id_tag)
            .where("activa", "==", True)
            .limit(1)
            .stream()
        )
        if not vinculos:
            return
        vinculo = vinculos[0].to_dict()
        punto_snap = self._db.collection("punto_control").document(id_punto_control).get()
        if not punto_snap.exists:
            return
        punto = punto_snap.to_dict()
        tipo_punto = punto.get("tipo_punto", "checkpoint")
        id_camion = vinculo.get("id_camion")
        id_conductor = vinculo.get("id_conductor")
        if not id_camion or not id_conductor:
            return
        visitas_ref = self._db.collection("visita")
        abiertas = list(
            visitas_ref.where("id_camion", "==", id_camion).where("estado_visita", "==", "en_planta").limit(1).stream()
        )
        visita_id = None
        if tipo_punto == "porton_entrada":
            movimiento_tipo = "ingreso"
        elif tipo_punto == "porton_salida":
            movimiento_tipo = "salida"
        else:
            movimiento_tipo = "salida" if abiertas else "ingreso"
        if movimiento_tipo == "ingreso":
            if abiertas:
                visita_id = abiertas[0].to_dict().get("id_visita")
            else:
                visita_id = uuid4().hex
                visitas_ref.document(visita_id).set(
                    {
                        "id_visita": visita_id,
                        "id_camion": id_camion,
                        "id_conductor": id_conductor,
                        "id_planta": "planta_default",
                        "fecha_hora_ingreso": timestamp,
                        "fecha_hora_salida": None,
                        "estado_visita": "en_planta",
                        "motivo": "lectura_rfid",
                        "observacion": "Ingreso automático por portón de entrada",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        else:
            if not abiertas:
                return
            visita_doc = abiertas[0]
            visita_id = visita_doc.to_dict().get("id_visita")
            visita_doc.reference.update(
                {
                    "fecha_hora_salida": timestamp,
                    "estado_visita": "cerrada",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        if not visita_id:
            return
        movimiento_id = uuid4().hex
        self._db.collection("movimiento_acceso").document(movimiento_id).set(
            {
                "id_movimiento": movimiento_id,
                "id_visita": visita_id,
                "id_lectura": id_lectura,
                "tipo_movimiento": "paso_punto",
                "direccion_inferida": movimiento_tipo,
                "fecha_hora_movimiento": timestamp,
                "id_punto_control": id_punto_control,
                "validado": True,
                "observacion": f"Pasó por {tipo_punto}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )


webhook_controller = WebhookController()
