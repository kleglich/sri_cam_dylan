"""Vista de inicio: saludo, indicadores del día y la rutina que falta (manual de usuario, en pantalla)."""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import ttk

from .estilos import COLORES, FUENTE
from .widgets import crear_arbol, fecha_hora_legible, llenar_arbol, tarjeta, texto

ROLES = {"Secretaria": "Secretaría", "Gerencia": "Gerencia"}


def saludo(hora: int) -> str:
    return "Buenos días" if hora < 12 else "Buenas tardes" if hora < 19 else "Buenas noches"


class VistaInicio(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.shell = app.vista
        self.datos = self.ctx.consultas.dashboard(self.sesion)

        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(2, weight=1)

        self._encabezado()
        self._indicadores()
        self._rutina()
        self._importaciones()

    def _encabezado(self) -> None:
        marco = tk.Frame(self, bg=COLORES["fondo"])
        marco.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        texto(marco, saludo(datetime.now().hour), tamano=22, negrita=True, fondo=COLORES["fondo"]).pack(anchor="w")
        texto(
            marco,
            f"Entró como {ROLES.get(self.sesion.rol, self.sesion.rol)}. Abajo está lo que falta hacer hoy.",
            tamano=11,
            color=COLORES["texto_suave"],
            fondo=COLORES["fondo"],
        ).pack(anchor="w", pady=(4, 0))

    def _indicadores(self) -> None:
        datos = self.datos
        fila = tk.Frame(self, bg=COLORES["fondo"])
        fila.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        for indice in range(5):
            fila.grid_columnconfigure(indice, weight=1, uniform="kpi")

        # La efectividad solo tiene sentido cuando el día está cerrado: antes parece un error.
        if not datos["entregas_hoy"]:
            efectividad, detalle = "—", "hoy no hay entregas"
        elif datos["pendientes_hoy"]:
            efectividad, detalle = "—", "se calcula al cerrar el día"
        else:
            efectividad = f"{datos['efectividad_hoy']:.1f} %".replace(".", ",")
            detalle = "entregas hechas"
        tarjetas = [
            ("SUSCRIPTORES", str(datos["suscriptores"]), "activos", COLORES["primario"]),
            ("RUTAS", str(datos["rutas"]), "registradas", COLORES["primario"]),
            ("REPARTIDORES", str(datos["distribuidores"]), "activos", COLORES["primario"]),
            ("ENTREGAS DE HOY", str(datos["entregas_hoy"]), "programadas", COLORES["acento"]),
            ("EFECTIVIDAD HOY", efectividad, detalle,
             COLORES["exito"] if efectividad != "—" else COLORES["texto_suave"]),
        ]
        for indice, (titulo, valor, pie, color) in enumerate(tarjetas):
            caja = tarjeta(fila, relleno=12)
            caja.grid(row=0, column=indice, sticky="nsew", padx=(0 if indice == 0 else 5, 5 if indice < 4 else 0))
            texto(caja, titulo, tamano=9, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w")
            tk.Label(caja, text=valor, bg=COLORES["panel"], fg=color, font=(FUENTE, 22, "bold")).pack(anchor="w", pady=(2, 0))
            texto(caja, pie, tamano=9, color=COLORES["texto_suave"]).pack(anchor="w")

    def _pasos(self) -> list[tuple[bool | None, str, str, str]]:
        """(hecho, título, detalle, pantalla). hecho None = tarea sin marca."""
        d = self.datos
        if self.sesion.rol == "Gerencia":
            estado = self.ctx.respaldos.estado(self.sesion)
            dias_drive = estado["dias_drive"]
            return [
                (None, "Revisar el reporte del día", "Cuántas entregas había, cuántas se hicieron y qué novedades hubo.", "reportes"),
                (not estado["drive_vencido"], "Copiar el respaldo a Google Drive (cada semana)",
                 "Nunca se ha copiado." if dias_drive is None else f"Última copia hace {dias_drive} día(s).", "respaldos"),
                (not estado["verificacion_vencida"], "Verificar un respaldo (cada mes)",
                 "Comprueba que la información se puede recuperar.", "respaldos"),
            ]
        listado, reportes, pendientes = d["novedades_suscripcion_hoy"], d["reportes_hoy"], d["pendientes_hoy"]
        if not d["entregas_hoy"]:
            cierre = (True, "Hoy no hay entregas programadas.")
        elif pendientes:
            cierre = (False, f"Faltan {pendientes} entrega(s) por cerrar. Hágalo al final de la jornada.")
        else:
            cierre = (True, "Día cerrado: lo que no se reportó quedó como entregado.")
        return [
            (listado > 0, "1. Pasar el listado impreso",
             f"{listado} novedad(es) pasada(s) hoy." if listado
             else "Si el listado de hoy trae ingresos, retiros o cambios, páselos aquí.", "novedades"),
            (reportes > 0, "2. Registrar lo que reportan los repartidores",
             f"{reportes} reporte(s) registrado(s) hoy." if reportes
             else "Lo que no se entregó o tuvo un problema (ejemplar faltante, reclamo).", "entregas"),
            (cierre[0], "3. Cerrar el día", cierre[1], "entregas"),
        ]

    def _rutina(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 4))
        texto(panel, "Rutina de hoy", tamano=14, negrita=True).pack(anchor="w", pady=(0, 6))

        for hecho, titulo, detalle, clave in self._pasos():
            fila = tk.Frame(panel, bg=COLORES["panel"], highlightbackground=COLORES["borde"], highlightthickness=1)
            fila.pack(fill="x", pady=3)
            ttk.Button(fila, text="Ir", style="Mini.TButton", width=4,
                       command=lambda c=clave: self.shell.mostrar(c)).pack(side="right", padx=10)
            marca, color = ("✓", COLORES["exito"]) if hecho else ("•", COLORES["texto_suave"]) if hecho is None else ("○", COLORES["aviso"])
            tk.Label(fila, text=marca, bg=COLORES["panel"], fg=color, font=(FUENTE, 18, "bold"), width=2).pack(side="left", padx=(8, 4))
            bloque = tk.Frame(fila, bg=COLORES["panel"])
            bloque.pack(side="left", fill="x", expand=True, pady=6)
            texto(bloque, titulo, tamano=13, negrita=True).pack(anchor="w")
            texto(bloque, detalle, tamano=11, color=COLORES["texto_suave"], wraplength=430, justify="left").pack(anchor="w")

        otras = [
            ("importar", "Importar listado", "RF-01"), ("rutas", "Rutas", "RF-02"),
            ("distribuidores", "Repartidores", "RF-04"), ("consultas", "Consultar historial", "RF-06"),
        ]
        visibles = [o for o in otras if self.sesion.puede(o[2])]
        if visibles:
            texto(panel, "Otras tareas", tamano=11, negrita=True, color=COLORES["texto_suave"]).pack(anchor="w", pady=(10, 4))
            botones = tk.Frame(panel, bg=COLORES["panel"])
            botones.pack(anchor="w")
            for clave, titulo, _req in visibles:
                ttk.Button(botones, text=titulo, style="Mini.TButton",
                           command=lambda c=clave: self.shell.mostrar(c)).pack(side="left", padx=(0, 6))


    def _importaciones(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=2, column=1, sticky="nsew", padx=(8, 0), pady=(0, 4))
        texto(panel, "Últimas importaciones", tamano=13, negrita=True).pack(anchor="w")
        texto(panel, "Listados de repartidores cargados.", tamano=10, color=COLORES["texto_suave"]).pack(anchor="w", pady=(3, 10))

        arbol = crear_arbol(
            panel,
            [
                ("archivo", "Archivo", 120, True),
                ("fecha", "Fecha", 150, False),
                ("rechazados", "Rechazados", 110, False),
            ],
            alto=8,
        )
        importaciones = self.ctx.archivos.listar(8)
        llenar_arbol(
            arbol,
            [
                (
                    a.id,
                    (a.nombre_archivo, fecha_hora_legible(a.fecha_carga), a.total_rechazados),
                    "aviso" if a.total_rechazados else None,  # ámbar: hay casos por revisar, no es un error
                )
                for a in importaciones
            ],
        )
        if not importaciones:
            texto(panel, "Aún no se han importado listados.", tamano=10, color=COLORES["texto_suave"]).pack(anchor="w", pady=(8, 0))
