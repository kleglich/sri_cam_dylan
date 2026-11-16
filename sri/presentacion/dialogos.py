"""Diálogos modales de la interfaz."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .estilos import COLORES, FUENTE
from .widgets import centro, mostrar_error, mostrar_info, texto


class DialogoContrasena(tk.Toplevel):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.title("Cambiar contraseña")
        self.configure(bg=COLORES["panel"])
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        centro(self, 440, 430)

        marco = tk.Frame(self, bg=COLORES["panel"], padx=28, pady=24)
        marco.pack(fill="both", expand=True)

        texto(marco, "Cambiar contraseña", tamano=16, negrita=True).pack(anchor="w")
        texto(
            marco,
            f"Usuario: {app.sesion.nombre} · Rol: {app.sesion.rol}",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(4, 18))

        self.actual = self._campo(marco, "Contraseña actual")
        self.nueva = self._campo(marco, "Nueva contraseña (mínimo 8 caracteres)")
        self.confirmacion = self._campo(marco, "Confirmar nueva contraseña")

        botones = tk.Frame(marco, bg=COLORES["panel"])
        botones.pack(fill="x", pady=(12, 0))
        ttk.Button(botones, text="Cancelar", style="Secundario.TButton", command=self.destroy).pack(side="right")
        ttk.Button(botones, text="Guardar", style="Primario.TButton", command=self._guardar).pack(side="right", padx=(0, 8))

        self.after(120, self.actual.focus_set)

    def _campo(self, master, etiqueta: str) -> ttk.Entry:
        texto(master, etiqueta.upper(), tamano=9, negrita=True, color=COLORES["texto_suave"]).pack(
            anchor="w", pady=(8, 4)
        )
        entrada = ttk.Entry(master, show="•", font=(FUENTE, 11))
        entrada.pack(fill="x", ipady=4)
        return entrada

    def _guardar(self) -> None:
        try:
            self.app.ctx.auth.cambiar_contrasena(
                self.app.sesion,
                self.actual.get(),
                self.nueva.get(),
                self.confirmacion.get(),
            )
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        mostrar_info(self, "La contraseña se actualizó correctamente.")
        self.destroy()


class DialogoHistorial(tk.Toplevel):
    def __init__(self, master, app, suscriptor_id: int, nombre: str):
        super().__init__(master)
        self.app = app
        self.title(f"Historial de entregas · {nombre}")
        self.configure(bg=COLORES["fondo"])
        self.transient(master)
        centro(self, 940, 560)
        self.minsize(760, 460)

        marco = tk.Frame(self, bg=COLORES["fondo"], padx=22, pady=20)
        marco.pack(fill="both", expand=True)

        suscriptor = app.ctx.suscriptores.obtener(suscriptor_id)
        texto(marco, nombre, tamano=17, negrita=True, fondo=COLORES["fondo"]).pack(anchor="w")
        if suscriptor:
            texto(
                marco,
                f"Dirección: {suscriptor.direccion}   ·   Ruta: {suscriptor.zona}   ·   "
                f"Distribuidor: {suscriptor.distribuidor or 'Sin asignar'}",
                tamano=9,
                color=COLORES["texto_suave"],
                fondo=COLORES["fondo"],
            ).pack(anchor="w", pady=(4, 2))
            if suscriptor.novedades:
                texto(
                    marco,
                    f"Última novedad: {suscriptor.novedades}",
                    tamano=9,
                    color=COLORES["aviso"],
                    fondo=COLORES["fondo"],
                ).pack(anchor="w", pady=(2, 0))

        from .widgets import crear_arbol, llenar_arbol

        arbol = crear_arbol(
            marco,
            [
                ("fecha", "Fecha", 120),
                ("estado", "Estado", 140),
                ("novedad", "Novedad registrada", 520),
            ],
            alto=14,
        )
        arbol.pack(fill="both", expand=True, pady=(16, 12))
        try:
            entregas = app.ctx.consultas.historial_suscriptor(app.sesion, suscriptor_id)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        from ..util import formato_fecha

        llenar_arbol(
            arbol,
            [
                (
                    e.id or 0,
                    (formato_fecha(e.fecha), e.estado, e.novedad or "—"),
                    "exito" if e.estado == "ENTREGADA" else ("alerta" if e.estado == "NO ENTREGADA" else "aviso"),
                )
                for e in entregas
            ],
        )
        pie = tk.Frame(marco, bg=COLORES["fondo"])
        pie.pack(fill="x")
        texto(
            pie,
            f"{len(entregas)} registro(s) de entrega",
            tamano=9,
            color=COLORES["texto_suave"],
            fondo=COLORES["fondo"],
        ).pack(side="left")
        ttk.Button(pie, text="Cerrar", style="Secundario.TButton", command=self.destroy).pack(side="right")
