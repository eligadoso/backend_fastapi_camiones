# Backend FastAPI WebHooks

## Estructura

- `app/models/base_model.py`: modelos de datos
- `app/controllers/base_controller.py`: reglas de negocio y envío a Firebase
- `app/api/base_api.py`: endpoints HTTP

## Variables de entorno

1. Copia `.env.example` a `.env`
2. Completa credenciales cuando las tengas:
   - `THINGSPEAK_READ_API_KEY`
   - `FIREBASE_CREDENTIALS_PATH`
   - `FIREBASE_REALTIME_DB_URL` (opcional)
   - `FIREBASE_COLLECTION`
   - `SESSION_SECRET`
   - `FRONTEND_ORIGIN`

## Ejecución

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Prueba de conexión Firebase

```bash
python scripts/test_firebase_connection.py --credentials-path caminesproyecto.json
```

Ese script además crea el usuario inicial `admin / admin123` si todavía no existe en la colección `usuario`.

También puedes usar las variables de `.env`:

- `FIREBASE_CREDENTIALS_PATH`
- `FIREBASE_REALTIME_DB_URL`
- `FIREBASE_COLLECTION`

## Base principal

- La persistencia principal del backend está en Firebase Firestore.
- El webhook de ThingSpeak guarda lecturas en Firebase y auto-registra `field1` como UID en `tag_rfid` cuando no existe.
- `field2` se interpreta como `id_esp32` del punto de control y se registra en `punto_control` si no existe.
- Cuando llegan `field1` y `field2`, se crea una lectura en `lectura_rfid` con RFID, punto de control y fecha/hora.
- Usuario inicial para sesión backend:
  - `username`: `admin`
  - `password`: `admin123`

## Prueba de lectura ThingSpeak (field1)

```bash
python scripts/test_thingspeak_field1.py --url "https://api.thingspeak.com/channels/3324961/fields/1/last.json?api_key=TU_API_KEY"
```

También puedes usar:

- `THINGSPEAK_BASE_URL`
- `THINGSPEAK_CHANNEL_ID`
- `THINGSPEAK_READ_API_KEY`
- `THINGSPEAK_FIELD1_URL`
- `THINGSPEAK_TIMEOUT`
