"""Ventana principal de la aplicación de escritorio."""

from __future__ import annotations

import tkinter as tk

from .estilos import COLORES, configurar_estilos
from .login import LoginFrame
from .widgets import centro


class Aplicacion(tk.Tk):
    def __init__(self, contexto):
        super().__init__()
        self.ctx = contexto
        self.sesion = None
        self.title("SRI · Sistema de Respaldo de Información — Distribuciones Cam Dylan S.A.S.")
        self.configure(bg=COLORES["fondo"])
        self.minsize(1140, 700)
        centro(self, 1280, 800)
        configurar_estilos(self)
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.vista = None
        self.mostrar_login()

    def _limpiar(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def mostrar_login(self) -> None:
        self._limpiar()
        self.vista = LoginFrame(self, self)
        self.vista.pack(fill="both", expand=True)

    def iniciar_sesion(self, sesion) -> None:
        self.sesion = sesion
        self._limpiar()
        from .principal import ShellFrame

        self.vista = ShellFrame(self, self)
        self.vista.pack(fill="both", expand=True)
        self.after(300, self._pedir_contrasena if sesion.cambiar_contrasena else self._mostrar_avisos)

    def _pedir_contrasena(self) -> None:
        """Plan de despliegue: no se trabaja con la contraseña de demostración."""
        from .dialogos import DialogoContrasena

        DialogoContrasena(self, self, obligatorio=True, al_terminar=self._mostrar_avisos)

    def _mostrar_avisos(self) -> None:
        """RF-07: un respaldo fallido o una copia en Google Drive vencida no pasan inadvertidos."""
        from tkinter import messagebox

        try:
            avisos = self.ctx.respaldos.avisos()
        except Exception:  # noqa: BLE001
            return
        if avisos:
            messagebox.showwarning("Aviso de respaldos", "\n\n".join(avisos), parent=self)

    def _respaldo_diario(self) -> None:
        """RF-07: si hoy aún no hay respaldo, se genera al salir (nunca bloquea la salida)."""
        if self.sesion is not None:
            self.ctx.respaldos.respaldo_automatico(self.sesion.usuario_id)

    def cerrar_sesion(self) -> None:
        self._respaldo_diario()
        self.sesion = None
        self.mostrar_login()

    def reiniciar_sesion(self, mensaje: str | None = None) -> None:
        from tkinter import messagebox

        if mensaje:
            messagebox.showinfo("Sesión finalizada", mensaje, parent=self)
        self.sesion = None  # tras restaurar, el usuario puede no existir en la base: no se respalda
        self.mostrar_login()

    def _cerrar(self) -> None:
        try:
            self._respaldo_diario()
            self.ctx.cerrar()
        finally:
            self.destroy()
