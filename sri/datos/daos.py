"""Objetos de acceso a datos (DAO), uno por tabla (sección 5.3.1)."""

from __future__ import annotations

import sqlite3
from datetime import date

from ..dominio.modelos import (
    ArchivoImportacion,
    Distribuidor,
    Entrega,
    NovedadSuscripcion,
    Respaldo,
    Ruta,
    Suscriptor,
    Usuario,
)
from ..seguridad import Cifrador
from ..util import ahora_iso, normalizar
from .base_datos import BaseDatos


class UsuarioDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def buscar_por_nombre(self, nombre: str) -> sqlite3.Row | None:
        return self.bd.uno("SELECT * FROM usuario WHERE nombre = ? COLLATE NOCASE", (nombre.strip(),))

    def obtener(self, usuario_id: int) -> Usuario | None:
        fila = self.bd.uno("SELECT * FROM usuario WHERE id = ?", (usuario_id,))
        return self._mapear(fila) if fila else None

    def listar(self) -> list[Usuario]:
        return [self._mapear(f) for f in self.bd.todos("SELECT * FROM usuario ORDER BY nombre")]

    def crear(self, nombre: str, rol: str, hash_contrasena: str) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO usuario (nombre, rol, contrasena_hash, activo, creado_en) VALUES (?, ?, ?, 1, ?)",
            (nombre, rol, hash_contrasena, ahora_iso()),
        )
        return int(cur.lastrowid)

    def actualizar_hash(self, usuario_id: int, hash_contrasena: str) -> None:
        self.bd.ejecutar("UPDATE usuario SET contrasena_hash = ? WHERE id = ?", (hash_contrasena, usuario_id))

    def contar(self) -> int:
        return int(self.bd.uno("SELECT COUNT(*) FROM usuario")[0])

    @staticmethod
    def _mapear(fila: sqlite3.Row) -> Usuario:
        return Usuario(
            id=fila["id"],
            nombre=fila["nombre"],
            rol=fila["rol"],
            activo=bool(fila["activo"]),
        )


class DistribuidorDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def listar(self, incluir_inactivos: bool = True) -> list[Distribuidor]:
        condicion = "" if incluir_inactivos else "WHERE d.activo = 1"
        filas = self.bd.todos(
            f"""
            SELECT d.*, COUNT(r.id) AS rutas
            FROM distribuidor d
            LEFT JOIN ruta r ON r.distribuidor_id = d.id
            {condicion}
            GROUP BY d.id
            ORDER BY d.activo DESC, d.nombre
            """
        )
        return [
            Distribuidor(
                id=f["id"],
                nombre=f["nombre"],
                telefono=f["telefono"],
                activo=bool(f["activo"]),
                rutas=f["rutas"],
            )
            for f in filas
        ]

    def obtener(self, distribuidor_id: int) -> Distribuidor | None:
        fila = self.bd.uno(
            """
            SELECT d.*, (SELECT COUNT(*) FROM ruta r WHERE r.distribuidor_id = d.id) AS rutas
            FROM distribuidor d WHERE d.id = ?
            """,
            (distribuidor_id,),
        )
        if not fila:
            return None
        return Distribuidor(fila["id"], fila["nombre"], fila["telefono"], bool(fila["activo"]), fila["rutas"])

    def existe_nombre(self, nombre: str, excluir_id: int | None = None) -> bool:
        if excluir_id:
            fila = self.bd.uno(
                "SELECT 1 FROM distribuidor WHERE nombre = ? COLLATE NOCASE AND id <> ?",
                (nombre, excluir_id),
            )
        else:
            fila = self.bd.uno("SELECT 1 FROM distribuidor WHERE nombre = ? COLLATE NOCASE", (nombre,))
        return fila is not None

    def crear(self, nombre: str, telefono: str) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO distribuidor (nombre, telefono, activo, creado_en) VALUES (?, ?, 1, ?)",
            (nombre, telefono, ahora_iso()),
        )
        return int(cur.lastrowid)

    def actualizar(self, distribuidor_id: int, nombre: str, telefono: str) -> None:
        self.bd.ejecutar(
            "UPDATE distribuidor SET nombre = ?, telefono = ? WHERE id = ?",
            (nombre, telefono, distribuidor_id),
        )

    def cambiar_activo(self, distribuidor_id: int, activo: bool) -> None:
        self.bd.ejecutar("UPDATE distribuidor SET activo = ? WHERE id = ?", (1 if activo else 0, distribuidor_id))


class RutaDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def listar(self) -> list[Ruta]:
        filas = self.bd.todos(
            """
            SELECT r.*, COALESCE(d.nombre, '') AS distribuidor,
                   (SELECT COUNT(*) FROM suscriptor s WHERE s.ruta_id = r.id) AS suscriptores
            FROM ruta r
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            ORDER BY r.zona
            """
        )
        return [self._mapear(f) for f in filas]

    def obtener(self, ruta_id: int) -> Ruta | None:
        fila = self.bd.uno(
            """
            SELECT r.*, COALESCE(d.nombre, '') AS distribuidor,
                   (SELECT COUNT(*) FROM suscriptor s WHERE s.ruta_id = r.id) AS suscriptores
            FROM ruta r LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            WHERE r.id = ?
            """,
            (ruta_id,),
        )
        return self._mapear(fila) if fila else None

    def buscar_por_zona(self, zona: str) -> Ruta | None:
        fila = self.bd.uno("SELECT * FROM ruta WHERE zona_normalizada = ?", (normalizar(zona),))
        return self._mapear(fila) if fila else None

    def crear(self, zona: str, distribuidor_id: int | None = None) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO ruta (zona, zona_normalizada, distribuidor_id, creado_en) VALUES (?, ?, ?, ?)",
            (zona, normalizar(zona), distribuidor_id, ahora_iso()),
        )
        return int(cur.lastrowid)

    def actualizar(self, ruta_id: int, zona: str, distribuidor_id: int | None) -> None:
        self.bd.ejecutar(
            "UPDATE ruta SET zona = ?, zona_normalizada = ?, distribuidor_id = ? WHERE id = ?",
            (zona, normalizar(zona), distribuidor_id, ruta_id),
        )

    def asignar(self, ruta_id: int, distribuidor_id: int | None) -> None:
        self.bd.ejecutar("UPDATE ruta SET distribuidor_id = ? WHERE id = ?", (distribuidor_id, ruta_id))

    def contar_por_distribuidor(self, distribuidor_id: int) -> int:
        return int(
            self.bd.uno("SELECT COUNT(*) FROM ruta WHERE distribuidor_id = ?", (distribuidor_id,))[0]
        )

    @staticmethod
    def _mapear(fila: sqlite3.Row) -> Ruta:
        claves = fila.keys()
        return Ruta(
            id=fila["id"],
            zona=fila["zona"],
            distribuidor_id=fila["distribuidor_id"],
            distribuidor=fila["distribuidor"] if "distribuidor" in claves else "",
            suscriptores=fila["suscriptores"] if "suscriptores" in claves else 0,
        )


class ArchivoDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def crear(self, nombre_archivo: str, usuario_id: int) -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO archivo_importacion (nombre_archivo, fecha_carga, usuario_id) VALUES (?, ?, ?)",
            (nombre_archivo, ahora_iso(), usuario_id),
        )
        return int(cur.lastrowid)

    def actualizar_totales(
        self, archivo_id: int, leidos: int, importados: int, actualizados: int, rechazados: int
    ) -> None:
        self.bd.ejecutar(
            """
            UPDATE archivo_importacion
            SET total_leidos = ?, total_importados = ?, total_actualizados = ?, total_rechazados = ?
            WHERE id = ?
            """,
            (leidos, importados, actualizados, rechazados, archivo_id),
        )

    def listar(self, limite: int = 15) -> list[ArchivoImportacion]:
        filas = self.bd.todos(
            """
            SELECT a.*, u.nombre AS usuario
            FROM archivo_importacion a JOIN usuario u ON u.id = a.usuario_id
            ORDER BY a.id DESC LIMIT ?
            """,
            (limite,),
        )
        return [
            ArchivoImportacion(
                id=f["id"],
                nombre_archivo=f["nombre_archivo"],
                fecha_carga=f["fecha_carga"],
                total_leidos=f["total_leidos"],
                total_importados=f["total_importados"],
                total_actualizados=f["total_actualizados"],
                total_rechazados=f["total_rechazados"],
                usuario=f["usuario"],
            )
            for f in filas
        ]


