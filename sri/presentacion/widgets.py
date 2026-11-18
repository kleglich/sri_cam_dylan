"""Componentes reutilizables de la interfaz (tarjetas, tablas, formularios)."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date, datetime, timedelta
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
    tamano = tamano + 1 if tamano < 11 else tamano  # textos pequeños un punto más grandes: usuarios mayores
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


def marco_desplazable(master, fondo: str) -> tuple[tk.Frame, tk.Frame]:
    """Devuelve (contenedor, interior): el interior se desplaza con barra y rueda si no cabe."""
    contenedor = tk.Frame(master, bg=fondo)
    lienzo = tk.Canvas(contenedor, bg=fondo, highlightthickness=0, bd=0)
    barra = ttk.Scrollbar(contenedor, orient="vertical", command=lienzo.yview)
    interior = tk.Frame(lienzo, bg=fondo)
    ventana = lienzo.create_window(0, 0, window=interior, anchor="nw")
    lienzo.configure(yscrollcommand=barra.set)
    interior.bind(
        "<Configure>",
        lambda _e: lienzo.configure(scrollregion=lienzo.bbox("all"), width=interior.winfo_reqwidth()),
    )
    lienzo.bind("<Configure>", lambda e: lienzo.itemconfigure(ventana, width=e.width))

    def rueda(evento) -> None:
        if not isinstance(evento.widget, ttk.Treeview):  # la lista se desplaza sola
            lienzo.yview_scroll(int(-evento.delta / 120), "units")

    contenedor.bind("<Enter>", lambda _e: contenedor.bind_all("<MouseWheel>", rueda))
    contenedor.bind("<Leave>", lambda _e: contenedor.unbind_all("<MouseWheel>"))
    barra.pack(side="right", fill="y")
    lienzo.pack(side="left", fill="both", expand=True)
    return contenedor, interior


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


# Estados de entrega dichos como los dice la empresa.
ESTADO_LEGIBLE = {
    "PENDIENTE": "Por entregar",
    "ENTREGADA": "Entregado",
    "NO ENTREGADA": "No se entregó",
    "CON NOVEDAD": "Entregado con novedad",
}


def al_escribir(entrada: tk.Widget, funcion, espera_ms: int = 350) -> None:
    """Ejecuta `funcion` cuando la persona deja de escribir (filtrar sin pulsar «Buscar»)."""
    pendiente = {"id": None}

    def programar(_evento=None):
        if pendiente["id"]:
            entrada.after_cancel(pendiente["id"])
        pendiente["id"] = entrada.after(espera_ms, funcion)

    entrada.bind("<KeyRelease>", programar, add="+")


class CampoFecha(tk.Frame):
    """Fecha dd/mm/aaaa con botones Hoy, Ayer y un calendario para elegirla sin escribir."""

    def __init__(self, master, valor=None, al_cambiar=None, fondo: str | None = None):
        super().__init__(master, bg=fondo or COLORES["panel"])
        self.al_cambiar = al_cambiar
        self.entrada = ttk.Entry(self, width=11, font=(FUENTE, 12))
        self.entrada.pack(side="left", ipady=3)
        self.botones = [
            ttk.Button(self, text="Hoy", style="Mini.TButton", width=4, command=lambda: self.set(date.today(), True)),
            ttk.Button(self, text="Ayer", style="Mini.TButton", width=4,
                       command=lambda: self.set(date.today() - timedelta(days=1), True)),
            ttk.Button(self, text="Calendario", style="Mini.TButton", width=9, command=self._abrir_calendario),
        ]
        for boton in self.botones:
            boton.pack(side="left", padx=(4, 0))
        self.entrada.bind("<Return>", lambda _e: self._avisar())
        if valor is not None:
            self.set(valor)

    def get(self) -> str:
        return self.entrada.get().strip()

    def set(self, valor, avisar: bool = False) -> None:
        self.entrada.delete(0, "end")
        if valor:
            self.entrada.insert(0, valor.strftime("%d/%m/%Y"))
        if avisar:
            self._avisar()

    def estado(self, activo: bool) -> None:
        for control in [self.entrada, *self.botones]:
            control.configure(state="normal" if activo else "disabled")

    def _avisar(self) -> None:
        if self.al_cambiar:
            self.al_cambiar()

    def _abrir_calendario(self) -> None:
        try:
            actual = datetime.strptime(self.get(), "%d/%m/%Y").date()
        except ValueError:
            actual = date.today()
        Calendario(self, actual, lambda dia: self.set(dia, True))


MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre")


class Calendario(tk.Toplevel):
    """Mes en una cuadrícula; un clic en el día lo elige. Los días futuros no se pueden elegir."""

    def __init__(self, master, fecha: date, al_elegir):
        super().__init__(master)
        self.title("Elegir fecha")
        self.configure(bg=COLORES["panel"])
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.al_elegir = al_elegir
        self.anio, self.mes = fecha.year, fecha.month
        self.marco = tk.Frame(self, bg=COLORES["panel"], padx=14, pady=12)
        self.marco.pack()
        self._dibujar()
        self.update_idletasks()
        x = master.winfo_rootx()
        y = master.winfo_rooty() + master.winfo_height() + 4
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    def _mover(self, pasos: int) -> None:
        total = self.anio * 12 + self.mes - 1 + pasos
        self.anio, self.mes = divmod(total, 12)
        self.mes += 1
        self._dibujar()

    def _dibujar(self) -> None:
        for widget in self.marco.winfo_children():
            widget.destroy()
        cabeza = tk.Frame(self.marco, bg=COLORES["panel"])
        cabeza.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 8))
        ttk.Button(cabeza, text="◀", width=3, style="Secundario.TButton", command=lambda: self._mover(-1)).pack(side="left")
        ttk.Button(cabeza, text="▶", width=3, style="Secundario.TButton", command=lambda: self._mover(1)).pack(side="right")
        tk.Label(cabeza, text=f"{MESES[self.mes - 1]} {self.anio}", bg=COLORES["panel"],
                 font=(FUENTE, 13, "bold"), fg=COLORES["texto"]).pack(side="left", expand=True)
        for columna, nombre in enumerate(("Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do")):
            tk.Label(self.marco, text=nombre, bg=COLORES["panel"], fg=COLORES["texto_suave"],
                     font=(FUENTE, 11, "bold"), width=4).grid(row=1, column=columna)
        hoy = date.today()
        for fila, semana in enumerate(calendar.monthcalendar(self.anio, self.mes), start=2):
            for columna, dia in enumerate(semana):
                if not dia:
                    continue
                fecha = date(self.anio, self.mes, dia)
                boton = tk.Button(
                    self.marco, text=str(dia), width=4, font=(FUENTE, 12), relief="flat",
                    bg=COLORES["primario"] if fecha == hoy else COLORES["primario_suave"],
                    fg="white" if fecha == hoy else COLORES["texto"],
                    state="disabled" if fecha > hoy else "normal",
                    command=lambda f=fecha: self._elegir(f),
                )
                boton.grid(row=fila, column=columna, padx=2, pady=2)

    def _elegir(self, fecha: date) -> None:
        self.destroy()
        self.al_elegir(fecha)
