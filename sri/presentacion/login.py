"""Pantalla de inicio de sesión (RF-08)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .estilos import COLORES, FUENTE
from .widgets import texto


class LoginFrame(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.grid_columnconfigure(0, weight=5, uniform="login")
        self.grid_columnconfigure(1, weight=4, uniform="login")
        self.grid_rowconfigure(0, weight=1)

        self._construir_marca()
        self._construir_formulario()

    # ------------------------------------------------------------------ #
    def _construir_marca(self) -> None:
        panel = tk.Frame(self, bg=COLORES["sidebar"])
        panel.grid(row=0, column=0, sticky="nsew")
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        centro = tk.Frame(panel, bg=COLORES["sidebar"])
        centro.grid(row=0, column=0, sticky="nsew", padx=56, pady=56)
        centro.grid_rowconfigure(5, weight=1)

        logo = tk.Frame(centro, bg=COLORES["primario"], width=76, height=76)
        logo.grid(row=0, column=0, sticky="w")
        logo.grid_propagate(False)
        tk.Label(
            logo,
            text="SRI",
            bg=COLORES["primario"],
            fg="white",
            font=(FUENTE, 22, "bold"),
        ).place(relx=0.5, rely=0.5, anchor="center")

        texto(
            centro,
            "Sistema de Respaldo\nde Información",
            tamano=27,
            negrita=True,
            color="white",
            fondo=COLORES["sidebar"],
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(26, 8))
        texto(
            centro,
            "Distribuciones Cam Dylan S.A.S.",
            tamano=12,
            color=COLORES["sidebar_texto"],
            fondo=COLORES["sidebar"],
        ).grid(row=2, column=0, sticky="w")

        tk.Frame(centro, bg=COLORES["sidebar_activo"], height=2, width=64).grid(
            row=3, column=0, sticky="w", pady=(26, 18)
        )

        caracteristicas = [
            "Consolida el listado de repartidores y las novedades",
            "Historial propio de suscriptores, rutas y entregas",
            "Respaldo diario cifrado y copia en Google Drive",
            "Datos cifrados y acceso por rol",
        ]
        bloque_caracteristicas = tk.Frame(centro, bg=COLORES["sidebar"])
        bloque_caracteristicas.grid(row=4, column=0, sticky="w")
        for caracteristica in caracteristicas:
            fila = tk.Frame(bloque_caracteristicas, bg=COLORES["sidebar"])
            fila.pack(anchor="w", pady=(0, 8))
            tk.Label(
                fila,
                text="•",
                bg=COLORES["sidebar"],
                fg=COLORES["acento"],
                font=(FUENTE, 13, "bold"),
            ).pack(side="left", padx=(0, 10))
            texto(
                fila,
                caracteristica,
                tamano=10,
                color=COLORES["sidebar_texto"],
                fondo=COLORES["sidebar"],
            ).pack(side="left")

        texto(
            centro,
            "Universidad de Santander · Proyecto Integrador · 2026",
            tamano=9,
            color=COLORES["sidebar_suave"],
            fondo=COLORES["sidebar"],
        ).grid(row=6, column=0, sticky="sw")

    def _construir_formulario(self) -> None:
        contenedor = tk.Frame(self, bg=COLORES["fondo"])
        contenedor.grid(row=0, column=1, sticky="nsew")
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)

        tarjeta = tk.Frame(
            contenedor,
            bg=COLORES["panel"],
            highlightbackground=COLORES["borde"],
            highlightthickness=1,
            padx=38,
            pady=36,
        )
        tarjeta.grid(row=0, column=0, padx=46, pady=20, sticky="ew")

        texto(tarjeta, "Iniciar sesión", tamano=20, negrita=True).pack(anchor="w")
        texto(
            tarjeta,
            "Ingrese sus credenciales para acceder al sistema.",
            tamano=10,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(5, 26))

        texto(tarjeta, "USUARIO", tamano=9, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
        self.usuario = ttk.Entry(tarjeta, font=(FUENTE, 12))
        self.usuario.pack(fill="x", pady=(6, 16), ipady=4)

        texto(tarjeta, "CONTRASEÑA", tamano=9, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
        self.contrasena = ttk.Entry(tarjeta, font=(FUENTE, 12), show="•")
        self.contrasena.pack(fill="x", pady=(6, 8), ipady=4)

        self.error = texto(tarjeta, "", tamano=9, color=COLORES["alerta"])
        self.error.pack(anchor="w", pady=(0, 12))

        self.boton = ttk.Button(tarjeta, text="Ingresar al sistema", style="Primario.TButton", command=self._ingresar)
        self.boton.pack(fill="x", ipady=4)

        texto(
            tarjeta,
            "Acceso de demostración: secretaria / gerencia · Contraseña: Sri2026*",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(22, 0))

        self.usuario.bind("<Return>", lambda _e: self._ingresar())
        self.contrasena.bind("<Return>", lambda _e: self._ingresar())
        self.after(200, self.usuario.focus_set)

    # ------------------------------------------------------------------ #
    def _ingresar(self) -> None:
        nombre = self.usuario.get().strip()
        contrasena = self.contrasena.get()
        if not nombre or not contrasena:
            self._mostrar_error("Ingrese el usuario y la contraseña.")
            return
        self.boton.configure(state="disabled", text="Validando…")
        self.update_idletasks()
        try:
            sesion = self.ctx.auth.iniciar_sesion(nombre, contrasena)
        except Exception as error:  # noqa: BLE001 - se muestra el mensaje de negocio
            self.boton.configure(state="normal", text="Ingresar al sistema")
            self.contrasena.delete(0, "end")
            self._mostrar_error(str(error) or "No se pudo iniciar sesión.")
            return
        self.error.configure(text="")
        self.app.iniciar_sesion(sesion)

    def _mostrar_error(self, mensaje: str) -> None:
        self.error.configure(text=mensaje)
