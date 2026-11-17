# Entregable y trazabilidad

**SRI · Sistema de Respaldo de Información — Distribuciones Cam Dylan S.A.S.**
Versión 2.0.0 · alineada con el informe *Avance_informe_proyecto1_v5.3*.

Este documento funciona como acta de entrega: enumera los artefactos, relaciona cada requisito del informe con su implementación y sus pruebas, y describe el procedimiento de verificación.

---

## 1. Resumen del entregable

| Elemento | Estado | Ubicación |
|---|---|---|
| Aplicación de escritorio funcional | Entregado | `sri_cam_dylan/` |
| Código fuente por capas | Entregado | `sri/` |
| Base de datos de demostración | Se genera con `python herramientas\preparar_demo.py` (el `.rar` no incluye `sri.key` ni la base cifrada con ella) | `datos/sri_cam_dylan.db` |
| Listado de repartidores de ejemplo (formato del Anexo D) | Entregado | `datos_ejemplo/` |
| Respaldos cifrados de demostración (manual y diario) | Entregados | `respaldos/` |
| Pruebas automatizadas | 31/31 OK | `pruebas/test_sri.py` |
| Capturas de pantalla | 10 pantallas | `docs/capturas/` |
| Manual de usuario | Entregado | `docs/MANUAL_USUARIO.md` |
| Documento de arquitectura | Entregado | `docs/ARQUITECTURA.md` |
| Guion de sustentación | Entregado | `docs/GUION_SUSTENTACION.md` |
| README de instalación | Entregado | `README.md` |

**Tecnología:** Python 3.11+ · Tkinter/ttk · SQLite · openpyxl · xlrd · cryptography (ver la nota de tecnología en la sección 9).

**Credenciales de demostración:** `secretaria` / `gerencia`, contraseña `Sri2026*`.

---

## 2. Cambios frente a la versión anterior (informe v3.1 → v5.3)

La entrevista a la Gerencia cambió el supuesto central: la editorial ya no entrega archivos digitales, sino **listados impresos**, y la única base de datos de la empresa es el **Excel de repartidores** que la gerente actualiza a mano.

| Tema | Antes (v3.1) | Ahora (v5.3) |
|---|---|---|
| RF-01 | Importar el Excel de la editorial cada día | Cargar el **listado de repartidores**: una hoja por distribuidor, columnas N°, nombre, dirección, TIE, PT y código de ruta; separar la periodicidad del nombre; asociar el código de ruta al distribuidor; unir suscriptores con dos direcciones |
| RF-09 (nuevo) | — | Registrar **ingresos, retiros y cambios** del listado impreso |
| RF-05 | Registrar el estado de cada entrega | Registrar **solo las novedades**; al **cerrar el día** las programadas pendientes quedan ENTREGADA |
| RF-03 | Efectividad = efectivas ÷ registradas | Efectividad = efectivas ÷ **programadas según la periodicidad**, con la lista de novedades del día |
| RF-02 | Asignar rutas | Además, **ruta imprimible** por distribuidor (diarias, sábados y domingos, Portafolio) |
| RF-07 / RN-09 | Respaldo manual semanal | **Respaldo diario automático**, se conservan **7**, copia semanal a **Google Drive** y **aviso al iniciar sesión** si algo falla |
| RN-11, RN-12 (nuevas) | — | Programación por periodicidad y cierre del día; un retiro marca inactivo y no borra |
| Modelo de datos | — | Suscriptor con dirección de fin de semana, productos, periodicidad y estado; tabla `novedad_suscripcion` |

Las bases de datos y los respaldos de la versión anterior se **migran automáticamente** al abrirlos (`BaseDatos._migrar`).

---

## 3. Lista de verificación

- [x] Los nueve requisitos funcionales (RF-01 a RF-09) están implementados y accesibles desde la interfaz.
- [x] Las doce reglas de negocio (RN-01 a RN-12) se validan en la capa de servicios y/o en la base de datos.
- [x] La interfaz está en español, con fechas `dd/mm/aaaa`, tipografía ampliada y menú según rol.
- [x] Los datos personales (nombre, direcciones, novedades) se cifran con AES-256-GCM y las contraseñas usan PBKDF2-SHA256.
- [x] La importación es transaccional, justifica cada rechazo y lista los casos para revisar con la Gerencia.
- [x] Las entregas se programan por periodicidad y el cierre del día da por cumplidas las que no tienen novedad.
- [x] El reporte calcula la efectividad sobre las entregas programadas y evita la división por cero.
- [x] El respaldo diario es automático, se conservan siete y la copia semanal a Google Drive queda registrada y avisada.
- [x] La bitácora no contiene nombres ni direcciones de suscriptores.
- [x] Las pruebas automatizadas pasan en bases temporales, sin afectar la demo.
- [x] Las bases de la versión anterior se actualizan solas (prueba de migración).
- [ ] Empaquetado como `.exe` independiente (no solicitado; se ejecuta con Python).

