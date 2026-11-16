"""Registro de novedades de suscripción del listado impreso (RF-09, RN-12)."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from ..dominio.periodicidad import OPCIONES, etiqueta
from .estilos import COLORES, FUENTE
from .widgets import (
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

TIPOS = ("Ingreso", "Retiro", "Cambio")


class VistaNovedades(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.rutas: dict[str, int] = {}
        self.encontrados = {}
        self.seleccionado = None

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        cabecera_vista(
            self,
            "Novedades de suscripción",
            "Pase aquí los ingresos, retiros y cambios que llegan en el listado impreso. "
            "Un retiro no borra al suscriptor: conserva su historial (RN-12).",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))

        self._construir_formulario()
        self._construir_lista()
        self._cargar_rutas()
        self._cambiar_tipo()
        self._cargar_dia()

    # ------------------------------------------------------------------ #
    def _construir_formulario(self) -> None:
        panel = tarjeta(self, relleno=16)
        panel.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        panel.grid_columnconfigure(1, weight=1)
        panel.grid_columnconfigure(3, weight=1)

        fila = 0
        etiqueta_campo(panel, "TIPO DE NOVEDAD").grid(row=fila, column=0, sticky="w")
        self.tipo = tk.StringVar(value="Ingreso")
        opciones = tk.Frame(panel, bg=COLORES["panel"])
        opciones.grid(row=fila, column=1, columnspan=3, sticky="w", pady=4)
        for tipo in TIPOS:
            tk.Radiobutton(
                opciones, text=tipo, value=tipo, variable=self.tipo, command=self._cambiar_tipo,
                bg=COLORES["panel"], font=(FUENTE, 11), activebackground=COLORES["panel"],
            ).pack(side="left", padx=(0, 16))

        fila += 1
        etiqueta_campo(panel, "FECHA DEL LISTADO").grid(row=fila, column=0, sticky="w")
        self.fecha = ttk.Entry(panel, width=14, font=(FUENTE, 11))
        self.fecha.grid(row=fila, column=1, sticky="w", pady=4, ipady=3)
        self.fecha.insert(0, date.today().strftime("%d/%m/%Y"))
        self.fecha.bind("<FocusOut>", lambda _e: self._cargar_dia())

        fila += 1
        self.marco_busqueda = tk.Frame(panel, bg="#f3f8fa", padx=10, pady=8)
        self.marco_busqueda.grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(6, 8))
        texto(self.marco_busqueda, "Busque al suscriptor (nombre o dirección):", tamano=9, fondo="#f3f8fa").pack(anchor="w")
        linea = tk.Frame(self.marco_busqueda, bg="#f3f8fa")
        linea.pack(fill="x", pady=(4, 6))
        self.buscar = ttk.Entry(linea, font=(FUENTE, 11))
        self.buscar.pack(side="left", fill="x", expand=True, ipady=3)
        self.buscar.bind("<Return>", lambda _e: self._buscar())
        ttk.Button(linea, text="Buscar", style="Secundario.TButton", command=self._buscar).pack(side="left", padx=(8, 0))
        self.arbol_busqueda = crear_arbol(
            self.marco_busqueda,
            [("nombre", "Nombre", 180), ("direccion", "Dirección", 200), ("ruta", "Ruta", 60, False), ("estado", "Estado", 80, False)],
            alto=4,
        )
        self.arbol_busqueda.bind("<<TreeviewSelect>>", self._seleccionar)

        self.campos = {}
        for etiqueta_texto, clave in (
            ("NOMBRE", "nombre"),
            ("DIRECCIÓN (ENTRE SEMANA)", "direccion"),
            ("DIRECCIÓN DE FIN DE SEMANA (SI ES OTRA)", "direccion_fs"),
        ):
            fila += 1
            etiqueta_campo(panel, etiqueta_texto).grid(row=fila, column=0, sticky="w")
            entrada = ttk.Entry(panel, font=(FUENTE, 11))
            entrada.grid(row=fila, column=1, columnspan=3, sticky="ew", pady=4, ipady=3)
            self.campos[clave] = entrada

        fila += 1
        etiqueta_campo(panel, "PRODUCTOS").grid(row=fila, column=0, sticky="w")
        productos = tk.Frame(panel, bg=COLORES["panel"])
        productos.grid(row=fila, column=1, columnspan=3, sticky="w", pady=4)
        self.tie = tk.BooleanVar(value=True)
        self.pt = tk.BooleanVar(value=False)
        for texto_producto, variable in (("El Tiempo (TIE)", self.tie), ("Portafolio (PT)", self.pt)):
            tk.Checkbutton(
                productos, text=texto_producto, variable=variable, bg=COLORES["panel"], font=(FUENTE, 11),
                activebackground=COLORES["panel"],
            ).pack(side="left", padx=(0, 16))

        fila += 1
        etiqueta_campo(panel, "PERIODICIDAD").grid(row=fila, column=0, sticky="w")
        self.periodicidad = ttk.Combobox(panel, values=list(OPCIONES), width=14, font=(FUENTE, 11))
        self.periodicidad.grid(row=fila, column=1, sticky="w", pady=4, ipady=2)
        self.periodicidad.set("Diaria")
        etiqueta_campo(panel, "RUTA").grid(row=fila, column=2, sticky="e", padx=(12, 8))
        self.ruta = ttk.Combobox(panel, state="readonly", width=12, font=(FUENTE, 11))
        self.ruta.grid(row=fila, column=3, sticky="w", pady=4, ipady=2)

        fila += 1
        etiqueta_campo(panel, "DETALLE (OPCIONAL)").grid(row=fila, column=0, sticky="w")
        self.detalle = ttk.Entry(panel, font=(FUENTE, 11))
        self.detalle.grid(row=fila, column=1, columnspan=3, sticky="ew", pady=4, ipady=3)

        fila += 1
        acciones = tk.Frame(panel, bg=COLORES["panel"])
        acciones.grid(row=fila, column=0, columnspan=4, sticky="ew", pady=(12, 0))
        ttk.Button(acciones, text="Guardar novedad", style="Primario.TButton", command=self._guardar).pack(side="left")
        ttk.Button(acciones, text="Limpiar", style="Secundario.TButton", command=self._limpiar).pack(side="left", padx=(8, 0))
        self.estado = texto(
            panel,
            "La periodicidad admite: Diaria, L-V, L-S, S-D, D o una lista de días.",
            tamano=9,
            color=COLORES["texto_suave"],
            wraplength=560,
            justify="left",
        )
        self.estado.grid(row=fila + 1, column=0, columnspan=4, sticky="w", pady=(10, 0))

    def _construir_lista(self) -> None:
        panel = tarjeta(self, relleno=16)
        panel.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        texto(panel, "Novedades del día", tamano=12, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Úsela para avisar a cada distribuidor los cambios de su ruta.",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 10))
        self.arbol_dia = crear_arbol(
            panel,
            [("tipo", "Tipo", 70, False), ("suscriptor", "Suscriptor", 150), ("ruta", "Ruta", 55, False), ("detalle", "Detalle", 160)],
            alto=18,
        )
        self.resumen = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.resumen.pack(anchor="w", pady=(8, 0))

    # ------------------------------------------------------------------ #
    def _cargar_rutas(self) -> None:
        try:
            rutas = self.ctx.operativo.listar_rutas(self.sesion)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.rutas = {r.zona: r.id for r in rutas}
        self.ruta.configure(values=list(self.rutas))

    def _cargar_dia(self) -> None:
        try:
            novedades = self.ctx.suscripciones.novedades_del_dia(self.sesion, self.fecha.get())
        except Exception:  # noqa: BLE001 - fecha a medio escribir
            return
        llenar_arbol(
            self.arbol_dia,
            [
                (n.id, (n.tipo.capitalize(), n.suscriptor, n.zona, n.detalle),
                 {"INGRESO": "exito", "RETIRO": "alerta"}.get(n.tipo, "aviso"))
                for n in novedades
            ],
        )
        self.resumen.configure(text=f"{len(novedades)} novedad(es) registradas para el {self.fecha.get()}.")

    def _cambiar_tipo(self) -> None:
        tipo = self.tipo.get()
        if tipo == "Ingreso":
            self.marco_busqueda.grid_remove()
            self._limpiar(conservar_tipo=True)
        else:
            self.marco_busqueda.grid()
        editable = "disabled" if tipo == "Retiro" else "normal"
        for entrada in self.campos.values():
            entrada.configure(state=editable)
        self.periodicidad.configure(state=editable)
        self.ruta.configure(state="disabled" if tipo == "Retiro" else "readonly")

    def _buscar(self) -> None:
        try:
            encontrados = self.ctx.suscripciones.buscar(self.sesion, self.buscar.get().strip(), limite=50)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.encontrados = {s.id: s for s in encontrados}
        llenar_arbol(
            self.arbol_busqueda,
            [
                (s.id, (s.nombre, s.direccion, s.zona, "Activo" if s.activo else "Retirado"), None if s.activo else "inactivo")
                for s in encontrados
            ],
        )
        if not encontrados:
            self.estado.configure(text="No se encontraron suscriptores con ese texto.", fg=COLORES["aviso"])

    def _seleccionar(self, _evento=None) -> None:
        seleccion = self.arbol_busqueda.selection()
        if not seleccion:
            return
        suscriptor = self.encontrados.get(int(seleccion[0]))
        if not suscriptor:
            return
        self.seleccionado = suscriptor.id
        for clave, valor in (("nombre", suscriptor.nombre), ("direccion", suscriptor.direccion),
                             ("direccion_fs", suscriptor.direccion_fs)):
            entrada = self.campos[clave]
            estado = str(entrada.cget("state"))
            entrada.configure(state="normal")
            entrada.delete(0, "end")
            entrada.insert(0, valor)
            entrada.configure(state=estado)
        self.tie.set("TIE" in suscriptor.productos)
        self.pt.set("PT" in suscriptor.productos)
        self.periodicidad.set(etiqueta(suscriptor.periodicidad))
        self.ruta.set(suscriptor.zona)
        self.estado.configure(text=f"Seleccionado: {suscriptor.nombre} · ruta {suscriptor.zona}.", fg=COLORES["texto_suave"])

    def _limpiar(self, conservar_tipo: bool = False) -> None:
        self.seleccionado = None
        for entrada in self.campos.values():
            entrada.configure(state="normal")
            entrada.delete(0, "end")
        self.detalle.delete(0, "end")
        self.buscar.delete(0, "end")
        llenar_arbol(self.arbol_busqueda, [])
        self.tie.set(True)
        self.pt.set(False)
        self.periodicidad.set("Diaria")
        if not conservar_tipo:
            self._cambiar_tipo()

    def _guardar(self) -> None:
        tipo = self.tipo.get()
        datos = {
            "nombre": self.campos["nombre"].get(),
            "direccion": self.campos["direccion"].get(),
            "direccion_fs": self.campos["direccion_fs"].get(),
            "productos": [p for p, v in (("TIE", self.tie), ("PT", self.pt)) if v.get()],
            "periodicidad": self.periodicidad.get(),
            "ruta_id": self.rutas.get(self.ruta.get()),
            "detalle": self.detalle.get(),
        }
        servicio = self.ctx.suscripciones
        try:
            if tipo == "Ingreso":
                resultado = servicio.registrar_ingreso(self.sesion, self.fecha.get(), **datos)
                if resultado["aviso"]:
                    mostrar_info(self, resultado["aviso"], "Revise el ingreso")
                mensaje = "Ingreso registrado."
            elif not self.seleccionado:
                mostrar_error(self, "Busque y seleccione primero al suscriptor.")
                return
            elif tipo == "Retiro":
                nombre = self.campos["nombre"].get()
                if not confirmar(self, f"¿Registrar el retiro de {nombre}?\n\nNo se borra: queda en el historial.", "Confirmar retiro"):
                    return
                servicio.registrar_retiro(self.sesion, self.seleccionado, self.fecha.get(), datos["detalle"])
                mensaje = "Retiro registrado; el suscriptor queda inactivo."
            else:
                campos = servicio.registrar_cambio(self.sesion, self.seleccionado, self.fecha.get(), **datos)
                mensaje = "Cambio registrado: " + ", ".join(campos) + "."
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self._limpiar()
        self._cargar_dia()
        self.estado.configure(text=mensaje, fg=COLORES["exito"])
