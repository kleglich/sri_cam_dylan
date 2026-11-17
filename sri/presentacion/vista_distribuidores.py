"""Gestión de distribuidores (RF-04, RN-02)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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


class VistaDistribuidores(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.seleccionado = None
        self.mapa = {}

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        cabecera_vista(
            self,
            "Distribuidores",
            "Registre, actualice y dé de baja a los integrantes del equipo operativo. "
            "Para dar de baja a un repartidor, primero pase sus rutas a otro.",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))

        self._construir_lista()
        self._construir_formulario()
        self._cargar()

    def _construir_lista(self) -> None:
        panel = tarjeta(self, relleno=16)
        panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        texto(fila, "Equipo operativo", tamano=12, negrita=True).pack(side="left")
        ttk.Button(fila, text="Actualizar", style="Secundario.TButton", command=self._cargar).pack(side="right")

        self.arbol = crear_arbol(
            panel,
            [
                ("nombre", "Nombre", 230),
                ("telefono", "Teléfono", 140),
                ("rutas", "Rutas", 70),
                ("estado", "Estado", 90),
            ],
            alto=16,
        )
        self.arbol.pack(fill="both", expand=True, pady=(12, 0))
        self.arbol.bind("<<TreeviewSelect>>", self._seleccionar)

    def _construir_formulario(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

        self.titulo_formulario = texto(panel, "Nuevo distribuidor", tamano=12, negrita=True)
        self.titulo_formulario.pack(anchor="w")
        texto(
            panel,
            "El nombre y el teléfono son obligatorios.",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 16))

        etiqueta_campo(panel, "NOMBRE COMPLETO").pack(anchor="w")
        self.nombre = ttk.Entry(panel, font=(FUENTE, 12))
        self.nombre.pack(fill="x", pady=(5, 12), ipady=4)

        etiqueta_campo(panel, "TELÉFONO").pack(anchor="w")
        self.telefono = ttk.Entry(panel, font=(FUENTE, 12))
        self.telefono.pack(fill="x", pady=(5, 16), ipady=4)

        self.estado = texto(panel, "Seleccione un distribuidor o cree uno nuevo.", tamano=9, color=COLORES["texto_suave"])
        self.estado.pack(anchor="w", pady=(0, 16))

        ttk.Button(panel, text="Guardar", style="Primario.TButton", command=self._guardar).pack(fill="x")
        ttk.Button(panel, text="Nuevo", style="Secundario.TButton", command=self._nuevo).pack(fill="x", pady=(8, 0))
        self.boton_estado = ttk.Button(panel, text="Dar de baja", style="Peligro.TButton", command=self._cambiar_estado)
        self.boton_estado.pack(fill="x", pady=(8, 0))

        nota = tk.Frame(panel, bg="#f3f8fa")
        nota.pack(fill="x", pady=(18, 0))
        texto(
            nota,
            "Las rutas se asignan desde la opción “Rutas y distribuidores”. "
            "Cada ruta es de un solo repartidor a la vez.",
            tamano=8,
            color=COLORES["texto_suave"],
            fondo="#f3f8fa",
            wraplength=340,
            justify="left",
        ).pack(anchor="w", padx=10, pady=8)

    # ------------------------------------------------------------------ #
    def _cargar(self) -> None:
        try:
            distribuidores = self.ctx.operativo.listar_distribuidores(self.sesion, incluir_inactivos=True)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.mapa = {d.id: d for d in distribuidores}
        llenar_arbol(
            self.arbol,
            [
                (
                    d.id,
                    (
                        d.nombre,
                        d.telefono,
                        d.rutas,
                        "Activo" if d.activo else "Inactivo",
                    ),
                    None if d.activo else "inactivo",
                )
                for d in distribuidores
            ],
        )
        if self.seleccionado and self.seleccionado in self.mapa:
            self.arbol.selection_set(str(self.seleccionado))

    def _seleccionar(self, _evento=None) -> None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return
        identificador = int(seleccion[0])
        distribuidor = self.mapa.get(identificador)
        if not distribuidor:
            return
        self.seleccionado = identificador
        self.titulo_formulario.configure(text="Editar distribuidor")
        self.nombre.delete(0, "end")
        self.nombre.insert(0, distribuidor.nombre)
        self.telefono.delete(0, "end")
        self.telefono.insert(0, distribuidor.telefono)
        self.boton_estado.configure(
            text="Reactivar" if not distribuidor.activo else "Dar de baja",
            style="Primario.TButton" if not distribuidor.activo else "Peligro.TButton",
        )
        self.estado.configure(
            text=(
                f"{distribuidor.nombre} · {distribuidor.rutas} ruta(s) asignada(s) · "
                + ("activo" if distribuidor.activo else "inactivo")
            ),
            fg=COLORES["texto_suave"],
        )

    def _nuevo(self) -> None:
        self.seleccionado = None
        self.arbol.selection_remove(*self.arbol.selection())
        self.titulo_formulario.configure(text="Nuevo distribuidor")
        self.nombre.delete(0, "end")
        self.telefono.delete(0, "end")
        self.boton_estado.configure(text="Dar de baja", style="Peligro.TButton")
        self.estado.configure(text="Complete los datos del nuevo distribuidor.", fg=COLORES["texto_suave"])
        self.nombre.focus_set()

    def _guardar(self) -> None:
        try:
            if self.seleccionado is None:
                self.seleccionado = self.ctx.operativo.crear_distribuidor(
                    self.sesion, self.nombre.get(), self.telefono.get()
                )
                mensaje = "Distribuidor creado correctamente."
            else:
                self.ctx.operativo.actualizar_distribuidor(
                    self.sesion, self.seleccionado, self.nombre.get(), self.telefono.get()
                )
                mensaje = "Distribuidor actualizado correctamente."
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._cargar()
        if self.seleccionado:
            self.arbol.selection_set(str(self.seleccionado))
        mostrar_info(self, mensaje)

    def _cambiar_estado(self) -> None:
        if not self.seleccionado:
            mostrar_error(self, "Seleccione un distribuidor de la lista.")
            return
        distribuidor = self.mapa.get(self.seleccionado)
        if not distribuidor:
            return
        try:
            self.ctx.operativo.cambiar_estado_distribuidor(
                self.sesion, self.seleccionado, not distribuidor.activo
            )
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._cargar()
        self.arbol.selection_set(str(self.seleccionado))
        mostrar_info(
            self,
            "Distribuidor reactivado." if not distribuidor.activo else "Distribuidor dado de baja.",
        )
