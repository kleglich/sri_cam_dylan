"""Genera el listado de repartidores de ejemplo (formato del Anexo D del informe v5.3).

Una hoja por distribuidor con las columnas N°, NOMBRE, DIRECCION, TIE, PT y RUTA;
la periodicidad va escrita junto al nombre. Incluye a propósito los casos que
encontró la revisión del listado real: hoja repetida, código de ruta de un
distribuidor que ya no trabaja (AL), suscriptor con dirección de oficina entre
semana y de casa el fin de semana, filas incompletas y una periodicidad rara.

Uso:
    python herramientas/generar_datos_demo.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

NOMBRES = (
    "Ana", "Luis", "Marta", "Carlos", "Diana", "Jorge", "Sandra", "Pedro",
    "Claudia", "Andrés", "Paula", "Javier", "Rosa", "Diego", "Liliana", "Óscar",
    "Camila", "Fernando", "Gloria", "Ricardo", "Natalia", "Miguel", "Teresa", "Julián",
)
APELLIDOS = (
    "Pérez", "Gómez", "Ruiz", "Mora", "Salazar", "Ramírez", "Torres", "Vargas",
    "Rojas", "Cárdenas", "Becerra", "Suárez", "Peña", "Ortiz", "Navarro", "Castillo",
)
# (nombre, teléfono, nombre de la hoja, código de ruta)
DISTRIBUIDORES = (
    ("Carlos Pérez", "300 412 8890", "CARLOS", "CP"),
    ("Pedro Gómez", "311 528 4471", "PEDRO", "PG"),
    ("Marta Salazar", "320 774 1120", "MARTA", "MS"),
    ("Luis Ramírez", "315 690 3388", "LUIS", "LR"),
)
PERIODICIDADES = ("", "", "", "", "", " D", " S-D", " L-V", " L-S", " miércoles, sábado y domingo")
ENCABEZADO = ["N°", "NOMBRE", "DIRECCION", "TIE", "PT", "RUTA"]
POR_HOJA = 18


def _hojas() -> dict[str, list[list]]:
    hojas: dict[str, list[list]] = {}
    indice = 0
    for _nombre, _tel, hoja, codigo in DISTRIBUIDORES:
        filas = []
        for numero in range(1, POR_HOJA + 1):
            nombre = f"{NOMBRES[indice % len(NOMBRES)]} {APELLIDOS[indice % len(APELLIDOS)]} {APELLIDOS[(indice // 4) % len(APELLIDOS)]}"  # únicos
            nombre += PERIODICIDADES[indice % len(PERIODICIDADES)]
            direccion = f"Calle {10 + indice} # {2 + indice % 25}-{10 + indice % 40}"
            tie = "X" if indice % 6 else ""
            pt = "X" if indice % 6 == 0 or indice % 9 == 0 else ""
            filas.append([numero, nombre, direccion, tie, pt, codigo])
            indice += 1
        hojas[hoja] = filas

    # Suscriptor que recibe en la oficina entre semana y en la casa el fin de semana.
    hojas["CARLOS"].append([POR_HOJA + 1, "Germán Pabón L-V", "Oficina Avenida 0 # 11-20", "X", "", "CP"])
    hojas["LUIS"].append([POR_HOJA + 1, "Germán Pabón S-D", "Casa Calle 31 # 2-05", "X", "", "LR"])
    # Código de ruta de un distribuidor que ya no trabaja en la empresa.
    hojas["MARTA"] += [
        [POR_HOJA + 1, "Beatriz Contreras", "Avenida 7 # 12-44", "X", "", "AL"],
        [POR_HOJA + 2, "Héctor Villamizar D", "Calle 22 # 3-18", "X", "", "AL"],
    ]
    # Filas que deben rechazarse o revisarse.
    hojas["PEDRO"] += [
        [POR_HOJA + 1, "Suscriptor sin dirección", "", "X", "", "PG"],
        [POR_HOJA + 2, "Suscriptor sin producto", "Carrera 15 # 8-90", "", "", "PG"],
        [POR_HOJA + 3, "Mónica Cáceres (quincenal)", "Carrera 16 # 8-91", "X", "", "PG"],
    ]
    # Dos hojas casi iguales para un mismo distribuidor: la vigente es la segunda.
    copia = [list(f) for f in hojas["CARLOS"][:5]]
    copia[0][4] = "X"  # en la hoja vigente el primer suscriptor también recibe Portafolio
    hojas["CARLOS (2)"] = copia
    return hojas


def _guardar(ruta: Path, hojas: dict[str, list[list]]) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    libro = Workbook()
    libro.remove(libro.active)
    for titulo, filas in hojas.items():
        hoja = libro.create_sheet(titulo)
        hoja.append(ENCABEZADO)
        for fila in filas:
            hoja.append(fila)
        hoja.column_dimensions["B"].width = 42
        hoja.column_dimensions["C"].width = 30
    libro.save(ruta)
    return ruta


def generar_archivos(destino: str | Path | None = None) -> dict[str, Path]:
    """Crea el listado base y una versión actualizada para la demostración en vivo."""
    destino = Path(destino) if destino else Path(__file__).resolve().parent.parent / "datos_ejemplo"
    hojas = _hojas()
    base = _guardar(destino / "listado_repartidores.xlsx", hojas)

    actualizado = {titulo: [list(f) for f in filas] for titulo, filas in hojas.items()}
    actualizado["PEDRO"].append([POR_HOJA + 4, "Lucía Mogollón L-S", "Carrera 9 # 14-28", "X", "X", "PG"])
    actualizado["MARTA"].append([POR_HOJA + 3, "Édgar Contreras", "Calle 18 # 7-61", "X", "", "MS"])
    nueva = _guardar(destino / "listado_repartidores_actualizado.xlsx", actualizado)
    return {"base": base, "nueva": nueva}


if __name__ == "__main__":
    for nombre, ruta in generar_archivos().items():
        print(f"{nombre:8} -> {ruta}")
