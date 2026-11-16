"""Paleta, tipografías y estilos ttk de la interfaz."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

COLORES = {
    "fondo": "#f2f6f8",
    "panel": "#ffffff",
    "sidebar": "#0d2b3c",
    "sidebar_activo": "#1a4a62",
    "sidebar_texto": "#d7e6ee",
    "sidebar_suave": "#88a5b4",
    "primario": "#176b8c",
    "primario_hover": "#125772",
    "primario_suave": "#e3f0f5",
    "acento": "#d9852b",
    "texto": "#1b2b36",
    "texto_suave": "#5c6b76",
    "borde": "#d6e1e7",
    "exito": "#1e7a4d",
    "alerta": "#b3261e",
    "aviso": "#8a5a00",
    "blanco": "#ffffff",
}

FUENTE = "Segoe UI"


def configurar_estilos(root: tk.Misc) -> ttk.Style:
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    root.option_add("*Font", (FUENTE, 10))
    root.option_add("*TCombobox*Listbox.font", (FUENTE, 10))

    estilo.configure(".", font=(FUENTE, 10), background=COLORES["fondo"], foreground=COLORES["texto"])
    estilo.configure("TFrame", background=COLORES["fondo"])
    estilo.configure("TLabel", background=COLORES["fondo"], foreground=COLORES["texto"])
    estilo.configure("TButton", font=(FUENTE, 10), padding=(12, 7))

    estilo.configure(
        "Primario.TButton",
        background=COLORES["primario"],
        foreground=COLORES["blanco"],
        font=(FUENTE, 10, "bold"),
        padding=(14, 8),
        borderwidth=0,
    )
    estilo.map(
        "Primario.TButton",
        background=[("active", COLORES["primario_hover"]), ("disabled", "#9db9c6")],
        foreground=[("disabled", "#eef4f7")],
    )
    estilo.configure(
        "Secundario.TButton",
        background=COLORES["blanco"],
        foreground=COLORES["primario"],
        font=(FUENTE, 10),
        padding=(12, 7),
        bordercolor=COLORES["borde"],
        relief="solid",
        borderwidth=1,
    )
    estilo.map(
        "Secundario.TButton",
        background=[("active", COLORES["primario_suave"])],
        bordercolor=[("active", COLORES["primario"])],
    )
    estilo.configure(
        "Peligro.TButton",
        background="#fbeae9",
        foreground=COLORES["alerta"],
        font=(FUENTE, 10, "bold"),
        padding=(12, 7),
        borderwidth=0,
    )
    estilo.map("Peligro.TButton", background=[("active", "#f5d6d4")])

    estilo.configure(
        "TEntry",
        fieldbackground=COLORES["blanco"],
        bordercolor=COLORES["borde"],
        padding=(8, 7),
    )
    estilo.map("TEntry", bordercolor=[("focus", COLORES["primario"])])
    estilo.configure(
        "TCombobox",
        fieldbackground=COLORES["blanco"],
        background=COLORES["blanco"],
        bordercolor=COLORES["borde"],
        padding=(8, 6),
        arrowsize=16,
    )
    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", COLORES["blanco"])],
        bordercolor=[("focus", COLORES["primario"])],
    )

    estilo.configure(
        "Treeview",
        background=COLORES["blanco"],
        fieldbackground=COLORES["blanco"],
        foreground=COLORES["texto"],
        rowheight=30,
        font=(FUENTE, 10),
        borderwidth=0,
    )
    estilo.configure(
        "Treeview.Heading",
        background="#e8f1f5",
        foreground=COLORES["sidebar"],
        font=(FUENTE, 9, "bold"),
        padding=(6, 7),
        relief="flat",
    )
    estilo.map(
        "Treeview",
        background=[("selected", COLORES["primario"])],
        foreground=[("selected", COLORES["blanco"])],
    )
    estilo.configure("TProgressbar", troughcolor=COLORES["primario_suave"], background=COLORES["primario"])
    estilo.configure("Vertical.TScrollbar", background="#c7d6de", arrowcolor=COLORES["sidebar"])

    return estilo
