"""Novedades de entrega y cierre del día (RF-05, RN-03, RN-04, RN-11)."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from ..dominio.modelos import ESTADOS_ENTREGA
from ..util import parsear_fecha
from .estilos import COLORES, FUENTE
from .widgets import (
    cabecera_vista,
    crear_arbol,
    etiqueta_campo,
    confirmar,
    llenar_arbol,
    mostrar_error,
    mostrar_info,
    tarjeta,
    texto,
)

TODAS = "(Todas las rutas)"


class VistaEntregas(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.filas = {}
        self.rutas_por_nombre = {}
        self.seleccionado = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecera_vista(
            self,
            "Novedades de entrega",
            "Entregas programadas según la periodicidad. Registre solo las novedades y, al final, "
            "cierre el día: las demás se dan por entregadas (RN-11).",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._construir_filtros()
        self._construir_tabla()
        self._construir_formulario()
        self._cargar_rutas()
        self._cargar()

    # ------------------------------------------------------------------ #
    def _construir_filtros(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")

        etiqueta_campo(fila, "FECHA (DD/MM/AAAA)").pack(side="left")
        self.fecha = ttk.Entry(fila, width=13, font=(FUENTE, 10))
        self.fecha.pack(side="left", padx=(8, 18), ipady=3)
        self.fecha.insert(0, date.today().strftime("%d/%m/%Y"))

        etiqueta_campo(fila, "RUTA").pack(side="left")
        self.combo_ruta = ttk.Combobox(fila, state="readonly", width=16, font=(FUENTE, 10))
        self.combo_ruta.pack(side="left", padx=(8, 18), ipady=2)
        self.combo_ruta.set(TODAS)

        etiqueta_campo(fila, "BUSCAR").pack(side="left")
        self.buscar = ttk.Entry(fila, width=18, font=(FUENTE, 10))
        self.buscar.pack(side="left", padx=(8, 0), ipady=3)
        self.buscar.bind("<Return>", lambda _e: self._cargar())

        ttk.Button(fila, text="Cerrar el día", style="Primario.TButton", command=self._cerrar_dia).pack(
            side="right"
        )
        ttk.Button(fila, text="Cargar", style="Secundario.TButton", command=self._cargar).pack(
            side="right", padx=(0, 8)
        )

        self.resumen = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.resumen.pack(anchor="w", pady=(10, 0))

    def _construir_tabla(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="nsew", pady=(0, 12))

        self.arbol = crear_arbol(
            panel,
            [
                ("suscriptor", "Suscriptor", 190),
                ("direccion", "Dirección", 235),
                ("ruta", "Ruta", 110),
                ("distribuidor", "Distribuidor", 130),
                ("estado", "Estado del día", 115),
                ("novedad", "Novedad", 165),
            ],
            alto=12,
        )
        self.arbol.pack(fill="both", expand=True)
        self.arbol.bind("<<TreeviewSelect>>", self._seleccionar)

    def _construir_formulario(self) -> None:
        panel = tarjeta(self, relleno=16)
        panel.grid(row=3, column=0, sticky="ew")

        self.info = texto(
            panel,
            "Seleccione un suscriptor en la tabla para registrar su novedad.",
            tamano=10,
            negrita=True,
        )
        self.info.pack(anchor="w")

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x", pady=(10, 0))

        etiqueta_campo(fila, "ESTADO").pack(side="left")
        self.combo_estado = ttk.Combobox(
            fila, state="readonly", values=list(ESTADOS_ENTREGA), width=18, font=(FUENTE, 10)
        )
        self.combo_estado.set("CON NOVEDAD")
        self.combo_estado.pack(side="left", padx=(8, 18), ipady=2)

        etiqueta_campo(fila, "NOVEDAD (SI APLICA)").pack(side="left")
        self.novedad = ttk.Entry(fila, font=(FUENTE, 10))
        self.novedad.pack(side="left", fill="x", expand=True, padx=(8, 12), ipady=3)

        ttk.Button(fila, text="Guardar novedad", style="Primario.TButton", command=self._guardar).pack(
            side="right"
        )

        self.estado = texto(
            panel,
            "Ejemplos: ejemplar faltante en el paquete, reposición o reclamo del suscriptor. "
            "CON NOVEDAD exige describirla.",
            tamano=8,
            color=COLORES["texto_suave"],
        )
        self.estado.pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def _cargar_rutas(self) -> None:
        try:
            rutas = self.ctx.operativo.listar_rutas(self.sesion)
        except Exception:  # noqa: BLE001
            rutas = []
        self.rutas_por_nombre = {r.zona: r.id for r in rutas}
        self.combo_ruta.configure(values=[TODAS] + list(self.rutas_por_nombre))

    def _cargar(self) -> None:
        try:
            fecha = parsear_fecha(self.fecha.get())
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.fecha.delete(0, "end")
        self.fecha.insert(0, fecha.strftime("%d/%m/%Y"))
        ruta_id = self.rutas_por_nombre.get(self.combo_ruta.get())
        try:
            filas = self.ctx.consultas.suscriptores_con_estado(
                self.sesion,
                fecha.strftime("%d/%m/%Y"),
                ruta_id=ruta_id,
                texto=self.buscar.get().strip(),
                limite=300,
            )
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return

        self.filas = {f["suscriptor"].id: f for f in filas}
        llenar_arbol(
            self.arbol,
            [
                (
                    f["suscriptor"].id,
                    (
                        f["suscriptor"].nombre,
                        f["suscriptor"].direccion,
                        f["suscriptor"].zona,
                        f["suscriptor"].distribuidor or "Sin asignar",
                        f["estado"],
                        f["novedad"] or "—",
                    ),
                    self._etiqueta(f["estado"]),
                )
                for f in filas
            ],
        )
        filtro = "todas las rutas" if not ruta_id else self.combo_ruta.get()
        self.resumen.configure(
            text=(
                f"{len(filas)} entrega(s) programada(s) · {filtro} · {fecha.strftime('%d/%m/%Y')} · "
                f"{sum(1 for f in filas if f['estado'] == 'PENDIENTE')} pendiente(s) de cerrar. "
                "Se muestran hasta 300; use los filtros para acotar."
            )
        )
        if self.seleccionado and self.seleccionado in self.filas:
            self.arbol.selection_set(str(self.seleccionado))
        else:
            self.seleccionado = None
            self.info.configure(text="Seleccione un suscriptor en la tabla para registrar su novedad.")

    def _seleccionar(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        identificador = int(seleccion[0])
        fila = self.filas.get(identificador)
        if not fila:
            return
        self.seleccionado = identificador
        suscriptor = fila["suscriptor"]
        self.info.configure(
            text=f"{suscriptor.nombre} · {suscriptor.direccion} · Ruta {suscriptor.zona}"
        )
        self.combo_estado.set(fila["estado"])
        self.novedad.delete(0, "end")
        if fila["novedad"]:
            self.novedad.insert(0, fila["novedad"])
        self.estado.configure(
            text=f"Estado actual del {self.fecha.get()}: {fila['estado']}.",
            fg=COLORES["texto_suave"],
        )

    def _guardar(self) -> None:
        if not self.seleccionado:
            mostrar_error(self, "Seleccione primero un suscriptor de la tabla.")
            return
        try:
            self.ctx.operativo.registrar_entrega(
                self.sesion,
                self.seleccionado,
                self.fecha.get(),
                self.combo_estado.get(),
                self.novedad.get(),
            )
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        guardado = self.seleccionado
        self._cargar()
        self.seleccionado = guardado
        if guardado in self.filas:
            self.arbol.selection_set(str(guardado))
            self.arbol.see(str(guardado))
        self.estado.configure(
            text=f"Entrega actualizada a {self.combo_estado.get()} para el {self.fecha.get()}.",
            fg=COLORES["exito"],
        )

    def _cerrar_dia(self) -> None:
        fecha = self.fecha.get()
        if not confirmar(
            self,
            f"Se darán por ENTREGADAS las entregas programadas del {fecha} que siguen pendientes.\n\n"
            "Las novedades registradas se conservan. ¿Cerrar el día?",
            "Cerrar el día",
        ):
            return
        try:
            resultado = self.ctx.operativo.cerrar_dia(self.sesion, fecha)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._cargar()
        respaldo = resultado["respaldo"]
        mostrar_info(
            self,
            f"Día {fecha} cerrado: {resultado['marcadas']} entrega(s) marcadas como ENTREGADA.\n\n"
            + (f"Respaldo diario creado: {respaldo.name}" if respaldo else "El respaldo diario de hoy ya existía."),
            "Día cerrado",
        )

    @staticmethod
    def _etiqueta(estado: str) -> str | None:
        return {
            "ENTREGADA": "exito",
            "NO ENTREGADA": "alerta",
            "CON NOVEDAD": "aviso",
        }.get(estado)