---

## 4. Matriz de trazabilidad · requisitos funcionales

| RF | Implementación principal | Interfaz | Pruebas automatizadas | Evidencia |
|---|---|---|---|---|
| **RF-01** Importar el listado de repartidores | `servicios/importacion.py`, `servicios/lectores.py`, `dominio/periodicidad.py`, `config.json` | `vista_importacion.py` | `test_rf01_formato_real_dos_listas_y_columnas_sin_encabezado`, `test_listado_multihoja_periodicidad_productos_y_rutas`, `test_rn07_dos_direcciones_es_un_solo_suscriptor`, `test_importacion_repetida_no_duplica`, `test_archivo_sin_columnas_obligatorias_no_modifica`, `test_archivo_danado_mensaje_claro_y_no_modifica`, `test_archivo_csv` | `capturas/03_importar.png` |
| **RF-02** Asignar y modificar rutas; ruta imprimible | `servicios/operativo.py` (`crear_ruta`, `actualizar_ruta`, `asignar_ruta`, `secciones_ruta`, `exportar_ruta_html`) | `vista_rutas.py` | `test_rutas_y_rn01`, `test_rf02_ruta_imprimible_por_secciones` | `capturas/05_rutas.png` |
| **RF-03** Reporte diario de entregas | `servicios/consultas.py` (`generar_reporte`, `exportar_csv`, `exportar_html`), `EntregaDAO.estadisticas_fecha` | `vista_reportes.py` | `test_rn11_programacion_y_cierre_del_dia`, `test_reporte_sin_programadas_y_exportes` | `capturas/08_reportes.png` |
| **RF-04** Gestionar distribuidores | `servicios/operativo.py` | `vista_distribuidores.py` | `test_rutas_y_rn01` (RN-02), `test_rn08_permisos_por_rol` | `capturas/06_distribuidores.png` |
| **RF-05** Registrar novedad de entrega y cerrar el día | `servicios/operativo.py` (`registrar_entrega`, `cerrar_dia`), `EntregaDAO.marcar_entregadas` | `vista_entregas.py` | `test_rn03_rn04_entregas`, `test_rn11_programacion_y_cierre_del_dia` | `capturas/04_entregas.png` |
| **RF-06** Consultar historial | `servicios/consultas.py`, `SuscriptorDAO.listar` | `vista_consultas.py`, `dialogos.py` | `test_consultas_filtros_e_historial`, `test_busqueda_encuentra_suscriptores_fuera_del_limite`, `test_rf06_buscar_suscriptores_sin_entregas_y_ficha` | `capturas/07_consultas.png` |
| **RF-07** Respaldo diario, Google Drive y restauración | `servicios/respaldos.py`, `seguridad.py`, `presentacion/app.py` (respaldo al salir y avisos) | `vista_respaldos.py` | `test_rn09_respaldo_diario_unico_y_conserva_siete`, `test_rf07_copia_drive_y_avisos`, `test_rf07_fallo_del_respaldo_diario_se_avisa`, `test_rf07_verificar_respaldo_y_copia_de_la_clave`, `test_respaldo_cifrado_y_restauracion` | `capturas/09_respaldos.png` |
| **RF-08** Iniciar sesión y roles | `servicios/autenticacion.py`, `dominio/modelos.py` (`PERMISOS`) | `login.py`, `principal.py` | `test_login_valido_e_invalido`, `test_rn08_permisos_por_rol`, `test_contrasenas_y_bitacora_sin_lo_escrito_en_usuario` | `capturas/01_login.png` |
| **RF-09** Registrar novedades de suscripción | `servicios/suscripciones.py`, `NovedadSuscripcionDAO` | `vista_novedades.py` | `test_rf09_ingreso_validaciones_y_aviso`, `test_rf09_cambio`, `test_rn12_retiro_no_borra_y_sale_de_la_programacion` | `capturas/10_novedades.png` |

---

