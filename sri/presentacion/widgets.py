"""Componentes reutilizables de la interfaz (tarjetas, tablas, formularios)."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk
from typing import Iterable

from .estilos import COLORES, FUENTE


def texto(
    master,
    contenido: str,
    tamano: int = 10,
    negrita: bool = False,
    color: str | None = None,
    fondo: str | None = None,
    **kwargs,
) -> tk.Label:
    return tk.Label(
        master,
        text=contenido,
        font=(FUENTE, tamano, "bold" if negrita else "normal"),
        fg=color or COLORES["texto"],
        bg=fondo or COLORES["panel"],
        **kwargs,
    )


def tarjeta(master, relleno: int = 16, fondo: str | None = None) -> tk.Frame:
    return tk.Frame(
        master,
        bg=fondo or COLORES["panel"],
        highlightbackground=COLORES["borde"],
        highlightthickness=1,
        bd=0,
        padx=relleno,
        pady=relleno,
    )


def cabecera_vista(master, titulo: str, subtitulo: str = "") -> tk.Frame:
    marco = tk.Frame(master, bg=COLORES["fondo"])
    texto(marco, titulo, tamano=20, negrita=True, fondo=COLORES["fondo"]).pack(anchor="w")
    if subtitulo:
        texto(
            marco,
            subtitulo,
            tamano=10,
            color=COLORES["texto_suave"],
            fondo=COLORES["fondo"],
        ).pack(anchor="w", pady=(4, 0))
    return marco


def etiqueta_campo(master, etiqueta: str) -> tk.Label:
    return texto(master, etiqueta, tamano=9, negrita=True, color=COLORES["texto_suave"])


def crear_arbol(
    master,
    columnas: Iterable[tuple],
    alto: int = 10,
    seleccion: str = "browse",
) -> ttk.Treeview:
    """Crea un Treeview con encabezados y barra vertical dentro de un contenedor.

    Cada columna se define como ``(clave, título, ancho)`` o
    ``(clave, título, ancho, estirar)``. Las columnas numéricas se marcan con
    ``estirar=False`` para que conserven su ancho y no recorten los encabezados
    cuando la ventana cambia de tamaño.
    """
    contenedor = tk.Frame(master, bg=COLORES["panel"], highlightbackground=COLORES["borde"], highlightthickness=1)
    contenedor.pack(fill="both", expand=True)

    ids = [c[0] for c in columnas]
    arbol = ttk.Treeview(contenedor, columns=ids, show="headings", height=alto, selectmode=seleccion)
    for definicion in columnas:
        columna, titulo, ancho = definicion[:3]
        estirar = definicion[3] if len(definicion) > 3 else True
        arbol.heading(columna, text=titulo, anchor="w")
        arbol.column(columna, width=ancho, minwidth=70 if estirar else ancho, anchor="w", stretch=estirar)

    barra = ttk.Scrollbar(contenedor, orient="vertical", command=arbol.yview)
    arbol.configure(yscrollcommand=barra.set)
    arbol.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")

    arbol.tag_configure("exito", foreground=COLORES["exito"])
    arbol.tag_configure("alerta", foreground=COLORES["alerta"])
    arbol.tag_configure("aviso", foreground=COLORES["aviso"])
    arbol.tag_configure("inactivo", foreground="#8a99a3")
    return arbol


def llenar_arbol(arbol: ttk.Treeview, filas: Iterable[tuple[str, Iterable, str | None]]) -> None:
    """Reemplaza el contenido del árbol.

    filas: (iid, valores, etiqueta_de_color o None)
    """
    for item in arbol.get_children():
        arbol.delete(item)
    for iid, valores, etiqueta in filas:
        arbol.insert("", "end", iid=str(iid), values=tuple(valores), tags=(etiqueta,) if etiqueta else ())


def centro(ventana: tk.Toplevel | tk.Tk, ancho: int, alto: int) -> None:
    ventana.update_idletasks()
    pantalla_ancho = ventana.winfo_screenwidth()
    pantalla_alto = ventana.winfo_screenheight()
    ancho = min(ancho, pantalla_ancho - 20)
    alto = min(alto, pantalla_alto - 50)
    x = max(0, (pantalla_ancho - ancho) // 2)
    y = max(0, (pantalla_alto - alto) // 2 - 24)
    ventana.geometry(f"{ancho}x{alto}+{x}+{y}")


def fecha_hora_legible(valor: str) -> str:
    if not valor:
        return ""
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return valor


def mostrar_error(master, mensaje: str) -> None:
    messagebox.showerror("No se pudo completar la operación", mensaje, parent=master)


def mostrar_info(master, mensaje: str, titulo: str = "Operación exitosa") -> None:
    messagebox.showinfo(titulo, mensaje, parent=master)


def confirmar(master, mensaje: str, titulo: str = "Confirmar") -> bool:
    return messagebox.askyesno(titulo, mensaje, parent=master)
