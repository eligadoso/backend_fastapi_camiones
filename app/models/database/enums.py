import enum


class EstadoGeneral(str, enum.Enum):
    activo = "activo"
    inactivo = "inactivo"


class EstadoTag(str, enum.Enum):
    activo = "activo"
    inactivo = "inactivo"
    bloqueado = "bloqueado"
    perdido = "perdido"


class TipoZona(str, enum.Enum):
    acceso = "acceso"
    patio = "patio"
    carga = "carga"
    descarga = "descarga"
    salida = "salida"


class TipoPunto(str, enum.Enum):
    porton_entrada = "porton_entrada"
    porton_salida = "porton_salida"
    checkpoint = "checkpoint"


class EstadoVisita(str, enum.Enum):
    en_planta = "en_planta"
    cerrada = "cerrada"
    anulada = "anulada"


class ResultadoLectura(str, enum.Enum):
    valida = "valida"
    rechazada = "rechazada"
    desconocida = "desconocida"


class TipoMovimiento(str, enum.Enum):
    ingreso = "ingreso"
    salida = "salida"


class SeveridadAlerta(str, enum.Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class EstadoAlerta(str, enum.Enum):
    pendiente = "pendiente"
    atendida = "atendida"
    cerrada = "cerrada"
