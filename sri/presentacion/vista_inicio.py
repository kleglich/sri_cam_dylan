"""Vista de inicio: indicadores del día y accesos rápidos."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .estilos import COLORES, FUENTE
from .widgets import crear_arbol, fecha_hora_legible, llenar_arbol, tarjeta, texto


class VistaInicio(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.shell = app.vista

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(2, weight=1)

        self._encabezado()
        self._indicadores()
        self._accesos()
        self._importaciones()

    def _encabezado(self) -> None:
        marco = tk.Frame(self, bg=COLORES["fondo"])
        marco.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        nombre = self.sesion.nombre.capitalize()
        texto(
            marco,
            f"Bienvenido(a), {nombre}",
            tamano=22,
            negrita=True,
            fondo=COLORES["fondo"],
        ).pack(anchor="w")
        texto(
            marco,
            "Resumen de la operación de hoy y accesos a las tareas de su rol.",
            tamano=10,
            color=COLORES["texto_suave"],
            fondo=COLORES["fondo"],
        ).pack(anchor="w", pady=(4, 0))

    def _indicadores(self) -> None:
        datos = self.ctx.consultas.dashboard(self.sesion)
        fila = tk.Frame(self, bg=COLORES["fondo"])
        fila.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        for indice in range(5):
            fila.grid_columnconfigure(indice, weight=1, uniform="kpi")

        efectividad = datos["efectividad_hoy"]
        tarjetas = [
            ("SUSCRIPTORES", str(datos["suscriptores"]), "activos", COLORES["primario"]),
            ("RUTAS", str(datos["rutas"]), "zonas registradas", COLORES["primario"]),
            ("DISTRIBUIDORES", str(datos["distribuidores"]), "activos", COLORES["primario"]),
            ("ENTREGAS DE HOY", str(datos["entregas_hoy"]), "programadas", COLORES["acento"]),
            (
                "EFECTIVIDAD HOY",
                "—" if efectividad is None else f"{efectividad:.1f} %".replace(".", ","),
                "entregas efectivas", COLORES["exito"] if efectividad else COLORES["texto_suave"],
            ),
        ]
        for indice, (titulo, valor, detalle, color) in enumerate(tarjetas):
            tarjeta_kpi = tarjeta(fila, relleno=14)
            tarjeta_kpi.grid(row=0, column=indice, sticky="nsew", padx=(0 if indice == 0 else 5, 5 if indice < 4 else 0))
            texto(tarjeta_kpi, titulo, tamano=8, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
            tk.Label(
                tarjeta_kpi,
                text=valor,
                bg=COLORES["panel"],
                fg=color,
                font=(FUENTE, 23, "bold"),
            ).pack(anchor="w", pady=(4, 2))
            texto(tarjeta_kpi, detalle, tamano=8, color=COLORES["texto_suave"]).pack(anchor="w")

    def _accesos(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 4))
        texto(panel, "Tareas frecuentes", tamano=12, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Accesos directos habilitados para su rol.",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 14))

        acciones = [
            ("novedades", "Pasar las novedades del listado impreso", "RF-09", "Ingresos, retiros y cambios de suscriptores."),
            ("entregas", "Registrar novedades de entrega y cerrar el día", "RF-05", "Solo lo que reportan los distribuidores."),
            ("importar", "Importar el listado de repartidores", "RF-01", "Carga inicial o recarga del Excel de la empresa."),
            ("rutas", "Asignar rutas a los distribuidores", "RF-02", "Una ruta tiene un único distribuidor a la vez."),
            ("distribuidores", "Gestionar distribuidores", "RF-04", "Altas, cambios y bajas del equipo operativo."),
            ("consultas", "Consultar el historial", "RF-06", "Suscriptores, rutas y entregas anteriores."),
            ("reportes", "Generar el reporte diario de entregas", "RF-03", "Programadas, efectivas y novedades del día."),
            ("respaldos", "Copiar el respaldo a Google Drive", "RF-07", "Copia semanal cifrada fuera del equipo."),
        ]
        visibles = [a for a in acciones if self.sesion.puede(a[2])]
        for indice, (clave, titulo, requisito, detalle) in enumerate(visibles):
            boton = ttk.Button(
                panel,
                text=titulo,
                style="Secundario.TButton",
                command=lambda c=clave: self.shell.mostrar(c),
            )
            boton.pack(fill="x", pady=2)

        aviso = tk.Frame(panel, bg="#f3f8fa")
        aviso.pack(fill="x", pady=(16, 0))
        texto(
            aviso,
            "Protección de datos: la información personal de los suscriptores se guarda cifrada "
            "(AES-256-GCM) y solo se usa con fines logísticos (Ley 1581 de 2012).",
            tamano=8,
            color=COLORES["texto_suave"],
            fondo="#f3f8fa",
            wraplength=390,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

    def _importaciones(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=2, column=1, sticky="nsew", padx=(8, 0), pady=(0, 4))
        texto(panel, "Últimas importaciones", tamano=12, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Listados de repartidores cargados recientemente.",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 12))

        arbol = crear_arbol(
            panel,
            [
                ("archivo", "Archivo", 120, True),
                ("fecha", "Fecha", 120, False),
                ("leidos", "Leídos", 56, False),
                ("importados", "Nuevos", 62, False),
                ("rechazados", "Rech.", 50, False),
            ],
            alto=9,
        )
        arbol.pack(fill="both", expand=True)
        importaciones = self.ctx.archivos.listar(8)
        llenar_arbol(
            arbol,
            [
                (
                    a.id,
                    (
                        a.nombre_archivo,
                        fecha_hora_legible(a.fecha_carga),
                        a.total_leidos,
                        a.total_importados,
                        a.total_rechazados,
                    ),
                    "alerta" if a.total_rechazados else None,
                )
                for a in importaciones
            ],
        )
        if not importaciones:
            texto(
                panel,
                "Aún no se han importado archivos.",
                tamano=9,
                color=COLORES["texto_suave"],
            ).pack(anchor="w", pady=(8, 0))
