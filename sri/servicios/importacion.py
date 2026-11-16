"""Importación del listado de repartidores de la empresa (RF-01).

El listado es un libro de Excel con una hoja por distribuidor. Cada fila trae
número, nombre (con la periodicidad anotada), dirección, las columnas de
producto TIE (El Tiempo) y PT (Portafolio) y el código de ruta.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path

from ..datos.base_datos import BaseDatos
from ..datos.daos import ArchivoDAO, DistribuidorDAO, RutaDAO, SuscriptorDAO
from ..dominio.modelos import ArchivoImportacion, Distribuidor, Rechazo, ResumenImportacion, Sesion, Suscriptor
from ..dominio.periodicidad import separar_nombre, solo_entre_semana, solo_fin_de_semana, unir
from ..seguridad import Cifrador
from ..util import DatosInvalidos, ErrorNegocio, limpiar_texto, normalizar
from .auditoria import AuditoriaServicio
from .autenticacion import AutenticacionServicio
from .lectores import crear_lector, mapear_columnas

ARCHIVO_ILEGIBLE = (
    "El archivo está dañado o no se puede leer. Revise que sea el listado de repartidores "
    "en Excel e inténtelo de nuevo. La base de datos no se modificó."
)
NOMBRES_CAMPO = {
    "numero": "número",
    "nombre": "nombre",
    "direccion": "dirección",
    "tie": "TIE (El Tiempo)",
    "pt": "PT (Portafolio)",
    "ruta": "código de ruta",
    "novedades": "novedades",
}
CAMPOS = ("numero", "nombre", "direccion", "direccion_fs", "tie", "pt", "ruta", "novedades")
NO_MARCADO = {"", "0", "NO", "N", "-", "FALSO", "FALSE"}
FILAS_BUSQUEDA_ENCABEZADO = 10


class ImportacionServicio:
    def __init__(
        self,
        bd: BaseDatos,
        config: dict,
        archivos: ArchivoDAO,
        rutas: RutaDAO,
        suscriptores: SuscriptorDAO,
        cifrador: Cifrador,
        auth: AutenticacionServicio,
        auditoria: AuditoriaServicio,
        distribuidores: DistribuidorDAO,
    ):
        self.bd = bd
        self.config = config
        self.archivos = archivos
        self.rutas = rutas
        self.suscriptores = suscriptores
        self.cifrador = cifrador
        self.auth = auth
        self.auditoria = auditoria
        self.distribuidores = distribuidores

    def importar(self, sesion: Sesion, ruta_archivo: str | Path) -> ResumenImportacion:
        self.auth.exigir(sesion, "RF-01")
        ruta = Path(ruta_archivo)
        if not ruta.exists():
            raise DatosInvalidos("El archivo seleccionado no existe.")
        if not ruta.is_file():
            raise DatosInvalidos("La ruta seleccionada no es un archivo.")

        lector = crear_lector(ruta, self.config.get("formatos_admitidos"))
        obligatorias = self.config.get("columnas_obligatorias", ["nombre", "direccion", "tie", "pt", "ruta"])
        mapeo = self.config.get("mapeo_columnas", {})
        self._maximo = int(self.config.get("importacion", {}).get("maximo_rechazos_detallados", 500))
        resumen = ResumenImportacion(archivo=ruta.name, leidos=0, importados=0, actualizados=0, rechazados=0)

        try:
            with self.bd.transaccion():
                archivo_id = self.archivos.crear(ruta.name, sesion.usuario_id)
                self._activos = {d.id: d for d in self.distribuidores.listar(incluir_inactivos=False)}
                self._rutas_vistas: dict[tuple[str, str], int] = {}
                for hoja, filas in lector.leer(ruta):
                    mapa, encontrado = self._encabezado(filas, obligatorias, mapeo)
                    if mapa is None:  # hoja vacía
                        continue
                    if not encontrado:
                        faltantes = [NOMBRES_CAMPO.get(c, c) for c in obligatorias if c not in mapa]
                        raise DatosInvalidos(
                            f"La hoja «{hoja}» no contiene las columnas obligatorias: "
                            + ", ".join(faltantes)
                            + ". Revise el mapeo de columnas en config.json."
                        )
                    resumen.hojas += 1
                    distribuidor = self._distribuidor_de_hoja(hoja)
                    for numero_fila, valores in filas:
                        datos = self._extraer(valores, mapa)
                        if not (datos["nombre"] or datos["direccion"] or datos["ruta"]):
                            continue
                        resumen.leidos += 1
                        self._procesar(datos, hoja, numero_fila, distribuidor, archivo_id, resumen)

                if resumen.leidos == 0:
                    raise DatosInvalidos("El archivo no contiene filas de suscriptores para importar.")
                self.archivos.actualizar_totales(
                    archivo_id, resumen.leidos, resumen.importados, resumen.actualizados, resumen.rechazados
                )
                if not resumen.cuadra:  # RNF-04: se revierte antes de confirmar
                    raise ErrorNegocio(
                        "El conteo de control de la importación no cuadra; no se aplicó. "
                        "Notifique al equipo de desarrollo."
                    )
        except sqlite3.Error as error:
            raise ErrorNegocio(
                "No se pudo completar la importación. La base de datos no se modificó."
            ) from error
        except ErrorNegocio:
            raise
        except Exception as error:  # noqa: BLE001 - errores de openpyxl/xlrd/zip sin detalle técnico
            raise DatosInvalidos(ARCHIVO_ILEGIBLE) from error

        self.auditoria.registrar(
            "IMPORTACION",
            (
                f"{ruta.name}: {resumen.hojas} hojas, {resumen.leidos} leídos, {resumen.importados} importados, "
                f"{resumen.actualizados} actualizados, {resumen.rechazados} rechazados, "
                f"{len(resumen.revisar)} casos para revisar"
            ),
            sesion.usuario_id,
        )
        return resumen

    def historial(self, sesion: Sesion, limite: int = 15) -> list[ArchivoImportacion]:
        self.auth.exigir(sesion, "RF-06")
        return self.archivos.listar(limite)

    # ------------------------------------------------------------------ #
    def _procesar(
        self, datos: dict, hoja: str, fila: int, distribuidor: Distribuidor | None, archivo_id: int,
        resumen: ResumenImportacion,
    ) -> None:
        faltan = [NOMBRES_CAMPO[c] for c in ("nombre", "direccion", "ruta") if not datos[c]]
        if faltan:
            return self._rechazar(resumen, hoja, fila, "Faltan datos obligatorios: " + ", ".join(faltan))
        productos = [p for p in ("TIE", "PT") if normalizar(datos[p.lower()]) not in NO_MARCADO]
        if not productos:
            return self._rechazar(resumen, hoja, fila, "No tiene producto marcado (TIE o PT)")

        nombre, periodicidad, reconocida = separar_nombre(datos["nombre"])
        if not reconocida:
            self._revisar(resumen, hoja, fila, "Periodicidad no reconocida junto al nombre; se tomó como diaria")
        direccion = datos["direccion"]
        ruta_id = self._ruta(datos["ruta"], hoja, fila, distribuidor, resumen)
        indice = self.cifrador.indice(normalizar(nombre), normalizar(direccion))
        indice_nombre = self.cifrador.indice(normalizar(nombre))
        comunes = {
            "nombre": nombre,
            "productos": ",".join(productos),
            "periodicidad": periodicidad,
            "numero": self._numero(datos["numero"]),
            "indice_nombre": indice_nombre,
        }
        if datos["novedades"]:
            comunes["novedades"] = datos["novedades"]

        existente = self.suscriptores.buscar_por_indice(indice)
        if existente is not None:
            # RN-07: no se duplica; se actualizan sus datos (la hoja más reciente prevalece).
            self.suscriptores.actualizar(existente.id, {**comunes, "direccion": direccion, "ruta_id": ruta_id})
            resumen.actualizados += 1
            if not existente.activo:
                self._revisar(resumen, hoja, fila, "El suscriptor está retirado en el sistema; no se reactivó")
            return

        candidatos = self.suscriptores.buscar_por_indice_nombre(indice_nombre)
        for candidato in candidatos:
            union = self._unir_direcciones(candidato, comunes, direccion, ruta_id, indice)
            if union:
                resumen.actualizados += 1
                if union == "nueva":  # se unió solo por el nombre: que la Gerencia lo confirme
                    self._revisar(resumen, hoja, fila, "Se unió con otro registro del mismo nombre como dirección de entre semana / fin de semana")
                return
        if candidatos:
            self._revisar(resumen, hoja, fila, "Posible duplicado: otro suscriptor tiene el mismo nombre y otra dirección")

        datos_nuevos = {**comunes, "direccion": direccion, "ruta_id": ruta_id, "archivo_id": archivo_id,
                        "indice_busqueda": indice}
        self.suscriptores.crear(datos_nuevos)
        resumen.importados += 1

    def _unir_direcciones(
        self, candidato: Suscriptor, comunes: dict, direccion: str, ruta_id: int, indice: str
    ) -> str | None:
        """RN-07: un suscriptor con dirección entre semana y otra de fin de semana es uno solo.

        Devuelve "nueva" si une dos registros, "recarga" si la dirección ya estaba unida y None si no aplica.
        """
        periodicidad = comunes["periodicidad"]
        productos = ",".join(p for p in ("TIE", "PT") if p in candidato.productos or p in comunes["productos"])
        union = {"periodicidad": unir(candidato.periodicidad, periodicidad), "productos": productos}
        mismo_fin_de_semana = candidato.direccion_fs and normalizar(candidato.direccion_fs) == normalizar(direccion)
        if mismo_fin_de_semana or (
            not candidato.direccion_fs and solo_fin_de_semana(periodicidad) and solo_entre_semana(candidato.periodicidad)
        ):
            self.suscriptores.actualizar(candidato.id, {
                **union,
                "direccion_fs": direccion,
                "ruta_fs_id": ruta_id if ruta_id != candidato.ruta_id else None,
            })
            return "recarga" if mismo_fin_de_semana else "nueva"
        if not candidato.direccion_fs and solo_entre_semana(periodicidad) and solo_fin_de_semana(candidato.periodicidad):
            # El registro existente era el de fin de semana: su dirección pasa a ser la de fin de semana.
            self.suscriptores.actualizar(candidato.id, {
                **union,
                "direccion": direccion,
                "ruta_id": ruta_id,
                "direccion_fs": candidato.direccion,
                "ruta_fs_id": candidato.ruta_id if candidato.ruta_id != ruta_id else None,
                "indice_busqueda": indice,
                "numero": comunes["numero"],
            })
            return "nueva"
        return None

    def _ruta(self, codigo: str, hoja: str, fila: int, distribuidor: Distribuidor | None,
              resumen: ResumenImportacion) -> int:
        """Asocia el código de ruta a su distribuidor y señala los que no tienen uno activo."""
        clave = (normalizar(codigo), hoja)
        if clave in self._rutas_vistas:
            return self._rutas_vistas[clave]
        ruta = self.rutas.buscar_por_zona(codigo)
        dueno = self._dueno_del_codigo(codigo, distribuidor)
        if ruta is None:
            distribuidor_id = dueno.id if dueno else None
            ruta_id = self.rutas.crear(codigo, distribuidor_id)
            resumen.rutas_creadas += 1
        else:
            ruta_id, distribuidor_id = ruta.id, ruta.distribuidor_id
            if distribuidor_id is None and dueno:
                self.rutas.asignar(ruta_id, dueno.id)
                distribuidor_id = dueno.id
        actual = self._activos.get(distribuidor_id)
        if actual is None:
            self._revisar(resumen, hoja, fila, f"El código de ruta «{codigo}» no corresponde a un distribuidor activo")
        elif distribuidor and actual.id != distribuidor.id:
            self._revisar(
                resumen, hoja, fila,
                f"El código de ruta «{codigo}» está en la hoja «{hoja}», pero la ruta es de {actual.nombre}",
            )
        self._rutas_vistas[clave] = ruta_id
        return ruta_id

    def _dueno_del_codigo(self, codigo: str, distribuidor_hoja: Distribuidor | None) -> Distribuidor | None:
        """El código de ruta lleva las iniciales del distribuidor (p. ej. «CP» = Carlos Pérez).

        Si el código tiene forma de iniciales y no son las de un distribuidor activo
        (como «AL», de uno que ya no trabaja), no se asigna. Si no tiene esa forma,
        se usa el distribuidor de la hoja.
        """
        letras = normalizar(codigo).replace(" ", "")
        if not re.fullmatch(r"[A-Z]{2,3}\d*", letras):
            return distribuidor_hoja
        letras = re.sub(r"\d", "", letras)
        coincidencias = [
            d for d in self._activos.values()
            if letras in {self._iniciales(d.nombre), self._iniciales(d.nombre)[:2]}
        ]
        return coincidencias[0] if len(coincidencias) == 1 else None

    @staticmethod
    def _iniciales(nombre: str) -> str:
        return "".join(parte[0] for parte in normalizar(nombre).split())

    def _distribuidor_de_hoja(self, hoja: str) -> Distribuidor | None:
        """La hoja se llama como el distribuidor (nombre, primer nombre o iniciales)."""
        buscado = re.sub(r"[\s(]*\d+\)?$", "", normalizar(hoja))  # «CARLOS (2)» → «CARLOS»
        if not buscado:
            return None
        coincidencias = []
        for distribuidor in self._activos.values():
            nombre = normalizar(distribuidor.nombre)
            iniciales = "".join(parte[0] for parte in nombre.split())
            if nombre == buscado or nombre.startswith(buscado + " ") or iniciales == buscado:
                coincidencias.append(distribuidor)
        return coincidencias[0] if len(coincidencias) == 1 else None

    @staticmethod
    def _encabezado(filas, obligatorias: list[str], mapeo: dict) -> tuple[dict | None, bool]:
        """Busca la fila de encabezados entre las primeras filas con datos de la hoja."""
        primera = None
        revisadas = 0
        for _numero, valores in filas:
            textos = [limpiar_texto(v) for v in valores]
            if not any(textos):
                continue
            mapa = mapear_columnas(textos, mapeo)
            if all(c in mapa for c in obligatorias):
                return mapa, True
            primera = primera if primera is not None else mapa
            revisadas += 1
            if revisadas >= FILAS_BUSQUEDA_ENCABEZADO:
                break
        return primera, False

    def _rechazar(self, resumen: ResumenImportacion, hoja: str, fila: int, motivo: str) -> None:
        resumen.rechazados += 1
        if len(resumen.rechazos) < self._maximo:
            resumen.rechazos.append(Rechazo(fila, motivo, hoja))
        else:
            resumen.truncado = True

    def _revisar(self, resumen: ResumenImportacion, hoja: str, fila: int, motivo: str) -> None:
        if len(resumen.revisar) < self._maximo:
            resumen.revisar.append(Rechazo(fila, motivo, hoja))

    @staticmethod
    def _numero(valor: str) -> int | None:
        try:
            return int(float(valor))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _texto(valor: object) -> str:
        if valor is None:
            return ""
        if isinstance(valor, (datetime, date)):
            return valor.strftime("%d/%m/%Y")
        if isinstance(valor, float) and valor.is_integer():
            return str(int(valor))
        return limpiar_texto(valor)

    def _extraer(self, valores: list, mapa: dict[str, int]) -> dict[str, str]:
        def valor(campo: str) -> str:
            indice = mapa.get(campo)
            if indice is None or indice >= len(valores):
                return ""
            return self._texto(valores[indice])

        return {campo: valor(campo) for campo in CAMPOS}
