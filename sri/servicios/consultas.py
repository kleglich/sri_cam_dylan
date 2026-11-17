"""Consultas, reporte diario de entregas y exportación (RF-03, RF-06, RN-05, RN-11)."""

from __future__ import annotations

import csv
import html
from datetime import date
from pathlib import Path

from ..datos.daos import (
    ArchivoDAO,
    DistribuidorDAO,
    EntregaDAO,
    NovedadSuscripcionDAO,
    ReporteDAO,
    RutaDAO,
    SuscriptorDAO,
)
from ..dominio.modelos import (
    ESTADOS_ENTREGA,
    Entrega,
    FilaReporte,
    NovedadSuscripcion,
    ReporteDiario,
    Sesion,
    Suscriptor,
)
from ..util import DatosInvalidos, formato_fecha, parsear_fecha
from .autenticacion import AutenticacionServicio


class ConsultasServicio:
    def __init__(
        self,
        suscriptores: SuscriptorDAO,
        entregas: EntregaDAO,
        rutas: RutaDAO,
        distribuidores: DistribuidorDAO,
        reportes: ReporteDAO,
        archivos: ArchivoDAO,
        auth: AutenticacionServicio,
        novedades: NovedadSuscripcionDAO,
    ):
        self.suscriptores = suscriptores
        self.entregas = entregas
        self.rutas = rutas
        self.distribuidores = distribuidores
        self.reportes = reportes
        self.archivos = archivos
        self.auth = auth
        self.novedades = novedades

    # ------------------------------------------------------------------ #
    # Consultas operativas
    # ------------------------------------------------------------------ #
    def suscriptores_con_estado(
        self,
        sesion: Sesion,
        fecha: str,
        ruta_id: int | None = None,
        texto: str = "",
        limite: int = 300,
    ) -> list[dict]:
        """Entregas programadas del día (RN-11) con su estado; sin registro = PENDIENTE."""
        self.auth.exigir(sesion, "RF-06")
        fecha_iso = parsear_fecha(fecha).isoformat()
        estados = self.entregas.mapa_estado_fecha(fecha_iso)
        filas = []
        for suscriptor in self.suscriptores.listar_del_dia(fecha_iso, ruta_id=ruta_id, texto=texto, limite=limite):
            estado, novedad = estados.get(suscriptor.id, ("PENDIENTE", ""))
            filas.append({"suscriptor": suscriptor, "estado": estado, "novedad": novedad})
        return filas

    def buscar_entregas(self, sesion: Sesion, filtros: dict) -> list[Entrega]:
        self.auth.exigir(sesion, "RF-06")
        desde = filtros.get("desde") or ""
        hasta = filtros.get("hasta") or ""
        estado = filtros.get("estado") or ""
        if desde:
            desde = parsear_fecha(desde).isoformat()
        if hasta:
            hasta = parsear_fecha(hasta).isoformat()
        if desde and hasta and desde > hasta:
            raise DatosInvalidos("La fecha inicial no puede ser posterior a la fecha final.")
        if estado and estado not in ESTADOS_ENTREGA:
            raise DatosInvalidos("El estado seleccionado no es válido.")

        # El texto se busca primero sobre los suscriptores descifrados y luego se
        # filtran sus entregas en SQL, para no perder coincidencias por el límite.
        texto = (filtros.get("texto") or "").strip()
        suscriptor_ids = None
        if texto:
            suscriptor_ids = [
                s.id for s in self.suscriptores.listar(texto=texto, limite=self.suscriptores.contar())
            ]
        return self.entregas.buscar(
            desde=desde or None,
            hasta=hasta or None,
            estado=estado or None,
            ruta_id=filtros.get("ruta_id") or None,
            distribuidor_id=filtros.get("distribuidor_id") or None,
            limite=int(filtros.get("limite", 500)),
            suscriptor_ids=suscriptor_ids,
        )

    def historial_suscriptor(self, sesion: Sesion, suscriptor_id: int) -> list[Entrega]:
        self.auth.exigir(sesion, "RF-06")
        return self.entregas.historial_suscriptor(suscriptor_id)

    def ficha_suscriptor(self, sesion: Sesion, suscriptor_id: int) -> tuple[Suscriptor | None, list[NovedadSuscripcion]]:
        """Datos del suscriptor (con su estado) y sus novedades de ingreso, cambio y retiro (RF-06)."""
        self.auth.exigir(sesion, "RF-06")
        return self.suscriptores.obtener(suscriptor_id), self.novedades.listar(suscriptor_id=suscriptor_id)

    def buscar_suscriptores(self, sesion: Sesion, filtros: dict) -> list[Suscriptor]:
        """RF-06: encuentra suscriptores aunque no tengan entregas registradas."""
        self.auth.exigir(sesion, "RF-06")
        estado = filtros.get("estado") or ""
        if estado and estado not in ("ACTIVO", "RETIRADO"):
            raise DatosInvalidos("El estado seleccionado no es válido.")
        limite = int(filtros.get("limite", 500))
        filas = self.suscriptores.listar(
            ruta_id=filtros.get("ruta_id") or None, texto=(filtros.get("texto") or "").strip(), limite=-1
        )
        if filtros.get("distribuidor_id"):
            rutas = {r.id for r in self.rutas.listar() if r.distribuidor_id == filtros["distribuidor_id"]}
            filas = [s for s in filas if s.ruta_id in rutas or s.ruta_fs_id in rutas]
        if estado:
            filas = [s for s in filas if s.estado == estado]
        return filas[:limite]

    # ------------------------------------------------------------------ #
    # Reporte diario (RF-03)
    # ------------------------------------------------------------------ #
    def generar_reporte(self, sesion: Sesion, fecha: str) -> ReporteDiario:
        self.auth.exigir(sesion, "RF-03")
        fecha_dt = parsear_fecha(fecha)
        if fecha_dt > date.today():
            raise DatosInvalidos("No se puede generar el reporte de una fecha futura.")
        fecha_iso = fecha_dt.isoformat()
        filas = self.entregas.estadisticas_fecha(fecha_iso)
        por_ruta: list[FilaReporte] = []
        por_distribuidor: dict[str, FilaReporte] = {}
        for fila in filas:
            item = FilaReporte(
                clave=fila["zona"],
                total=fila["total"] or 0,
                efectivas=fila["efectivas"] or 0,
                no_entregadas=fila["no_entregadas"] or 0,
                novedades=fila["novedades"] or 0,
                pendientes=fila["pendientes"] or 0,
            )
            por_ruta.append(item)
            clave = fila["distribuidor"] or "Sin asignar"
            acumulado = por_distribuidor.setdefault(
                clave, FilaReporte(clave=clave, total=0, efectivas=0, no_entregadas=0, novedades=0, pendientes=0)
            )
            acumulado.total += item.total
            acumulado.efectivas += item.efectivas
            acumulado.no_entregadas += item.no_entregadas
            acumulado.novedades += item.novedades
            acumulado.pendientes += item.pendientes

        total = sum(f.total for f in por_ruta)
        efectivas = sum(f.efectivas for f in por_ruta)
        reporte = ReporteDiario(
            fecha=fecha_iso,
            total=total,
            efectivas=efectivas,
            no_entregadas=sum(f.no_entregadas for f in por_ruta),
            novedades=sum(f.novedades for f in por_ruta),
            pendientes=sum(f.pendientes for f in por_ruta),
            por_ruta=por_ruta,
            por_distribuidor=sorted(por_distribuidor.values(), key=lambda f: f.clave),
            novedades_entrega=self.entregas.listar_novedades_fecha(fecha_iso),
            novedades_suscripcion=self.novedades.listar(fecha=fecha_iso),
        )
        if total > 0:
            self.reportes.guardar(
                fecha_iso, total, efectivas, reporte.porcentaje, sesion.usuario_id
            )
        return reporte

    def exportar_csv(self, sesion: Sesion, reporte: ReporteDiario, destino: str | Path) -> Path:
        self.auth.exigir(sesion, "RF-03")
        ruta = Path(destino)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
            escritor = csv.writer(archivo, delimiter=";")
            escritor.writerow(["REPORTE DIARIO DE ENTREGAS - SRI CAM DYLAN S.A.S."])
            escritor.writerow(["Fecha", formato_fecha(reporte.fecha)])
            escritor.writerow(["Entregas programadas", reporte.total])
            escritor.writerow(["Entregas efectivas", reporte.efectivas])
            escritor.writerow(
                ["Efectividad", self._porcentaje_texto(reporte.porcentaje)]
            )
            escritor.writerow([])
            self._tabla_csv(escritor, reporte.por_ruta, "DETALLE POR RUTA")
            escritor.writerow([])
            self._tabla_csv(escritor, reporte.por_distribuidor, "DETALLE POR DISTRIBUIDOR")
            escritor.writerow([])
            escritor.writerow(["NOVEDADES DEL DÍA"])
            escritor.writerow(["Tipo", "Suscriptor", "Ruta", "Detalle"])
            for tipo, suscriptor, zona, detalle in self.filas_novedades(reporte):
                escritor.writerow([tipo, suscriptor, zona, detalle])
        return ruta

    def exportar_html(self, sesion: Sesion, reporte: ReporteDiario, destino: str | Path) -> Path:
        self.auth.exigir(sesion, "RF-03")
        ruta = Path(destino)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        filas_ruta = self._filas_html(reporte.por_ruta)
        filas_distribuidor = self._filas_html(reporte.por_distribuidor)
        efectividad = self._porcentaje_texto(reporte.porcentaje)
        filas_novedades = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(valor))}</td>" for valor in fila) + "</tr>"
            for fila in self.filas_novedades(reporte)
        ) or '<tr><td colspan="4">Sin novedades registradas.</td></tr>'
        contenido = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Reporte diario de entregas {formato_fecha(reporte.fecha)}</title>
