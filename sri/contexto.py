"""Composición de dependencias: única raíz de creación de DAO y servicios."""

from __future__ import annotations

from pathlib import Path

from .config import cargar_config, ruta_base_datos, ruta_clave
from .datos.base_datos import BaseDatos
from .datos.daos import (
    ArchivoDAO,
    DistribuidorDAO,
    EntregaDAO,
    EventoDAO,
    NovedadSuscripcionDAO,
    ReporteDAO,
    RespaldoDAO,
    RutaDAO,
    SuscriptorDAO,
    UsuarioDAO,
)
from .seguridad import Cifrador
from .servicios.auditoria import AuditoriaServicio
from .servicios.autenticacion import AutenticacionServicio
from .servicios.consultas import ConsultasServicio
from .servicios.importacion import ImportacionServicio
from .servicios.operativo import OperativoServicio
from .servicios.respaldos import RespaldoServicio
from .servicios.suscripciones import SuscripcionServicio


class Contexto:
    def __init__(
        self,
        config: dict | None = None,
        db_path: str | Path | None = None,
        key_path: str | Path | None = None,
        crear_usuarios: bool = True,
    ):
        self.config = config or cargar_config()
        self.bd = BaseDatos(db_path or ruta_base_datos(self.config))
        self.cifrador = Cifrador(Path(key_path) if key_path else ruta_clave(self.config))

        self.usuarios = UsuarioDAO(self.bd)
        self.distribuidores = DistribuidorDAO(self.bd)
        self.rutas = RutaDAO(self.bd)
        self.suscriptores = SuscriptorDAO(self.bd, self.cifrador)
        self.entregas = EntregaDAO(self.bd, self.cifrador)
        self.archivos = ArchivoDAO(self.bd)
        self.reportes = ReporteDAO(self.bd)
        self.respaldos_dao = RespaldoDAO(self.bd)
        self.eventos = EventoDAO(self.bd)
        self.novedades = NovedadSuscripcionDAO(self.bd, self.cifrador)
        self.suscriptores.completar_indices_nombre()  # bases migradas desde la versión anterior

        self.auditoria = AuditoriaServicio(self.eventos)
        self.auth = AutenticacionServicio(self.usuarios, self.auditoria)
        self.importacion = ImportacionServicio(
            self.bd,
            self.config,
            self.archivos,
            self.rutas,
            self.suscriptores,
            self.cifrador,
            self.auth,
            self.auditoria,
            self.distribuidores,
        )
        self.suscripciones = SuscripcionServicio(
            self.bd,
            self.suscriptores,
            self.rutas,
            self.novedades,
            self.cifrador,
            self.auth,
            self.auditoria,
        )
        self.operativo = OperativoServicio(
            self.distribuidores,
            self.rutas,
            self.suscriptores,
            self.entregas,
            self.auth,
            self.auditoria,
        )
        self.consultas = ConsultasServicio(
            self.suscriptores,
            self.entregas,
            self.rutas,
            self.distribuidores,
            self.reportes,
            self.archivos,
            self.auth,
            self.novedades,
        )
        self.respaldos = RespaldoServicio(
            self.bd,
            self.respaldos_dao,
            self.auth,
            self.auditoria,
            self.cifrador,
            self.config,
            self.eventos,
        )
        self.operativo.respaldo_diario = self.respaldos.respaldo_automatico
        self.respaldos.al_restaurar = self._tras_restaurar

        if crear_usuarios:
            self.auth.asegurar_usuarios_iniciales()

    def _tras_restaurar(self) -> None:
        self.bd.preparar()
        self.suscriptores.completar_indices_nombre()

    def cerrar(self) -> None:
        self.bd.cerrar()
