"""Consulta del historial de suscriptores, rutas y entregas (RF-06)."""

from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from tkinter import ttk

from ..dominio.modelos import ESTADOS_ENTREGA, PRODUCTOS
from ..dominio.periodicidad import etiqueta
from ..util import formato_fecha
from .dialogos import DialogoHistorial
from .estilos import COLORES, FUENTE
from .widgets import (
    ESTADO_LEGIBLE,
    CampoFecha,
    al_escribir,
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
        self.suscriptores = {}
        self.modo = tk.StringVar(value="entregas")

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

        fila0 = tk.Frame(panel, bg=COLORES["panel"])
        fila0.pack(fill="x", pady=(0, 10))
        etiqueta_campo(fila0, "BUSCAR EN").pack(side="left")
        for valor, nombre in (("entregas", "Entregas"), ("suscriptores", "Suscriptores (aunque no tengan entregas)")):
            tk.Radiobutton(
                fila0, text=nombre, value=valor, variable=self.modo, command=self._cambiar_modo,
                bg=COLORES["panel"], activebackground=COLORES["panel"], font=(FUENTE, 10),
            ).pack(side="left", padx=(10, 0))

        fila1 = tk.Frame(panel, bg=COLORES["panel"])
        fila1.pack(fill="x")
        etiqueta_campo(fila1, "SUSCRIPTOR O DIRECCIÓN").pack(side="left")
        self.texto_busqueda = ttk.Entry(fila1, width=26, font=(FUENTE, 12))
        self.texto_busqueda.pack(side="left", padx=(8, 16), ipady=3)
        self.texto_busqueda.bind("<Return>", lambda _e: self._buscar())
        al_escribir(self.texto_busqueda, self._buscar)

        etiqueta_campo(fila1, "RUTA").pack(side="left")
        self.combo_ruta = ttk.Combobox(fila1, state="readonly", width=19, font=(FUENTE, 12))
        self.combo_ruta.pack(side="left", padx=(8, 16), ipady=2)
        self.combo_ruta.set(TODAS)

        etiqueta_campo(fila1, "DISTRIBUIDOR").pack(side="left")
        self.combo_distribuidor = ttk.Combobox(fila1, state="readonly", width=21, font=(FUENTE, 12))
        self.combo_distribuidor.pack(side="left", padx=(8, 0), ipady=2)
        self.combo_distribuidor.set(TODAS)

        fila2 = tk.Frame(panel, bg=COLORES["panel"])
        fila2.pack(fill="x", pady=(10, 0))
        etiqueta_campo(fila2, "DESDE").pack(side="left")
        self.desde = CampoFecha(fila2, al_cambiar=self._buscar)
        self.desde.pack(side="left", padx=(8, 18))

        etiqueta_campo(fila2, "HASTA").pack(side="left")
        self.hasta = CampoFecha(fila2, al_cambiar=self._buscar)
        self.hasta.pack(side="left", padx=(8, 18))

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
        self.desde.set(hoy - timedelta(days=7))
        self.hasta.set(hoy)

        self._cargar_rutas()

    def _construir_resultados(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="nsew")

        self.marco_entregas = tk.Frame(panel, bg=COLORES["panel"])
        self.marco_entregas.pack(fill="both", expand=True)
        self.marco_suscriptores = tk.Frame(panel, bg=COLORES["panel"])
        self.arbol_suscriptores = crear_arbol(
            self.marco_suscriptores,
            [
                ("suscriptor", "Suscriptor", 170),
                ("direccion", "Dirección", 170),
                ("ruta", "Ruta", 64, False),
                ("distribuidor", "Repartidor", 120),
                ("periodicidad", "Periodicidad", 110),
                ("productos", "Productos", 110),
                ("estado", "Estado", 215, False),
            ],
            alto=14,
        )
        self.arbol_suscriptores.bind("<Double-1>", self._abrir_historial)
        self.arbol = crear_arbol(
            self.marco_entregas,
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
        pie.pack(fill="x", side="bottom", pady=(10, 0))
        self.resumen = texto(pie, "", tamano=9, color=COLORES["texto_suave"])
        self.resumen.pack(side="left")
        texto(
            pie,
            "Doble clic para ver la ficha del suscriptor: estado, novedades y entregas.",
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
        self.desde.set(None)
        self.hasta.set(None)
        self._buscar()

    def _cambiar_modo(self) -> None:
        suscriptores = self.modo.get() == "suscriptores"
        (self.marco_entregas if suscriptores else self.marco_suscriptores).pack_forget()
        (self.marco_suscriptores if suscriptores else self.marco_entregas).pack(fill="both", expand=True)
        self.combo_estado.configure(values=[TODAS] + (["ACTIVO", "RETIRADO"] if suscriptores else list(ESTADOS_ENTREGA)))
        self.combo_estado.set(TODAS)
        for campo in (self.desde, self.hasta):  # las fechas solo filtran entregas
            campo.estado(not suscriptores)
        self._buscar()

    def _buscar_suscriptores(self) -> None:
        filtros = {
            "texto": self.texto_busqueda.get().strip(),
            "ruta_id": self.rutas_por_nombre.get(self.combo_ruta.get()),
            "distribuidor_id": self.distribuidores_por_nombre.get(self.combo_distribuidor.get()),
            "estado": "" if self.combo_estado.get() == TODAS else self.combo_estado.get(),
        }
        try:
            filas = self.ctx.consultas.buscar_suscriptores(self.sesion, filtros)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.suscriptores = {s.id: s for s in filas}
        llenar_arbol(
            self.arbol_suscriptores,
            [
                (
                    s.id,
                    (
                        s.nombre,
                        s.direccion + (f" / fin de semana: {s.direccion_fs}" if s.direccion_fs else ""),
                        s.zona,
                        s.distribuidor or "Sin asignar",
                        etiqueta(s.periodicidad),
                        ", ".join(PRODUCTOS[p] for p in s.productos.split(",") if p in PRODUCTOS),
                        "Activo" if s.activo else f"Retirado desde {formato_fecha(s.fecha_retiro)}",
                    ),
                    None if s.activo else "inactivo",
                )
                for s in filas
            ],
        )
        self.resumen.configure(text=f"{len(filas)} suscriptor(es) encontrado(s).")

    def _buscar(self) -> None:
        if self.modo.get() == "suscriptores":
            self._buscar_suscriptores()
            return
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
                        ESTADO_LEGIBLE.get(e.estado, e.estado),
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
        if self.modo.get() == "suscriptores":
            seleccion = self.arbol_suscriptores.selection()
            suscriptor = self.suscriptores.get(int(seleccion[0])) if seleccion else None
            if suscriptor:
                DialogoHistorial(self, self.app, suscriptor.id, suscriptor.nombre)
            return
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        entrega = self.entregas.get(int(seleccion[0]))
        if not entrega:
            return
        DialogoHistorial(self, self.app, entrega.suscriptor_id, entrega.suscriptor)