# Entregas programadas de un día (RN-11): suscriptor activo en la fecha y con ese día en su periodicidad.
PROGRAMADO = (
    "(s.fecha_ingreso IS NULL OR s.fecha_ingreso <= :fecha)"
    " AND (s.fecha_retiro IS NULL OR s.fecha_retiro > :fecha)"
    " AND substr(s.periodicidad, :dia, 1) = '1'"
)
# El fin de semana la entrega va a la ruta de fin de semana, si el suscriptor tiene una.
RUTA_DEL_DIA = "CASE WHEN :finde = 1 AND s.ruta_fs_id IS NOT NULL THEN s.ruta_fs_id ELSE s.ruta_id END"


def parametros_dia(fecha_iso: str) -> dict:
    dia = date.fromisoformat(fecha_iso).weekday()
    return {"fecha": fecha_iso, "dia": dia + 1, "finde": 1 if dia >= 5 else 0}


class SuscriptorDAO:
    CIFRADAS = {
        "nombre": "nombre_cifrado",
        "direccion": "direccion_cifrada",
        "direccion_fs": "direccion_fs_cifrada",
        "novedades": "novedades_cifrada",
    }
    PLANAS = {
        "ruta_id", "ruta_fs_id", "productos", "periodicidad", "estado", "fecha_ingreso",
        "fecha_retiro", "numero", "indice_busqueda", "indice_nombre", "archivo_id",
    }
    SELECT = """
        SELECT s.*, r.zona, COALESCE(d.nombre, '') AS distribuidor, COALESCE(rf.zona, '') AS zona_fs
        FROM suscriptor s
        JOIN ruta r ON r.id = s.ruta_id
        LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
        LEFT JOIN ruta rf ON rf.id = s.ruta_fs_id
    """

    def __init__(self, bd: BaseDatos, cifrador: Cifrador):
        self.bd = bd
        self.cifrador = cifrador

    def _columnas(self, datos: dict) -> tuple[list[str], list]:
        columnas, valores = [], []
        for clave, valor in datos.items():
            if clave in self.CIFRADAS:
                columnas.append(self.CIFRADAS[clave])
                valores.append(self.cifrador.cifrar(valor or ""))
            elif clave in self.PLANAS:
                columnas.append(clave)
                valores.append(valor)
            else:
                raise KeyError(f"Campo de suscriptor desconocido: {clave}")
        return columnas, valores

    def crear(self, datos: dict) -> int:
        columnas, valores = self._columnas(datos)
        ahora = ahora_iso()
        columnas += ["creado_en", "actualizado_en"]
        valores += [ahora, ahora]
        marcas = ", ".join(["?"] * len(columnas))
        cur = self.bd.ejecutar(
            f"INSERT INTO suscriptor ({', '.join(columnas)}) VALUES ({marcas})", tuple(valores)
        )
        return int(cur.lastrowid)

    def actualizar(self, suscriptor_id: int, datos: dict) -> None:
        if not datos:
            return
        columnas, valores = self._columnas(datos)
        asignaciones = ", ".join(f"{c} = ?" for c in columnas)
        self.bd.ejecutar(
            f"UPDATE suscriptor SET {asignaciones}, actualizado_en = ? WHERE id = ?",
            (*valores, ahora_iso(), suscriptor_id),
        )

    def actualizar_novedades(self, suscriptor_id: int, novedades: str) -> None:
        self.actualizar(suscriptor_id, {"novedades": novedades})

    def buscar_por_indice(self, indice: str) -> Suscriptor | None:
        fila = self.bd.uno(self.SELECT + " WHERE s.indice_busqueda = ?", (indice,))
        return self.mapear(fila) if fila else None

    def buscar_por_indice_nombre(self, indice: str) -> list[Suscriptor]:
        return [self.mapear(f) for f in self.bd.todos(self.SELECT + " WHERE s.indice_nombre = ?", (indice,))]

    def obtener(self, suscriptor_id: int) -> Suscriptor | None:
        fila = self.bd.uno(self.SELECT + " WHERE s.id = ?", (suscriptor_id,))
        return self.mapear(fila) if fila else None

    def listar(
        self, ruta_id: int | None = None, texto: str = "", limite: int = 500, solo_activos: bool = False
    ) -> list[Suscriptor]:
        condiciones, parametros = [], []
        if ruta_id:
            condiciones.append("(s.ruta_id = ? OR s.ruta_fs_id = ?)")
            parametros += [ruta_id, ruta_id]
        if solo_activos:
            condiciones.append("s.estado = 'ACTIVO'")
        sql = self.SELECT + (" WHERE " + " AND ".join(condiciones) if condiciones else "")
        # Los datos están cifrados: para buscar texto hay que descifrar todas las
        # filas (LIMIT -1 = sin límite) y recortar después del filtro (RF-06).
        sql += " ORDER BY s.id LIMIT ?"
        parametros.append(-1 if texto else limite)
        resultados = self._filtrar([self.mapear(f) for f in self.bd.todos(sql, tuple(parametros))], texto)
        resultados.sort(key=lambda s: normalizar(s.nombre))
        return resultados if limite < 0 else resultados[:limite]  # limite < 0 = sin límite

    def listar_del_dia(
        self, fecha_iso: str, ruta_id: int | None = None, texto: str = "", limite: int = 500
    ) -> list[Suscriptor]:
        """Entregas programadas del día (RN-11) más las que ya tienen un registro.

        La ruta y la dirección son las del día: el fin de semana se usan las de
        fin de semana cuando el suscriptor las tiene.
        """
        parametros = parametros_dia(fecha_iso)
        sql = f"""
            SELECT s.*, r.zona, COALESCE(d.nombre, '') AS distribuidor, '' AS zona_fs
            FROM suscriptor s
            LEFT JOIN entrega e ON e.suscriptor_id = s.id AND e.fecha = :fecha
            JOIN ruta r ON r.id = {RUTA_DEL_DIA}
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            WHERE (e.id IS NOT NULL OR ({PROGRAMADO}))
        """
        if ruta_id:
            sql += " AND r.id = :ruta"
            parametros["ruta"] = ruta_id
        sql += " ORDER BY r.zona, s.numero, s.id LIMIT :limite"
        parametros["limite"] = -1 if texto else limite
        resultados = self._filtrar([self.mapear(f) for f in self.bd.todos(sql, parametros)], texto)
        if parametros["finde"]:
            for suscriptor in resultados:
                suscriptor.direccion = suscriptor.direccion_fs or suscriptor.direccion
        return resultados if limite < 0 else resultados[:limite]  # limite < 0 = sin límite

    def listar_por_rutas(self, ruta_ids: list[int]) -> list[Suscriptor]:
        """Suscriptores activos de un conjunto de rutas (entre semana o fin de semana)."""
        if not ruta_ids:
            return []
        marcas = ",".join(["?"] * len(ruta_ids))
        filas = self.bd.todos(
            self.SELECT
            + f" WHERE s.estado = 'ACTIVO' AND (s.ruta_id IN ({marcas}) OR s.ruta_fs_id IN ({marcas}))"
            + " ORDER BY s.numero, s.id",
            tuple(ruta_ids) * 2,
        )
        return [self.mapear(f) for f in filas]

    @staticmethod
    def _filtrar(resultados: list[Suscriptor], texto: str) -> list[Suscriptor]:
        if not texto:
            return resultados
        buscado = normalizar(texto)
        return [
            s
            for s in resultados
            if buscado in normalizar(s.nombre)
            or buscado in normalizar(s.direccion)
            or buscado in normalizar(s.direccion_fs)
            or buscado in normalizar(s.zona)
        ]

    def retirados_sin_anonimizar(self, hasta: str) -> list[int]:
        return [f[0] for f in self.bd.todos(
            "SELECT id FROM suscriptor WHERE estado = 'RETIRADO' AND fecha_retiro <= ? AND indice_nombre <> 'ANONIMIZADO'",
            (hasta,),
        )]

    def contar(self, solo_activos: bool = False) -> int:
        condicion = " WHERE estado = 'ACTIVO'" if solo_activos else ""
        return int(self.bd.uno("SELECT COUNT(*) FROM suscriptor" + condicion)[0])

    def contar_por_ruta(self) -> dict[int, int]:
        return {f["ruta_id"]: f["total"] for f in self.bd.todos(
            "SELECT ruta_id, COUNT(*) AS total FROM suscriptor GROUP BY ruta_id"
        )}

    def completar_indices_nombre(self) -> None:
        """Calcula el índice por nombre de los suscriptores migrados de una versión anterior."""
        for fila in self.bd.todos("SELECT id, nombre_cifrado FROM suscriptor WHERE indice_nombre = ''"):
            nombre = normalizar(self.cifrador.descifrar(fila["nombre_cifrado"]))
            self.bd.ejecutar(
                "UPDATE suscriptor SET indice_nombre = ? WHERE id = ?",
                (self.cifrador.indice(nombre), fila["id"]),
            )

    def mapear(self, fila: sqlite3.Row) -> Suscriptor:
        claves = fila.keys()
        return Suscriptor(
            id=fila["id"],
            nombre=self.cifrador.descifrar(fila["nombre_cifrado"]),
            direccion=self.cifrador.descifrar(fila["direccion_cifrada"]),
            novedades=self.cifrador.descifrar(fila["novedades_cifrada"]),
            ruta_id=fila["ruta_id"],
            zona=fila["zona"] if "zona" in claves else "",
            distribuidor=fila["distribuidor"] if "distribuidor" in claves else "",
            archivo_id=fila["archivo_id"],
            direccion_fs=self.cifrador.descifrar(fila["direccion_fs_cifrada"]),
            productos=fila["productos"],
            periodicidad=fila["periodicidad"],
            estado=fila["estado"],
            fecha_ingreso=fila["fecha_ingreso"],
            fecha_retiro=fila["fecha_retiro"],
            ruta_fs_id=fila["ruta_fs_id"],
            zona_fs=fila["zona_fs"] if "zona_fs" in claves else "",
            numero=fila["numero"],
        )