## 5. Matriz de trazabilidad · reglas de negocio

| RN | Regla del informe | Dónde se aplica | Prueba |
|---|---|---|---|
| **RN-01** | Cada ruta tiene un único distribuidor a la vez | `ruta.distribuidor_id`; `asignar_ruta/actualizar_ruta` | `test_rutas_y_rn01` |
| **RN-02** | Un distribuidor con rutas no puede darse de baja | `cambiar_estado_distribuidor` | `test_rutas_y_rn01` |
| **RN-03** | Una entrega por suscriptor y fecha; solo estados válidos | `UNIQUE (suscriptor_id, fecha)`, `CHECK`, `registrar_entrega` | `test_rn03_rn04_entregas` |
| **RN-04** | No se registran entregas con fecha futura | `registrar_entrega`, `cerrar_dia`, `generar_reporte` | `test_rn03_rn04_entregas`, `test_rn11_programacion_y_cierre_del_dia` |
| **RN-05** | Efectividad = efectivas ÷ programadas × 100 | `ReporteDiario.porcentaje` sobre `estadisticas_fecha` | `test_rn11_programacion_y_cierre_del_dia` |
| **RN-06** | Importación completa o no se aplica; rechazos justificados | `BaseDatos.transaccion`, `ImportacionServicio.importar` | `test_listado_multihoja…`, `test_archivo_sin_columnas_obligatorias_no_modifica` |
| **RN-07** | Un suscriptor no se duplica; con dos direcciones es uno solo | Índice ciego único; `_unir_direcciones` | `test_importacion_repetida_no_duplica`, `test_rn07_dos_direcciones_es_un_solo_suscriptor` |
| **RN-08** | Solo autenticados; cada rol usa sus funciones | `PERMISOS`, `AutenticacionServicio.exigir` | `test_rn08_permisos_por_rol` |
| **RN-09** | Respaldo diario automático, se conservan 7, copia semanal a Google Drive | `respaldo_automatico`, `_depurar_diarios`, `copiar_a_drive`, `avisos` | `test_rn09_respaldo_diario_unico_y_conserva_siete`, `test_rf07_copia_drive_y_avisos` |
| **RN-10** | Datos personales solo con fines logísticos | Cifrado de campos, bitácora sin datos personales, aviso en la ruta impresa | `test_bitacora_sin_datos_personales` |
| **RN-11** | Entregas programadas por periodicidad; sin novedad al cierre = cumplidas | `PROGRAMADO` / `RUTA_DEL_DIA` en `daos.py`, `marcar_entregadas` | `test_rn11_programacion_y_cierre_del_dia` |
| **RN-12** | Un retiro marca inactivo; no se borra | `registrar_retiro` (`estado`, `fecha_retiro`); la depuración anual anonimiza sin borrar | `test_rn12_retiro_no_borra_y_sale_de_la_programacion`, `test_depuracion_anual_anonimiza_retirados_antiguos` |

---

## 6. Cobertura de requisitos no funcionales

| RNF | Cómo se atiende | Evidencia |
|---|---|---|
| **RNF-01** Seguridad y Habeas Data | AES-256-GCM por campo, índice ciego, PBKDF2, respaldos cifrados (también en Google Drive), bitácora sin datos personales | `sri/seguridad.py`, `test_listado_multihoja…`, `test_bitacora_sin_datos_personales` |
| **RNF-02** Rendimiento | 10 000 registros importados en ≈2,2 s; una novedad se confirma en < 2 s | `test_rnf02_10000_registros_en_10_segundos` |
| **RNF-03** Disponibilidad | Funciona sin Internet; respaldo diario (en el peor caso se pierde un día) | `sri/servicios/respaldos.py` |
| **RNF-04** Integridad de la importación | Leídos = importados + actualizados + rechazados; se verifica **antes** de confirmar la transacción | `ResumenImportacion.cuadra` |
| **RNF-05** Mantenibilidad | Respaldo diario automático, copia semanal externa, migración automática del esquema, configuración externa | `test_base_de_la_version_anterior_se_actualiza` |

---

## 7. Resultado de las pruebas

```bat
python -m unittest discover -s pruebas -v
```

```text
Ran 31 tests in ~11 s
OK
[RNF-02: importación de 10.000 registros en 2.23 s]
```

