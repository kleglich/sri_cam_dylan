"""Registro de eventos: bitácora sin datos personales (sección 5.3.2)."""

from __future__ import annotations

import sqlite3

from ..datos.daos import EventoDAO


class AuditoriaServicio:
    def __init__(self, dao: EventoDAO):
        self.dao = dao

    def registrar(self, tipo: str, detalle: str, usuario_id: int | None = None) -> None:
        try:
            self.dao.crear(tipo, detalle, usuario_id)
        except sqlite3.Error:
            # La bitácora nunca debe impedir la operación principal.
            pass

    def listar(self, limite: int = 50) -> list[dict]:
        return self.dao.listar(limite)
