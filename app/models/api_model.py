from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class CamionCreate(BaseModel):
    patente: str
    id_empresa: int
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None


class CamionUpdate(BaseModel):
    patente: str | None = None
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None
    estado: str | None = None


class ConductorCreate(BaseModel):
    rut: str
    nombre: str
    apellido: str
    telefono: str | None = None
    licencia: str | None = None


class ConductorUpdate(BaseModel):
    nombre: str | None = None
    apellido: str | None = None
    telefono: str | None = None
    licencia: str | None = None
    estado: str | None = None


class TagCreate(BaseModel):
    uid_tag: str
    codigo_interno: str | None = None


class TagUpdate(BaseModel):
    codigo_interno: str | None = None
    estado: str | None = None
    fecha_baja: datetime | None = None
    id_conductor: str | None = None


class TagConductorAsignacion(BaseModel):
    id_conductor: str


class TipoPuntoCreate(BaseModel):
    nombre: str
    descripcion: str | None = None


class TipoPuntoUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None


class AsignacionTagCreate(BaseModel):
    id_tag: str
    id_camion: str


class VinculacionCreate(BaseModel):
    id_tag: str
    id_camion: str
    id_conductor: str


class PuntoControlCreate(BaseModel):
    nombre: str
    tipo_punto: str = "checkpoint"
    id_esp32: str
    id_zona: str | None = None
    ubicacion: str | None = None
    cordenadas: str | None = None


class PuntoControlUpdate(BaseModel):
    nombre: str | None = None
    tipo_punto: str | None = None
    id_zona: str | None = None
    ubicacion: str | None = None
    cordenadas: str | None = None
    activo: bool | None = None


class RutaPunto(BaseModel):
    id_punto_control: str
    orden: int


class RutaCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    activa: bool = True
    puntos: list[RutaPunto] = []


class RutaUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    activa: bool | None = None
    puntos: list[RutaPunto] | None = None


class RutaCamionAsignacionCreate(BaseModel):
    id_ruta: str
    id_camion: str
    hora_inicio: datetime


class DashboardSummary(BaseModel):
    camiones_en_planta: int
    ingresos_hoy: int
    tiempo_promedio_estadia_min: int


class DashboardMovimiento(BaseModel):
    estado: str
    hora: str
    patente: str
    conductor: str
    punto_control: str | None = None
    timestamp: datetime
