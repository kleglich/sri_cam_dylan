"""Utilidades comunes: fechas, normalización de texto y validaciones."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime


class ErrorNegocio(Exception):
    """Error controlado que se muestra al usuario con un mensaje claro."""


class DatosInvalidos(ErrorNegocio):
    """Una entrada no cumple las reglas de negocio o el formato esperado."""


class PermisoDenegado(ErrorNegocio):
    """El rol del usuario no tiene permitida la operación."""


class Conflicto(ErrorNegocio):
    """La operación choca con una regla de negocio (duplicados, dependencias)."""


def normalizar(texto: object) -> str:
    """Devuelve el texto en mayúsculas, sin acentos y con espacios simples.

    Se usa para comparar zonas, nombres y direcciones sin depender de tildes,
    mayúsculas o espacios repetidos.
    """
    if texto is None:
        return ""
    cadena = str(texto).strip()
    if not cadena:
        return ""
    cadena = unicodedata.normalize("NFKD", cadena)
    cadena = "".join(c for c in cadena if not unicodedata.combining(c))
    cadena = re.sub(r"\s+", " ", cadena)
    return cadena.upper()


def limpiar_texto(texto: object) -> str:
    """Recorta y compacta espacios conservando tildes y mayúsculas."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def parsear_fecha(texto: str) -> date:
    """Convierte una fecha dd/mm/aaaa (o aaaa-mm-dd) a date."""
    cadena = (texto or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(cadena, formato).date()
        except ValueError:
            continue
    raise DatosInvalidos("La fecha debe tener el formato dd/mm/aaaa.")


def formato_fecha(valor: date | datetime | str | None) -> str:
    """Devuelve la fecha en formato dd/mm/aaaa para la interfaz."""
    if valor is None:
        return ""
    if isinstance(valor, str):
        try:
            valor = datetime.strptime(valor[:10], "%Y-%m-%d").date()
        except ValueError:
            return valor
    return valor.strftime("%d/%m/%Y")


def hoy_iso() -> str:
    return date.today().isoformat()


def ahora_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def validar_telefono(telefono: str) -> str:
    """Valida un teléfono numérico con separadores habituales."""
    cadena = limpiar_texto(telefono)
    if not cadena:
        raise DatosInvalidos("El teléfono es obligatorio.")
    if not re.fullmatch(r"[0-9+\-() ]{7,25}", cadena):
        raise DatosInvalidos("El teléfono debe tener un formato numérico válido (mínimo 7 dígitos).")
    if len(re.sub(r"\D", "", cadena)) < 7:
        raise DatosInvalidos("El teléfono debe tener al menos 7 dígitos.")
    return cadena


def validar_usuario(nombre: str) -> str:
    cadena = limpiar_texto(nombre)
    if len(cadena) < 3:
        raise DatosInvalidos("El nombre del usuario debe tener al menos 3 caracteres.")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", cadena):
        raise DatosInvalidos("El usuario solo admite letras, números, punto, guion y guion bajo.")
    return cadena


def nombre_archivo_seguro(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nombre).strip("_") or "archivo"
