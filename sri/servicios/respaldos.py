"""Respaldo y restauración cifrada de la base de datos (RF-07, RN-09, RNF-05).

- Respaldo diario automático: al cerrar el día o al cerrar la sesión/aplicación
  si ese día aún no hay respaldo. Se conservan los siete más recientes.
- Copia semanal: la Gerencia copia el último respaldo (ya cifrado) a la carpeta
  sincronizada con Google Drive; la aplicación de Drive lo sube cuando hay Internet.
- Avisos: si el respaldo diario falló o hace más de siete días que no hay copia
  en Google Drive, se avisa al iniciar la sesión.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
import sqlite3
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from ..config import directorio_respaldos
from ..datos.base_datos import BaseDatos
from ..datos.daos import EventoDAO, RespaldoDAO
from ..dominio.modelos import Respaldo, Sesion
from ..seguridad import Cifrador
from ..util import Conflicto, DatosInvalidos, ErrorNegocio
from .auditoria import AuditoriaServicio
from .autenticacion import AutenticacionServicio

PREFIJO_DIARIO = "sri_diario_"


class RespaldoServicio:
    def __init__(
        self,
        bd: BaseDatos,
        dao: RespaldoDAO,
        auth: AutenticacionServicio,
        auditoria: AuditoriaServicio,
        cifrador: Cifrador,
        config: dict,
        eventos: EventoDAO,
    ):
        self.bd = bd
        self.dao = dao
        self.auth = auth
        self.auditoria = auditoria
        self.cifrador = cifrador
        self.config = config
        self.eventos = eventos
        # Lo conecta el Contexto: migra y completa índices tras restaurar un respaldo antiguo.
        self.al_restaurar: Callable[[], None] | None = None

    @property
    def _ajustes(self) -> dict:
        return self.config.get("respaldo", {})

    def listar(self, sesion: Sesion) -> list[Respaldo]:
        self.auth.exigir(sesion, "RF-07")
        return self.dao.listar()

    # ------------------------------------------------------------------ #
    # Estado y avisos (RN-09)
    # ------------------------------------------------------------------ #
    def estado(self, sesion: Sesion) -> dict:
        self.auth.exigir(sesion, "RF-07")
        return self._estado()

    def _estado(self) -> dict:
        diario = self.dao.listar(1, tipo="DIARIO")
        drive = self.dao.listar(1, tipo="DRIVE")
        dias_drive = self._dias(drive[0].fecha) if drive else None
        ultimo = self.eventos.ultimo(("RESPALDO_DIARIO", "RESPALDO_FALLIDO"))
        limite = int(self._ajustes.get("dias_copia_drive", 7))
        verificado = self.eventos.ultimo(("RESPALDO_VERIFICADO",))
        dias_verificacion = self._dias(verificado["fecha"]) if verificado else None
        return {
            "ultimo_diario": diario[0].fecha if diario else None,
            "ultimo_drive": drive[0].fecha if drive else None,
            "carpeta_drive": str(Path(drive[0].ruta_archivo).parent) if drive else "",
            "dias_drive": dias_drive,
            "drive_vencido": dias_drive is None or dias_drive > limite,
            "fallo_diario": bool(ultimo and ultimo["tipo"] == "RESPALDO_FALLIDO"),
            "fecha_fallo": ultimo["fecha"] if ultimo and ultimo["tipo"] == "RESPALDO_FALLIDO" else None,
            "ultima_verificacion": verificado["fecha"] if verificado else None,
            "dias_verificacion": dias_verificacion,
            "verificacion_vencida": bool(diario or drive)
            and (dias_verificacion is None or dias_verificacion > int(self._ajustes.get("dias_verificacion", 30))),
        }

    def avisos(self) -> list[str]:
        """Avisos visibles al iniciar la sesión (RF-07): no requieren permiso y no tienen datos personales."""
        estado = self._estado()
        avisos = []
        if estado["fallo_diario"]:
            avisos.append(
                f"El respaldo automático del {estado['fecha_fallo'][:10]} falló. "
                "Revise el espacio en disco y la carpeta de respaldos, o pida a la Gerencia crear uno manual."
            )
        if estado["drive_vencido"]:
            if estado["dias_drive"] is None:
                avisos.append("Aún no se ha copiado ningún respaldo a Google Drive. La Gerencia debe hacerlo en «Respaldos».")
            else:
                avisos.append(
                    f"Han pasado {estado['dias_drive']} días desde la última copia en Google Drive. "
                    "La Gerencia debe copiar el último respaldo en «Respaldos»."
                )
        if estado["verificacion_vencida"]:
            cuando = (
                "Aún no se ha verificado ningún respaldo"
                if estado["dias_verificacion"] is None
                else f"Han pasado {estado['dias_verificacion']} días sin verificar un respaldo"
            )
            avisos.append(
                f"{cuando}. Una vez al mes, la Gerencia debe pulsar «Verificar respaldo» en «Respaldos» "
                "para comprobar que se puede recuperar la información."
            )
        return avisos

    # ------------------------------------------------------------------ #
    # Respaldo diario automático
    # ------------------------------------------------------------------ #
    def respaldo_automatico(self, usuario_id: int) -> Path | None:
        """Tarea del sistema (sin control de rol): un respaldo por día.

        Nunca lanza excepciones, porque se ejecuta al cerrar la aplicación; si
        falla, deja el evento RESPALDO_FALLIDO para avisar en la siguiente sesión.
        """
        hoy = date.today()
        diarios = self.dao.listar(1, tipo="DIARIO")
        if diarios and diarios[0].fecha[:10] == hoy.isoformat():
            return None
        try:
            destino = directorio_respaldos(self.config) / f"{PREFIJO_DIARIO}{hoy:%Y%m%d}.sribak"
            ruta = self._generar(destino, usuario_id, "DIARIO")
            self._depurar_diarios()
        except Exception as error:  # noqa: BLE001
            self.auditoria.registrar("RESPALDO_FALLIDO", f"Respaldo diario fallido: {type(error).__name__}", usuario_id)
            return None
        self.auditoria.registrar("RESPALDO_DIARIO", f"Respaldo diario creado en {ruta.name}", usuario_id)
        return ruta

    def _depurar_diarios(self) -> None:
        conservar = int(self._ajustes.get("conservar_diarios", 7))
        for viejo in self.dao.listar(1000, tipo="DIARIO")[conservar:]:
            archivo = Path(viejo.ruta_archivo)
            if archivo.name.startswith(PREFIJO_DIARIO) and archivo.exists():
                archivo.unlink()
            self.dao.eliminar(viejo.id)

    # ------------------------------------------------------------------ #
    # Respaldo manual, copia a Google Drive y restauración
    # ------------------------------------------------------------------ #
    def crear(self, sesion: Sesion, destino: str | Path | None = None) -> Path:
        self.auth.exigir(sesion, "RF-07")
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        if destino is None:
            destino = directorio_respaldos(self.config) / f"sri_respaldo_{marca}.sribak"
        destino = Path(destino)
        if destino.is_dir():
            destino = destino / f"sri_respaldo_{marca}.sribak"
        if destino.suffix.lower() != ".sribak":
            destino = destino.with_suffix(destino.suffix + ".sribak") if destino.suffix else destino.with_suffix(".sribak")
        ruta = self._generar(destino, sesion.usuario_id, "MANUAL")
        self.auditoria.registrar("RESPALDO", f"Respaldo creado en {ruta.name}", sesion.usuario_id)
        return ruta

    def crear_antes_de_importar(self, sesion: Sesion) -> Path:
        """Respaldo de seguridad que quien importa (Secretaría) puede crear antes de cargar un listado.
        Crear una copia no expone datos ni cambia nada; restaurarla sigue siendo solo de la Gerencia."""
        self.auth.exigir(sesion, "RF-01")
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = self._generar(directorio_respaldos(self.config) / f"sri_antes_de_importar_{marca}.sribak", sesion.usuario_id, "MANUAL")
        self.auditoria.registrar("RESPALDO", f"Respaldo previo a la importación: {ruta.name}", sesion.usuario_id)
        return ruta

    def copiar_a_drive(self, sesion: Sesion, carpeta: str | Path) -> Path:
        """Copia semanal (RN-09): el último respaldo, ya cifrado, a la carpeta de Google Drive."""
        self.auth.exigir(sesion, "RF-07")
        carpeta = Path(carpeta) if carpeta else None
        if not carpeta or not carpeta.is_dir():
            raise DatosInvalidos(
                "La carpeta de Google Drive no está disponible. Verifique que la aplicación de Google Drive "
                "para escritorio esté instalada y elija la carpeta sincronizada."
            )
        origen = next(
            (Path(r.ruta_archivo) for r in self.dao.listar(50) if r.tipo != "DRIVE" and Path(r.ruta_archivo).exists()),
            None,
        )
        if origen is None:  # no hay respaldo local: se genera uno ahora
            origen = self.respaldo_automatico(sesion.usuario_id) or self.crear(sesion)
        destino = carpeta / origen.name
        try:
            shutil.copy2(origen, destino)
        except OSError as error:
            raise ErrorNegocio(
                "No se pudo copiar el respaldo a Google Drive. Verifique la carpeta y el espacio disponible."
            ) from error
        self.dao.crear(self._ahora(), str(destino), sesion.usuario_id, "DRIVE")
        self.auditoria.registrar("RESPALDO_DRIVE", f"Respaldo {origen.name} copiado a Google Drive", sesion.usuario_id)
        return destino

    def restaurar(self, sesion: Sesion, archivo: str | Path) -> Path:
        self.auth.exigir(sesion, "RF-07")
        origen = Path(archivo)
        if self.bd.conexion.in_transaction:
            raise ErrorNegocio("Hay una operación en curso; intente restaurar de nuevo.")
        with self._copia_validada(origen) as copia:
            self.bd.conexion.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.bd.restaurar_desde(copia)

        if not self.bd.verificar_integridad():
            raise ErrorNegocio("La base de datos restaurada no supera la verificación de integridad.")
        self.bd.conexion.execute("PRAGMA foreign_keys = ON")
        if self.al_restaurar:
            self.al_restaurar()
        # El usuario de la sesión puede no existir en el respaldo: se registra sin usuario.
        self.auditoria.registrar("RESPALDO", f"Base restaurada desde {origen.name}", None)
        return origen

    def verificar(self, sesion: Sesion, archivo: str | Path) -> dict:
        """Prueba de restauración sin reemplazar la base (sección 6.6, rutina mensual)."""
        self.auth.exigir(sesion, "RF-07")
        origen = Path(archivo)
        with self._copia_validada(origen) as copia:
            suscriptores = copia.execute("SELECT COUNT(*) FROM suscriptor").fetchone()[0]
            entregas, ultima = copia.execute("SELECT COUNT(*), MAX(fecha) FROM entrega").fetchone()
        self.auditoria.registrar("RESPALDO_VERIFICADO", f"Respaldo {origen.name} verificado: se puede restaurar", sesion.usuario_id)
        return {"archivo": origen.name, "suscriptores": suscriptores, "entregas": entregas, "ultima_entrega": ultima}

    def guardar_copia_clave(self, sesion: Sesion, carpeta: str | Path) -> Path:
        """Copia sri.key a otra carpeta (por ejemplo, una USB): sin ella no se abre ningún respaldo."""
        self.auth.exigir(sesion, "RF-07")
        carpeta = Path(carpeta) if carpeta else None
        if not carpeta or not carpeta.is_dir():
            raise DatosInvalidos("Elija una carpeta disponible, por ejemplo la de la memoria USB.")
        clave = self.cifrador.ruta_clave.read_bytes()
        destino = carpeta / "sri.key"
        if destino.exists() and destino.read_bytes() != clave:
            raise Conflicto("En esa carpeta ya hay otra clave sri.key distinta; no se reemplaza. Elija otra carpeta.")
        try:
            destino.write_bytes(clave)
        except OSError as error:
            raise ErrorNegocio("No se pudo escribir la clave en esa carpeta. Verifique que la USB esté conectada.") from error
        self.auditoria.registrar("CLAVE_COPIADA", "Copia de la clave guardada fuera del equipo", sesion.usuario_id)
        return destino

    # ------------------------------------------------------------------ #
    @contextmanager
    def _copia_validada(self, origen: Path):
        """Descifra el respaldo en un archivo temporal, verifica su integridad y entrega la conexión."""
        if not origen.exists() or not origen.is_file():
            raise DatosInvalidos("El archivo de respaldo no existe.")
        try:
            datos = self.cifrador.descifrar_bytes(origen.read_bytes())
        except OSError as error:
            raise ErrorNegocio("No se pudo leer el archivo de respaldo.") from error
        temporal = copia = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db", dir=self.bd.ruta.parent) as archivo:
                archivo.write(datos)
                temporal = Path(archivo.name)
            copia = sqlite3.connect(str(temporal))
            resultado = copia.execute("PRAGMA integrity_check").fetchone()
            if not resultado or resultado[0] != "ok":
                raise DatosInvalidos("El respaldo está dañado y no supera la verificación de integridad.")
            tablas = {f[0] for f in copia.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"usuario", "suscriptor", "ruta", "entrega", "distribuidor"}.issubset(tablas):
                raise DatosInvalidos("El archivo no corresponde a un respaldo del SRI.")
            yield copia
        except sqlite3.Error as error:
            raise ErrorNegocio("No se pudo leer o restaurar el respaldo.") from error
        finally:
            if copia is not None:
                copia.close()
            if temporal and temporal.exists():
                try:
                    temporal.unlink()
                except OSError:
                    pass

    def _generar(self, destino: Path, usuario_id: int, tipo: str) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        # Se registra antes de la copia para que el propio respaldo conserve su
        # entrada en el historial; si la escritura falla, se elimina el registro.
        respaldo_id = self.dao.crear(self._ahora(), str(destino), usuario_id, tipo)
        temporal = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".db", dir=self.bd.ruta.parent) as archivo:
                temporal = Path(archivo.name)
            copia = sqlite3.connect(str(temporal))
            try:
                self.bd.respaldar_a(copia)
            finally:
                copia.close()
            cifrado = self.cifrador.cifrar_bytes(temporal.read_bytes())
            if not cifrado:
                raise ErrorNegocio("No se pudo generar el contenido del respaldo.")
            destino.write_bytes(cifrado)
        except OSError as error:
            self.dao.eliminar(respaldo_id)
            raise ErrorNegocio(
                "No se pudo escribir el respaldo. Verifique el destino y el espacio disponible."
            ) from error
        except Exception:
            self.dao.eliminar(respaldo_id)
            raise
        finally:
            if temporal and temporal.exists():
                try:
                    temporal.unlink()
                except OSError:
                    pass
        return destino

    @staticmethod
    def _ahora() -> str:
        return datetime.now().replace(microsecond=0).isoformat(sep=" ")

    @staticmethod
    def _dias(fecha: str) -> int | None:
        try:
            return (date.today() - datetime.fromisoformat(fecha).date()).days
        except ValueError:
            return None
