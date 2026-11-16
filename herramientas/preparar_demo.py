"""Prepara una base de datos de demostración con el listado, novedades y entregas.

Uso:
    python herramientas/preparar_demo.py              # solo si la base está vacía
    python herramientas/preparar_demo.py --reiniciar  # elimina la base actual y la recrea

ADVERTENCIA: --reiniciar borra la base de datos local del SRI (conserva la clave sri.key).
"""

from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from generar_datos_demo import DISTRIBUIDORES, generar_archivos  # noqa: E402

from sri.config import cargar_config, directorio_datos  # noqa: E402
from sri.contexto import Contexto  # noqa: E402
from sri.util import formato_fecha  # noqa: E402

NOVEDADES_ENTREGA = (
    ("CON NOVEDAD", "Ejemplar faltante en el paquete; se repuso"),
    ("CON NOVEDAD", "Reclamo del suscriptor: llegó mojado"),
    ("NO ENTREGADA", ""),
    ("CON NOVEDAD", "Portería no permitió el ingreso"),
)
DIAS_HISTORIA = 6


def main(reiniciar: bool = False) -> int:
    config = cargar_config()
    base_datos = directorio_datos(config) / "sri_cam_dylan.db"

    if reiniciar:
        for sufijo in ("", "-wal", "-shm"):
            archivo = Path(str(base_datos) + sufijo)
            if archivo.exists():
                archivo.unlink()
        print("Base de datos anterior eliminada.")

    archivos = generar_archivos(RAIZ / "datos_ejemplo")
    print(f"Listados de ejemplo generados en {RAIZ / 'datos_ejemplo'}")

    contexto = Contexto(config=config)
    try:
        if contexto.suscriptores.contar() > 0:
            print("La base de datos ya contiene información. Use --reiniciar para recrear la demostración.")
            return 1

        secretaria = contexto.auth.iniciar_sesion("secretaria", "Sri2026*")
        gerencia = contexto.auth.iniciar_sesion("gerencia", "Sri2026*")
        operativo = contexto.operativo

        for nombre, telefono, _hoja, _codigo in DISTRIBUIDORES:
            operativo.crear_distribuidor(secretaria, nombre, telefono)

        resumen = contexto.importacion.importar(secretaria, archivos["base"])
        print(
            f"Carga inicial: {resumen.hojas} hojas, {resumen.leidos} leídos, {resumen.importados} nuevos, "
            f"{resumen.actualizados} actualizados, {resumen.rechazados} rechazados, "
            f"{len(resumen.revisar)} casos para revisar."
        )

        # La Gerencia decide a quién pasa la ruta AL del distribuidor que se retiró.
        rutas = {r.zona: r.id for r in operativo.listar_rutas(secretaria)}
        luis = next(d.id for d in operativo.listar_distribuidores(secretaria) if d.nombre == "Luis Ramírez")
        operativo.asignar_ruta(secretaria, rutas["AL"], luis)

        hoy = date.today()
        aleatorio = random.Random(7)
        for desplazamiento in range(DIAS_HISTORIA, -1, -1):
            dia = hoy - timedelta(days=desplazamiento)
            programados = contexto.suscriptores.listar_del_dia(dia.isoformat(), limite=-1)
            for suscriptor in aleatorio.sample(programados, k=max(1, len(programados) // 15)):
                estado, novedad = aleatorio.choice(NOVEDADES_ENTREGA)
                operativo.registrar_entrega(secretaria, suscriptor.id, formato_fecha(dia), estado, novedad)
            if desplazamiento:  # hoy queda abierto para la demostración
                operativo.cerrar_dia(secretaria, formato_fecha(dia))
        print(f"Novedades de entrega de los últimos {DIAS_HISTORIA} días registradas y días cerrados.")

        # Novedades de suscripción del listado impreso de hoy (RF-09).
        servicio = contexto.suscripciones
        servicio.registrar_ingreso(
            secretaria, formato_fecha(hoy), "Sonia Delgado", "Avenida 1 # 6-72", ["TIE", "PT"], "L-V", rutas["MS"],
            detalle="Ingreso del listado impreso",
        )
        candidatos = contexto.suscriptores.listar(solo_activos=True, limite=10)
        servicio.registrar_retiro(secretaria, candidatos[0].id, formato_fecha(hoy), "Retiro del listado impreso")
        cambio = candidatos[1]
        servicio.registrar_cambio(
            secretaria, cambio.id, formato_fecha(hoy), cambio.nombre, cambio.direccion + " Apto 201",
            cambio.productos.split(","), "S-D", cambio.ruta_id, cambio.direccion_fs, "Cambio de periodicidad",
        )
        print("Novedades de suscripción de hoy: 1 ingreso, 1 retiro y 1 cambio.")

        ayer = hoy - timedelta(days=1)
        reporte = contexto.consultas.generar_reporte(gerencia, formato_fecha(ayer))
        print(f"Reporte de ayer: {reporte.total} programadas, efectividad {reporte.porcentaje} %.")

        respaldo = contexto.respaldos.crear(gerencia, RAIZ / "respaldos" / "sri_respaldo_inicial.sribak")
        print(f"Respaldo manual de demostración: {respaldo}")

        print("\nDemostración lista.")
        print("  Usuarios: secretaria / gerencia · Contraseña: Sri2026*")
        print(f"  Base de datos: {base_datos}")
        print(f"  Listado para importar en vivo: {archivos['nueva']}")
        return 0
    finally:
        contexto.cerrar()


if __name__ == "__main__":
    raise SystemExit(main("--reiniciar" in sys.argv))
