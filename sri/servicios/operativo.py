"""Servicio operativo: distribuidores, rutas y entregas (RF-02, RF-04, RF-05, RN-11)."""

from __future__ import annotations

import html
import sqlite3
from datetime import date
from pathlib import Path
from typing import Callable

from ..datos.daos import DistribuidorDAO, EntregaDAO, RutaDAO, SuscriptorDAO
from ..dominio.modelos import ESTADOS_ENTREGA, Distribuidor, Entrega, Ruta, Sesion
from ..dominio.periodicidad import etiqueta
from ..util import (
    Conflicto,
    DatosInvalidos,
    formato_fecha,
    limpiar_texto,
    parsear_fecha,
    validar_telefono,
)
from .auditoria import AuditoriaServicio
from .autenticacion import AutenticacionServicio


class OperativoServicio:
    def __init__(
        self,
        distribuidores: DistribuidorDAO,
        rutas: RutaDAO,
        suscriptores: SuscriptorDAO,
        entregas: EntregaDAO,
        auth: AutenticacionServicio,
        auditoria: AuditoriaServicio,
    ):
        self.distribuidores = distribuidores
        self.rutas = rutas
        self.suscriptores = suscriptores
        self.entregas = entregas
        self.auth = auth
        self.auditoria = auditoria
        # Lo conecta el Contexto: respaldo automático al cerrar el día (RF-07).
        self.respaldo_diario: Callable[[int], Path | None] | None = None

    # ------------------------------------------------------------------ #
    # Distribuidores (RF-04)
    # ------------------------------------------------------------------ #
    def listar_distribuidores(self, sesion: Sesion, incluir_inactivos: bool = True) -> list[Distribuidor]:
        self._exigir_alguna(sesion, "RF-02", "RF-04", "RF-06")
        return self.distribuidores.listar(incluir_inactivos)

    def crear_distribuidor(self, sesion: Sesion, nombre: str, telefono: str) -> int:
        self.auth.exigir(sesion, "RF-04")
        nombre = self._validar_nombre_distribuidor(nombre)
        telefono = validar_telefono(telefono)
        if self.distribuidores.existe_nombre(nombre):
            raise Conflicto("Ya existe un distribuidor con ese nombre.")
        nuevo = self.distribuidores.crear(nombre, telefono)
        self.auditoria.registrar("DISTRIBUIDOR", f"Distribuidor creado: {nombre}", sesion.usuario_id)
        return nuevo

    def actualizar_distribuidor(
        self, sesion: Sesion, distribuidor_id: int, nombre: str, telefono: str
    ) -> None:
        self.auth.exigir(sesion, "RF-04")
        if not self.distribuidores.obtener(distribuidor_id):
            raise DatosInvalidos("El distribuidor seleccionado no existe.")
        nombre = self._validar_nombre_distribuidor(nombre)
        telefono = validar_telefono(telefono)
        if self.distribuidores.existe_nombre(nombre, excluir_id=distribuidor_id):
            raise Conflicto("Ya existe otro distribuidor con ese nombre.")
        self.distribuidores.actualizar(distribuidor_id, nombre, telefono)
        self.auditoria.registrar("DISTRIBUIDOR", f"Distribuidor actualizado: {nombre}", sesion.usuario_id)

    def cambiar_estado_distribuidor(self, sesion: Sesion, distribuidor_id: int, activo: bool) -> None:
        self.auth.exigir(sesion, "RF-04")
        distribuidor = self.distribuidores.obtener(distribuidor_id)
        if not distribuidor:
            raise DatosInvalidos("El distribuidor seleccionado no existe.")
        if not activo and self.rutas.contar_por_distribuidor(distribuidor_id) > 0:
            # RN-02
            raise Conflicto(
                "El distribuidor tiene rutas asignadas. Reasigne esas rutas antes de darlo de baja."
            )
        self.distribuidores.cambiar_activo(distribuidor_id, activo)
        accion = "reactivado" if activo else "dado de baja"
        self.auditoria.registrar("DISTRIBUIDOR", f"Distribuidor {accion}: {distribuidor.nombre}", sesion.usuario_id)

    # ------------------------------------------------------------------ #
    # Rutas (RF-02, RN-01)
    # ------------------------------------------------------------------ #
    def listar_rutas(self, sesion: Sesion) -> list[Ruta]:
        self._exigir_alguna(sesion, "RF-02", "RF-04", "RF-06")
        return self.rutas.listar()

    def crear_ruta(self, sesion: Sesion, zona: str, distribuidor_id: int | None = None) -> int:
        self.auth.exigir(sesion, "RF-02")
        zona = self._validar_zona(zona)
        self._validar_distribuidor_asignable(distribuidor_id)
        if self.rutas.buscar_por_zona(zona):
            raise Conflicto("Ya existe una ruta con esa zona.")
        try:
            nueva = self.rutas.crear(zona, distribuidor_id)
        except sqlite3.IntegrityError as error:
            raise Conflicto("Ya existe una ruta con esa zona.") from error
        self.auditoria.registrar("RUTA", f"Ruta creada: {zona}", sesion.usuario_id)
        return nueva

    def actualizar_ruta(
        self, sesion: Sesion, ruta_id: int, zona: str, distribuidor_id: int | None
    ) -> None:
        self.auth.exigir(sesion, "RF-02")
        ruta = self.rutas.obtener(ruta_id)
        if not ruta:
            raise DatosInvalidos("La ruta seleccionada no existe.")
        zona = self._validar_zona(zona)
        self._validar_distribuidor_asignable(distribuidor_id)
        otra = self.rutas.buscar_por_zona(zona)
        if otra and otra.id != ruta_id:
            raise Conflicto("Ya existe otra ruta con esa zona.")
        try:
            self.rutas.actualizar(ruta_id, zona, distribuidor_id)
        except sqlite3.IntegrityError as error:
            raise Conflicto("Ya existe otra ruta con esa zona.") from error
        self.auditoria.registrar("RUTA", f"Ruta actualizada: {zona}", sesion.usuario_id)

    def asignar_ruta(self, sesion: Sesion, ruta_id: int, distribuidor_id: int | None) -> None:
        self.auth.exigir(sesion, "RF-02")
        ruta = self.rutas.obtener(ruta_id)
        if not ruta:
            raise DatosInvalidos("La ruta seleccionada no existe.")
        self._validar_distribuidor_asignable(distribuidor_id)
        # RN-01: cada ruta tiene un único distribuidor a la vez.
        self.rutas.asignar(ruta_id, distribuidor_id)
        detalle = f"Ruta {ruta.zona} reasignada" if distribuidor_id else f"Ruta {ruta.zona} sin asignar"
        self.auditoria.registrar("RUTA", detalle, sesion.usuario_id)

    # ------------------------------------------------------------------ #
    # Entregas (RF-05, RN-03, RN-04)
    # ------------------------------------------------------------------ #
    def registrar_entrega(
        self,
        sesion: Sesion,
        suscriptor_id: int,
        fecha: str,
        estado: str,
        novedad: str = "",
    ) -> Entrega:
        self.auth.exigir(sesion, "RF-05")
        fecha_dt = parsear_fecha(fecha)
        if fecha_dt > date.today():
            raise DatosInvalidos("La fecha es posterior a hoy. Elija hoy o un día anterior.")
        estado = (estado or "").strip().upper()
        if estado not in ESTADOS_ENTREGA:
            raise DatosInvalidos(
                "Estado no válido. Use: " + ", ".join(ESTADOS_ENTREGA) + "."
            )
        suscriptor = self.suscriptores.obtener(suscriptor_id)
        if not suscriptor:
            raise DatosInvalidos("El suscriptor seleccionado no existe.")
        if suscriptor.fecha_retiro and fecha_dt.isoformat() >= suscriptor.fecha_retiro:
            raise DatosInvalidos(
                "Ese suscriptor ya estaba retirado en esa fecha. Revise la fecha o busque al suscriptor correcto."
            )
        novedad = limpiar_texto(novedad)
        if estado == "CON NOVEDAD" and not novedad:
            raise DatosInvalidos(
                "Escriba qué pasó (o elija un motivo rápido) y vuelva a pulsar «Entregado con novedad»."
            )
        if estado != "CON NOVEDAD":
            novedad = ""

        self.entregas.guardar(fecha_dt.isoformat(), suscriptor_id, estado, novedad, sesion.usuario_id)
        if estado == "CON NOVEDAD":
            self.suscriptores.actualizar_novedades(suscriptor_id, novedad)
        return self.entregas.obtener(fecha_dt.isoformat(), suscriptor_id)  # type: ignore[return-value]

    def pendientes_del_dia(self, sesion: Sesion, fecha: str) -> int:
        """Entregas programadas que el cierre del día marcaría como ENTREGADA."""
        self.auth.exigir(sesion, "RF-05")
        return self.entregas.contar_por_estado(parsear_fecha(fecha).isoformat()).get("PENDIENTE", 0)

    def cerrar_dia(self, sesion: Sesion, fecha: str) -> dict:
        """RF-05 / RN-11: los distribuidores solo reportan novedades; al cerrar el día
        las entregas programadas que siguen pendientes se dan por cumplidas y se
        genera el respaldo diario automático (RF-07)."""
        self.auth.exigir(sesion, "RF-05")
        fecha_dt = parsear_fecha(fecha)
        if fecha_dt > date.today():
            raise DatosInvalidos("Todavía no se puede cerrar ese día. Elija hoy o un día anterior.")
        marcadas = self.entregas.marcar_entregadas(fecha_dt.isoformat(), sesion.usuario_id)
        self.auditoria.registrar(
            "CIERRE_DIA", f"Día {formato_fecha(fecha_dt)} cerrado: {marcadas} entregas dadas por cumplidas",
            sesion.usuario_id,
        )
        respaldo = self.respaldo_diario(sesion.usuario_id) if self.respaldo_diario else None
        return {"marcadas": marcadas, "respaldo": respaldo}

    # ------------------------------------------------------------------ #
    # Ruta imprimible (RF-02)
    # ------------------------------------------------------------------ #
    def secciones_ruta(self, sesion: Sesion, distribuidor_id: int) -> dict[str, list[tuple]]:
        """Arma la ruta del distribuidor con las secciones de la hoja impresa:
        entregas diarias, sábados y domingos, y Portafolio."""
        self.auth.exigir(sesion, "RF-02")
        rutas = [r for r in self.rutas.listar() if r.distribuidor_id == distribuidor_id]
        ids = {r.id for r in rutas}
        secciones: dict[str, list[tuple]] = {"Entregas diarias": [], "Sábados y domingos": [], "Portafolio": []}
        for s in self.suscriptores.listar_por_rutas(list(ids)):
            entre_semana = "1" in s.periodicidad[:5]
            fin_de_semana = "1" in s.periodicidad[5:]
            ruta_fs = s.ruta_fs_id or s.ruta_id
            if "TIE" in s.productos and entre_semana and s.ruta_id in ids:
                secciones["Entregas diarias"].append((s, s.direccion, s.zona))
            if "TIE" in s.productos and fin_de_semana and ruta_fs in ids and (not entre_semana or s.direccion_fs):
                secciones["Sábados y domingos"].append((s, s.direccion_fs or s.direccion, s.zona_fs or s.zona))
            if "PT" in s.productos and s.ruta_id in ids:
                secciones["Portafolio"].append((s, s.direccion, s.zona))
        return secciones

    def exportar_ruta_html(self, sesion: Sesion, distribuidor_id: int, destino: str | Path) -> Path:
        distribuidor = self.distribuidores.obtener(distribuidor_id) if distribuidor_id else None
        if not distribuidor:
            raise DatosInvalidos("La ruta no tiene un distribuidor asignado.")
        secciones = self.secciones_ruta(sesion, distribuidor_id)
        codigos = sorted({r.zona for r in self.rutas.listar() if r.distribuidor_id == distribuidor_id})
        bloques = []
        for titulo, filas in secciones.items():
            celdas = "".join(
                "<tr>"
                f"<td>{s.numero or ''}</td><td>{html.escape(s.nombre)}</td><td>{html.escape(direccion)}</td>"
                f"<td>{html.escape(etiqueta(s.periodicidad))}</td>"
                f"<td>{'X' if 'TIE' in s.productos else ''}</td><td>{'X' if 'PT' in s.productos else ''}</td>"
                f"<td>{html.escape(zona)}</td><td class='check'>&#9744;</td>"
                "</tr>"
                for s, direccion, zona in filas
            ) or '<tr><td colspan="8">Sin suscriptores en esta sección.</td></tr>'
            bloques.append(
                f"<h2>{html.escape(titulo)} ({len(filas)})</h2><table><thead><tr><th>N°</th><th>Nombre</th>"
                "<th>Dirección</th><th>Periodicidad</th><th>TIE</th><th>PT</th><th>Ruta</th><th>✓</th>"
                f"</tr></thead><tbody>{celdas}</tbody></table>"
            )
        contenido = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>Ruta de {html.escape(distribuidor.nombre)}</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; color: #1c2b36; margin: 28px; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  h2 {{ font-size: 15px; margin-top: 24px; color: #12314a; }}
  .sub {{ color: #5b6b77; margin-top: 0; }}
  .aviso {{ border: 1px solid #e0b252; background: #fff8e6; padding: 8px 12px; font-size: 12px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 6px; }}
  th, td {{ border: 1px solid #d5dee4; padding: 6px 8px; text-align: left; font-size: 12px; }}
  th {{ background: #eef4f7; }}
  .check {{ text-align: center; font-size: 15px; }}
  @media print {{ .no-print {{ display: none; }} body {{ margin: 10mm; }} h2 {{ break-after: avoid; }} }}
</style></head><body>
<button class="no-print" onclick="window.print()">Imprimir</button>
<h1>Ruta de entrega · {html.escape(distribuidor.nombre)}</h1>
<p class="sub">Distribuciones Cam Dylan S.A.S. · Códigos de ruta: {html.escape(", ".join(codigos) or "—")} ·
Generada el {formato_fecha(date.today())} desde el SRI</p>
<p class="aviso">Contiene datos personales de suscriptores (Ley 1581 de 2012): úsela solo para la entrega,
no la comparta y destruya la hoja anterior al recibir esta.</p>
{"".join(bloques)}
</body></html>"""
        ruta = Path(destino)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
        self.auditoria.registrar("RUTA", f"Ruta imprimible generada para {distribuidor.nombre}", sesion.usuario_id)
        return ruta

    # ------------------------------------------------------------------ #
    def _exigir_alguna(self, sesion: Sesion, *requisitos: str) -> None:
        if not any(sesion.puede(r) for r in requisitos):
            from ..util import PermisoDenegado

            raise PermisoDenegado(
                "Esta información no está disponible para su usuario. Ingrese con el usuario que corresponde."
            )

    @staticmethod
    def _validar_nombre_distribuidor(nombre: str) -> str:
        nombre = limpiar_texto(nombre)
        if len(nombre) < 3:
            raise DatosInvalidos("El nombre del distribuidor debe tener al menos 3 caracteres.")
        return nombre

    @staticmethod
    def _validar_zona(zona: str) -> str:
        zona = limpiar_texto(zona)
        if len(zona) < 2:
            raise DatosInvalidos("La zona o ruta debe tener al menos 2 caracteres.")
        return zona

    def _validar_distribuidor_asignable(self, distribuidor_id: int | None) -> None:
        if distribuidor_id in (None, 0):
            return
        distribuidor = self.distribuidores.obtener(distribuidor_id)
        if not distribuidor:
            raise DatosInvalidos("El distribuidor seleccionado no existe.")
        if not distribuidor.activo:
            raise DatosInvalidos("El distribuidor está dado de baja; reactívelo antes de asignarle rutas.")
