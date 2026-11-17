"""Configuración externa del SRI (parámetros fuera del código).

La ruta de los datos puede cambiarse con la variable de entorno SRI_DATA_DIR,
lo que permite ejecutar pruebas y demostraciones aisladas.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

RUTA_RAIZ = Path(__file__).resolve().parent.parent
RUTA_CONFIG = Path(os.environ.get("SRI_CONFIG", RUTA_RAIZ / "config.json"))

CONFIG_DEFECTO = {
    "aplicacion": "SRI · Distribuciones Cam Dylan S.A.S.",
    "version": "2.0.0",
    "formatos_admitidos": [
        ".xlsx",
        ".xls",
        ".csv"
    ],
    "mapeo_columnas": {
        "numero": [
            "n°",
            "nº",
            "no",
            "n",
            "numero",
            "número",
            "num",
            "item"
        ],
        "nombre": [
            "nombre",
            "nombres",
            "nombre suscriptor",
            "nombre completo",
            "suscriptor",
            "cliente"
        ],
        "direccion": [
            "direccion",
            "dirección",
            "dir",
            "domicilio",
            "direccion entrega"
        ],
        "direccion_fs": [
            "direccion fin de semana",
            "dirección fin de semana",
            "dir fin de semana",
            "direccion fds"
        ],
        "tie": [
            "tie",
            "el tiempo",
            "tiempo"
        ],
        "pt": [
            "pt",
            "portafolio"
        ],
        "ruta": [
            "ruta",
            "codigo ruta",
            "código de ruta",
            "codigo de ruta",
            "cod ruta",
            "codigo",
            "código",
            "zona"
        ],
        "novedades": [
            "novedades",
            "novedad",
            "observaciones",
            "observacion",
            "notas"
        ]
    },
    "importacion": {
        "maximo_rechazos_detallados": 500
    },
    "respaldo": {
        "carpeta_por_defecto": "respaldos",
        "conservar_diarios": 7,
        "carpeta_google_drive": "",
        "dias_copia_drive": 7
    }
}


def _combinar(base: dict, encima: dict) -> dict:
    resultado = dict(base)
    for clave, valor in encima.items():
        if isinstance(valor, dict) and isinstance(resultado.get(clave), dict):
            resultado[clave] = _combinar(resultado[clave], valor)
        else:
            resultado[clave] = valor
    return resultado


def cargar_config() -> dict:
    """Carga config.json y completa las claves que falten con los valores por defecto."""
    if RUTA_CONFIG.exists():
        try:
            with RUTA_CONFIG.open("r", encoding="utf-8") as archivo:
                return _combinar(CONFIG_DEFECTO, json.load(archivo))
        except (json.JSONDecodeError, OSError) as error:
            raise RuntimeError(f"No se pudo leer {RUTA_CONFIG}: {error}") from error
    return dict(CONFIG_DEFECTO)


def guardar_config(config: dict) -> None:
    """Guarda la configuración (por ejemplo, la carpeta de Google Drive elegida)."""
    RUTA_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def directorio_datos(config: dict | None = None) -> Path:
    ruta = Path(os.environ.get("SRI_DATA_DIR", RUTA_RAIZ / "datos"))
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def ruta_base_datos(config: dict | None = None) -> Path:
    return directorio_datos(config) / "sri_cam_dylan.db"


def ruta_clave(config: dict | None = None) -> Path:
    return directorio_datos(config) / "sri.key"


def directorio_respaldos(config: dict | None = None) -> Path:
    nombre = (config or {}).get("respaldo", {}).get("carpeta_por_defecto", "respaldos")
    ruta = Path(os.environ.get("SRI_BACKUP_DIR", RUTA_RAIZ / nombre))
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def directorio_exportes() -> Path:
    ruta = Path(os.environ.get("SRI_EXPORT_DIR", RUTA_RAIZ / "exportes"))
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
