"""Diálogos modales de la interfaz."""

from __future__ import annotations

import tkinter as tk
from dataclasses import replace
from tkinter import ttk

from .estilos import COLORES, FUENTE
from .widgets import centro, mostrar_error, mostrar_info, texto


class DialogoContrasena(tk.Toplevel):
    def __init__(self, master, app, obligatorio: bool = False, al_terminar=None):
        super().__init__(master)
        self.app = app
        self.obligatorio = obligatorio
        self.al_terminar = al_terminar
        self.title("Cambiar contraseña")
        self.configure(bg=COLORES["panel"])
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()
        centro(self, 440, 500 if obligatorio else 430)

        marco = tk.Frame(self, bg=COLORES["panel"], padx=28, pady=24)
        marco.pack(fill="both", expand=True)

        texto(marco, "Cambiar contraseña", tamano=16, negrita=True).pack(anchor="w")
        texto(
            marco,
            f"Usuario: {app.sesion.nombre} · Rol: {app.sesion.rol}",
            tamano=9,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(4, 18))
        if obligatorio:
            texto(
                marco,
                "Entró con la contraseña de demostración. Por seguridad, elija una propia "
                "antes de continuar; si cierra esta ventana, la sesión se cerrará.",
                tamano=9,
                color=COLORES["aviso"],
                wraplength=380,
                justify="left",
            ).pack(anchor="w", pady=(0, 10))

        self.actual = self._campo(marco, "Contraseña actual")
        self.nueva = self._campo(marco, "Nueva contraseña (mínimo 8 caracteres)")
        self.confirmacion = self._campo(marco, "Confirmar nueva contraseña")

        botones = tk.Frame(marco, bg=COLORES["panel"])
        botones.pack(fill="x", pady=(12, 0))
        ttk.Button(
            botones, text="Cerrar sesión" if obligatorio else "Cancelar", style="Secundario.TButton", command=self._cancelar
        ).pack(side="right")
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        ttk.Button(botones, text="Guardar", style="Primario.TButton", command=self._guardar).pack(side="right", padx=(0, 8))

        self.after(120, self.actual.focus_set)

    def _campo(self, master, etiqueta: str) -> ttk.Entry:
        texto(master, etiqueta.upper(), tamano=9, negrita=True, color=COLORES["texto_suave"]).pack(
            anchor="w", pady=(8, 4)
        )
        entrada = ttk.Entry(master, show="•", font=(FUENTE, 12))
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
        self.app.sesion = replace(self.app.sesion, cambiar_contrasena=False)
        self.destroy()
        if self.al_terminar:
            self.al_terminar()

    def _cancelar(self) -> None:
        self.destroy()
        if self.obligatorio:
            self.app.cerrar_sesion()


class DialogoCasos(tk.Toplevel):
    """Rechazos y casos para revisar con la Gerencia después de importar (RF-01)."""

    def __init__(self, master, app, resumen, mensaje: str):
        super().__init__(master)
        self.app = app
        self.resumen = resumen
        self.title("Revisar con la Gerencia")
        self.configure(bg=COLORES["fondo"])
        self.transient(master)
        centro(self, 900, 560)
        self.minsize(720, 420)

        from .widgets import crear_arbol, llenar_arbol

        marco = tk.Frame(self, bg=COLORES["fondo"], padx=22, pady=20)
        marco.pack(fill="both", expand=True)
        texto(marco, "Importación completada", tamano=16, negrita=True, fondo=COLORES["fondo"]).pack(anchor="w")
        texto(marco, mensaje, tamano=9, color=COLORES["texto_suave"], fondo=COLORES["fondo"],
              wraplength=840, justify="left").pack(anchor="w", pady=(4, 12))
        arbol = crear_arbol(
            marco, [("tipo", "Tipo", 100, False), ("hoja", "Hoja", 150, False), ("fila", "Fila", 50, False), ("motivo", "Motivo", 520)], alto=12
        )
        llenar_arbol(
            arbol,
            [(f"r{i}", ("Rechazado", c.hoja, c.fila, c.motivo), "alerta") for i, c in enumerate(resumen.rechazos)]
            + [(f"v{i}", ("Para revisar", c.hoja, c.fila, c.motivo), "aviso") for i, c in enumerate(resumen.revisar)],
        )
        pie = tk.Frame(marco, bg=COLORES["fondo"])
        pie.pack(fill="x", pady=(12, 0))
        texto(pie, "Exporte la lista para revisarla con la gerente y anotar qué se decide en cada caso.",
              tamano=9, color=COLORES["texto_suave"], fondo=COLORES["fondo"]).pack(side="left")
        ttk.Button(pie, text="Cerrar", style="Secundario.TButton", command=self.destroy).pack(side="right")
        ttk.Button(pie, text="Exportar a Excel (CSV)…", style="Primario.TButton", command=self._exportar).pack(
            side="right", padx=(0, 8)
        )

    def _exportar(self) -> None:
        from pathlib import Path
        from tkinter import filedialog

        from ..config import directorio_exportes

        destino = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar los casos para revisar",
            initialdir=str(directorio_exportes()),
            initialfile=f"revision_{Path(self.resumen.archivo).stem}.csv",
            defaultextension=".csv",
            filetypes=[("CSV para Excel", "*.csv")],
        )
        if not destino:
            return
        try:
            ruta = self.app.ctx.importacion.exportar_casos(self.app.sesion, self.resumen, destino)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        mostrar_info(self, f"Lista exportada en:\n{ruta}")


