"""Consulta del historial de entregas (RF-06)."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from ..dominio.modelos import ESTADOS_ENTREGA
from ..util import formato_fecha
from .dialogos import DialogoHistorial
from .estilos import COLORES, FUENTE
from .widgets import (
    cabecera_vista,
    crear_arbol,
    etiqueta_campo,
    llenar_arbol,
    mostrar_error,
    tarjeta,
    texto,
)

TODAS = "(Todas)"


class VistaConsultas(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.entregas = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecera_vista(
            self,
            "Consulta del historial",
            "Consulte suscriptores, rutas y entregas por texto, ruta, distribuidor, rango de fechas o estado.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._construir_filtros()
        self._construir_resultados()
        self._buscar()

    def _construir_filtros(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        fila1 = tk.Frame(panel, bg=COLORES["panel"])
        fila1.pack(fill="x")
        etiqueta_campo(fila1, "SUSCRIPTOR O DIRECCIÓN").pack(side="left")
        self.texto_busqueda = ttk.Entry(fila1, width=26, font=(FUENTE, 10))
        self.texto_busqueda.pack(side="left", padx=(8, 16), ipady=3)
        self.texto_busqueda.bind("<Return>", lambda _e: self._buscar())

        etiqueta_campo(fila1, "RUTA").pack(side="left")
        self.combo_ruta = ttk.Combobox(fila1, state="readonly", width=19, font=(FUENTE, 10))
        self.combo_ruta.pack(side="left", padx=(8, 16), ipady=2)
        self.combo_ruta.set(TODAS)

        etiqueta_campo(fila1, "DISTRIBUIDOR").pack(side="left")
        self.combo_distribuidor = ttk.Combobox(fila1, state="readonly", width=21, font=(FUENTE, 10))
        self.combo_distribuidor.pack(side="left", padx=(8, 0), ipady=2)
        self.combo_distribuidor.set(TODAS)

        fila2 = tk.Frame(panel, bg=COLORES["panel"])
        fila2.pack(fill="x", pady=(10, 0))
        etiqueta_campo(fila2, "DESDE (DD/MM/AAAA)").pack(side="left")
        self.desde = ttk.Entry(fila2, width=13, font=(FUENTE, 10))
        self.desde.pack(side="left", padx=(8, 18), ipady=3)

        etiqueta_campo(fila2, "HASTA (DD/MM/AAAA)").pack(side="left")
        self.hasta = ttk.Entry(fila2, width=13, font=(FUENTE, 10))
        self.hasta.pack(side="left", padx=(8, 18), ipady=3)

        etiqueta_campo(fila2, "ESTADO").pack(side="left")
        self.combo_estado = ttk.Combobox(
            fila2, state="readonly", values=[TODAS] + list(ESTADOS_ENTREGA), width=15, font=(FUENTE, 10)
        )
        self.combo_estado.set(TODAS)
        self.combo_estado.pack(side="left", padx=(8, 18), ipady=2)

        ttk.Button(fila2, text="Limpiar", style="Secundario.TButton", command=self._limpiar).pack(side="right")
        ttk.Button(fila2, text="Buscar", style="Primario.TButton", command=self._buscar).pack(
            side="right", padx=(0, 8)
        )

        hoy = date.today()
        self.desde.insert(0, (hoy - timedelta(days=7)).strftime("%d/%m/%Y"))
        self.hasta.insert(0, hoy.strftime("%d/%m/%Y"))

        self._cargar_rutas()

    def _construir_resultados(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="nsew")

        self.arbol = crear_arbol(
            panel,
            [
                ("fecha", "Fecha", 75),
                ("suscriptor", "Suscriptor", 180),
                ("direccion", "Dirección", 210),
                ("ruta", "Ruta", 110),
                ("distribuidor", "Distribuidor", 120),
                ("estado", "Estado", 100),
                ("novedad", "Novedad", 140),
            ],
            alto=14,
        )
        self.arbol.pack(fill="both", expand=True)
        self.arbol.bind("<Double-1>", self._abrir_historial)

        pie = tk.Frame(panel, bg=COLORES["panel"])
        pie.pack(fill="x", pady=(10, 0))
        self.resumen = texto(pie, "", tamano=9, color=COLORES["texto_suave"])
        self.resumen.pack(side="left")
        texto(
            pie,
            "Doble clic sobre una entrega para ver el historial completo del suscriptor.",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(side="right")

    # ------------------------------------------------------------------ #
    def _cargar_rutas(self) -> None:
        try:
            rutas = self.ctx.operativo.listar_rutas(self.sesion)
            distribuidores = self.ctx.operativo.listar_distribuidores(self.sesion, incluir_inactivos=True)
        except Exception:  # noqa: BLE001
            rutas, distribuidores = [], []
        self.rutas_por_nombre = {r.zona: r.id for r in rutas}
        self.distribuidores_por_nombre = {d.nombre: d.id for d in distribuidores}
        self.combo_ruta.configure(values=[TODAS] + list(self.rutas_por_nombre))
        self.combo_distribuidor.configure(values=[TODAS] + list(self.distribuidores_por_nombre))

    def _limpiar(self) -> None:
        self.texto_busqueda.delete(0, "end")
        self.combo_ruta.set(TODAS)
        self.combo_distribuidor.set(TODAS)
        self.combo_estado.set(TODAS)
        self.desde.delete(0, "end")
        self.hasta.delete(0, "end")
        self._buscar()

    def _buscar(self) -> None:
        filtros = {
            "texto": self.texto_busqueda.get().strip(),
            "ruta_id": self.rutas_por_nombre.get(self.combo_ruta.get()),
            "distribuidor_id": self.distribuidores_por_nombre.get(self.combo_distribuidor.get()),
            "desde": self.desde.get().strip(),
            "hasta": self.hasta.get().strip(),
            "estado": "" if self.combo_estado.get() == TODAS else self.combo_estado.get(),
        }
        try:
            filas = self.ctx.consultas.buscar_entregas(self.sesion, filtros)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.entregas = {e.id or indice: e for indice, e in enumerate(filas, start=1)}
        llenar_arbol(
            self.arbol,
            [
                (
                    e.id or indice,
                    (
                        formato_fecha(e.fecha),
                        e.suscriptor,
                        e.direccion,
                        e.zona,
                        e.distribuidor,
                        e.estado,
                        e.novedad or "—",
                    ),
                    {
                        "ENTREGADA": "exito",
                        "NO ENTREGADA": "alerta",
                        "CON NOVEDAD": "aviso",
                    }.get(e.estado),
                )
                for indice, e in enumerate(filas, start=1)
            ],
        )
        texto_resumen = f"{len(filas)} entrega(s) encontrada(s)."
        if len(filas) >= 500:
            texto_resumen += " Se alcanzó el límite de 500; acote los filtros para ver más."
        self.resumen.configure(text=texto_resumen)

    def _abrir_historial(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        entrega = self.entregas.get(int(seleccion[0]))
        if not entrega:
            return
        DialogoHistorial(self, self.app, entrega.suscriptor_id, entrega.suscriptor)
