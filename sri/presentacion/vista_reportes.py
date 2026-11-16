"""Reporte diario de entregas (RF-03, RN-05, RN-11)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from datetime import date
from pathlib import Path
from tkinter import filedialog, ttk

from ..config import directorio_exportes
from ..util import formato_fecha
from .estilos import COLORES, FUENTE
from .widgets import (
    cabecera_vista,
    crear_arbol,
    etiqueta_campo,
    llenar_arbol,
    mostrar_error,
    mostrar_info,
    tarjeta,
    texto,
)


class VistaReportes(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.reporte = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_rowconfigure(4, weight=1)

        cabecera_vista(
            self,
            "Reporte diario de entregas",
            "Entregas programadas según la periodicidad, efectivas y novedades del día, por ruta y distribuidor. "
            "Mientras el día no se cierre, las entregas sin novedad aparecen como pendientes.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._construir_filtro()
        self._construir_kpis()
        self._construir_detalle()
        self._construir_novedades()
        self._generar()

    def _construir_filtro(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        etiqueta_campo(fila, "FECHA DEL REPORTE").pack(side="left")
        self.fecha = ttk.Entry(fila, width=14, font=(FUENTE, 10))
        self.fecha.pack(side="left", padx=(8, 12), ipady=3)
        self.fecha.insert(0, date.today().strftime("%d/%m/%Y"))
        ttk.Button(fila, text="Generar reporte", style="Primario.TButton", command=self._generar).pack(side="left")

        exportar = tk.Frame(fila, bg=COLORES["panel"])
        exportar.pack(side="right")
        self.boton_html = ttk.Button(
            exportar, text="Exportar a PDF (HTML)", style="Secundario.TButton", command=self._exportar_html, state="disabled"
        )
        self.boton_html.pack(side="right")
        self.boton_csv = ttk.Button(
            exportar, text="Exportar a Excel (CSV)", style="Secundario.TButton", command=self._exportar_csv, state="disabled"
        )
        self.boton_csv.pack(side="right", padx=(0, 8))

        self.estado = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.estado.pack(anchor="w", pady=(10, 0))

    def _construir_kpis(self) -> None:
        fila = tk.Frame(self, bg=COLORES["fondo"])
        fila.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        for indice in range(6):
            fila.grid_columnconfigure(indice, weight=1, uniform="kpi")
        self.kpis = {}
        definiciones = [
            ("total", "PROGRAMADAS", COLORES["texto"]),
            ("efectivas", "EFECTIVAS", COLORES["exito"]),
            ("efectividad", "EFECTIVIDAD", COLORES["primario"]),
            ("no_entregadas", "NO ENTREGADAS", COLORES["alerta"]),
            ("novedades", "CON NOVEDAD", COLORES["aviso"]),
            ("pendientes", "PENDIENTES", COLORES["texto_suave"]),
        ]
        for indice, (clave, etiqueta, color) in enumerate(definiciones):
            panel = tarjeta(fila, relleno=12)
            panel.grid(row=0, column=indice, sticky="nsew", padx=(0 if indice == 0 else 4, 4 if indice < 5 else 0))
            texto(panel, etiqueta, tamano=8, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
            variable = tk.StringVar(value="—")
            tk.Label(panel, textvariable=variable, bg=COLORES["panel"], fg=color, font=(FUENTE, 20, "bold")).pack(
                anchor="w", pady=(3, 0)
            )
            self.kpis[clave] = variable

    def _construir_detalle(self) -> None:
        contenedor = tk.Frame(self, bg=COLORES["fondo"])
        contenedor.grid(row=3, column=0, sticky="nsew")
        contenedor.grid_columnconfigure(0, weight=1)
        contenedor.grid_columnconfigure(1, weight=1)
        contenedor.grid_rowconfigure(0, weight=1)

        panel_ruta = tarjeta(contenedor, relleno=14)
        panel_ruta.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        texto(panel_ruta, "Detalle por ruta", tamano=11, negrita=True).pack(anchor="w")
        self.arbol_ruta = crear_arbol(
            panel_ruta,
            [
                ("clave", "Ruta", 100, True),
                ("total", "Total", 40, False),
                ("efectivas", "Efect.", 44, False),
                ("no_entregadas", "No ent.", 54, False),
                ("novedades", "Noved.", 52, False),
                ("pendientes", "Pend.", 44, False),
                ("porcentaje", "Efectividad", 76, False),
            ],
            alto=6,
        )
        self.arbol_ruta.pack(fill="both", expand=True, pady=(10, 0))

        panel_dist = tarjeta(contenedor, relleno=14)
        panel_dist.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        texto(panel_dist, "Detalle por distribuidor", tamano=11, negrita=True).pack(anchor="w")
        self.arbol_dist = crear_arbol(
            panel_dist,
            [
                ("clave", "Distribuidor", 95, True),
                ("total", "Total", 40, False),
                ("efectivas", "Efect.", 44, False),
                ("no_entregadas", "No ent.", 54, False),
                ("novedades", "Noved.", 52, False),
                ("pendientes", "Pend.", 44, False),
                ("porcentaje", "Efectividad", 76, False),
            ],
            alto=6,
        )
        self.arbol_dist.pack(fill="both", expand=True, pady=(10, 0))

    def _construir_novedades(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        texto(panel, "Novedades del día", tamano=11, negrita=True).pack(anchor="w")
        self.arbol_novedades = crear_arbol(
            panel,
            [("tipo", "Tipo", 110, False), ("suscriptor", "Suscriptor", 200), ("ruta", "Ruta", 70, False), ("detalle", "Detalle", 320)],
            alto=4,
        )

    # ------------------------------------------------------------------ #
    def _generar(self) -> None:
        try:
            reporte = self.ctx.consultas.generar_reporte(self.sesion, self.fecha.get())
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.reporte = reporte
        self.kpis["total"].set(str(reporte.total))
        self.kpis["efectivas"].set(str(reporte.efectivas))
        self.kpis["efectividad"].set("—" if reporte.porcentaje is None else f"{reporte.porcentaje:.1f} %".replace(".", ","))
        self.kpis["no_entregadas"].set(str(reporte.no_entregadas))
        self.kpis["novedades"].set(str(reporte.novedades))
        self.kpis["pendientes"].set(str(reporte.pendientes))

        def filas(items):
            return [
                (
                    indice,
                    (
                        f.clave,
                        f.total,
                        f.efectivas,
                        f.no_entregadas,
                        f.novedades,
                        f.pendientes,
                        "—" if f.porcentaje is None else f"{f.porcentaje:.1f} %".replace(".", ","),
                    ),
                    "exito" if (f.porcentaje or 0) >= 90 else ("alerta" if f.porcentaje is not None and f.porcentaje < 70 else None),
                )
                for indice, f in enumerate(items, start=1)
            ]

        llenar_arbol(self.arbol_ruta, filas(reporte.por_ruta))
        llenar_arbol(self.arbol_dist, filas(reporte.por_distribuidor))
        llenar_arbol(
            self.arbol_novedades,
            [(i, fila, None) for i, fila in enumerate(self.ctx.consultas.filas_novedades(reporte), start=1)],
        )

        if reporte.sin_datos:
            self.estado.configure(
                text="No hay entregas programadas en la fecha; no se calcula el porcentaje.",
                fg=COLORES["aviso"],
            )
            self.boton_csv.configure(state="disabled")
            self.boton_html.configure(state="disabled")
        else:
            self.estado.configure(
                text=f"Reporte del {formato_fecha(reporte.fecha)} generado y guardado.",
                fg=COLORES["exito"],
            )
            self.boton_csv.configure(state="normal")
            self.boton_html.configure(state="normal")

    def _exportar_csv(self) -> None:
        if not self.reporte or self.reporte.sin_datos:
            return
        nombre = f"reporte_entregas_{self.reporte.fecha}.csv"
        destino = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar reporte en CSV",
            initialdir=str(directorio_exportes()),
            initialfile=nombre,
            defaultextension=".csv",
            filetypes=[("CSV para Excel", "*.csv")],
        )
        if not destino:
            return
        try:
            ruta = self.ctx.consultas.exportar_csv(self.sesion, self.reporte, destino)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        mostrar_info(self, f"Reporte exportado en:\n{ruta}")

    def _exportar_html(self) -> None:
        if not self.reporte or self.reporte.sin_datos:
            return
        nombre = f"reporte_entregas_{self.reporte.fecha}.html"
        destino = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar reporte imprimible",
            initialdir=str(directorio_exportes()),
            initialfile=nombre,
            defaultextension=".html",
            filetypes=[("Documento HTML", "*.html")],
        )
        if not destino:
            return
        try:
            ruta = self.ctx.consultas.exportar_html(self.sesion, self.reporte, destino)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        if isinstance(ruta, Path) and ruta.exists():
            webbrowser.open(ruta.resolve().as_uri())
        mostrar_info(
            self,
            "Se abrió el reporte imprimible en el navegador. Use “Imprimir / Guardar como PDF” "
            f"para generar el PDF.\n\nArchivo: {ruta}",
        )