class EntregaDAO:
    def __init__(self, bd: BaseDatos, cifrador: Cifrador):
        self.bd = bd
        self.cifrador = cifrador

    def guardar(
        self,
        fecha: str,
        suscriptor_id: int,
        estado: str,
        novedad: str,
        usuario_id: int,
    ) -> None:
        self.bd.ejecutar(
            """
            INSERT INTO entrega (fecha, suscriptor_id, estado, novedad, registrado_por, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (suscriptor_id, fecha) DO UPDATE SET
                estado = excluded.estado,
                novedad = excluded.novedad,
                registrado_por = excluded.registrado_por,
                actualizado_en = excluded.actualizado_en
            """,
            (fecha, suscriptor_id, estado, self.cifrador.cifrar(novedad) if novedad else "", usuario_id, ahora_iso()),
        )

    def obtener(self, fecha: str, suscriptor_id: int) -> Entrega | None:
        fila = self.bd.uno(
            "SELECT * FROM entrega WHERE fecha = ? AND suscriptor_id = ?",
            (fecha, suscriptor_id),
        )
        if not fila:
            return None
        return Entrega(
            id=fila["id"],
            fecha=fila["fecha"],
            suscriptor_id=fila["suscriptor_id"],
            estado=fila["estado"],
            novedad=self.cifrador.descifrar(fila["novedad"]),
            registrado_por=fila["registrado_por"],
        )

    def mapa_estado_fecha(self, fecha: str) -> dict[int, tuple[str, str]]:
        return {
            f["suscriptor_id"]: (f["estado"], self.cifrador.descifrar(f["novedad"]))
            for f in self.bd.todos("SELECT suscriptor_id, estado, novedad FROM entrega WHERE fecha = ?", (fecha,))
        }

    def listar_fecha(self, fecha: str, limite: int = 500) -> list[Entrega]:
        filas = self.bd.todos(
            """
            SELECT e.*, s.nombre_cifrado, s.direccion_cifrada, r.zona,
                   COALESCE(d.nombre, '') AS distribuidor
            FROM entrega e
            JOIN suscriptor s ON s.id = e.suscriptor_id
            JOIN ruta r ON r.id = s.ruta_id
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            WHERE e.fecha = ?
            ORDER BY s.id
            LIMIT ?
            """,
            (fecha, limite),
        )
        return [self._mapear(f) for f in filas]

    def buscar(
        self,
        desde: str | None = None,
        hasta: str | None = None,
        estado: str | None = None,
        ruta_id: int | None = None,
        distribuidor_id: int | None = None,
        limite: int = 500,
        suscriptor_ids: list[int] | None = None,
    ) -> list[Entrega]:
        condiciones: list[str] = []
        parametros: list = []
        if suscriptor_ids is not None:
            # shortcut: SQLite admite hasta 32 766 parámetros; con más suscriptores usar una tabla temporal.
            condiciones.append(f"e.suscriptor_id IN ({','.join('?' * len(suscriptor_ids)) or 'NULL'})")
            parametros.extend(suscriptor_ids)
        if desde:
            condiciones.append("e.fecha >= ?")
            parametros.append(desde)
        if hasta:
            condiciones.append("e.fecha <= ?")
            parametros.append(hasta)
        if estado:
            condiciones.append("e.estado = ?")
            parametros.append(estado)
        if ruta_id:
            condiciones.append("s.ruta_id = ?")
            parametros.append(ruta_id)
        if distribuidor_id:
            condiciones.append("r.distribuidor_id = ?")
            parametros.append(distribuidor_id)
        where = " WHERE " + " AND ".join(condiciones) if condiciones else ""
        parametros.append(limite)
        filas = self.bd.todos(
            f"""
            SELECT e.*, s.nombre_cifrado, s.direccion_cifrada, r.zona,
                   COALESCE(d.nombre, 'Sin asignar') AS distribuidor
            FROM entrega e
            JOIN suscriptor s ON s.id = e.suscriptor_id
            JOIN ruta r ON r.id = s.ruta_id
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            {where}
            ORDER BY e.fecha DESC, s.id
            LIMIT ?
            """,
            tuple(parametros),
        )
        return [self._mapear(f) for f in filas]

    def historial_suscriptor(self, suscriptor_id: int, limite: int = 300) -> list[Entrega]:
        filas = self.bd.todos(
            """
            SELECT e.*, s.nombre_cifrado, s.direccion_cifrada, r.zona,
                   COALESCE(d.nombre, '') AS distribuidor
            FROM entrega e
            JOIN suscriptor s ON s.id = e.suscriptor_id
            JOIN ruta r ON r.id = s.ruta_id
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            WHERE e.suscriptor_id = ?
            ORDER BY e.fecha DESC
            LIMIT ?
            """,
            (suscriptor_id, limite),
        )
        return [self._mapear(f) for f in filas]

    # Entregas del día: las programadas (RN-11) y las que tienen registro; sin registro = PENDIENTE.
    DIA = f"""
        WITH dia AS (
            SELECT s.id AS suscriptor_id, {RUTA_DEL_DIA} AS ruta_id,
                   COALESCE(e.estado, 'PENDIENTE') AS estado
            FROM suscriptor s
            LEFT JOIN entrega e ON e.suscriptor_id = s.id AND e.fecha = :fecha
            WHERE e.id IS NOT NULL OR ({PROGRAMADO})
        )
    """

    def estadisticas_fecha(self, fecha: str) -> list[sqlite3.Row]:
        return self.bd.todos(
            self.DIA
            + """
            SELECT r.zona, COALESCE(d.nombre, 'Sin asignar') AS distribuidor,
                   COUNT(*) AS total,
                   SUM(CASE WHEN dia.estado = 'ENTREGADA' THEN 1 ELSE 0 END) AS efectivas,
                   SUM(CASE WHEN dia.estado = 'NO ENTREGADA' THEN 1 ELSE 0 END) AS no_entregadas,
                   SUM(CASE WHEN dia.estado = 'CON NOVEDAD' THEN 1 ELSE 0 END) AS novedades,
                   SUM(CASE WHEN dia.estado = 'PENDIENTE' THEN 1 ELSE 0 END) AS pendientes
            FROM dia
            JOIN ruta r ON r.id = dia.ruta_id
            LEFT JOIN distribuidor d ON d.id = r.distribuidor_id
            GROUP BY r.id
            ORDER BY r.zona
            """,
            parametros_dia(fecha),
        )

    def contar_fecha(self, fecha: str) -> int:
        return int(self.bd.uno("SELECT COUNT(*) FROM entrega WHERE fecha = ?", (fecha,))[0])

    def contar_por_estado(self, fecha: str) -> dict[str, int]:
        filas = self.bd.todos(
            self.DIA + " SELECT estado, COUNT(*) AS total FROM dia GROUP BY estado",
            parametros_dia(fecha),
        )
        return {f["estado"]: f["total"] for f in filas}

    def marcar_entregadas(self, fecha: str, usuario_id: int) -> int:
        """Cierre del día (RF-05, RN-11): las programadas sin novedad quedan ENTREGADA."""
        parametros = parametros_dia(fecha)
        parametros.update(usuario=usuario_id, ahora=ahora_iso())
        cur = self.bd.ejecutar(
            f"""
            INSERT INTO entrega (fecha, suscriptor_id, estado, novedad, registrado_por, actualizado_en)
            SELECT :fecha, s.id, 'ENTREGADA', '', :usuario, :ahora
            FROM suscriptor s
            WHERE {PROGRAMADO}
            ON CONFLICT (suscriptor_id, fecha) DO UPDATE SET
                estado = 'ENTREGADA', registrado_por = excluded.registrado_por,
                actualizado_en = excluded.actualizado_en
            WHERE entrega.estado = 'PENDIENTE'
            """,
            parametros,
        )
        return max(cur.rowcount, 0)

    def borrar_novedades(self, suscriptor_ids: list[int]) -> None:
        marcas = ",".join(["?"] * len(suscriptor_ids))
        self.bd.ejecutar(f"UPDATE entrega SET novedad = '' WHERE suscriptor_id IN ({marcas})", tuple(suscriptor_ids))

    def listar_novedades_fecha(self, fecha: str) -> list[Entrega]:
        return [e for e in self.listar_fecha(fecha, limite=-1) if e.estado in ("NO ENTREGADA", "CON NOVEDAD")]

    def _mapear(self, fila: sqlite3.Row) -> Entrega:
        return Entrega(
            id=fila["id"],
            fecha=fila["fecha"],
            suscriptor_id=fila["suscriptor_id"],
            estado=fila["estado"],
            novedad=self.cifrador.descifrar(fila["novedad"]),
            suscriptor=self.cifrador.descifrar(fila["nombre_cifrado"]),
            direccion=self.cifrador.descifrar(fila["direccion_cifrada"]),
            zona=fila["zona"],
            distribuidor=fila["distribuidor"],
            registrado_por=fila["registrado_por"],
        )


