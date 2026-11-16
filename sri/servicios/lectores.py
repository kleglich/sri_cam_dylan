"""Lectores del listado de repartidores (patrón Estrategia, sección 6.3.2).

Cada lector devuelve las hojas del archivo como (nombre_hoja, filas), donde
filas es un iterador de (número_de_fila, valores). El listado de la empresa
tiene una hoja por distribuidor; un CSV se trata como una sola hoja.
"""

from __future__ import annotations

import csv
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator

from ..util import DatosInvalidos, normalizar

Hoja = tuple[str, Iterator[tuple[int, list]]]


class FormatoNoSoportado(DatosInvalidos):
    pass


class LectorArchivo(ABC):
    @abstractmethod
    def leer(self, ruta: Path) -> Iterator[Hoja]:
        raise NotImplementedError


class LectorXlsx(LectorArchivo):
    def leer(self, ruta: Path) -> Iterator[Hoja]:
        try:
            from openpyxl import load_workbook
        except ImportError as error:  # pragma: no cover
            raise FormatoNoSoportado(
                "Falta la dependencia openpyxl. Ejecute: pip install -r requirements.txt"
            ) from error

        libro = load_workbook(filename=str(ruta), read_only=True, data_only=True)
        try:
            for hoja in libro.worksheets:
                filas = ((n, list(f)) for n, f in enumerate(hoja.iter_rows(values_only=True), start=1))
                yield hoja.title, filas
        finally:
            libro.close()


class LectorXls(LectorArchivo):
    def leer(self, ruta: Path) -> Iterator[Hoja]:
        try:
            import xlrd
        except ImportError as error:  # pragma: no cover
            raise FormatoNoSoportado(
                "El formato .xls requiere la dependencia xlrd. Ejecute: pip install -r requirements.txt"
            ) from error

        libro = xlrd.open_workbook(str(ruta))
        for hoja in libro.sheets():
            yield hoja.name, ((n + 1, hoja.row_values(n)) for n in range(hoja.nrows))


class LectorCsv(LectorArchivo):
    def leer(self, ruta: Path) -> Iterator[Hoja]:
        contenido = None
        for codificacion in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                contenido = ruta.read_text(encoding=codificacion)
                break
            except UnicodeDecodeError:
                continue
        if contenido is None:
            raise DatosInvalidos("No se pudo leer el archivo CSV por problemas de codificación.")

        muestra = contenido[:4096]
        delimitador = ","
        try:
            delimitador = csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
        except csv.Error:
            if muestra.count(";") > muestra.count(","):
                delimitador = ";"
        lector = csv.reader(contenido.splitlines(), delimiter=delimitador)
        yield ruta.stem, ((n, list(f)) for n, f in enumerate(lector, start=1))


def crear_lector(ruta: str | Path, formatos_admitidos: list[str] | None = None) -> LectorArchivo:
    ruta = Path(ruta)
    formatos = {f.lower() for f in (formatos_admitidos or [".xlsx", ".xls"])}
    extension = ruta.suffix.lower()
    if extension not in formatos:
        raise FormatoNoSoportado(
            f"Formato '{extension}' no admitido. Use: {', '.join(sorted(formatos))}."
        )
    if extension == ".xlsx":
        return LectorXlsx()
    if extension == ".xls":
        return LectorXls()
    return LectorCsv()


def _canonica(texto: str) -> str:
    """Normaliza un encabezado ignorando tildes, espacios y puntuación."""
    return re.sub(r"[^A-Z0-9]", "", normalizar(texto))


def mapear_columnas(encabezados: list[str], mapeo: dict[str, list[str]]) -> dict[str, int]:
    """Relaciona cada campo lógico con el índice de la columna del archivo.

    El mapeo es configurable (config.json), de modo que un cambio de formato
    del listado no exige reprogramar (AD-06).
    """
    normalizados = [_canonica(encabezado) for encabezado in encabezados]
    resultado: dict[str, int] = {}
    for campo, sinonimos in mapeo.items():
        for sinonimo in sinonimos:
            buscado = _canonica(sinonimo)
            if buscado and buscado in normalizados:
                resultado[campo] = normalizados.index(buscado)
                break
    return resultado
