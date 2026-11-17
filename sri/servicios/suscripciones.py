"""Novedades de suscripción tomadas de los listados impresos (RF-09, RN-07, RN-12)."""

from __future__ import annotations

import re
import sqlite3
from datetime import date

from ..datos.base_datos import BaseDatos
from ..datos.daos import EntregaDAO, NovedadSuscripcionDAO, RutaDAO, SuscriptorDAO
from ..dominio.modelos import NovedadSuscripcion, Sesion, Suscriptor
from ..dominio.periodicidad import parsear
from ..seguridad import Cifrador
from ..util import Conflicto, DatosInvalidos, limpiar_texto, normalizar, parsear_fecha, restar_meses
from .auditoria import AuditoriaServicio
from .autenticacion import AutenticacionServicio

DIRECCION_INCOMPLETA = (
    "La dirección está incompleta (debe incluir al menos un número, por ejemplo «Calle 10 # 5-20»). "
    "Consulte a la editorial antes de registrar la novedad."
)
CAMPOS_CAMBIO = {
    "nombre": "nombre",
    "direccion": "dirección",
    "direccion_fs": "dirección de fin de semana",
    "productos": "productos",
    "periodicidad": "periodicidad",
    "ruta_id": "ruta",
}


class SuscripcionServicio:
    def __init__(
        self,
        bd: BaseDatos,
        suscriptores: SuscriptorDAO,
        rutas: RutaDAO,
        novedades: NovedadSuscripcionDAO,
        cifrador: Cifrador,
        auth: AutenticacionServicio,
        auditoria: AuditoriaServicio,
        entregas: EntregaDAO,
    ):
        self.bd = bd
        self.entregas = entregas
        self.suscriptores = suscriptores
        self.rutas = rutas
        self.novedades = novedades
        self.cifrador = cifrador
        self.auth = auth
        self.auditoria = auditoria

    # ------------------------------------------------------------------ #
    def registrar_ingreso(
        self,
        sesion: Sesion,
        fecha: str,
        nombre: str,
        direccion: str,
        productos: list[str],
        periodicidad: str,
        ruta_id: int | None,
        direccion_fs: str = "",
        detalle: str = "",
    ) -> dict:
        """Registra un ingreso. Devuelve {"id", "aviso"}; el aviso advierte homónimos."""
        self.auth.exigir(sesion, "RF-09")
        fecha_iso = self._fecha(fecha)
        datos = self._validar(nombre, direccion, direccion_fs, productos, periodicidad, ruta_id)
        indice = self.cifrador.indice(normalizar(datos["nombre"]), normalizar(datos["direccion"]))
        indice_nombre = self.cifrador.indice(normalizar(datos["nombre"]))
        existente = self.suscriptores.buscar_por_indice(indice)
        if existente and existente.activo:
            raise Conflicto("Ese suscriptor ya está registrado y activo con la misma dirección.")

        aviso = None
        with self.bd.transaccion():
            if existente:  # reingreso de un suscriptor retirado: se reactiva y conserva su historial
                suscriptor_id = existente.id
                self.suscriptores.actualizar(
                    suscriptor_id, {**datos, "estado": "ACTIVO", "fecha_retiro": None, "fecha_ingreso": fecha_iso}
                )
                texto = "Reingreso"
            else:
                homonimos = self.suscriptores.buscar_por_indice_nombre(indice_nombre)
                if homonimos:
                    aviso = (
                        f"Atención: ya hay {len(homonimos)} suscriptor(es) con el mismo nombre y otra dirección. "
                        "Verifique que no sea el mismo suscriptor."
                    )
                suscriptor_id = self.suscriptores.crear({
                    **datos,
                    "indice_busqueda": indice,
                    "indice_nombre": indice_nombre,
                    "fecha_ingreso": fecha_iso,
                })
                texto = "Ingreso"
            self.novedades.crear(fecha_iso, "INGRESO", self._detalle(texto, detalle), suscriptor_id, sesion.usuario_id)
        self.auditoria.registrar("NOVEDAD_SUSCRIPCION", f"Ingreso de suscriptor #{suscriptor_id}", sesion.usuario_id)
        return {"id": suscriptor_id, "aviso": aviso}

    def registrar_retiro(self, sesion: Sesion, suscriptor_id: int, fecha: str, detalle: str = "") -> None:
        """RN-12: el retiro marca al suscriptor como inactivo; no lo borra."""
        self.auth.exigir(sesion, "RF-09")
        fecha_iso = self._fecha(fecha)
        suscriptor = self._existente(suscriptor_id)
        if not suscriptor.activo:
            raise Conflicto("El suscriptor ya está retirado.")
        with self.bd.transaccion():
            self.suscriptores.actualizar(suscriptor_id, {"estado": "RETIRADO", "fecha_retiro": fecha_iso})
            self.novedades.crear(fecha_iso, "RETIRO", self._detalle("Retiro", detalle), suscriptor_id, sesion.usuario_id)
        self.auditoria.registrar("NOVEDAD_SUSCRIPCION", f"Retiro de suscriptor #{suscriptor_id}", sesion.usuario_id)

    def registrar_cambio(
        self,
        sesion: Sesion,
        suscriptor_id: int,
        fecha: str,
        nombre: str,
        direccion: str,
        productos: list[str],
        periodicidad: str,
        ruta_id: int | None,
        direccion_fs: str = "",
        detalle: str = "",
    ) -> list[str]:
        """Aplica un cambio de datos. Devuelve los nombres de los campos que cambiaron."""
        self.auth.exigir(sesion, "RF-09")
        fecha_iso = self._fecha(fecha)
        actual = self._existente(suscriptor_id)
        if not actual.activo:
            raise Conflicto("El suscriptor está retirado; registre un ingreso para reactivarlo.")
        datos = self._validar(nombre, direccion, direccion_fs, productos, periodicidad, ruta_id)
        anteriores = {
            "nombre": actual.nombre, "direccion": actual.direccion, "direccion_fs": actual.direccion_fs,
            "productos": actual.productos, "periodicidad": actual.periodicidad, "ruta_id": actual.ruta_id,
        }
        cambios = {
            campo: valor for campo, valor in datos.items()
            if (normalizar(valor) if isinstance(valor, str) else valor) != (
                normalizar(anteriores[campo]) if isinstance(anteriores[campo], str) else anteriores[campo]
            )
        }
        if not cambios:
            raise DatosInvalidos("No hay cambios respecto a los datos registrados del suscriptor.")
        if "nombre" in cambios or "direccion" in cambios:
            cambios["indice_busqueda"] = self.cifrador.indice(normalizar(datos["nombre"]), normalizar(datos["direccion"]))
            cambios["indice_nombre"] = self.cifrador.indice(normalizar(datos["nombre"]))
        campos = [CAMPOS_CAMBIO[c] for c in CAMPOS_CAMBIO if c in cambios]
        try:
            with self.bd.transaccion():
                self.suscriptores.actualizar(suscriptor_id, cambios)
                texto = "Cambio de " + ", ".join(campos)
                self.novedades.crear(fecha_iso, "CAMBIO", self._detalle(texto, detalle), suscriptor_id, sesion.usuario_id)
        except sqlite3.IntegrityError as error:
            raise Conflicto("Ya existe otro suscriptor con ese nombre y esa dirección.") from error
        self.auditoria.registrar("NOVEDAD_SUSCRIPCION", f"Cambio de suscriptor #{suscriptor_id}", sesion.usuario_id)
        return campos

    def depurar_retirados(self, sesion: Sesion, meses: int) -> int:
        """Depuración anual (Ley 1581, secciones 2.4 y 6.6): anonimiza a los retirados hace más de
        `meses`. El registro y sus entregas se conservan para las estadísticas (RN-12); se borran el
        nombre, las direcciones y los textos de novedades. Devuelve cuántos se anonimizaron."""
        self.auth.exigir(sesion, "DEPURACION")
        if not isinstance(meses, int) or not 1 <= meses <= 120:
            raise DatosInvalidos("Indique un plazo entre 1 y 120 meses.")
        ids = self.suscriptores.retirados_sin_anonimizar(restar_meses(date.today(), meses).isoformat())
        if not ids:
            return 0
        with self.bd.transaccion():
            for suscriptor_id in ids:
                self.suscriptores.actualizar(suscriptor_id, {
                    "nombre": f"Suscriptor anonimizado {suscriptor_id}",
                    "direccion": "",
                    "direccion_fs": "",
                    "novedades": "",
                    "indice_busqueda": f"anonimizado-{suscriptor_id}",
                    "indice_nombre": "ANONIMIZADO",
                })
            self.entregas.borrar_novedades(ids)
            self.novedades.suprimir_detalles(ids, "Detalle suprimido en la depuración anual")
        self.auditoria.registrar("DEPURACION", f"{len(ids)} suscriptor(es) retirado(s) anonimizado(s)", sesion.usuario_id)
        return len(ids)

    # ------------------------------------------------------------------ #
    def novedades_del_dia(self, sesion: Sesion, fecha: str) -> list[NovedadSuscripcion]:
        """Lista que la Secretaría usa para avisar a los distribuidores."""
        self.auth.exigir(sesion, "RF-09")
        return self.novedades.listar(fecha=parsear_fecha(fecha).isoformat())

    def buscar(self, sesion: Sesion, texto: str, limite: int = 100) -> list[Suscriptor]:
        self.auth.exigir(sesion, "RF-09")
        return self.suscriptores.listar(texto=texto, limite=limite)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _fecha(fecha: str) -> str:
        fecha_dt = parsear_fecha(fecha)
        if fecha_dt > date.today():
            raise DatosInvalidos("No se registran novedades con fecha futura.")
        return fecha_dt.isoformat()

    def _existente(self, suscriptor_id: int) -> Suscriptor:
        suscriptor = self.suscriptores.obtener(suscriptor_id) if suscriptor_id else None
        if not suscriptor:
            raise DatosInvalidos("Seleccione un suscriptor existente.")
        return suscriptor

    def _validar(
        self, nombre: str, direccion: str, direccion_fs: str, productos: list[str], periodicidad: str,
        ruta_id: int | None,
    ) -> dict:
        nombre = limpiar_texto(nombre)
        if len(nombre) < 3:
            raise DatosInvalidos("El nombre del suscriptor es obligatorio (al menos 3 caracteres).")
        direccion = self._direccion(direccion, obligatoria=True)
        direccion_fs = self._direccion(direccion_fs, obligatoria=False)
        elegidos = [p for p in ("TIE", "PT") if p in {str(x).upper() for x in productos or []}]
        if not elegidos:
            raise DatosInvalidos("Marque al menos un producto: El Tiempo o Portafolio.")
        mascara = parsear(periodicidad) if limpiar_texto(periodicidad) else None
        if mascara is None or "1" not in mascara:
            raise DatosInvalidos("La periodicidad no es válida. Use, por ejemplo: Diaria, L-V, S-D o D.")
        if not ruta_id or not self.rutas.obtener(ruta_id):
            raise DatosInvalidos("Seleccione la ruta del suscriptor.")
        return {
            "nombre": nombre,
            "direccion": direccion,
            "direccion_fs": direccion_fs,
            "productos": ",".join(elegidos),
            "periodicidad": mascara,
            "ruta_id": ruta_id,
        }

    @staticmethod
    def _direccion(direccion: str, obligatoria: bool) -> str:
        direccion = limpiar_texto(direccion)
        if not direccion and not obligatoria:
            return ""
        if len(direccion) < 6 or not re.search(r"\d", direccion):
            raise DatosInvalidos(DIRECCION_INCOMPLETA)
        return direccion

    @staticmethod
    def _detalle(texto: str, detalle: str) -> str:
        detalle = limpiar_texto(detalle)
        return f"{texto}: {detalle}" if detalle else texto