class NovedadSuscripcionDAO:
    def __init__(self, bd: BaseDatos, cifrador: Cifrador):
        self.bd = bd
        self.cifrador = cifrador

    def crear(self, fecha: str, tipo: str, detalle: str, suscriptor_id: int, usuario_id: int) -> int:
        cur = self.bd.ejecutar(
            """
            INSERT INTO novedad_suscripcion (fecha, tipo, detalle, suscriptor_id, usuario_id, registrado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (fecha, tipo, self.cifrador.cifrar(detalle), suscriptor_id, usuario_id, ahora_iso()),
        )
        return int(cur.lastrowid)

    def suprimir_detalles(self, suscriptor_ids: list[int], texto: str) -> None:
        marcas = ",".join(["?"] * len(suscriptor_ids))
        self.bd.ejecutar(
            f"UPDATE novedad_suscripcion SET detalle = ? WHERE suscriptor_id IN ({marcas})",
            (self.cifrador.cifrar(texto), *suscriptor_ids),
        )

    def listar(
        self, fecha: str | None = None, suscriptor_id: int | None = None, limite: int = 500
    ) -> list[NovedadSuscripcion]:
        condiciones, parametros = [], []
        if fecha:
            condiciones.append("n.fecha = ?")
            parametros.append(fecha)
        if suscriptor_id:
            condiciones.append("n.suscriptor_id = ?")
            parametros.append(suscriptor_id)
        where = " WHERE " + " AND ".join(condiciones) if condiciones else ""
        filas = self.bd.todos(
            f"""
            SELECT n.*, s.nombre_cifrado, r.zona, u.nombre AS usuario
            FROM novedad_suscripcion n
            JOIN suscriptor s ON s.id = n.suscriptor_id
            JOIN ruta r ON r.id = s.ruta_id
            JOIN usuario u ON u.id = n.usuario_id
            {where}
            ORDER BY n.fecha DESC, n.id DESC
            LIMIT ?
            """,
            (*parametros, limite),
        )
        return [
            NovedadSuscripcion(
                id=f["id"],
                fecha=f["fecha"],
                tipo=f["tipo"],
                detalle=self.cifrador.descifrar(f["detalle"]),
                suscriptor_id=f["suscriptor_id"],
                suscriptor=self.cifrador.descifrar(f["nombre_cifrado"]),
                zona=f["zona"],
                usuario=f["usuario"],
            )
            for f in filas
        ]


class ReporteDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def guardar(self, fecha: str, total: int, efectivas: int, porcentaje: float | None, usuario_id: int) -> None:
        self.bd.ejecutar(
            """
            INSERT INTO reporte_diario
                (fecha, total_entregas, entregas_efectivas, porcentaje_efectividad, usuario_id, generado_en)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (fecha) DO UPDATE SET
                total_entregas = excluded.total_entregas,
                entregas_efectivas = excluded.entregas_efectivas,
                porcentaje_efectividad = excluded.porcentaje_efectividad,
                usuario_id = excluded.usuario_id,
                generado_en = excluded.generado_en
            """,
            (fecha, total, efectivas, porcentaje, usuario_id, ahora_iso()),
        )

    def obtener(self, fecha: str) -> sqlite3.Row | None:
        return self.bd.uno("SELECT * FROM reporte_diario WHERE fecha = ?", (fecha,))


class RespaldoDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def crear(self, fecha: str, ruta_archivo: str, usuario_id: int, tipo: str = "MANUAL") -> int:
        cur = self.bd.ejecutar(
            "INSERT INTO respaldo (fecha, ruta_archivo, usuario_id, tipo) VALUES (?, ?, ?, ?)",
            (fecha, ruta_archivo, usuario_id, tipo),
        )
        return int(cur.lastrowid)

    def eliminar(self, respaldo_id: int) -> None:
        self.bd.ejecutar("DELETE FROM respaldo WHERE id = ?", (respaldo_id,))

    def listar(self, limite: int = 30, tipo: str | None = None) -> list[Respaldo]:
        condicion = "WHERE r.tipo = ?" if tipo else ""
        filas = self.bd.todos(
            f"""
            SELECT r.*, u.nombre AS usuario FROM respaldo r
            JOIN usuario u ON u.id = r.usuario_id
            {condicion}
            ORDER BY r.fecha DESC, r.id DESC LIMIT ?
            """,
            ((tipo, limite) if tipo else (limite,)),
        )
        return [
            Respaldo(
                id=f["id"], fecha=f["fecha"], ruta_archivo=f["ruta_archivo"], usuario=f["usuario"], tipo=f["tipo"]
            )
            for f in filas
        ]


class EventoDAO:
    def __init__(self, bd: BaseDatos):
        self.bd = bd

    def crear(self, tipo: str, detalle: str, usuario_id: int | None = None) -> None:
        self.bd.ejecutar(
            "INSERT INTO evento (fecha, usuario_id, tipo, detalle) VALUES (?, ?, ?, ?)",
            (ahora_iso(), usuario_id, tipo, detalle),
        )

    def ultimo(self, tipos: tuple[str, ...]) -> dict | None:
        fila = self.bd.uno(
            f"SELECT * FROM evento WHERE tipo IN ({','.join(['?'] * len(tipos))}) ORDER BY id DESC LIMIT 1",
            tipos,
        )
        return dict(fila) if fila else None

    def listar(self, limite: int = 50) -> list[dict]:
        filas = self.bd.todos(
            """
            SELECT e.*, COALESCE(u.nombre, 'sistema') AS usuario
            FROM evento e LEFT JOIN usuario u ON u.id = e.usuario_id
            ORDER BY e.id DESC LIMIT ?
            """,
            (limite,),
        )
        return [dict(f) for f in filas]
