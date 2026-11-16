"""Capa de datos: conexión SQLite, transacciones y creación del esquema."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from ..config import ruta_base_datos


class BaseDatos:
    """Única conexión de la aplicación (estación principal, sección 5.3.3)."""

    def __init__(self, ruta: str | Path | None = None):
        self.ruta = Path(ruta) if ruta else ruta_base_datos()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.conexion = sqlite3.connect(
            str(self.ruta), timeout=15, check_same_thread=False, isolation_level=None
        )
        self.conexion.row_factory = sqlite3.Row
        self._configurar()
        self._crear_esquema()

    def _configurar(self) -> None:
        cur = self.conexion.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("PRAGMA journal_mode = WAL")
        cur.execute("PRAGMA synchronous = NORMAL")
        cur.execute("PRAGMA busy_timeout = 15000")
        cur.close()

    def _crear_esquema(self) -> None:
        self._migrar()
        esquema = Path(__file__).with_name("esquema.sql").read_text(encoding="utf-8")
        self.conexion.executescript(esquema)
        self.conexion.commit()

    # Columnas agregadas en el informe v5.3; se añaden a bases (o respaldos) anteriores.
    COLUMNAS_NUEVAS = {
        "suscriptor": (
            ("direccion_fs_cifrada", "TEXT NOT NULL DEFAULT ''"),
            ("productos", "TEXT NOT NULL DEFAULT 'TIE'"),
            ("periodicidad", "TEXT NOT NULL DEFAULT '1111111'"),
            ("estado", "TEXT NOT NULL DEFAULT 'ACTIVO'"),
            ("fecha_ingreso", "TEXT"),
            ("fecha_retiro", "TEXT"),
            ("indice_nombre", "TEXT NOT NULL DEFAULT ''"),
            ("numero", "INTEGER"),
            ("ruta_fs_id", "INTEGER REFERENCES ruta (id)"),
        ),
        "respaldo": (("tipo", "TEXT NOT NULL DEFAULT 'MANUAL'"),),
    }

    def _migrar(self) -> None:
        for tabla, columnas in self.COLUMNAS_NUEVAS.items():
            existentes = {fila[1] for fila in self.conexion.execute(f"PRAGMA table_info({tabla})")}
            if not existentes:  # tabla nueva: la crea esquema.sql
                continue
            for nombre, definicion in columnas:
                if nombre not in existentes:
                    self.conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")

    def preparar(self) -> None:
        """Vuelve a aplicar esquema y migración (por ejemplo, tras restaurar un respaldo antiguo)."""
        self._crear_esquema()

    def ejecutar(self, sql: str, parametros: tuple | dict = ()) -> sqlite3.Cursor:
        return self.conexion.execute(sql, parametros)

    def uno(self, sql: str, parametros: tuple | dict = ()) -> sqlite3.Row | None:
        return self.conexion.execute(sql, parametros).fetchone()

    def todos(self, sql: str, parametros: tuple | dict = ()) -> list[sqlite3.Row]:
        return self.conexion.execute(sql, parametros).fetchall()

    @contextmanager
    def transaccion(self):
        """Todo o nada (RN-06). La importación completa ocurre aquí."""
        if self.conexion.in_transaction:
            raise RuntimeError("Ya existe una transacción activa en la conexión.")
        self.conexion.execute("BEGIN IMMEDIATE")
        try:
            yield self
        except Exception:
            self.conexion.rollback()
            raise
        else:
            self.conexion.commit()

    def respaldar_a(self, destino: sqlite3.Connection) -> None:
        """Copia consistente de la base con la API de respaldo de SQLite."""
        self.conexion.backup(destino)

    def restaurar_desde(self, origen: sqlite3.Connection) -> None:
        origen.backup(self.conexion)

    def verificar_integridad(self) -> bool:
        fila = self.uno("PRAGMA integrity_check")
        return bool(fila and fila[0] == "ok")

    def cerrar(self) -> None:
        try:
            self.conexion.close()
        except sqlite3.Error:
            pass