<style>
  body {{ font-family: "Segoe UI", Arial, sans-serif; color: #1c2b36; margin: 32px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  h2 {{ font-size: 16px; margin-top: 28px; color: #12314a; }}
  .sub {{ color: #5b6b77; margin-top: 0; }}
  .kpis {{ display: flex; gap: 16px; margin: 20px 0; flex-wrap: wrap; }}
  .kpi {{ border: 1px solid #d5dee4; border-radius: 8px; padding: 12px 20px; min-width: 140px; }}
  .kpi span {{ display: block; font-size: 12px; color: #5b6b77; text-transform: uppercase; }}
  .kpi strong {{ font-size: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
  th, td {{ border: 1px solid #d5dee4; padding: 8px 10px; text-align: left; font-size: 13px; }}
  th {{ background: #eef4f7; }}
  .pie {{ margin-top: 32px; font-size: 12px; color: #5b6b77; }}
  @media print {{ .no-print {{ display: none; }} body {{ margin: 12mm; }} }}
</style>
</head>
<body>
<button class="no-print" onclick="window.print()">Imprimir / Guardar como PDF</button>
<h1>Reporte diario de entregas</h1>
<p class="sub">Distribuciones Cam Dylan S.A.S. · Fecha: {html.escape(formato_fecha(reporte.fecha))}</p>
<div class="kpis">
  <div class="kpi"><span>Programadas</span><strong>{reporte.total}</strong></div>
  <div class="kpi"><span>Efectivas</span><strong>{reporte.efectivas}</strong></div>
  <div class="kpi"><span>Efectividad</span><strong>{efectividad}</strong></div>
  <div class="kpi"><span>No entregadas</span><strong>{reporte.no_entregadas}</strong></div>
  <div class="kpi"><span>Con novedad</span><strong>{reporte.novedades}</strong></div>
  <div class="kpi"><span>Pendientes</span><strong>{reporte.pendientes}</strong></div>
</div>
<h2>Detalle por ruta</h2>
<table><thead><tr><th>Ruta</th><th>Total</th><th>Efectivas</th><th>No entregadas</th><th>Con novedad</th><th>Pendientes</th><th>Efectividad</th></tr></thead>
<tbody>{filas_ruta}</tbody></table>
<h2>Detalle por distribuidor</h2>
<table><thead><tr><th>Distribuidor</th><th>Total</th><th>Efectivas</th><th>No entregadas</th><th>Con novedad</th><th>Pendientes</th><th>Efectividad</th></tr></thead>
<tbody>{filas_distribuidor}</tbody></table>
<h2>Novedades del día</h2>
<table><thead><tr><th>Tipo</th><th>Suscriptor</th><th>Ruta</th><th>Detalle</th></tr></thead>
<tbody>{filas_novedades}</tbody></table>
<p class="pie">Generado por el Sistema de Respaldo de Información (SRI) · Usuario: {html.escape(sesion.nombre)} · {formato_fecha(date.today())}</p>
</body>
</html>"""
        ruta.write_text(contenido, encoding="utf-8")
        return ruta

    # ------------------------------------------------------------------ #
    # Tablero de inicio
    # ------------------------------------------------------------------ #
    def dashboard(self, sesion: Sesion) -> dict:
        self.auth.exigir(sesion, "RF-06")
        hoy = date.today().isoformat()
        estados = self.entregas.contar_por_estado(hoy)
        total = sum(estados.values())
        efectivas = estados.get("ENTREGADA", 0)
        return {
            "suscriptores": self.suscriptores.contar(solo_activos=True),
            "rutas": self.rutas.contar(),
            "distribuidores": self.distribuidores.contar_activos(),
            "entregas_hoy": total,
            "efectivas_hoy": efectivas,
            "efectividad_hoy": round(efectivas / total * 100, 1) if total else None,
            "estados_hoy": estados,
            "importaciones": self.archivos.listar(5),
        }

    @staticmethod
    def filas_novedades(reporte: ReporteDiario) -> list[tuple[str, str, str, str]]:
        """Novedades de entrega y de suscripción del día, para pantalla y exportación."""
        filas = [
            (e.estado.capitalize(), e.suscriptor, e.zona, e.novedad or "—") for e in reporte.novedades_entrega
        ]
        filas += [
            (n.tipo.capitalize(), n.suscriptor, n.zona, n.detalle) for n in reporte.novedades_suscripcion
        ]
        return filas

    # ------------------------------------------------------------------ #
    @staticmethod
    def _porcentaje_texto(valor: float | None) -> str:
        if valor is None:
            return "Sin datos"
        return f"{valor:.1f} %".replace(".", ",")

    def _tabla_csv(self, escritor, filas: list[FilaReporte], titulo: str) -> None:
        escritor.writerow([titulo])
        escritor.writerow(["Ruta/Distribuidor", "Total", "Efectivas", "No entregadas", "Con novedad", "Pendientes", "Efectividad"])
        for fila in filas:
            escritor.writerow(
                [
                    fila.clave,
                    fila.total,
                    fila.efectivas,
                    fila.no_entregadas,
                    fila.novedades,
                    fila.pendientes,
                    self._porcentaje_texto(fila.porcentaje),
                ]
            )
        escritor.writerow(
            [
                "TOTAL",
                sum(f.total for f in filas),
                sum(f.efectivas for f in filas),
                sum(f.no_entregadas for f in filas),
                sum(f.novedades for f in filas),
                sum(f.pendientes for f in filas),
                self._porcentaje_texto(
                    round(sum(f.efectivas for f in filas) / sum(f.total for f in filas) * 100, 1)
                    if sum(f.total for f in filas)
                    else None
                ),
            ]
        )

    def _filas_html(self, filas: list[FilaReporte]) -> str:
        if not filas:
            return '<tr><td colspan="7">Sin datos registrados para la fecha.</td></tr>'
        celdas = []
        for fila in filas:
            celdas.append(
                "<tr>"
                f"<td>{html.escape(fila.clave)}</td>"
                f"<td>{fila.total}</td>"
                f"<td>{fila.efectivas}</td>"
                f"<td>{fila.no_entregadas}</td>"
                f"<td>{fila.novedades}</td>"
                f"<td>{fila.pendientes}</td>"
                f"<td>{self._porcentaje_texto(fila.porcentaje)}</td>"
                "</tr>"
            )
        return "".join(celdas)
