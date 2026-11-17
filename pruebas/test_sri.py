"""Pruebas automatizadas del SRI (requisitos y reglas de negocio del informe v5.3)."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

from sri.contexto import Contexto
from sri.dominio.periodicidad import DIARIA, etiqueta, parsear, separar_nombre
from sri.seguridad import Cifrador
from sri.util import Conflicto, DatosInvalidos, PermisoDenegado, formato_fecha

ENCABEZADO = ["N°", "NOMBRE", "DIRECCION", "TIE", "PT", "RUTA"]
LISTADO_BASE = {
    "CARLOS": [
        [1, "Ana Pérez", "Calle 10 # 5-20", "X", "", "CP"],
        [2, "Luis Gómez S-D", "Avenida 3 # 2-10", "X", "X", "CP"],
        [3, "Marta Ruiz L-V", "Carrera 8 # 9-40", "X", "", "CP"],
    ]
}


class BaseSRI(unittest.TestCase):
    def setUp(self) -> None:
        self.temporal = Path(tempfile.mkdtemp(prefix="sri_pruebas_"))
        self._respaldos_antes = os.environ.get("SRI_BACKUP_DIR")
        os.environ["SRI_BACKUP_DIR"] = str(self.temporal / "respaldos")
        self.ctx = Contexto(
            db_path=self.temporal / "prueba.db",
            key_path=self.temporal / "prueba.key",
        )
        self.secretaria = self.ctx.auth.iniciar_sesion("secretaria", "Sri2026*")
        self.gerencia = self.ctx.auth.iniciar_sesion("gerencia", "Sri2026*")
        self.hoy = date.today()
        # Fechas pasadas con día de la semana conocido (RN-11 depende de la periodicidad).
        self.lunes = self.hoy - timedelta(days=self.hoy.weekday() + 7)
        self.sabado = self.lunes + timedelta(days=5)

    def tearDown(self) -> None:
        self.ctx.cerrar()
        if self._respaldos_antes is None:
            os.environ.pop("SRI_BACKUP_DIR", None)
        else:
            os.environ["SRI_BACKUP_DIR"] = self._respaldos_antes
        shutil.rmtree(self.temporal, ignore_errors=True)

    # ------------------------------------------------------------------ #
    def crear_listado(self, nombre: str, hojas: dict[str, list], encabezado: list | None = None) -> Path:
        ruta = self.temporal / nombre
        libro = Workbook()
        libro.remove(libro.active)
        for titulo, filas in hojas.items():
            ws = libro.create_sheet(titulo)
            ws.append(encabezado or ENCABEZADO)
            for fila in filas:
                ws.append(fila)
        libro.save(ruta)
        return ruta

    def importar_demo(self, filas: list | None = None, hojas: dict | None = None, nombre: str = "listado.xlsx"):
        hojas = hojas or ({"CARLOS": filas} if filas else LISTADO_BASE)
        return self.ctx.importacion.importar(self.secretaria, self.crear_listado(nombre, hojas))

    def preparar_ruta(self, zona: str = "Centro", distribuidor: str = "Carlos"):
        dist = self.ctx.operativo.crear_distribuidor(self.secretaria, distribuidor, "3001234567")
        ruta = self.ctx.operativo.crear_ruta(self.secretaria, zona, dist)
        return dist, ruta

    def suscriptor(self, texto: str):
        return self.ctx.suscriptores.listar(texto=texto)[0]

    def f(self, dia: date) -> str:
        return formato_fecha(dia)


class PruebasAutenticacion(BaseSRI):
    def test_login_valido_e_invalido(self):
        self.assertEqual(self.secretaria.rol, "Secretaria")
        self.assertEqual(self.gerencia.rol, "Gerencia")
        with self.assertRaises(DatosInvalidos):
            self.ctx.auth.iniciar_sesion("secretaria", "incorrecta")
        with self.assertRaises(DatosInvalidos):
            self.ctx.auth.iniciar_sesion("noexiste", "Sri2026*")

    def test_contrasenas_y_bitacora_sin_lo_escrito_en_usuario(self):
        self.assertTrue(self.secretaria.cambiar_contrasena)  # entró con la de demostración
        for nueva in ("", "corta", "Sri2026*"):
            with self.assertRaises(DatosInvalidos):
                self.ctx.auth.cambiar_contrasena(self.secretaria, "Sri2026*", nueva, nueva)
        self.ctx.auth.cambiar_contrasena(self.secretaria, "Sri2026*", "Propia-2026", "Propia-2026")
        self.assertFalse(self.ctx.auth.iniciar_sesion("secretaria", "Propia-2026").cambiar_contrasena)
        with self.assertRaises(DatosInvalidos):
            self.ctx.auth.iniciar_sesion("MiClaveSecreta123", "x")  # contraseña escrita en el campo usuario
        bitacora = " ".join(e["detalle"] for e in self.ctx.auditoria.listar(20))
        self.assertNotIn("MiClaveSecreta123", bitacora)

    def test_rn08_permisos_por_rol(self):
        archivo = self.crear_listado("x.xlsx", {"H": []})
        with self.assertRaises(PermisoDenegado):
            self.ctx.importacion.importar(self.gerencia, archivo)
        with self.assertRaises(PermisoDenegado):
            self.ctx.consultas.generar_reporte(self.secretaria, "01/01/2026")
        with self.assertRaises(PermisoDenegado):
            self.ctx.respaldos.crear(self.secretaria, self.temporal / "x.sribak")
        with self.assertRaises(PermisoDenegado):
            self.ctx.operativo.crear_distribuidor(self.gerencia, "Pedro", "3001112233")
        with self.assertRaises(PermisoDenegado):  # RF-09 es de la Secretaría
            self.ctx.suscripciones.registrar_retiro(self.gerencia, 1, self.f(self.hoy))


class PruebasPeriodicidad(unittest.TestCase):
    def test_separar_nombre_y_etiquetas(self):
        casos = {
            "JUAN PÉREZ S-D": ("JUAN PÉREZ", "S-D", True),
            "Ana Ruiz": ("Ana Ruiz", "Diaria", True),
            "Luis Mora L-V": ("Luis Mora", "L-V", True),
            "Rosa Peña D": ("Rosa Peña", "D", True),
            "Eva Ríos miércoles, sábado y domingo": ("Eva Ríos", "Miércoles, sábado y domingo", True),
            "Pedro Gil (L-S)": ("Pedro Gil", "L-S", True),
            "Raro Caso L-X-V": ("Raro Caso L-X-V", "Diaria", False),
        }
        for entrada, (nombre, texto, reconocida) in casos.items():
            base, mascara, ok = separar_nombre(entrada)
            self.assertEqual((base, etiqueta(mascara), ok), (nombre, texto, reconocida), entrada)
        self.assertEqual(parsear("Diaria"), DIARIA)
        self.assertEqual(parsear("lunes a viernes"), "1111100")
        self.assertIsNone(parsear("cada tanto"))


class PruebasImportacion(BaseSRI):
    def test_listado_multihoja_periodicidad_productos_y_rutas(self):
        self.ctx.operativo.crear_distribuidor(self.secretaria, "Carlos Pérez", "3001234567")
        hojas = {
            "CARLOS": [
                [1, "Ana Pérez", "Calle 10 # 5-20", "X", "", "CP"],
                [2, "Luis Gómez S-D", "Avenida 3 # 2-10", "X", "X", "CP"],
                [3, "Sin Producto", "Calle 1 # 1-1", "", "", "CP"],
                [4, "Sin Dirección", "", "X", "", "CP"],
                [5, "Raro Caso L-X-V", "Calle 2 # 2-2", "X", "", "CP"],
                [6, "Beatriz Mora", "Calle 3 # 3-3", "X", "", "AL"],  # iniciales de un distribuidor retirado
                [None, None, None, None, None, None],
            ],
            "CARLOS (2)": [[1, "ANA PEREZ", "calle 10 # 5-20", "X", "X", "CP"]],  # hoja repetida: prevalece la última
            "MARIA": [[1, "Rosa Peña D", "Carrera 4 # 4-4", "X", "", "MR"]],  # sin distribuidor activo
        }
        resumen = self.importar_demo(hojas=hojas)
        self.assertEqual(resumen.hojas, 3)
        self.assertEqual(resumen.leidos, 8)
        self.assertEqual((resumen.importados, resumen.actualizados, resumen.rechazados), (5, 1, 2))
        self.assertTrue(resumen.cuadra)  # RN-06 / RNF-04
        motivos = " ".join(r.motivo for r in resumen.rechazos)
        self.assertIn("producto", motivos)
        self.assertIn("dirección", motivos)
        revisar = " ".join(r.motivo for r in resumen.revisar)
        self.assertIn("Periodicidad no reconocida", revisar)
        self.assertIn("«MR» no corresponde a un distribuidor activo", revisar)
        self.assertIn("«AL» no corresponde a un distribuidor activo", revisar)

        luis = self.suscriptor("Luis")
        self.assertEqual(luis.nombre, "Luis Gómez")  # la periodicidad se separa del nombre
        self.assertEqual(luis.periodicidad, "0000011")
        self.assertEqual(luis.productos, "TIE,PT")
        ana = self.suscriptor("Ana")
        self.assertEqual(ana.productos, "TIE,PT")  # actualizada por la hoja más reciente
        rutas = {r.zona: r for r in self.ctx.operativo.listar_rutas(self.secretaria)}
        self.assertEqual(rutas["CP"].distribuidor, "Carlos Pérez")  # hoja CARLOS → Carlos Pérez
        self.assertIsNone(rutas["MR"].distribuidor_id)
        self.assertIsNone(rutas["AL"].distribuidor_id)  # no se asigna a Carlos por estar en su hoja

        conexion = sqlite3.connect(self.ctx.bd.ruta)
        try:
            crudos = " ".join(f[0] + f[1] for f in conexion.execute("SELECT nombre_cifrado, direccion_cifrada FROM suscriptor"))
        finally:
            conexion.close()
        self.assertNotIn("Ana", crudos)  # RNF-01
        self.assertIn("enc:v1:", crudos)

    def test_rn07_dos_direcciones_es_un_solo_suscriptor(self):
        hojas = {
            "CARLOS": [[1, "Pedro Mora L-V", "Oficina Calle 5 # 1-10", "X", "", "CP"]],
            "MARTA": [[1, "Pedro Mora S-D", "Casa Carrera 9 # 7-70", "X", "", "MS"]],
        }
        resumen = self.importar_demo(hojas=hojas)
        self.assertEqual((resumen.importados, resumen.actualizados), (1, 1))
        self.assertEqual(self.ctx.suscriptores.contar(), 1)
        pedro = self.suscriptor("Pedro")
        self.assertEqual(pedro.direccion, "Oficina Calle 5 # 1-10")
        self.assertEqual(pedro.direccion_fs, "Casa Carrera 9 # 7-70")
        self.assertEqual(pedro.periodicidad, DIARIA)
        self.assertEqual(pedro.zona_fs, "MS")
        # El sábado la entrega va a la casa, por la ruta MS.
        sabado = self.ctx.suscriptores.listar_del_dia(self.sabado.isoformat())
        self.assertEqual([(s.direccion, s.zona) for s in sabado], [("Casa Carrera 9 # 7-70", "MS")])
        repetida = self.importar_demo(hojas=hojas)
        self.assertEqual((repetida.importados, repetida.actualizados), (0, 2))
        self.assertEqual(self.ctx.suscriptores.contar(), 1)

    def test_rf01_formato_real_dos_listas_y_columnas_sin_encabezado(self):
        # Como la Figura 12 del Anexo D: N°, TIE y RUTA sin encabezado; dos listas por hoja; G vacía.
        encabezado = [None, "NOMBRE", "DIRECCION", None, "PT", None, None, None, "NOMBRE", "DIRECCION", None, "PT", None, "TELEFONO"]
        filas = [
            [1, "Suscriptor 001", "Calle 1 # 1-1", "X", None, "MI", None, 1, "Suscriptor 101 L-V", "Calle 101 # 1-1", "X", "X", "AL", "3001112233"],
            [2, "Suscriptor 006 MIERCOLES", "Calle 6 # 6-6", "X", None, "MI", None, 2, "Suscriptor 102 D", "Calle 102 # 2-2", "X", None, "AL", None],
            [3, "Suscriptor 003", "Calle 3 # 3-3", "X", "X", "MI", None, None, None, None, None, None, None, None],
        ]
        resumen = self.ctx.importacion.importar(self.secretaria, self.crear_listado("real.xlsx", {"Repartidor 1": filas}, encabezado))
        self.assertEqual((resumen.leidos, resumen.importados, resumen.rechazados), (5, 5, 0))  # RNF-04: nadie se pierde
        self.assertEqual(self.suscriptor("006").periodicidad, "0010000")  # «MIERCOLES»
        self.assertEqual(self.suscriptor("101").productos, "TIE,PT")
        self.assertEqual(self.suscriptor("102").zona, "AL")
        sin_leer = [r for r in resumen.revisar if "columna N" in r.motivo]
        self.assertEqual(len(sin_leer), 1)  # el teléfono a la derecha no se pierde en silencio
        self.assertIn("1 dato(s)", sin_leer[0].motivo)
        self.assertIn("lista 2", " ".join(r.hoja for r in resumen.revisar))

    def test_importacion_repetida_no_duplica(self):
        self.importar_demo()
        resumen = self.importar_demo()
        self.assertEqual(resumen.importados, 0)
        self.assertEqual(resumen.actualizados, 3)
        self.assertEqual(self.ctx.suscriptores.contar(), 3)

    def test_archivo_sin_columnas_obligatorias_no_modifica(self):
        archivo = self.crear_listado("incompleto.xlsx", {"CARLOS": [[1, "Ana", "Calle 1 # 2-3"]]}, ["N°", "Nombre", "Dirección"])
        with self.assertRaises(DatosInvalidos) as contexto:
            self.ctx.importacion.importar(self.secretaria, archivo)
        self.assertIn("TIE", str(contexto.exception))
        self.assertEqual(self.ctx.suscriptores.contar(), 0)
        self.assertEqual(self.ctx.archivos.listar(), [])

    def test_archivo_danado_mensaje_claro_y_no_modifica(self):
        archivo = self.temporal / "danado.xlsx"
        archivo.write_bytes(b"esto no es un libro de Excel")
        with self.assertRaises(DatosInvalidos) as contexto:
            self.ctx.importacion.importar(self.secretaria, archivo)
        self.assertIn("dañado", str(contexto.exception))
        self.assertEqual(self.ctx.suscriptores.contar(), 0)
        self.assertEqual(self.ctx.archivos.listar(), [])

    def test_archivo_csv(self):
        archivo = self.temporal / "listado.csv"
        archivo.write_text(
            "N°;Nombre;Dirección;TIE;PT;Ruta\n1;Pedro Rojas;Calle 50 # 1-2;X;;Sur\n2;Sara Díaz;Calle 51 # 1-2;X;;Sur\n",
            encoding="utf-8",
        )
        resumen = self.ctx.importacion.importar(self.secretaria, archivo)
        self.assertEqual(resumen.importados, 2)

    def test_bitacora_sin_datos_personales(self):
        self.importar_demo()
        eventos = self.ctx.auditoria.listar(50)
        detalle = " ".join(evento["detalle"] for evento in eventos)
        self.assertIn("IMPORTACION", " ".join(evento["tipo"] for evento in eventos))
        self.assertNotIn("Ana", detalle)

    def test_rnf02_10000_registros_en_10_segundos(self):
        filas = [[i, f"Suscriptor {i:05d}", f"Calle {i} # {i % 90}-{i % 50}", "X", "", f"R{i % 20}"] for i in range(10_000)]
        archivo = self.crear_listado("grande.xlsx", {"CARLOS": filas})
        inicio = time.perf_counter()
        resumen = self.ctx.importacion.importar(self.secretaria, archivo)
        duracion = time.perf_counter() - inicio
        self.assertEqual(resumen.importados, 10_000)
        self.assertTrue(resumen.cuadra)
        self.assertLessEqual(duracion, 10, f"La importación tardó {duracion:.2f} s")
        # RNF-02 (v5.3): registrar una novedad se confirma en menos de 2 segundos.
        ruta = {r.zona: r.id for r in self.ctx.operativo.listar_rutas(self.secretaria)}["R1"]
        inicio = time.perf_counter()
        self.ctx.suscripciones.registrar_ingreso(
            self.secretaria, self.f(self.hoy), "Nueva Persona", "Calle 99 # 9-99", ["TIE"], "Diaria", ruta
        )
        self.assertLess(time.perf_counter() - inicio, 2)
        print(f"[RNF-02: importación de 10.000 registros en {duracion:.2f} s]", end=" ")


class PruebasSuscripciones(BaseSRI):
    def setUp(self) -> None:
        super().setUp()
        self.importar_demo()
        self.ruta_cp = {r.zona: r.id for r in self.ctx.operativo.listar_rutas(self.secretaria)}["CP"]

    def ingreso(self, **cambios):
        datos = dict(
            fecha=self.f(self.lunes), nombre="Nora Vera", direccion="Calle 30 # 4-15",
            productos=["TIE"], periodicidad="L-V", ruta_id=self.ruta_cp,
        )
        datos.update(cambios)
        return self.ctx.suscripciones.registrar_ingreso(self.secretaria, **datos)

    def test_rf09_ingreso_validaciones_y_aviso(self):
        with self.assertRaises(DatosInvalidos):
            self.ingreso(productos=[])
        with self.assertRaises(DatosInvalidos):
            self.ingreso(direccion="Centro")  # dirección incompleta: se consulta a la editorial
        with self.assertRaises(DatosInvalidos):
            self.ingreso(periodicidad="cada tanto")
        with self.assertRaises(DatosInvalidos):
            self.ingreso(fecha=self.f(self.hoy + timedelta(days=1)))
        resultado = self.ingreso()
        self.assertIsNone(resultado["aviso"])
        with self.assertRaises(Conflicto):
            self.ingreso()
        homonimo = self.ingreso(direccion="Carrera 1 # 1-1")
        self.assertIsNotNone(homonimo["aviso"])
        nora = self.ctx.suscriptores.obtener(resultado["id"])
        self.assertEqual((nora.periodicidad, nora.fecha_ingreso), ("1111100", self.lunes.isoformat()))
        novedades = self.ctx.suscripciones.novedades_del_dia(self.secretaria, self.f(self.lunes))
        self.assertEqual([n.tipo for n in novedades], ["INGRESO", "INGRESO"])
        # No estaba programada antes de su ingreso.
        antes = self.ctx.suscriptores.listar_del_dia((self.lunes - timedelta(days=7)).isoformat())
        self.assertNotIn(resultado["id"], [s.id for s in antes])

    def test_rn12_retiro_no_borra_y_sale_de_la_programacion(self):
        ana = self.suscriptor("Ana")
        self.ctx.suscripciones.registrar_retiro(self.secretaria, ana.id, self.f(self.lunes), "Canceló")
        retirada = self.ctx.suscriptores.obtener(ana.id)
        self.assertEqual((retirada.estado, retirada.fecha_retiro), ("RETIRADO", self.lunes.isoformat()))
        del_lunes = [s.id for s in self.ctx.suscriptores.listar_del_dia(self.lunes.isoformat())]
        del_domingo_previo = [s.id for s in self.ctx.suscriptores.listar_del_dia((self.lunes - timedelta(days=1)).isoformat())]
        self.assertNotIn(ana.id, del_lunes)
        self.assertIn(ana.id, del_domingo_previo)  # el historial anterior se conserva
        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.registrar_entrega(self.secretaria, ana.id, self.f(self.lunes), "NO ENTREGADA")
        with self.assertRaises(Conflicto):
            self.ctx.suscripciones.registrar_retiro(self.secretaria, ana.id, self.f(self.lunes))
        self.ingreso(nombre="Ana Pérez", direccion="Calle 10 # 5-20", periodicidad="Diaria")  # reingreso
        self.assertTrue(self.ctx.suscriptores.obtener(ana.id).activo)
        self.assertEqual(self.ctx.suscriptores.contar(), 3)

    def test_depuracion_anual_anonimiza_retirados_antiguos(self):
        ana, luis = self.suscriptor("Ana"), self.suscriptor("Luis")
        hace_dos_anios = self.f(self.hoy - timedelta(days=730))
        self.ctx.operativo.registrar_entrega(self.secretaria, ana.id, self.f(self.hoy - timedelta(days=800)), "CON NOVEDAD", "Reclamo de Ana")
        self.ctx.suscripciones.registrar_retiro(self.secretaria, ana.id, hace_dos_anios, "Ana se mudó")
        self.ctx.suscripciones.registrar_retiro(self.secretaria, luis.id, self.f(self.lunes))  # reciente: no se toca
        with self.assertRaises(PermisoDenegado):
            self.ctx.suscripciones.depurar_retirados(self.secretaria, 12)
        self.assertEqual(self.ctx.suscripciones.depurar_retirados(self.gerencia, 12), 1)
        anonima = self.ctx.suscriptores.obtener(ana.id)
        self.assertEqual((anonima.nombre, anonima.direccion, anonima.estado), (f"Suscriptor anonimizado {ana.id}", "", "RETIRADO"))
        historial = self.ctx.consultas.historial_suscriptor(self.gerencia, ana.id)
        self.assertEqual([e.novedad for e in historial], [""])  # la entrega se conserva, sin el texto
        _, novedades = self.ctx.consultas.ficha_suscriptor(self.gerencia, ana.id)
        self.assertNotIn("Ana", " ".join(n.detalle for n in novedades))
        self.assertEqual(self.ctx.suscriptores.obtener(luis.id).nombre, "Luis Gómez")
        self.assertEqual(self.ctx.suscripciones.depurar_retirados(self.gerencia, 12), 0)  # no repite

    def test_rf06_buscar_suscriptores_sin_entregas_y_ficha(self):
        marta = self.suscriptor("Marta")
        self.ctx.suscripciones.registrar_retiro(self.secretaria, marta.id, self.f(self.lunes), "Canceló")
        self.assertEqual(self.ctx.consultas.buscar_entregas(self.secretaria, {"texto": "Marta"}), [])  # no tiene entregas
        encontrados = self.ctx.consultas.buscar_suscriptores(self.gerencia, {"texto": "Marta"})
        self.assertEqual([s.nombre for s in encontrados], ["Marta Ruiz"])
        self.assertEqual(self.ctx.consultas.buscar_suscriptores(self.gerencia, {"estado": "RETIRADO"})[0].id, marta.id)
        self.assertEqual(len(self.ctx.consultas.buscar_suscriptores(self.gerencia, {"estado": "ACTIVO"})), 2)
        suscriptor, novedades = self.ctx.consultas.ficha_suscriptor(self.gerencia, marta.id)
        self.assertEqual((suscriptor.estado, suscriptor.fecha_retiro), ("RETIRADO", self.lunes.isoformat()))
        self.assertEqual([n.tipo for n in novedades], ["RETIRO"])

    def test_rf09_cambio(self):
        marta = self.suscriptor("Marta")
        campos = self.ctx.suscripciones.registrar_cambio(
            self.secretaria, marta.id, self.f(self.lunes), "Marta Ruiz", "Carrera 8 # 9-99",
            ["TIE", "PT"], "Diaria", self.ruta_cp,
        )
        self.assertEqual(campos, ["dirección", "productos", "periodicidad"])
        actual = self.ctx.suscriptores.obtener(marta.id)
        self.assertEqual((actual.direccion, actual.productos, actual.periodicidad), ("Carrera 8 # 9-99", "TIE,PT", DIARIA))
        with self.assertRaises(DatosInvalidos):
            self.ctx.suscripciones.registrar_cambio(
                self.secretaria, marta.id, self.f(self.lunes), "Marta Ruiz", "Carrera 8 # 9-99",
                ["TIE", "PT"], "Diaria", self.ruta_cp,
            )


class PruebasOperacion(BaseSRI):
    def test_rutas_y_rn01(self):
        dist1, ruta = self.preparar_ruta()
        dist2 = self.ctx.operativo.crear_distribuidor(self.secretaria, "Pedro", "3105556677")

        with self.assertRaises(Conflicto):
            self.ctx.operativo.crear_ruta(self.secretaria, "centro")

        self.ctx.operativo.asignar_ruta(self.secretaria, ruta, dist2)
        actual = self.ctx.operativo.listar_rutas(self.secretaria)[0]
        self.assertEqual(actual.distribuidor_id, dist2)  # RN-01: un solo distribuidor

        with self.assertRaises(Conflicto):  # RN-02
            self.ctx.operativo.cambiar_estado_distribuidor(self.secretaria, dist2, False)

        self.ctx.operativo.asignar_ruta(self.secretaria, ruta, None)
        self.ctx.operativo.cambiar_estado_distribuidor(self.secretaria, dist2, False)
        inactivo = [d for d in self.ctx.operativo.listar_distribuidores(self.secretaria) if d.id == dist2][0]
        self.assertFalse(inactivo.activo)
        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.asignar_ruta(self.secretaria, ruta, dist2)

    def test_rn03_rn04_entregas(self):
        self.importar_demo()
        suscriptor = self.suscriptor("Ana")
        hoy = self.f(self.hoy)

        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.registrar_entrega(self.secretaria, suscriptor.id, hoy, "PERDIDA")
        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.registrar_entrega(self.secretaria, suscriptor.id, self.f(self.hoy + timedelta(days=1)), "NO ENTREGADA")
        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.registrar_entrega(self.secretaria, suscriptor.id, hoy, "CON NOVEDAD", "")

        self.ctx.operativo.registrar_entrega(self.secretaria, suscriptor.id, hoy, "CON NOVEDAD", "Ejemplar faltante")
        self.assertEqual(self.ctx.suscriptores.obtener(suscriptor.id).novedades, "Ejemplar faltante")
        conexion = sqlite3.connect(self.ctx.bd.ruta)
        try:
            crudo = conexion.execute("SELECT novedad FROM entrega WHERE suscriptor_id = ?", (suscriptor.id,)).fetchone()[0]
        finally:
            conexion.close()
        self.assertTrue(crudo.startswith("enc:v1:"))  # RNF-01: novedad cifrada
        self.assertNotIn("Ejemplar", crudo)

    def test_rn11_programacion_y_cierre_del_dia(self):
        self.importar_demo()  # Ana diaria, Luis S-D, Marta L-V
        nombres = lambda dia: sorted(s.nombre for s in self.ctx.suscriptores.listar_del_dia(dia.isoformat()))
        self.assertEqual(nombres(self.lunes), ["Ana Pérez", "Marta Ruiz"])
        self.assertEqual(nombres(self.sabado), ["Ana Pérez", "Luis Gómez"])

        marta = self.suscriptor("Marta")
        self.ctx.operativo.registrar_entrega(self.secretaria, marta.id, self.f(self.lunes), "NO ENTREGADA")
        antes = self.ctx.consultas.generar_reporte(self.gerencia, self.f(self.lunes))
        self.assertEqual((antes.total, antes.efectivas, antes.pendientes), (2, 0, 1))

        cierre = self.ctx.operativo.cerrar_dia(self.secretaria, self.f(self.lunes))
        self.assertEqual(cierre["marcadas"], 1)  # solo Ana; la novedad de Marta se conserva
        self.assertTrue(cierre["respaldo"] and cierre["respaldo"].exists())  # RF-07: respaldo diario
        self.assertEqual(self.ctx.operativo.cerrar_dia(self.secretaria, self.f(self.lunes))["marcadas"], 0)

        reporte = self.ctx.consultas.generar_reporte(self.gerencia, self.f(self.lunes))
        self.assertEqual((reporte.total, reporte.efectivas, reporte.porcentaje), (2, 1, 50.0))  # RN-05
        self.assertEqual([e.suscriptor for e in reporte.novedades_entrega], ["Marta Ruiz"])
        with self.assertRaises(DatosInvalidos):
            self.ctx.operativo.cerrar_dia(self.secretaria, self.f(self.hoy + timedelta(days=1)))

    def test_reporte_sin_programadas_y_exportes(self):
        vacio = self.ctx.consultas.generar_reporte(self.gerencia, self.f(self.lunes))
        self.assertTrue(vacio.sin_datos)
        self.assertIsNone(vacio.porcentaje)
        self.assertIsNone(self.ctx.reportes.obtener(self.lunes.isoformat()))

        self.importar_demo()
        ana = self.suscriptor("Ana")
        self.ctx.operativo.registrar_entrega(self.secretaria, ana.id, self.f(self.lunes), "CON NOVEDAD", "Reclamo")
        reporte = self.ctx.consultas.generar_reporte(self.gerencia, self.f(self.lunes))
        self.assertIsNotNone(self.ctx.reportes.obtener(self.lunes.isoformat()))
        html = self.ctx.consultas.exportar_html(self.gerencia, reporte, self.temporal / "r.html").read_text(encoding="utf-8")
        self.assertIn("Novedades del día", html)
        self.assertIn("Reclamo", html)
        csv = self.ctx.consultas.exportar_csv(self.gerencia, reporte, self.temporal / "r.csv").read_text(encoding="utf-8-sig")
        self.assertIn("Entregas programadas;2", csv)

    def test_consultas_filtros_e_historial(self):
        self.importar_demo()
        luis = self.suscriptor("Luis")
        self.ctx.operativo.registrar_entrega(self.secretaria, luis.id, self.f(self.sabado), "ENTREGADA")
        resultados = self.ctx.consultas.buscar_entregas(
            self.secretaria, {"texto": "luis", "desde": self.f(self.sabado), "hasta": self.f(self.sabado)}
        )
        self.assertEqual(len(resultados), 1)
        self.assertEqual(len(self.ctx.consultas.historial_suscriptor(self.secretaria, luis.id)), 1)
        self.assertEqual(self.ctx.consultas.buscar_entregas(self.secretaria, {"texto": "inexistente"}), [])

    def test_busqueda_encuentra_suscriptores_fuera_del_limite(self):
        filas = [[i, f"Cliente {i:04d}", f"Calle {i} # 1-1", "X", "", "CP"] for i in range(1_500)]
        self.importar_demo(filas)
        encontrados = self.ctx.consultas.suscriptores_con_estado(
            self.secretaria, self.f(self.lunes), texto="Cliente 1499", limite=300
        )
        self.assertEqual([f["suscriptor"].nombre for f in encontrados], ["Cliente 1499"])
        self.ctx.operativo.registrar_entrega(self.secretaria, encontrados[0]["suscriptor"].id, self.f(self.lunes), "ENTREGADA")
        entregas = self.ctx.consultas.buscar_entregas(self.secretaria, {"texto": "cliente 1499", "limite": 10})
        self.assertEqual(len(entregas), 1)

    def test_rf02_ruta_imprimible_por_secciones(self):
        carlos = self.ctx.operativo.crear_distribuidor(self.secretaria, "Carlos Pérez", "3001234567")
        self.importar_demo()
        secciones = self.ctx.operativo.secciones_ruta(self.secretaria, carlos)
        nombres = {titulo: [s.nombre for s, _d, _z in filas] for titulo, filas in secciones.items()}
        self.assertEqual(nombres["Entregas diarias"], ["Ana Pérez", "Marta Ruiz"])
        self.assertEqual(nombres["Sábados y domingos"], ["Luis Gómez"])
        self.assertEqual(nombres["Portafolio"], ["Luis Gómez"])
        html = self.ctx.operativo.exportar_ruta_html(self.secretaria, carlos, self.temporal / "ruta.html").read_text(encoding="utf-8")
        self.assertIn("Sábados y domingos", html)
        self.assertIn("Ley 1581", html)


class PruebasRespaldo(BaseSRI):
    def test_rn09_respaldo_diario_unico_y_conserva_siete(self):
        carpeta = self.temporal / "respaldos"
        carpeta.mkdir()
        for dias in range(8, 0, -1):  # ocho respaldos diarios anteriores
            dia = self.hoy - timedelta(days=dias)
            archivo = carpeta / f"sri_diario_{dia:%Y%m%d}.sribak"
            archivo.write_bytes(b"SRIBAK1")
            self.ctx.respaldos_dao.crear(f"{dia.isoformat()} 18:00:00", str(archivo), self.gerencia.usuario_id, "DIARIO")
        ruta = self.ctx.respaldos.respaldo_automatico(self.secretaria.usuario_id)
        self.assertTrue(ruta.exists())
        self.assertIsNone(self.ctx.respaldos.respaldo_automatico(self.secretaria.usuario_id))  # uno por día
        diarios = self.ctx.respaldos_dao.listar(100, tipo="DIARIO")
        self.assertEqual(len(diarios), 7)
        self.assertEqual(len(list(carpeta.glob("sri_diario_*.sribak"))), 7)
        self.assertFalse((carpeta / f"sri_diario_{self.hoy - timedelta(days=8):%Y%m%d}.sribak").exists())

    def test_rf07_copia_drive_y_avisos(self):
        self.assertTrue(any("Google Drive" in a for a in self.ctx.respaldos.avisos()))
        with self.assertRaises(DatosInvalidos):
            self.ctx.respaldos.copiar_a_drive(self.gerencia, self.temporal / "no_existe")
        drive = self.temporal / "Google Drive"
        drive.mkdir()
        copia = self.ctx.respaldos.copiar_a_drive(self.gerencia, drive)
        self.assertTrue(copia.exists())
        self.assertTrue(copia.read_bytes().startswith(b"SRIBAK1"))  # en la nube queda cifrado
        self.assertEqual(self.ctx.respaldos.estado(self.gerencia)["dias_drive"], 0)
        avisos = self.ctx.respaldos.avisos()
        self.assertEqual(len(avisos), 1)
        self.assertIn("verificado", avisos[0])  # falta la prueba mensual de restauración
        resultado = self.ctx.respaldos.verificar(self.gerencia, copia)
        self.assertEqual(resultado["suscriptores"], 0)
        self.assertEqual(self.ctx.respaldos.avisos(), [])

    def test_rf07_fallo_del_respaldo_diario_se_avisa(self):
        bloqueo = self.temporal / "bloqueo"
        bloqueo.write_text("no es carpeta")
        os.environ["SRI_BACKUP_DIR"] = str(bloqueo)
        self.assertIsNone(self.ctx.respaldos.respaldo_automatico(self.secretaria.usuario_id))
        self.assertTrue(any("falló" in a for a in self.ctx.respaldos.avisos()))

    def test_rf07_verificar_respaldo_y_copia_de_la_clave(self):
        self.importar_demo()
        archivo = self.ctx.respaldos.crear(self.gerencia, self.temporal / "r.sribak")
        self.ctx.operativo.crear_distribuidor(self.secretaria, "Posterior", "3009998877")
        resultado = self.ctx.respaldos.verificar(self.gerencia, archivo)
        self.assertEqual(resultado["suscriptores"], 3)
        # Verificar no reemplaza la base: lo creado después del respaldo sigue ahí.
        self.assertIn("Posterior", [d.nombre for d in self.ctx.operativo.listar_distribuidores(self.secretaria)])
        dañado = self.temporal / "d.sribak"
        dañado.write_bytes(b"SRIBAK1" + b"x" * 64)
        with self.assertRaises(DatosInvalidos):
            self.ctx.respaldos.verificar(self.gerencia, dañado)
        with self.assertRaises(PermisoDenegado):
            self.ctx.respaldos.verificar(self.secretaria, archivo)

        usb = self.temporal / "USB"
        usb.mkdir()
        copia = self.ctx.respaldos.guardar_copia_clave(self.gerencia, usb)
        self.assertEqual(copia.read_bytes(), (self.temporal / "prueba.key").read_bytes())
        self.ctx.respaldos.guardar_copia_clave(self.gerencia, usb)  # la misma clave otra vez: sin error
        otra = self.temporal / "OTRA"
        otra.mkdir()
        (otra / "sri.key").write_bytes(b"0" * 32)
        with self.assertRaises(Conflicto):  # nunca pisa una clave distinta
            self.ctx.respaldos.guardar_copia_clave(self.gerencia, otra)
        self.assertEqual((otra / "sri.key").read_bytes(), b"0" * 32)

    def test_respaldo_cifrado_y_restauracion(self):
        self.importar_demo()
        self.preparar_ruta(zona="Occidente", distribuidor="Original")
        archivo = self.temporal / "respaldo.sribak"
        ruta = self.ctx.respaldos.crear(self.gerencia, archivo)
        contenido = ruta.read_bytes()
        self.assertTrue(contenido.startswith(b"SRIBAK1"))
        self.assertNotIn(b"SQLite format 3", contenido)

        self.ctx.operativo.crear_distribuidor(self.secretaria, "Temporal", "3009998877")
        self.ctx.respaldos.restaurar(self.gerencia, archivo)
        nombres = [d.nombre for d in self.ctx.operativo.listar_distribuidores(self.secretaria)]
        self.assertIn("Original", nombres)
        self.assertNotIn("Temporal", nombres)
        self.assertEqual(self.ctx.suscriptores.contar(), 3)
        self.assertEqual(len(self.ctx.respaldos.listar(self.gerencia)), 1)
        eventos = " ".join(evento["detalle"] for evento in self.ctx.auditoria.listar(10))
        self.assertIn("restaurada", eventos)


class PruebasMigracion(unittest.TestCase):
    def test_base_de_la_version_anterior_se_actualiza(self):
        temporal = Path(tempfile.mkdtemp(prefix="sri_migracion_"))
        try:
            cifrador = Cifrador(temporal / "k.key")
            conexion = sqlite3.connect(temporal / "vieja.db")
            conexion.executescript(
                """
                CREATE TABLE ruta (id INTEGER PRIMARY KEY, zona TEXT NOT NULL, zona_normalizada TEXT NOT NULL UNIQUE,
                                   distribuidor_id INTEGER, creado_en TEXT NOT NULL);
                CREATE TABLE suscriptor (id INTEGER PRIMARY KEY, nombre_cifrado TEXT NOT NULL, direccion_cifrada TEXT NOT NULL,
                                         novedades_cifrada TEXT NOT NULL DEFAULT '', indice_busqueda TEXT NOT NULL,
                                         ruta_id INTEGER NOT NULL, archivo_id INTEGER, creado_en TEXT NOT NULL,
                                         actualizado_en TEXT NOT NULL);
                CREATE TABLE respaldo (id INTEGER PRIMARY KEY, fecha TEXT NOT NULL, ruta_archivo TEXT NOT NULL,
                                       usuario_id INTEGER NOT NULL);
                INSERT INTO ruta VALUES (1, 'Centro', 'CENTRO', NULL, '2026-01-01');
                """
            )
            conexion.execute(
                "INSERT INTO suscriptor VALUES (1, ?, ?, '', 'x', 1, NULL, '2026-01-01', '2026-01-01')",
                (cifrador.cifrar("Ana Vieja"), cifrador.cifrar("Calle 1 # 2-3")),
            )
            conexion.commit()
            conexion.close()

            ctx = Contexto(db_path=temporal / "vieja.db", key_path=temporal / "k.key")
            try:
                ana = ctx.suscriptores.listar()[0]
                self.assertEqual((ana.nombre, ana.periodicidad, ana.estado), ("Ana Vieja", DIARIA, "ACTIVO"))
                self.assertEqual(len(ctx.suscriptores.buscar_por_indice_nombre(cifrador.indice("ANA VIEJA"))), 1)
            finally:
                ctx.cerrar()
        finally:
            shutil.rmtree(temporal, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
