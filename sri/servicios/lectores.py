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


def detectar_listas(encabezados: list[str], mapeo: dict[str, list[str]]) -> tuple[list[dict[str, int]], list[str]] | None:
    """Detecta las listas de una fila de encabezados del listado real (Anexo D, Figura 12).

    Cada hoja puede traer varias listas lado a lado; cada una empieza en una
    columna «NOMBRE» y debe tener «DIRECCION». En el archivo de la empresa el
    número, la marca de El Tiempo y el código de ruta no tienen encabezado, así
    que, si no hay uno con nombre, se ubican por posición:
    [N°] NOMBRE DIRECCION [TIE] PT [RUTA].

    Devuelve (listas, campos que faltan) o None si la fila no es de encabezados.
    """
    canon = [_canonica(t) for t in encabezados]
    sinonimos = {campo: {c for c in map(_canonica, lista) if c} for campo, lista in mapeo.items()}
    inicios = [i for i, c in enumerate(canon) if c in sinonimos.get("nombre", set())]
    if not inicios:
        return None
    listas, faltantes, ultima = [], [], -1
    for k, inicio in enumerate(inicios):
        fin = inicios[k + 1] - 2 if k + 1 < len(inicios) else len(canon) - 1  # deja el N° de la lista siguiente
        mapa = {"nombre": inicio}
        for campo, nombres in sinonimos.items():
            if campo != "nombre":
                encontrada = next((j for j in range(max(ultima + 1, inicio - 1), fin + 1) if canon[j] in nombres), None)
                if encontrada is not None:
                    mapa[campo] = encontrada
        if "direccion" not in mapa:
            return None
        direccion = mapa["direccion"]
        for campo, j in (("numero", inicio - 1), ("tie", direccion + 1), ("pt", direccion + 2),
                         ("ruta", mapa.get("pt", direccion + 2) + 1)):
            if campo not in mapa and ultima < j < len(canon) and not canon[j]:
                mapa[campo] = j
        faltantes += [c for c in ("tie", "pt", "ruta") if c not in mapa and c not in faltantes]
        ultima = max(mapa.values())
        listas.append(mapa)
    return listas, faltantes


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
