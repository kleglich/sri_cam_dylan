"""Modelo del dominio del SRI (sección 5.2.1 del informe)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Rol = Literal["Secretaria", "Gerencia"]
EstadoEntrega = Literal["PENDIENTE", "ENTREGADA", "NO ENTREGADA", "CON NOVEDAD"]

ESTADOS_ENTREGA: tuple[str, ...] = ("PENDIENTE", "ENTREGADA", "NO ENTREGADA", "CON NOVEDAD")

PERMISOS = {
    "RF-01": {"Secretaria"},
    "RF-02": {"Secretaria"},
    "RF-03": {"Gerencia"},
    "RF-04": {"Secretaria"},
    "RF-05": {"Secretaria"},
    "RF-06": {"Secretaria", "Gerencia"},
    "RF-07": {"Gerencia"},
    "RF-08": {"Secretaria", "Gerencia"},
    "RF-09": {"Secretaria"},
}

TIPOS_NOVEDAD = ("INGRESO", "RETIRO", "CAMBIO")
PRODUCTOS = {"TIE": "El Tiempo", "PT": "Portafolio"}


@dataclass(frozen=True)
class Usuario:
    id: int
    nombre: str
    rol: str
    activo: bool = True

    def puede(self, requisito: str) -> bool:
        return self.rol in PERMISOS.get(requisito, set())


@dataclass(frozen=True)
class Sesion:
    usuario: Usuario

    @property
    def usuario_id(self) -> int:
        return self.usuario.id

    @property
    def nombre(self) -> str:
        return self.usuario.nombre

    @property
    def rol(self) -> str:
        return self.usuario.rol

    def puede(self, requisito: str) -> bool:
        return self.usuario.puede(requisito)


@dataclass
class Suscriptor:
    id: int
    nombre: str
    direccion: str
    novedades: str
    ruta_id: int
    zona: str = ""
    distribuidor: str = ""
    archivo_id: int | None = None
    direccion_fs: str = ""  # dirección de fin de semana (RN-07: un solo suscriptor)
    productos: str = "TIE"  # "TIE", "PT" o "TIE,PT"
    periodicidad: str = "1111111"  # máscara lunes..domingo (ver dominio/periodicidad.py)
    estado: str = "ACTIVO"  # ACTIVO o RETIRADO (RN-12)
    fecha_ingreso: str | None = None
    fecha_retiro: str | None = None
    ruta_fs_id: int | None = None  # ruta del fin de semana si es otra
    zona_fs: str = ""
    numero: int | None = None

    @property
    def activo(self) -> bool:
        return self.estado == "ACTIVO"


@dataclass
class Distribuidor:
    id: int
    nombre: str
    telefono: str
    activo: bool = True
    rutas: int = 0


@dataclass
class Ruta:
    id: int
    zona: str
    distribuidor_id: int | None = None
    distribuidor: str = ""
    suscriptores: int = 0


@dataclass
class Entrega:
    id: int | None
    fecha: str
    suscriptor_id: int
    estado: str
    novedad: str = ""
    suscriptor: str = ""
    direccion: str = ""
    zona: str = ""
    distribuidor: str = ""
    registrado_por: int | None = None


@dataclass
class ArchivoImportacion:
    id: int
    nombre_archivo: str
    fecha_carga: str
    total_leidos: int
    total_importados: int
    total_actualizados: int
    total_rechazados: int
    usuario: str = ""


@dataclass
class Rechazo:
    fila: int
    motivo: str
    hoja: str = ""


@dataclass
class NovedadSuscripcion:
    id: int
    fecha: str
    tipo: str
    detalle: str
    suscriptor_id: int
    suscriptor: str = ""
    zona: str = ""
    usuario: str = ""


@dataclass
class ResumenImportacion:
    archivo: str
    leidos: int
    importados: int
    actualizados: int
    rechazados: int
    rutas_creadas: int = 0
    rechazos: list[Rechazo] = field(default_factory=list)
    truncado: bool = False
    revisar: list[Rechazo] = field(default_factory=list)  # casos para revisar con la Gerencia
    hojas: int = 0

    @property
    def cuadra(self) -> bool:
        """RN-06: leídos = importados + actualizados + rechazados."""
        return self.leidos == self.importados + self.actualizados + self.rechazados


@dataclass
class FilaReporte:
    clave: str
    total: int
    efectivas: int
    no_entregadas: int
    novedades: int
    pendientes: int

    @property
    def porcentaje(self) -> float | None:
        return round(self.efectivas / self.total * 100, 1) if self.total else None


@dataclass
class ReporteDiario:
    fecha: str
    total: int
    efectivas: int
    no_entregadas: int = 0
    novedades: int = 0
    pendientes: int = 0
    por_ruta: list[FilaReporte] = field(default_factory=list)
    por_distribuidor: list[FilaReporte] = field(default_factory=list)
    novedades_entrega: list[Entrega] = field(default_factory=list)
    novedades_suscripcion: list[NovedadSuscripcion] = field(default_factory=list)

    @property
    def porcentaje(self) -> float | None:
        """RN-05: efectividad = entregas efectivas / entregas programadas * 100."""
        return round(self.efectivas / self.total * 100, 1) if self.total else None

    @property
    def sin_datos(self) -> bool:
        return self.total == 0


@dataclass
class Respaldo:
    id: int
    fecha: str
    ruta_archivo: str
    usuario: str = ""
    tipo: str = "MANUAL"  # DIARIO (automático), MANUAL o DRIVE (copia externa)