class DialogoHistorial(tk.Toplevel):
    """Ficha del suscriptor (RF-06): estado, novedades de suscripción y entregas."""

    def __init__(self, master, app, suscriptor_id: int, nombre: str):
        super().__init__(master)
        self.app = app
        self.title(f"Ficha del suscriptor · {nombre}")
        self.configure(bg=COLORES["fondo"])
        self.transient(master)
        centro(self, 960, 680)
        self.minsize(760, 560)

        from ..dominio.modelos import PRODUCTOS
        from ..dominio.periodicidad import etiqueta
        from ..util import formato_fecha
        from .widgets import crear_arbol, llenar_arbol

        marco = tk.Frame(self, bg=COLORES["fondo"], padx=22, pady=20)
        marco.pack(fill="both", expand=True)
        try:
            suscriptor, novedades = app.ctx.consultas.ficha_suscriptor(app.sesion, suscriptor_id)
            entregas = app.ctx.consultas.historial_suscriptor(app.sesion, suscriptor_id)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            self.destroy()
            return

        def linea(contenido: str, color: str = COLORES["texto_suave"], negrita: bool = False) -> None:
            texto(marco, contenido, tamano=10 if negrita else 9, negrita=negrita, color=color,
                  fondo=COLORES["fondo"], wraplength=900, justify="left").pack(anchor="w", pady=(2, 0))

        texto(marco, nombre, tamano=17, negrita=True, fondo=COLORES["fondo"]).pack(anchor="w")
        if suscriptor:
            if suscriptor.activo:
                desde = f" desde {formato_fecha(suscriptor.fecha_ingreso)}" if suscriptor.fecha_ingreso else ""
                linea(f"Estado: ACTIVO{desde}", COLORES["exito"], negrita=True)
            else:
                linea(f"Estado: RETIRADO desde {formato_fecha(suscriptor.fecha_retiro)}", COLORES["alerta"], negrita=True)
            productos = ", ".join(PRODUCTOS[x] for x in suscriptor.productos.split(",") if x in PRODUCTOS)
            linea(
                f"Dirección: {suscriptor.direccion}   ·   Ruta: {suscriptor.zona}   ·   "
                f"Distribuidor: {suscriptor.distribuidor or 'Sin asignar'}"
            )
            if suscriptor.direccion_fs:
                linea(f"Fin de semana: {suscriptor.direccion_fs}   ·   Ruta: {suscriptor.zona_fs or suscriptor.zona}")
            linea(f"Periodicidad: {etiqueta(suscriptor.periodicidad)}   ·   Productos: {productos}")
            if suscriptor.novedades:
                linea(f"Última novedad: {suscriptor.novedades}", COLORES["aviso"])

        texto(marco, f"Novedades de suscripción ({len(novedades)})", tamano=11, negrita=True,
              fondo=COLORES["fondo"]).pack(anchor="w", pady=(14, 4))
        caja_novedades = tk.Frame(marco, bg=COLORES["fondo"], height=150)
        caja_novedades.pack(fill="x")
        caja_novedades.pack_propagate(False)
        arbol_novedades = crear_arbol(
            caja_novedades, [("fecha", "Fecha", 100), ("tipo", "Tipo", 90), ("detalle", "Detalle", 520), ("usuario", "Registró", 110)], alto=4
        )
        llenar_arbol(
            arbol_novedades,
            [
                (n.id, (formato_fecha(n.fecha), n.tipo.capitalize(), n.detalle, n.usuario),
                 {"INGRESO": "exito", "RETIRO": "alerta"}.get(n.tipo, "aviso"))
                for n in novedades
            ],
        )

        texto(marco, f"Entregas ({len(entregas)})", tamano=11, negrita=True,
              fondo=COLORES["fondo"]).pack(anchor="w", pady=(14, 4))
        arbol = crear_arbol(
            marco, [("fecha", "Fecha", 120), ("estado", "Estado", 140), ("novedad", "Novedad registrada", 520)], alto=9
        )
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
        pie.pack(fill="x", pady=(10, 0))
        ttk.Button(pie, text="Cerrar", style="Secundario.TButton", command=self.destroy).pack(side="right")