Además se ejecutó una **prueba de humo de la interfaz** sobre una copia de la base demo: inicio de sesión con ambos roles, apertura de las 9 vistas, importación del listado actualizado, registro de una novedad de entrega, ruta imprimible y copia a Google Drive, sin excepciones de Tk. Las capturas de `docs/capturas/` provienen de esa prueba.

---

## 8. Procedimiento de verificación manual

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Ejecutar `run.bat` | Pantalla de inicio de sesión |
| 2 | Ingresar `secretaria` / `Sri2026*` | Aviso «Aún no se ha copiado ningún respaldo a Google Drive»; menú con importar, novedades de suscripción, novedades de entrega, rutas, distribuidores e historial |
| 3 | Revisar **Inicio** | 76 suscriptores activos, 5 rutas, 4 distribuidores y las entregas programadas de hoy |
| 4 | **Pasar el listado impreso** | Novedades de hoy: 1 ingreso, 1 retiro y 1 cambio; registrar un ingreso con dirección «Centro» → mensaje de dirección incompleta |
| 5 | **Lo que reportan los repartidores** | Entregas de hoy según la periodicidad; tocar a un suscriptor, elegir un motivo rápido y pulsar **Entregado con novedad**; luego **Cerrar el día…** → la confirmación dice cuántas se marcarán |
| 6 | **Importar** `listado_repartidores_actualizado.xlsx` | 86 leídos = 3 nuevos + 81 actualizados + 2 rechazados, y 5 casos para revisar: periodicidad «quincenal», ruta AL en la hoja de Marta (ya es de Luis), el suscriptor retirado hoy (aparece en dos hojas) y un posible duplicado del suscriptor cuya dirección se cambió hoy |
| 7 | **Rutas** → seleccionar una ruta → **Imprimir ruta del distribuidor** | Hoja con las secciones Entregas diarias, Sábados y domingos y Portafolio |
| 8 | **Distribuidores** → dar de baja uno con rutas | Mensaje de RN-02; la baja no se aplica |
| 9 | Cerrar sesión e ingresar como `gerencia` | Menú con historial, reporte y respaldos |
| 10 | **Reporte diario** de ayer | 61 programadas y 93,4 % de efectividad; exportar CSV/HTML con la lista de novedades |
| 11 | **Respaldos** → **Copiar a Google Drive** | Se elige la carpeta sincronizada; el aviso desaparece y la copia queda en el historial |
| 12 | **Restaurar respaldo** (doble confirmación) | Sesión cerrada y datos restaurados |

> Los pasos 5 y 6 modifican la demo. Para dejarla como al inicio: `python herramientas\preparar_demo.py --reiniciar` (destructivo).
>
> El paso 6 muestra un efecto esperado: si se vuelve a cargar el Excel completo después de registrar novedades en el SRI, el Excel trae los datos anteriores. Por eso la recarga no reactiva retirados y marca para revisión los posibles duplicados.

---

## 9. Limitaciones declaradas

1. **Tecnología:** el informe v5.3 (secciones 6.3.1 y 6.3.4, Tabla 20) sigue proponiendo Java, JavaFX, JDBC, BCrypt, JasperReports y JUnit. El prototipo usa Python, Tkinter, PBKDF2, exportación CSV/HTML y `unittest`, con la misma arquitectura en capas. Hay que alinear el informe o declarar el cambio.
2. **Ruta de fin de semana:** la Tabla 19 tiene un solo `Ruta_ID`. Para los suscriptores que reciben entre semana en una ruta y el fin de semana en otra, se agregó `ruta_fs_id`.
3. **Unión de dos direcciones:** se hace por nombre y periodicidades complementarias (entre semana / fin de semana); cada unión queda en los casos para revisar.
4. **Código de ruta:** se asocia al distribuidor por sus iniciales (p. ej. CP = Carlos Pérez). Si el código no tiene forma de iniciales, se usa el distribuidor de la hoja.
5. **Google Drive:** el SRI copia el respaldo a la carpeta sincronizada; la subida a la nube la hace la aplicación de Google Drive para escritorio.
6. El respaldo diario se genera al cerrar el día, al cerrar la sesión o al cerrar la aplicación; no hay un programador del sistema operativo.
7. La exportación a PDF se hace desde el HTML mediante el navegador.
8. La clave `datos/sri.key` debe custodiarse fuera del equipo; sin ella no se recuperan los datos ni los respaldos (tampoco los de Google Drive).
9. RNF-02 y RNF-04 se verificaron con datos sintéticos; falta repetirlos con el listado real anonimizado en el computador de la gerente.
