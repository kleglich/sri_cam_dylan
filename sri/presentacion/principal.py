"""Contenedor principal: barra lateral por rol, encabezado y vistas."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk

from .dialogos import DialogoContrasena
from .estilos import COLORES, FUENTE
from .vista_consultas import VistaConsultas
from .vista_distribuidores import VistaDistribuidores
from .vista_entregas import VistaEntregas
from .vista_importacion import VistaImportacion
from .vista_inicio import VistaInicio
from .vista_novedades import VistaNovedades
from .vista_reportes import VistaReportes
from .vista_respaldos import VistaRespaldos
from .vista_rutas import VistaRutas
from .widgets import texto

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def fecha_larga() -> str:
    hoy = date.today()
    return f"{DIAS[hoy.weekday()]}, {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"


class ShellFrame(tk.Frame):
    VISTAS = {
        "inicio": (VistaInicio, "Inicio", None),
        "importar": (VistaImportacion, "Importar listado de repartidores", "RF-01"),
        "novedades": (VistaNovedades, "Pasar el listado impreso", "RF-09"),
        "entregas": (VistaEntregas, "Lo que reportan los repartidores", "RF-05"),
        "rutas": (VistaRutas, "Rutas y distribuidores", "RF-02"),
        "distribuidores": (VistaDistribuidores, "Distribuidores", "RF-04"),
        "consultas": (VistaConsultas, "Consulta del historial", "RF-06"),
        "reportes": (VistaReportes, "Reporte diario de entregas", "RF-03"),
        "respaldos": (VistaRespaldos, "Respaldos de la base de datos", "RF-07"),
    }

    # Botón «? Ayuda»: para qué sirve cada pantalla, en dos líneas.
    AYUDAS = {
        "inicio": "Resumen del día y la rutina que falta.\nPulse cada paso de la rutina para ir a esa pantalla.",
        "importar": "Carga el Excel de repartidores de la empresa, tal como está.\n"
                    "Se usa al empezar o para volver a cargar el listado completo; antes, cree un respaldo.",
        "novedades": "Aquí se pasan los ingresos, retiros y cambios que trae el listado impreso de la editorial.\n"
                     "Un retiro no borra al suscriptor: queda en el historial.",
        "entregas": "Aquí se registra solo lo que avisan los repartidores: lo que no se entregó o tuvo un problema.\n"
                    "Al final de la jornada pulse «Cerrar el día»: lo que no se reportó se da por entregado.",
        "rutas": "Cada ruta es de un solo repartidor. Aquí se crea, se cambia de repartidor\n"
                 "y se imprime la hoja de ruta actualizada.",
        "distribuidores": "Aquí se registran los repartidores y se dan de baja.\n"
                          "Para dar de baja a uno, primero pase sus rutas a otro.",
        "consultas": "Busque entregas o suscriptores, incluidos los retirados y los que no tienen entregas.\n"
                     "Doble clic para ver la ficha completa del suscriptor.",
        "reportes": "Resumen de un día: cuántas entregas había, cuántas se hicieron y qué novedades hubo.\n"
                    "Se puede guardar en Excel o imprimir.",
        "respaldos": "Las copias de seguridad se hacen solas cada día. Una vez por semana cópielas a Google Drive\n"
                     "y una vez al mes pulse «Verificar respaldo».",
    }

    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        app.vista = self  # disponible para las vistas que navegan desde accesos rápidos
        self._botones: dict[str, tk.Button] = {}
        self._clave_actual: str | None = None
        self._vista = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._construir_barra_lateral()
        self._construir_encabezado()
        self.contenido = tk.Frame(self, bg=COLORES["fondo"], padx=26, pady=18)
        self.contenido.grid(row=1, column=1, sticky="nsew")
        self.mostrar("inicio")

    # ------------------------------------------------------------------ #
    def _construir_barra_lateral(self) -> None:
        barra = tk.Frame(self, bg=COLORES["sidebar"], width=250)
        barra.grid(row=0, column=0, rowspan=2, sticky="ns")
        barra.grid_propagate(False)

        cabecera = tk.Frame(barra, bg=COLORES["sidebar"], padx=20, pady=22)
        cabecera.pack(fill="x")
        fila = tk.Frame(cabecera, bg=COLORES["sidebar"])
        fila.pack(anchor="w")
        logo = tk.Frame(fila, bg=COLORES["primario"], width=42, height=42)
        logo.pack(side="left")
        logo.grid_propagate(False)
        tk.Label(logo, text="SRI", bg=COLORES["primario"], fg="white", font=(FUENTE, 12, "bold")).place(
            relx=0.5, rely=0.5, anchor="center"
        )
        bloque = tk.Frame(fila, bg=COLORES["sidebar"])
        bloque.pack(side="left", padx=(12, 0))
        texto(bloque, "Cam Dylan S.A.S.", tamano=11, negrita=True, color="white", fondo=COLORES["sidebar"]).pack(anchor="w")
        texto(bloque, "Respaldo de información", tamano=8, color=COLORES["sidebar_suave"], fondo=COLORES["sidebar"]).pack(anchor="w")

        tk.Frame(barra, bg=COLORES["sidebar_activo"], height=1).pack(fill="x", padx=18, pady=(4, 14))

        texto(barra, "MENÚ PRINCIPAL", tamano=8, negrita=True, color=COLORES["sidebar_suave"], fondo=COLORES["sidebar"]).pack(
            anchor="w", padx=24, pady=(0, 8)
        )

        navegacion = tk.Frame(barra, bg=COLORES["sidebar"])
        navegacion.pack(fill="x")

        for clave, (_, etiqueta, requisito) in self.VISTAS.items():
            if requisito and not self.sesion.puede(requisito):
                continue
            boton = tk.Button(
                navegacion,
                text=f"   {etiqueta}",
                anchor="w",
                bg=COLORES["sidebar"],
                fg=COLORES["sidebar_texto"],
                activebackground=COLORES["sidebar_activo"],
                activeforeground="white",
                bd=0,
                relief="flat",
                font=(FUENTE, 11, "bold"),
                padx=12,
                pady=12,
                cursor="hand2",
                command=lambda c=clave: self.mostrar(c),
            )
            boton.pack(fill="x", padx=10, pady=1)
            boton.bind("<Enter>", lambda _e, b=boton, c=clave: self._resaltar(b, c, True))
            boton.bind("<Leave>", lambda _e, b=boton, c=clave: self._resaltar(b, c, False))
            self._botones[clave] = boton

        pie = tk.Frame(barra, bg=COLORES["sidebar"], padx=18, pady=18)
        pie.pack(side="bottom", fill="x")
        tk.Frame(pie, bg=COLORES["sidebar_activo"], height=1).pack(fill="x", pady=(0, 14))
        usuario = tk.Frame(pie, bg=COLORES["sidebar"])
        usuario.pack(fill="x")
        iniciales = "".join(parte[0] for parte in self.sesion.nombre.split()[:2]).upper() or "US"
        avatar = tk.Frame(usuario, bg=COLORES["primario"], width=34, height=34)
        avatar.pack(side="left")
        avatar.grid_propagate(False)
        tk.Label(avatar, text=iniciales, bg=COLORES["primario"], fg="white", font=(FUENTE, 9, "bold")).place(
            relx=0.5, rely=0.5, anchor="center"
        )
        datos = tk.Frame(usuario, bg=COLORES["sidebar"])
        datos.pack(side="left", padx=(10, 0))
        texto(datos, self.sesion.nombre.capitalize(), tamano=9, negrita=True, color="white", fondo=COLORES["sidebar"]).pack(anchor="w")
        texto(datos, self.sesion.rol, tamano=8, color=COLORES["sidebar_suave"], fondo=COLORES["sidebar"]).pack(anchor="w")

        acciones = tk.Frame(pie, bg=COLORES["sidebar"])
        acciones.pack(fill="x", pady=(12, 0))
        for etiqueta, comando in (
            ("Mi contraseña", self._cambiar_contrasena),
            ("Cerrar sesión", self.app.cerrar_sesion),
        ):
            tk.Button(
                acciones,
                text=etiqueta,
                bg=COLORES["sidebar"],
                fg=COLORES["sidebar_texto"],
                activebackground=COLORES["sidebar_activo"],
                activeforeground="white",
                bd=0,
                font=(FUENTE, 8),
                cursor="hand2",
                command=comando,
            ).pack(side="left", padx=(0, 14))

    def _construir_encabezado(self) -> None:
        cabecera = tk.Frame(self, bg=COLORES["panel"], height=68)
        cabecera.grid(row=0, column=1, sticky="ew")
        cabecera.grid_propagate(False)

        izquierda = tk.Frame(cabecera, bg=COLORES["panel"])
        izquierda.pack(side="left", padx=26, pady=12)
        self.titulo = texto(izquierda, "Inicio", tamano=14, negrita=True)
        self.titulo.pack(anchor="w")
        texto(
            izquierda,
            "Sistema de Respaldo de Información · Distribuciones Cam Dylan",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(2, 0))

        derecha = tk.Frame(cabecera, bg=COLORES["panel"])
        derecha.pack(side="right", padx=26)
        ttk.Button(derecha, text="?  Ayuda", style="Secundario.TButton", command=self._ayuda).pack(
            side="left", padx=(0, 18)
        )
        texto(derecha, fecha_larga(), tamano=9, color=COLORES["texto_suave"]).pack(side="left", padx=(0, 18))
        estado = tk.Frame(derecha, bg="#e8f5ee")
        estado.pack(side="left")
        tk.Label(
            estado,
            text="●  Sesión activa",
            bg="#e8f5ee",
            fg=COLORES["exito"],
            font=(FUENTE, 8, "bold"),
            padx=10,
            pady=4,
        ).pack()

        tk.Frame(self, bg=COLORES["borde"], height=1).grid(row=0, column=1, sticky="sew")

    def _resaltar(self, boton: tk.Button, clave: str, entrar: bool) -> None:
        if clave == self._clave_actual:
            return
        boton.configure(bg=COLORES["sidebar_activo"] if entrar else COLORES["sidebar"])

    def mostrar(self, clave: str) -> None:
        clase, titulo, requisito = self.VISTAS[clave]
        if requisito and not self.sesion.puede(requisito):
            return
        if self._clave_actual in self._botones:
            self._botones[self._clave_actual].configure(
                bg=COLORES["sidebar"], fg=COLORES["sidebar_texto"]
            )
        self._clave_actual = clave
        if clave in self._botones:
            self._botones[clave].configure(bg=COLORES["primario"], fg="white")

        if self._vista is not None:
            self._vista.destroy()
        for widget in self.contenido.winfo_children():
            widget.destroy()

        self.titulo.configure(text=titulo)
        self._vista = clase(self.contenido, self.app)
        self._vista.pack(fill="both", expand=True)

    def _ayuda(self) -> None:
        from tkinter import messagebox

        clave = self._clave_actual or "inicio"
        messagebox.showinfo(f"Ayuda · {self.VISTAS[clave][1]}", self.AYUDAS.get(clave, ""), parent=self)

    def _cambiar_contrasena(self) -> None:
        DialogoContrasena(self, self.app)
