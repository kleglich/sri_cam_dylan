"""Asistente de importación del listado de repartidores (RF-01)."""

from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .estilos import COLORES, FUENTE
from .widgets import (
    cabecera_vista,
    crear_arbol,
    fecha_hora_legible,
    llenar_arbol,
    mostrar_error,
    mostrar_info,
    tarjeta,
    texto,
)


class VistaImportacion(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.ruta_archivo: Path | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        cabecera_vista(
            self,
            "Importar listado de repartidores",
            "Carga el Excel de la empresa (una hoja por distribuidor), separa la periodicidad del nombre, "
            "asocia cada código de ruta a su distribuidor y consolida los datos en la base local.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 14))

        self._construir_seleccion()
        self._construir_resumen()

        centro = tk.Frame(self, bg=COLORES["fondo"])
        centro.grid(row=4, column=0, sticky="nsew", pady=(12, 0))
        centro.grid_columnconfigure(0, weight=1, uniform="centro")
        centro.grid_columnconfigure(1, weight=1, uniform="centro")
        centro.grid_rowconfigure(0, weight=1)
        self._construir_rechazos(centro)
        self._construir_historial(centro)

        self._cargar_historial()

    # ------------------------------------------------------------------ #
    def _construir_seleccion(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=1, column=0, sticky="ew")

        texto(panel, "1. Seleccione el archivo", tamano=11, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Formatos admitidos: .xlsx y .xls. Cada hoja debe tener las columnas N°, nombre, dirección, "
            "TIE, PT y código de ruta (el mapeo se configura en config.json).",
            tamano=9,
            color=COLORES["texto_suave"],
            wraplength=980,
            justify="left",
        ).pack(anchor="w", pady=(3, 12))

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        self.ruta_var = tk.StringVar(value="Ningún archivo seleccionado")
        caja = tk.Frame(fila, bg="#f7fafb", highlightbackground=COLORES["borde"], highlightthickness=1)
        caja.pack(side="left", fill="x", expand=True)
        self.ruta_label = tk.Label(
            caja,
            textvariable=self.ruta_var,
            bg="#f7fafb",
            fg=COLORES["texto"],
            font=(FUENTE, 9),
            anchor="w",
            padx=12,
            pady=10,
        )
        self.ruta_label.pack(fill="x")

        self.boton_examinar = ttk.Button(
            fila, text="Seleccionar…", style="Secundario.TButton", command=self._seleccionar
        )
        self.boton_examinar.pack(side="left", padx=(10, 0))
        self.boton_importar = ttk.Button(
            fila, text="Importar", style="Primario.TButton", command=self._importar, state="disabled"
        )
        self.boton_importar.pack(side="left", padx=(8, 0))

        self.barra = ttk.Progressbar(panel, mode="indeterminate")
        self.barra.pack(fill="x", pady=(12, 0))
        self.estado = texto(
            panel,
            "Seleccione un archivo para comenzar. La importación se aplica completa o no se aplica (RN-06).",
            tamano=9,
            color=COLORES["texto_suave"],
        )
        self.estado.pack(anchor="w", pady=(8, 0))

    def _construir_resumen(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="ew", pady=(12, 0))

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        self.resumen_vars = {}
        for indice, (clave, etiqueta, color) in enumerate(
            [
                ("leidos", "Registros leídos", COLORES["texto"]),
                ("importados", "Nuevos", COLORES["exito"]),
                ("actualizados", "Actualizados", COLORES["primario"]),
                ("rechazados", "Rechazados", COLORES["alerta"]),
                ("revisar", "Para revisar", COLORES["aviso"]),
            ]
        ):
            bloque = tk.Frame(fila, bg=COLORES["panel"])
            bloque.grid(row=0, column=indice, sticky="w", padx=(0 if indice == 0 else 30, 0))
            texto(bloque, etiqueta.upper(), tamano=8, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
            variable = tk.StringVar(value="—")
            tk.Label(
                bloque,
                textvariable=variable,
                bg=COLORES["panel"],
                fg=color,
                font=(FUENTE, 20, "bold"),
            ).pack(anchor="w")
            self.resumen_vars[clave] = variable

        self.aviso_cuadre = texto(
            panel,
            "",
            tamano=8,
            color=COLORES["texto_suave"],
        )
        self.aviso_cuadre.pack(anchor="w", pady=(6, 0))

    def _construir_rechazos(self, master) -> None:
        panel = tarjeta(master, relleno=14)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        texto(panel, "Rechazos y casos para revisar", tamano=11, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Cada rechazo queda justificado (RNF-04); los casos para revisar se consultan con la Gerencia.",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 10))
        self.arbol_rechazos = crear_arbol(
            panel,
            [("tipo", "Tipo", 80, False), ("hoja", "Hoja", 80, False), ("fila", "Fila", 46, False), ("motivo", "Motivo", 300)],
            alto=8,
        )
        self.arbol_rechazos.pack(fill="both", expand=True)

    def _construir_historial(self, master) -> None:
        panel = tarjeta(master, relleno=14)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        texto(panel, "Historial de importaciones", tamano=11, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Trazabilidad de los archivos cargados.",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 10))
        self.arbol_historial = crear_arbol(
            panel,
            [
                ("archivo", "Archivo", 120, True),
                ("fecha", "Carga", 120, False),
                ("leidos", "Leídos", 56, False),
                ("nuevos", "Nuevos", 62, False),
                ("rech", "Rech.", 50, False),
            ],
            alto=8,
        )
        self.arbol_historial.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    def _seleccionar(self) -> None:
        ruta = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar el listado de repartidores",
            filetypes=[
                ("Listado de repartidores (Excel)", "*.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not ruta:
            return
        self.ruta_archivo = Path(ruta)
        self.ruta_var.set(str(self.ruta_archivo))
        self.boton_importar.configure(state="normal")
        self.estado.configure(
            text=f"Archivo listo para importar: {self.ruta_archivo.name}",
            fg=COLORES["texto_suave"],
        )

    def _importar(self) -> None:
        if not self.ruta_archivo:
            mostrar_error(self, "Seleccione primero un archivo.")
            return
        self.boton_importar.configure(state="disabled")
        self.boton_examinar.configure(state="disabled")
        self.barra.start(12)
        self.estado.configure(text="Importando y validando los datos…", fg=COLORES["primario"])
        self.update_idletasks()

        ruta = self.ruta_archivo

        def trabajo():
            try:
                resultado = self.ctx.importacion.importar(self.sesion, ruta)
            except Exception as error:  # noqa: BLE001
                self.after(0, lambda e=error: self._fallar(e))
            else:
                self.after(0, lambda r=resultado: self._finalizar(r))

        threading.Thread(target=trabajo, daemon=True).start()

    def _finalizar(self, resumen) -> None:
        self.barra.stop()
        self.boton_importar.configure(state="normal")
        self.boton_examinar.configure(state="normal")
        self.resumen_vars["leidos"].set(str(resumen.leidos))
        self.resumen_vars["importados"].set(str(resumen.importados))
        self.resumen_vars["actualizados"].set(str(resumen.actualizados))
        self.resumen_vars["rechazados"].set(str(resumen.rechazados))
        self.resumen_vars["revisar"].set(str(len(resumen.revisar)))

        self.aviso_cuadre.configure(
            text=(
                f"{resumen.hojas} hoja(s) procesadas en una sola transacción (RN-06). "
                + (f"Se crearon {resumen.rutas_creadas} ruta(s) nueva(s)." if resumen.rutas_creadas else "")
            )
        )

        llenar_arbol(
            self.arbol_rechazos,
            [
                (f"r{indice}", ("Rechazado", r.hoja, r.fila, r.motivo), "alerta")
                for indice, r in enumerate(resumen.rechazos, start=1)
            ]
            + [
                (f"v{indice}", ("Revisar", r.hoja, r.fila, r.motivo), "aviso")
                for indice, r in enumerate(resumen.revisar, start=1)
            ],
        )
        if resumen.truncado:
            self.arbol_rechazos.insert(
                "", "end", values=("…", "", "", "Se muestran los primeros rechazos; el total está en el resumen.")
            )
        self.estado.configure(
            text=(
                f"Importación completada: {resumen.leidos} leídos = {resumen.importados} nuevos + "
                f"{resumen.actualizados} actualizados + {resumen.rechazados} rechazados."
            ),
            fg=COLORES["exito"] if resumen.cuadra else COLORES["alerta"],
        )
        self._cargar_historial()
        mensaje = (
            f"El archivo {resumen.archivo} se importó correctamente.\n\n"
            f"Leídos: {resumen.leidos}\nNuevos: {resumen.importados}\n"
            f"Actualizados: {resumen.actualizados}\nRechazados: {resumen.rechazados}"
        )
        mensaje += f"\nPara revisar con la Gerencia: {len(resumen.revisar)}"
        if resumen.rechazados or resumen.revisar:
            mensaje += "\n\nRevise el detalle en la parte inferior."
        mostrar_info(self, mensaje, "Importación completada")

    def _fallar(self, error: Exception) -> None:
        self.barra.stop()
        self.boton_importar.configure(state="normal")
        self.boton_examinar.configure(state="normal")
        self.estado.configure(text="La importación no se aplicó.", fg=COLORES["alerta"])
        mostrar_error(self, str(error))

    def _cargar_historial(self) -> None:
        try:
            archivos = self.ctx.importacion.historial(self.sesion, 20)
        except Exception:  # noqa: BLE001
            archivos = []
        llenar_arbol(
            self.arbol_historial,
            [
                (
                    a.id,
                    (
                        a.nombre_archivo,
                        fecha_hora_legible(a.fecha_carga),
                        a.total_leidos,
                        a.total_importados,
                        a.total_rechazados,
                    ),
                    "alerta" if a.total_rechazados else None,
                )
                for a in archivos
            ],
        )
