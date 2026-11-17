"""Respaldos y restauración de la base de datos (RF-07, RN-09)."""

from __future__ import annotations

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk

from ..config import directorio_respaldos, guardar_config
from .estilos import COLORES, FUENTE
from .widgets import (
    cabecera_vista,
    confirmar,
    crear_arbol,
    fecha_hora_legible,
    llenar_arbol,
    mostrar_error,
    mostrar_info,
    tarjeta,
    texto,
)


TIPOS = {"DIARIO": "Diario", "MANUAL": "Manual", "DRIVE": "Google Drive"}


class VistaRespaldos(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, bg=COLORES["fondo"])
        self.app = app
        self.ctx = app.ctx
        self.sesion = app.sesion
        self.rutas = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        cabecera_vista(
            self,
            "Respaldos de la base de datos",
            "El sistema genera cada día un respaldo cifrado y conserva los siete más recientes. "
            "Una vez por semana copie el último a Google Drive para tenerlo fuera del equipo (RN-09).",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 12))

        self._construir_acciones()
        self._construir_historial()
        self._cargar()

    def _construir_acciones(self) -> None:
        panel = tarjeta(self, relleno=18)
        panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        fila = tk.Frame(panel, bg=COLORES["panel"])
        fila.pack(fill="x")
        bloque = tk.Frame(fila, bg=COLORES["panel"])
        bloque.pack(side="left", fill="x", expand=True)
        texto(bloque, "Copia de seguridad cifrada", tamano=12, negrita=True).pack(anchor="w")
        texto(
            bloque,
            "El archivo .sribak se cifra con AES-256-GCM antes de escribirse. "
            "La restauración verifica la integridad y reemplaza los datos actuales.",
            tamano=9,
            color=COLORES["texto_suave"],
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        ttk.Button(fila, text="Restaurar respaldo…", style="Secundario.TButton", command=self._restaurar).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(fila, text="Crear respaldo ahora", style="Secundario.TButton", command=self._crear).pack(
            side="right", padx=(8, 0)
        )
        ttk.Button(fila, text="Copiar a Google Drive", style="Primario.TButton", command=self._copiar_drive).pack(
            side="right"
        )

        segunda = tk.Frame(panel, bg=COLORES["panel"])
        segunda.pack(fill="x", pady=(14, 0))
        texto(
            segunda,
            f"Carpeta sugerida: {directorio_respaldos(self.ctx.config)}",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(side="left")
        ttk.Button(segunda, text="Abrir carpeta", style="Secundario.TButton", command=self._abrir_carpeta).pack(
            side="right"
        )
        tercera = tk.Frame(panel, bg=COLORES["panel"])
        tercera.pack(fill="x", pady=(10, 0))
        ttk.Button(tercera, text="Verificar respaldo…", style="Secundario.TButton", command=self._verificar).pack(side="left")
        ttk.Button(tercera, text="Guardar copia de la clave…", style="Secundario.TButton", command=self._copiar_clave).pack(
            side="left", padx=(8, 0)
        )
        texto(
            tercera,
            "Verifique un respaldo cada mes y guarde la clave sri.key en una USB fuera del computador.",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(side="left", padx=(12, 0))

        self.estado = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.estado.pack(anchor="w", pady=(12, 0))
        self.norma = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.norma.pack(anchor="w", pady=(6, 0))
        self.verificacion = texto(panel, "", tamano=9, color=COLORES["texto_suave"])
        self.verificacion.pack(anchor="w", pady=(6, 0))

        depuracion = tk.Frame(panel, bg="#f3f8fa")
        depuracion.pack(fill="x", pady=(14, 0))
        texto(
            depuracion,
            "Depuración anual (Ley 1581): anonimizar a los suscriptores retirados hace más de",
            tamano=9,
            fondo="#f3f8fa",
        ).pack(side="left", padx=(12, 6), pady=8)
        self.meses = ttk.Spinbox(depuracion, from_=1, to=120, width=5, font=(FUENTE, 10))
        self.meses.set(12)
        self.meses.pack(side="left", pady=8)
        texto(depuracion, "meses", tamano=9, fondo="#f3f8fa").pack(side="left", padx=(6, 0))
        ttk.Button(depuracion, text="Depurar…", style="Secundario.TButton", command=self._depurar).pack(
            side="right", padx=8, pady=6
        )

    def _construir_historial(self) -> None:
        panel = tarjeta(self, relleno=14)
        panel.grid(row=2, column=0, sticky="nsew")
        texto(panel, "Historial de respaldos", tamano=11, negrita=True).pack(anchor="w")
        texto(
            panel,
            "Diarios (automáticos), manuales y copias en Google Drive.",
            tamano=8,
            color=COLORES["texto_suave"],
        ).pack(anchor="w", pady=(3, 10))

        self.arbol = crear_arbol(
            panel,
            [
                ("fecha", "Fecha", 150),
                ("tipo", "Tipo", 110, False),
                ("archivo", "Archivo", 330),
                ("usuario", "Generado por", 150),
            ],
            alto=12,
        )
        self.arbol.pack(fill="both", expand=True)

    # ------------------------------------------------------------------ #
    def _cargar(self) -> None:
        try:
            respaldos = self.ctx.respaldos.listar(self.sesion)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.rutas = {r.id: r.ruta_archivo for r in respaldos}
        llenar_arbol(
            self.arbol,
            [
                (
                    r.id,
                    (fecha_hora_legible(r.fecha), TIPOS.get(r.tipo, r.tipo), r.ruta_archivo, r.usuario),
                    None if Path(r.ruta_archivo).exists() else "alerta",
                )
                for r in respaldos
            ],
        )
        try:
            estado = self.ctx.respaldos.estado(self.sesion)
        except Exception:  # noqa: BLE001
            return
        diario = fecha_hora_legible(estado["ultimo_diario"]) if estado["ultimo_diario"] else "aún no hay"
        self.estado.configure(
            text=f"Último respaldo diario automático: {diario}."
            + (" ¡El último respaldo automático falló!" if estado["fallo_diario"] else ""),
            fg=COLORES["alerta"] if estado["fallo_diario"] else COLORES["texto_suave"],
        )
        if estado["dias_drive"] is None:
            self.norma.configure(text="Aún no se ha copiado ningún respaldo a Google Drive (RN-09).", fg=COLORES["alerta"])
        elif estado["drive_vencido"]:
            self.norma.configure(
                text=f"La última copia en Google Drive fue hace {estado['dias_drive']} días: cópiela ahora (RN-09).",
                fg=COLORES["aviso"],
            )
        else:
            self.norma.configure(
                text=f"Última copia en Google Drive: {fecha_hora_legible(estado['ultimo_drive'])}. Copia semanal al día (RN-09).",
                fg=COLORES["exito"],
            )
        self._carpeta_drive = estado["carpeta_drive"]
        if estado["dias_verificacion"] is None:
            self.verificacion.configure(
                text="Aún no se ha verificado ningún respaldo. Use «Verificar respaldo» una vez al mes.",
                fg=COLORES["aviso"],
            )
        else:
            self.verificacion.configure(
                text=f"Última verificación de un respaldo: {fecha_hora_legible(estado['ultima_verificacion'])}"
                + (" · ya pasó el mes: verifique uno ahora." if estado["verificacion_vencida"] else "."),
                fg=COLORES["aviso"] if estado["verificacion_vencida"] else COLORES["exito"],
            )

    def _copiar_drive(self) -> None:
        configurada = self.ctx.config.get("respaldo", {}).get("carpeta_google_drive", "")
        carpeta = configurada if configurada and Path(configurada).is_dir() else ""
        if not carpeta:
            sugerida = next(
                (str(c) for c in (Path.home() / "Google Drive", Path("G:/Mi unidad"), Path("G:/My Drive")) if c.is_dir()),
                getattr(self, "_carpeta_drive", "") or str(Path.home()),
            )
            carpeta = filedialog.askdirectory(
                parent=self, title="Elija la carpeta de Google Drive de la empresa", initialdir=sugerida
            )
            if not carpeta:
                return
        try:
            destino = self.ctx.respaldos.copiar_a_drive(self.sesion, carpeta)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        if carpeta != configurada:
            self.ctx.config.setdefault("respaldo", {})["carpeta_google_drive"] = carpeta
            try:
                guardar_config(self.ctx.config)
            except OSError:
                pass  # se volverá a preguntar la carpeta la próxima vez
        self._cargar()
        mostrar_info(
            self,
            f"Respaldo cifrado copiado a:\n{destino}\n\n"
            "Google Drive para escritorio lo subirá a la nube cuando haya conexión a Internet.",
            "Copia en Google Drive",
        )

    def _crear(self) -> None:
        marca = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = filedialog.asksaveasfilename(
            parent=self,
            title="Guardar respaldo cifrado",
            initialdir=str(directorio_respaldos(self.ctx.config)),
            initialfile=f"sri_respaldo_{marca}.sribak",
            defaultextension=".sribak",
            filetypes=[("Respaldo del SRI", "*.sribak")],
        )
        if not destino:
            return
        try:
            ruta = self.ctx.respaldos.crear(self.sesion, destino)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.estado.configure(text=f"Respaldo creado: {ruta}", fg=COLORES["exito"])
        self._cargar()
        mostrar_info(
            self,
            f"Respaldo cifrado creado correctamente en:\n{ruta}\n\n"
            "Recuerde copiar un respaldo a Google Drive al menos una vez por semana.",
            "Respaldo completado",
        )

    def _restaurar(self) -> None:
        archivo = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar respaldo para restaurar",
            initialdir=str(directorio_respaldos(self.ctx.config)),
            filetypes=[("Respaldo del SRI", "*.sribak"), ("Todos los archivos", "*.*")],
        )
        if not archivo:
            return
        if not confirmar(
            self,
            "La restauración reemplazará TODOS los datos actuales por los del respaldo.\n\n"
            "Se recomienda crear un respaldo de la base actual antes de continuar.\n\n¿Desea continuar?",
            "Confirmar restauración",
        ):
            return
        if not confirmar(
            self,
            f"Confirme nuevamente: se restaurará\n{Path(archivo).name}\n\ny se cerrará la sesión.",
            "Segunda confirmación",
        ):
            return
        try:
            self.ctx.respaldos.restaurar(self.sesion, archivo)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        self.app.reiniciar_sesion(
            "La base de datos se restauró correctamente. Por seguridad, inicie sesión de nuevo."
        )

    def _verificar(self) -> None:
        archivo = filedialog.askopenfilename(
            parent=self,
            title="Elegir el respaldo que se va a verificar",
            initialdir=str(directorio_respaldos(self.ctx.config)),
            filetypes=[("Respaldo del SRI", "*.sribak"), ("Todos los archivos", "*.*")],
        )
        if not archivo:
            return
        try:
            resultado = self.ctx.respaldos.verificar(self.sesion, archivo)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, f"El respaldo NO se puede restaurar.\n\n{error}")
            return
        self._cargar()
        ultima = resultado["ultima_entrega"]
        mostrar_info(
            self,
            f"El respaldo {resultado['archivo']} se descifró y está íntegro: se puede restaurar.\n\n"
            f"Suscriptores: {resultado['suscriptores']}\nEntregas: {resultado['entregas']}"
            + (f"\nÚltima entrega registrada: {ultima[8:10]}/{ultima[5:7]}/{ultima[:4]}" if ultima else "")
            + "\n\nLa base de datos actual no se modificó.",
            "Respaldo verificado",
        )

    def _copiar_clave(self) -> None:
        carpeta = filedialog.askdirectory(parent=self, title="Elija la memoria USB o la carpeta donde guardar la clave")
        if not carpeta:
            return
        try:
            destino = self.ctx.respaldos.guardar_copia_clave(self.sesion, carpeta)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        mostrar_info(
            self,
            f"Copia de la clave guardada en:\n{destino}\n\n"
            "Guarde esa memoria fuera del computador y en un lugar seguro: con la clave y un respaldo "
            "se recuperan todos los datos.",
            "Clave guardada",
        )

    def _depurar(self) -> None:
        try:
            meses = int(self.meses.get())
        except ValueError:
            mostrar_error(self, "Indique el plazo en meses (un número entre 1 y 120).")
            return
        if not confirmar(
            self,
            f"Se borrarán el nombre, las direcciones y las novedades de los suscriptores retirados hace más de "
            f"{meses} meses. Sus registros y entregas se conservan para las estadísticas.\n\n"
            "Esto no se puede deshacer en la base actual. ¿Continuar?",
            "Depuración anual",
        ):
            return
        try:
            cantidad = self.ctx.suscripciones.depurar_retirados(self.sesion, meses)
        except Exception as error:  # noqa: BLE001
            mostrar_error(self, str(error))
            return
        mostrar_info(
            self,
            f"Suscriptores anonimizados: {cantidad}.\n\nLos respaldos anteriores todavía tienen esos datos; "
            "desaparecen a medida que se reemplazan los 7 respaldos diarios.",
            "Depuración anual",
        )

    def _abrir_carpeta(self) -> None:
        carpeta = directorio_respaldos(self.ctx.config)
        try:
            os.startfile(str(carpeta))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            mostrar_info(self, f"Carpeta de respaldos:\n{carpeta}", "Carpeta de respaldos")
