"""Lo que reportan los repartidores y cierre del día (RF-05, RN-03, RN-04, RN-11)."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from ..util import formato_fecha, parsear_fecha
from .estilos import COLORES, FUENTE
from .widgets import (
    ESTADO_LEGIBLE,
    CampoFecha,
    al_escribir,
    cabecera_vista,
    confirmar,
    crear_arbol,
    etiqueta_campo,
    llenar_arbol,
    mostrar_error,
    mostrar_info,
    tarjeta,
    texto,
)

TODAS = "(Todas las rutas)"
MOTIVOS_RAPIDOS = ("Ejemplar faltante en el paquete", "Reclamo del suscriptor", "Se hizo reposición")
SIN_SELECCION = "Toque un suscriptor de la lista para registrar lo que avisó el repartidor."


class VistaEntregas(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.filas = {}
        self.rutas_por_nombre = {}
        self.seleccionado = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecera_vista(
            self,
            "Lo que reportan los repartidores",
            "Registre solo lo que avisen: lo que no se entregó o tuvo un problema. "
            "Lo que no se reporte se da por entregado al cerrar el día.",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._construir_filtros()
        self._construir_tabla()
        self._construir_registro()
        self._construir_cierre()
        self._cargar_rutas()
        self._cargar()

    # ------------------------------------------------------------------ #
    def _construir_filtros(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")

        etiqueta_campo(fila, "FECHA").pack(side="left")
        self.fecha = CampoFecha(fila, date.today(), al_cambiar=self._cargar)
        self.fecha.pack(side="left", padx=(8, 22))

        etiqueta_campo(fila, "RUTA").pack(side="left")
        self.combo_ruta = ttk.Combobox(fila, state="readonly", width=16, font=(FUENTE, 12))
        self.combo_ruta.pack(side="left", padx=(8, 22), ipady=2)
        self.combo_ruta.set(TODAS)
        self.combo_ruta.bind("<<ComboboxSelected>>", lambda _e: self._cargar())

        etiqueta_campo(fila, "BUSCAR").pack(side="left")
        self.buscar = ttk.Entry(fila, width=20, font=(FUENTE, 12))
        self.buscar.pack(side="left", padx=(8, 0), ipady=3)
        al_escribir(self.buscar, self._cargar)

        self.resumen = texto(panel, "", tamano=10, color=COLORES["texto_suave"])
        self.resumen.pack(anchor="w", pady=(10, 0))

    def _construir_tabla(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 12))
        self.arbol = crear_arbol(
            panel,
            [
                ("suscriptor", "Suscriptor", 200),
                ("direccion", "Dirección", 230),
                ("ruta", "Ruta", 60, False),
                ("distribuidor", "Repartidor", 140),
                ("estado", "Estado", 200, False),
                ("novedad", "Qué pasó", 190),
            ],
            alto=6,
        )
        self.arbol.bind("<<TreeviewSelect>>", self._seleccionar)

    def _construir_registro(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=3, column=0, sticky="nsew", padx=(0, 8))

        self.info = texto(panel, SIN_SELECCION, tamano=12, negrita=True, wraplength=760, justify="left")
        self.info.pack(anchor="w")

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x", pady=(8, 0))
        etiqueta_campo(fila, "QUÉ PASÓ").pack(side="left")
        # Motivos rápidos en la lista; también se puede escribir otro.
        self.novedad = ttk.Combobox(fila, values=list(MOTIVOS_RAPIDOS), font=(FUENTE, 12))
        self.novedad.pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=3)
        texto(fila, "elija un motivo o escríbalo", tamano=10, color=COLORES["texto_suave"]).pack(side="left", padx=(8, 0))

        botones = tk.Frame(panel, bg=COLORES["panel"])
        botones.pack(fill="x", pady=(10, 0))
        ttk.Button(botones, text="No se entregó", style="Alerta.TButton",
                   command=lambda: self._guardar("NO ENTREGADA")).pack(side="left")
        ttk.Button(botones, text="Entregado con novedad", style="Aviso.TButton",
                   command=lambda: self._guardar("CON NOVEDAD")).pack(side="left", padx=(10, 0))
        ttk.Button(botones, text="Sí se entregó", style="Secundario.TButton",
                   command=lambda: self._guardar("ENTREGADA")).pack(side="left", padx=(10, 0))

        self.estado = texto(panel, "", tamano=11, color=COLORES["texto_suave"], wraplength=760, justify="left")
        self.estado.pack(anchor="w", pady=(8, 0))

    def _construir_cierre(self) -> None:
        # Separado de los filtros y de la tabla para que no se pulse por error.
        panel = tarjeta(self, relleno=16, fondo="#f3f8fa")
        panel.grid(row=3, column=1, sticky="nsew", padx=(8, 0))
        texto(panel, "Al terminar la jornada", tamano=13, negrita=True, fondo="#f3f8fa").pack(anchor="w")
        texto(
            panel,
            "Lo que no se reportó se da por entregado y se guarda la copia de seguridad del día.",
            tamano=10,
            color=COLORES["texto_suave"],
            fondo="#f3f8fa",
            wraplength=250,
            justify="left",
        ).pack(anchor="w", pady=(4, 10))
        ttk.Button(panel, text="Cerrar el día…", style="Grande.TButton", command=self._cerrar_dia).pack(fill="x")

    # ------------------------------------------------------------------ #
    def _cargar_rutas(self) -> None:
        try:
            rutas = self.ctx.operativo.listar_rutas(self.sesion)
        except Exception:  # noqa: BLE001
            rutas = []
        self.rutas_por_nombre = {r.zona: r.id for r in rutas}
        self.combo_ruta.configure(values=[TODAS] + list(self.rutas_por_nombre))

    def _fecha(self) -> date | None:
        try:
            fecha = parsear_fecha(self.fecha.get())
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return None
        self.fecha.set(fecha)
        return fecha

    def _cargar(self) -> None:
        fecha = self._fecha()
        if fecha is None:
            return
        ruta_id = self.rutas_por_nombre.get(self.combo_ruta.get())
        try:
            filas = self.ctx.consultas.suscriptores_con_estado(
                self.sesion, formato_fecha(fecha), ruta_id=ruta_id, texto=self.buscar.get().strip(), limite=300
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
                        ESTADO_LEGIBLE.get(f["estado"], f["estado"]),
                        f["novedad"] or "—",
                    ),
                    {"ENTREGADA": "exito", "NO ENTREGADA": "alerta", "CON NOVEDAD": "aviso"}.get(f["estado"]),
                )
                for f in filas
            ],
        )
        pendientes = sum(1 for f in filas if f["estado"] == "PENDIENTE")
        reportes = sum(1 for f in filas if f["estado"] in ("NO ENTREGADA", "CON NOVEDAD"))
        self.resumen.configure(
            text=f"{len(filas)} entrega(s) para el {formato_fecha(fecha)} · {reportes} con reporte · "
            f"{pendientes} por entregar (se dan por entregadas al cerrar el día)."
            + (" Se muestran 300; escriba un nombre para acotar." if len(filas) >= 300 else "")
        )
        if self.seleccionado in self.filas:
            self.arbol.selection_set(str(self.seleccionado))
        else:
            self.seleccionado = None
            self.info.configure(text=SIN_SELECCION)

    def _seleccionar(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        fila = self.filas.get(int(seleccion[0])) if seleccion else None
        if not fila:
            return
        self.seleccionado = fila["suscriptor"].id
        s = fila["suscriptor"]
        self.info.configure(text=f"{s.nombre} · {s.direccion} · Ruta {s.zona}")
        self.novedad.delete(0, "end")
        if fila["novedad"]:
            self.novedad.insert(0, fila["novedad"])
        self.estado.configure(text=f"Ahora: {ESTADO_LEGIBLE.get(fila['estado'], fila['estado'])}.", fg=COLORES["texto_suave"])

    def _motivo(self, motivo: str) -> None:
        self.novedad.set(motivo)

    def _guardar(self, estado: str) -> None:
        if not self.seleccionado:
            mostrar_error(self, "Primero toque en la lista al suscriptor del que avisó el repartidor.")
            return
        nombre = self.filas[self.seleccionado]["suscriptor"].nombre
        try:
            self.ctx.operativo.registrar_entrega(
                self.sesion, self.seleccionado, self.fecha.get(), estado, self.novedad.get()
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
        mensajes = {
            "NO ENTREGADA": f"Listo. Se registró que no se entregó a {nombre}.",
            "CON NOVEDAD": f"Listo. Se registró la novedad de {nombre}.",
            "ENTREGADA": f"Listo. {nombre} quedó como entregado.",
        }
        self.estado.configure(text=mensajes[estado], fg=COLORES["exito"])
        self.novedad.delete(0, "end")

    def _cerrar_dia(self) -> None:
        fecha = self._fecha()
        if fecha is None:
            return
        texto_fecha = formato_fecha(fecha)
        try:
            pendientes = self.ctx.operativo.pendientes_del_dia(self.sesion, texto_fecha)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        if not pendientes:
            mostrar_info(self, f"El {texto_fecha} ya está cerrado: no quedan entregas por marcar.", "Cerrar el día")
            return
        if not confirmar(
            self,
            f"Se marcarán {pendientes} entrega(s) del {texto_fecha} como entregadas.\n\n"
            "Lo que ya registró como «No se entregó» o «Entregado con novedad» no cambia.\n\n¿Continuar?",
            "Cerrar el día",
        ):
            return
        try:
            resultado = self.ctx.operativo.cerrar_dia(self.sesion, texto_fecha)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._cargar()
        mostrar_info(
            self,
            f"Listo. El {texto_fecha} quedó cerrado: {resultado['marcadas']} entrega(s) marcadas como entregadas."
            + ("\n\nTambién se guardó la copia de seguridad del día." if resultado["respaldo"] else ""),
            "Día cerrado",
        )
