"""Asignación y modificación de rutas (RF-02, RN-01)."""

from __future__ import annotations

import tkinter as tk
import webbrowser
from tkinter import ttk

from ..config import directorio_exportes
from ..util import nombre_archivo_seguro

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

SIN_ASIGNAR = "(Sin asignar)"


class VistaRutas(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.seleccionada = None
        self.mapa = {}
        self.distribuidores = []
        self._por_nombre = {}

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        cabecera_vista(
            self,
            "Rutas y distribuidores",
            "Asigne o modifique la zona de entrega de cada distribuidor. "
            "Cada ruta es de un solo repartidor a la vez y agrupa a sus suscriptores.",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        self._construir_lista()
        self._construir_formulario()
        self._cargar()

    def _construir_lista(self) -> None:
        panel = tarjeta(self, relleno=16)
        panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        texto(fila, "Rutas registradas", tamano=12, negrita=True).pack(side="left")
        ttk.Button(fila, text="Actualizar", style="Secundario.TButton", command=self._cargar).pack(side="right")

        self.arbol = crear_arbol(
            panel,
            [
                ("zona", "Zona / ruta", 230),
                ("distribuidor", "Distribuidor asignado", 220),
                ("suscriptores", "Suscriptores", 100),
            ],
            alto=16,
        )
        self.arbol.pack(fill="both", expand=True, pady=(12, 0))
        self.arbol.bind("<<TreeviewSelect>>", self._seleccionar)

        self.resumen = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.resumen.pack(anchor="w", pady=(10, 0))

    def _construir_formulario(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

        self.titulo_formulario = texto(panel, "Nueva ruta", tamano=12, negrita=True)
        self.titulo_formulario.pack(anchor="w")
        texto(
            panel,
            "Defina la zona y, si lo desea, asígnela de inmediato a un distribuidor.",
            tamano=9,
            color=COLORES["texto_suave"],
            wraplength=340,
            justify="left",
        ).pack(anchor="w", pady=(3, 16))

        etiqueta_campo(panel, "ZONA O RUTA").pack(anchor="w")
        self.zona = ttk.Entry(panel, font=(FUENTE, 12))
        self.zona.pack(fill="x", pady=(5, 12), ipady=4)

        etiqueta_campo(panel, "DISTRIBUIDOR").pack(anchor="w")
        self.combo = ttk.Combobox(panel, state="readonly", font=(FUENTE, 12))
        self.combo.pack(fill="x", pady=(5, 16), ipady=3)

        self.estado = texto(panel, "Seleccione una ruta o cree una nueva.", tamano=9, color=COLORES["texto_suave"], wraplength=340, justify="left")
        self.estado.pack(anchor="w", pady=(0, 16))

        ttk.Button(panel, text="Guardar ruta", style="Primario.TButton", command=self._guardar).pack(fill="x")
        ttk.Button(panel, text="Nueva ruta", style="Secundario.TButton", command=self._nueva).pack(fill="x", pady=(8, 0))
        ttk.Button(
            panel, text="Imprimir ruta del distribuidor", style="Secundario.TButton", command=self._imprimir
        ).pack(fill="x", pady=(8, 0))

        nota = tk.Frame(panel, bg="#f3f8fa")
        nota.pack(fill="x", pady=(18, 0))
        texto(
            nota,
            "Si la ruta aún no tiene distribuidor, los suscriptores importados quedan agrupados "
            "en ella y podrá asignarla después desde este formulario.",
            tamano=8,
            color=COLORES["texto_suave"],
            fondo="#f3f8fa",
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

    # ------------------------------------------------------------------ #
    def _cargar(self) -> None:
        try:
            rutas = self.ctx.operativo.listar_rutas(self.sesion)
            self.distribuidores = self.ctx.operativo.listar_distribuidores(self.sesion, incluir_inactivos=False)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.mapa = {r.id: r for r in rutas}
        self._por_nombre = {d.nombre: d.id for d in self.distribuidores}
        valores = [SIN_ASIGNAR] + [d.nombre for d in self.distribuidores]
        self.combo.configure(values=valores)
        if not self.combo.get():
            self.combo.set(SIN_ASIGNAR)

        llenar_arbol(
            self.arbol,
            [
                (
                    r.id,
                    (r.zona, r.distribuidor or "Sin asignar", r.suscriptores),
                    "aviso" if not r.distribuidor_id else None,
                )
                for r in rutas
            ],
        )
        asignadas = sum(1 for r in rutas if r.distribuidor_id)
        self.resumen.configure(
            text=f"{len(rutas)} ruta(s) · {asignadas} asignada(s) · {len(rutas) - asignadas} pendiente(s) de asignar."
        )
        if self.seleccionada and self.seleccionada in self.mapa:
            self.arbol.selection_set(str(self.seleccionada))

    def _seleccionar(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        identificador = int(seleccion[0])
        ruta = self.mapa.get(identificador)
        if not ruta:
            return
        self.seleccionada = identificador
        self.titulo_formulario.configure(text="Editar ruta")
        self.zona.delete(0, "end")
        self.zona.insert(0, ruta.zona)
        if ruta.distribuidor and ruta.distribuidor in self._por_nombre:
            self.combo.set(ruta.distribuidor)
        elif ruta.distribuidor and ruta.distribuidor not in self._por_nombre:
            self.combo.configure(values=[SIN_ASIGNAR] + [d.nombre for d in self.distribuidores] + [ruta.distribuidor])
            self.combo.set(ruta.distribuidor)
        else:
            self.combo.set(SIN_ASIGNAR)
        self.estado.configure(
            text=f"{ruta.suscriptores} suscriptor(es) agrupado(s) en esta ruta.",
            fg=COLORES["texto_suave"],
        )

    def _imprimir(self) -> None:
        """RF-02: ruta generada desde la base de datos, para reemplazar las hojas corregidas a mano."""
        ruta = self.mapa.get(self.seleccionada)
        if not ruta or not ruta.distribuidor_id:
            mostrar_error(self, "Seleccione una ruta que tenga distribuidor asignado.")
            return
        destino = directorio_exportes() / f"ruta_{nombre_archivo_seguro(ruta.distribuidor)}.html"
        try:
            archivo = self.ctx.operativo.exportar_ruta_html(self.sesion, ruta.distribuidor_id, destino)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        webbrowser.open(archivo.resolve().as_uri())
        self.estado.configure(text=f"Ruta de {ruta.distribuidor} abierta para imprimir.", fg=COLORES["exito"])

    def _nueva(self) -> None:
        self.seleccionada = None
        self.arbol.selection_remove(*self.arbol.selection())
        self.titulo_formulario.configure(text="Nueva ruta")
        self.zona.delete(0, "end")
        self.combo.set(SIN_ASIGNAR)
        self.estado.configure(text="Escriba la zona o ruta y guarde.", fg=COLORES["texto_suave"])
        self.zona.focus_set()

    def _guardar(self) -> None:
        nombre = self.combo.get()
        distribuidor_id = self._por_nombre.get(nombre) if nombre != SIN_ASIGNAR else None
        try:
            if self.seleccionada is None:
                self.seleccionada = self.ctx.operativo.crear_ruta(
                    self.sesion, self.zona.get(), distribuidor_id
                )
                mensaje = "Ruta creada correctamente."
            else:
                self.ctx.operativo.actualizar_ruta(
                    self.sesion, self.seleccionada, self.zona.get(), distribuidor_id
                )
                mensaje = "Ruta actualizada correctamente."
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._cargar()
        self.arbol.selection_set(str(self.seleccionada))
        mostrar_info(self, mensaje)
