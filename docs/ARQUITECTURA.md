# Arquitectura del SRI

**Sistema de Respaldo de Información — Distribuciones Cam Dylan S.A.S.**

Este documento describe la arquitectura implementada, las decisiones de diseño, el modelo de datos, los mecanismos de seguridad y la estrategia de pruebas. Está alineado con el informe del proyecto (`Avance_informe_proyecto1_v5.3.pdf`) y con la matriz de trazabilidad de [`ENTREGABLE.md`](ENTREGABLE.md).

---

## 1. Objetivos de la arquitectura

1. **Cubrir los nueve requisitos funcionales** (RF-01 a RF-09) del informe sin dependencias de servidor.
2. **Hacer cumplir las reglas de negocio RN-01 a RN-12** en una capa central, no solo en la interfaz.
3. **Proteger los datos personales** de los suscriptores mediante cifrado en reposo.
4. **Garantizar trazabilidad**: toda importación, entrega, reporte y respaldo deja registro.
5. **Mantener el sistema comprensible y verificable** para un proyecto académico, con pruebas automatizadas.
6. **Permitir la evolución** hacia una estación centralizada o una API sin reescribir el dominio.

---

## 2. Vista de capas

```text
┌──────────────────────────────────────────────────────────────┐
│ Presentación (Tkinter/ttk)                                   │
│ login · shell · vistas · diálogos · estilos · widgets        │
└──────────────────────────────┬───────────────────────────────┘
                               │ llama servicios, nunca SQL
┌──────────────────────────────▼───────────────────────────────┐
│ Servicios de aplicación                                     │
│ autenticación · importación · suscripciones · operativo     │
│ consultas · respaldos · auditoría                            │
│  · valida permisos (RN-08)                                  │
│  · aplica reglas de negocio                                 │
│  · coordina transacciones                                   │
└───────────────┬──────────────────────────────┬───────────────┘
                │                              │
┌───────────────▼──────────────┐  ┌────────────▼───────────────┐
│ Dominio                      │  │ Datos                      │
│ modelos, estados, permisos,  │  │ BaseDatos (SQLite)         │
│ periodicidad, efectividad    │  │ DAO por entidad, migración │
│                              │  │ esquema.sql                │
└──────────────────────────────┘  └────────────────────────────┘
```

**Regla de dependencia:** la presentación depende de los servicios; los servicios dependen del dominio y de los DAO; los DAO dependen de la conexión. Ninguna capa superior ejecuta SQL directo ni conoce detalles de cifrado.

La composición se centraliza en `sri/contexto.py` (`Contexto`), que crea la conexión, el cifrador, los DAO y los servicios una sola vez. Esto facilita las pruebas: basta inyectar una base y una clave temporales.

---

## 3. Módulos

| Módulo | Responsabilidad |
|---|---|
| `main.py` | Punto de entrada, DPI, manejo de errores de arranque. |
| `sri/config.py` | Carga de `config.json`, rutas de datos/respaldos/exportes y variables de entorno. |
| `sri/contexto.py` | Raíz de composición de dependencias. |
| `sri/seguridad.py` | AES-256-GCM, índice ciego HMAC, PBKDF2, cifrado de respaldos. |
| `sri/util.py` | Normalización, fechas `dd/mm/aaaa`, validaciones y errores de negocio. |
| `sri/dominio/modelos.py` | Entidades, roles, permisos y cálculos (efectividad, cuadre de importación). |
| `sri/dominio/periodicidad.py` | Separa la periodicidad escrita junto al nombre («D», «S-D», «L-V», listas de días) y la guarda como máscara de 7 días. |
| `sri/datos/base_datos.py` | Conexión SQLite, PRAGMA, transacciones, backup/restore, integridad y migración de bases anteriores. |
| `sri/datos/daos.py` | Acceso a datos por entidad; descifra al leer y cifra al escribir. |
| `sri/datos/esquema.sql` | Esquema relacional, restricciones e índices. |
| `sri/servicios/autenticacion.py` | Login, cambio de contraseña, usuarios y verificación de permisos. |
| `sri/servicios/importacion.py` | Carga del listado de repartidores (multihoja), periodicidad, productos, código de ruta → distribuidor, dos direcciones, rechazos y casos para revisar. |
| `sri/servicios/lectores.py` | Estrategias de lectura para `.xlsx`, `.xls` y `.csv`; devuelven todas las hojas. |
| `sri/servicios/suscripciones.py` | Novedades de suscripción del listado impreso: ingreso, retiro y cambio (RF-09). |
| `sri/servicios/operativo.py` | Distribuidores, rutas, novedades de entrega, cierre del día y ruta imprimible. |
| `sri/servicios/consultas.py` | Búsquedas, reporte diario sobre entregas programadas, exportaciones y tablero. |
| `sri/servicios/respaldos.py` | Respaldo diario automático, retención de 7, copia a Google Drive, avisos y restauración. |
| `sri/servicios/auditoria.py` | Bitácora de eventos sin datos personales. |
| `sri/presentacion/*` | Interfaz: login, shell por rol, vistas y diálogos. |
| `pruebas/test_sri.py` | 26 pruebas automatizadas de requisitos, reglas y migración. |
| `herramientas/*` | Generación de archivos de ejemplo y preparación de la demo. |

### Patrones utilizados

- **Composición en una raíz** (`Contexto`): una sola instancia de conexión, cifrador y servicios.
- **DAO**: separa el acceso a SQLite del dominio.
- **Servicio de aplicación**: concentra reglas, permisos, transacciones y auditoría.
- **Estrategia**: `LectorArchivo` con implementaciones para XLSX, XLS y CSV.
- **Modelo de dominio rico**: `ResumenImportacion.cuadra` y `ReporteDiario.porcentaje` encapsulan las fórmulas.
- **Inyección de dependencias manual**: sin frameworks, adecuada al tamaño del proyecto.

---

## 4. Flujos principales

### 4.1 Inicio de sesión (RF-08)

```text
Usuario → LoginFrame → AutenticacionServicio.iniciar_sesion
        → UsuarioDAO.buscar_por_nombre
        → verificar_contrasena (PBKDF2 + compare_digest)
        → Sesion(usuario) → ShellFrame construye el menú según permisos
```

- Credenciales incorrectas generan un mensaje genérico y un evento `LOGIN_FALLIDO`.
- El menú y los accesos rápidos se filtran con `Sesion.puede("RF-xx")`.
- Cada servicio vuelve a verificar el permiso; la interfaz no es la única barrera.

### 4.2 Importación del listado de repartidores (RF-01)

```text
Selección del libro de Excel
   → crear_lector (por extensión) → una entrada por hoja
   → BEGIN IMMEDIATE
        por cada hoja (= un distribuidor):
          · buscar la fila de encabezados en las primeras filas y mapear columnas (config.json)
          · si faltan columnas obligatorias: error con el nombre de la hoja → ROLLBACK
          · distribuidor de la hoja = nombre, primer nombre o iniciales («CARLOS (2)» → Carlos Pérez)
          por cada fila con datos:
            · rechazar si falta nombre, dirección o código de ruta, o si no tiene TIE ni PT
            · separar la periodicidad del nombre (si no se entiende: diaria + caso para revisar)
            · código de ruta → distribuidor por sus iniciales; si no es de uno activo: caso para revisar
            · índice ciego (nombre + dirección): si existe → actualizar (la última hoja prevalece)
            · si no, buscar por nombre: L-V + S-D con otra dirección → un solo suscriptor
              con dirección y ruta de fin de semana (RN-07) + caso para revisar
            · si no, crear
        registrar archivo y totales; verificar leídos = nuevos + actualizados + rechazados
     COMMIT  (o ROLLBACK ante cualquier error; un archivo dañado da un mensaje claro)
   → auditar totales (sin datos personales)
```

La importación corre en un hilo secundario para que la ventana siga respondiendo.

### 4.3 Novedades, programación y cierre del día (RF-09, RF-05, RN-11, RN-12)

```text
Novedad de suscripción (RF-09), en una transacción:
  ingreso → validar nombre, dirección completa, producto, periodicidad y ruta → crear (fecha_ingreso)
            · si existe retirado con la misma dirección → reactivar (reingreso)
            · si hay homónimos con otra dirección → advertencia
  retiro  → estado RETIRADO + fecha_retiro (no se borra: RN-12)
  cambio  → aplicar solo los campos que cambiaron; recalcular índices si cambian nombre o dirección
  + registro en novedad_suscripcion (detalle cifrado)

Entregas programadas de una fecha (RN-11), en SQL:
  suscriptor activo en la fecha (fecha_ingreso ≤ fecha < fecha_retiro)
  y substr(periodicidad, día_de_la_semana, 1) = '1'
  ruta del día = ruta de fin de semana si es sábado/domingo y la tiene

Novedad de entrega: NO ENTREGADA / CON NOVEDAD (UPSERT único por suscriptor y fecha)
Cerrar el día: INSERT … SELECT de las programadas → ENTREGADA, sin tocar las que tienen novedad
               → respaldo diario automático
```

El reporte (RF-03) agrega en SQL las entregas del día —programadas más las registradas, sin registro = PENDIENTE— por ruta del día y distribuidor. Efectividad = ENTREGADA ÷ programadas; si no hay programadas no se calcula ni se guarda (RN-05). Incluye la lista de novedades de entrega y de suscripción.

### 4.4 Respaldo y restauración (RF-07, RN-09)

**Respaldo diario automático (RN-09)**

```text
Cerrar el día · cerrar la sesión · cerrar la aplicación
  → ¿ya hay respaldo DIARIO hoy? sí: nada
  → no: copia consistente (API backup de SQLite) → AES-256-GCM + cabecera SRIBAK1
        → respaldos/sri_diario_AAAAMMDD.sribak + registro tipo DIARIO
        → borrar los DIARIO más antiguos que los 7 más recientes
  → si algo falla: evento RESPALDO_FALLIDO (nunca bloquea la salida)
```

**Copia semanal a Google Drive**

```text
Gerencia → Copiar a Google Drive → carpeta sincronizada (se guarda en config.json)
  → copia del último respaldo local, ya cifrado → registro tipo DRIVE
  → la aplicación de Google Drive para escritorio lo sube cuando hay Internet
```

**Avisos al iniciar sesión:** si el último evento de respaldo diario es RESPALDO_FALLIDO, o si la última copia DRIVE tiene más de 7 días (o no existe), se muestra un aviso visible.

**Restaurar**

```text
Seleccionar .sribak → doble confirmación
  → verificar cabecera SRIBAK1 y descifrar
  → PRAGMA integrity_check y tablas del SRI en una copia temporal
  → reemplazar la base con la API de backup de SQLite
  → migrar si el respaldo es de la versión anterior (BaseDatos.preparar)
  → cerrar la sesión y exigir un nuevo login
```

---

## 5. Modelo de datos

```text
usuario (1) ───< archivo_importacion (1) ───< suscriptor (1) ───< entrega
   │                                              │  │  └──< novedad_suscripcion
   ├──< novedad_suscripcion                       │  └── ruta (entre semana) ─── distribuidor (0..1)
   ├──< reporte_diario                            └── ruta_fs (fin de semana, opcional)
   ├──< respaldo (DIARIO · MANUAL · DRIVE)
   └──< evento
```

| Tabla | Propósito | Restricciones clave |
|---|---|---|
| `usuario` | Usuarios y rol | `nombre` único, rol `Secretaria`/`Gerencia`, hash de contraseña |
| `distribuidor` | Equipo operativo | `nombre` único, `activo` |
| `ruta` | Zonas de entrega | `zona_normalizada` única, `distribuidor_id` opcional (un solo distribuidor) |
| `archivo_importacion` | Trazabilidad de cargas | Totales leídos/importados/actualizados/rechazados |
| `suscriptor` | Cliente | Nombre, dirección, dirección de fin de semana y novedades cifrados; `productos` (TIE/PT), `periodicidad` (máscara de 7 días), `estado` (ACTIVO/RETIRADO), `fecha_ingreso`, `fecha_retiro`, `numero`, `ruta_fs_id`; `indice_busqueda` único e `indice_nombre` |
| `novedad_suscripcion` | Ingresos, retiros y cambios (RF-09) | Tipo con `CHECK`, detalle cifrado, fecha y usuario |
| `entrega` | Estado diario | `UNIQUE (suscriptor_id, fecha)`; `CHECK` de estados |
| `reporte_diario` | Reporte guardado | `fecha` primaria, porcentaje y usuario |
| `respaldo` | Historial de copias | Fecha, ruta, usuario y `tipo` (DIARIO, MANUAL, DRIVE) |
| `evento` | Bitácora | Tipo, detalle y usuario opcional |

Decisiones relevantes:

- **Un solo distribuidor por ruta:** se modela como `ruta.distribuidor_id`, no como tabla puente. La reasignación actualiza la ruta y deja el historial en la bitácora.
- **Un estado por suscriptor y fecha:** la restricción `UNIQUE` y el `UPSERT` garantizan la RN-03.
- **Suscriptor sin duplicados:** el índice ciego único impide insertar dos veces el mismo par nombre + dirección normalizados.
- **Periodicidad como máscara:** `"0000011"` = sábado y domingo; permite programar las entregas con una sola consulta SQL.
- **Ruta de fin de semana:** la Tabla 19 del informe tiene un solo `Ruta_ID`; se agregó `ruta_fs_id` para el suscriptor que recibe entre semana en una ruta y el fin de semana en otra.
- **Migración:** `BaseDatos._migrar` agrega con `ALTER TABLE` las columnas nuevas a bases y respaldos anteriores; el `Contexto` completa el índice por nombre.
- **Fechas:** se almacenan en ISO (`aaaa-mm-dd`) y se muestran/parsean en `dd/mm/aaaa`.
- **Integridad referencial:** `PRAGMA foreign_keys = ON`; WAL para resistencia y concurrencia básica; `busy_timeout` de 15 s.

### Índices

- `ux_suscriptor_indice` (único) para duplicados.
- `ix_suscriptor_ruta` para listados por ruta.
- `ix_suscriptor_nombre` para homónimos y suscriptores con dos direcciones.
- `ix_novedad_fecha` para las novedades del día.
- `ix_entrega_fecha` para reportes y consultas por fecha.
- `ix_evento_fecha` para la bitácora.
- `ux_distribuidor_nombre` para nombres únicos.

---

## 6. Seguridad

### 6.1 Cifrado de campos personales

- Algoritmo: **AES-256-GCM** (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`).
- Nonce aleatorio de **12 bytes** por operación; el texto cifrado incluye la etiqueta de autenticación.
- Formato almacenado: `enc:v1:` + Base64(nonce || ciphertext || tag).
- Campos cifrados: `suscriptor.nombre_cifrado`, `direccion_cifrada`, `direccion_fs_cifrada`, `novedades_cifrada`, la novedad de `entrega` y el detalle de `novedad_suscripcion`.
- El cifrado es autenticado: cualquier alteración del dato produce un error al descifrar.

### 6.2 Índice ciego

- `HMAC-SHA256(clave, normalizar(nombre) + 0x1F + normalizar(dirección))`.
- Permite detectar duplicados y buscar sin descifrar.
- Es determinista: revela igualdad entre registros, pero no el contenido. Es un compromiso consciente para un prototipo local (ver AD-03).

### 6.3 Contraseñas

- **PBKDF2-HMAC-SHA256**, 240 000 iteraciones, sal aleatoria de 16 bytes.
- Formato: `pbkdf2_sha256$iteraciones$sal$hash`.
- Comparación con `hmac.compare_digest` para evitar ataques de tiempo.
- Longitud mínima: 8 caracteres.

### 6.4 Clave local

- `datos/sri.key` contiene 32 bytes aleatorios y se crea con permisos restringidos (`chmod 600` cuando el sistema lo permite).
- No se incluye en los respaldos. Debe custodiarse por separado.
- Si la clave no corresponde, los datos personales y los respaldos no se pueden leer; el sistema muestra un error controlado.

### 6.5 Bitácora

- Registra inicio de sesión, importaciones, novedades de suscripción (solo el número interno del suscriptor), cierres del día, cambios de rutas/distribuidores, respaldos (diarios, fallidos y copias a Drive) y restauraciones.
- **No** registra nombres, direcciones ni novedades de suscriptores.
- Se consulta mediante `AuditoriaServicio.listar`.

### 6.6 Superficie de riesgo y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Robo del archivo `.db` | Campos personales cifrados; contraseñas con hash |
| Robo del respaldo `.sribak` | Cifrado AES-GCM con cabecera propia |
| Fuerza bruta de contraseñas | PBKDF2 con 240 000 iteraciones; mensajes genéricos |
| Alteración de un dato cifrado | GCM detecta manipulación |
| Duplicados maliciosos | Índice ciego único + normalización |
| Acceso a funciones indebidas | Permisos verificados en cada servicio (RN-08) |
| Fuga por bitácora | Eventos sin datos personales |
| Restauración de un archivo ajeno | Validación de cabecera, integridad y tablas requeridas |
| Respaldo en la nube | El archivo ya va cifrado; cuenta de Google con verificación en dos pasos |
| Hoja de ruta impresa | Aviso de Ley 1581 en la hoja; se genera solo bajo demanda |

> El cifrado protege los datos en reposo. No sustituye controles del equipo (cuentas de Windows, disco cifrado, antivirus, bloqueo de pantalla).

---

## 7. Reglas de negocio y su implementación

| Regla | Implementación principal | Prueba |
|---|---|---|
| RN-01 Un distribuidor por ruta | `ruta.distribuidor_id` + `OperativoServicio.asignar_ruta` | `test_rutas_y_rn01` |
| RN-02 No dar de baja con rutas | `OperativoServicio.cambiar_estado_distribuidor` | `test_rutas_y_rn01` |
| RN-03 Estados válidos y uno por fecha | `CHECK` en SQL + `registrar_entrega` + `UNIQUE` | `test_rn03_rn04_entregas` |
| RN-04 Sin fechas futuras | `registrar_entrega`, `cerrar_dia` y `generar_reporte` | `test_rn03_rn04_entregas` |
| RN-05 Efectividad sobre programadas | `ReporteDiario.porcentaje` + `EntregaDAO.estadisticas_fecha` | `test_rn11_programacion_y_cierre_del_dia` |
| RN-06 Importación todo o nada y rechazos justificados | `BaseDatos.transaccion` + `ImportacionServicio` | `test_listado_multihoja_periodicidad_productos_y_rutas` |
| RN-07 Suscriptor no duplicado; dos direcciones = uno | Índice ciego único + `_unir_direcciones` | `test_rn07_dos_direcciones_es_un_solo_suscriptor` |
| RN-08 Acceso por rol | `PERMISOS`, `AutenticacionServicio.exigir` | `test_rn08_permisos_por_rol` |
| RN-09 Respaldo diario, 7 copias, Drive semanal | `respaldo_automatico`, `_depurar_diarios`, `copiar_a_drive`, `avisos` | `test_rn09_respaldo_diario_unico_y_conserva_siete`, `test_rf07_copia_drive_y_avisos` |
| RN-10 Solo fines logísticos | Cifrado, bitácora sin datos personales y avisos | `test_bitacora_sin_datos_personales` |
| RN-11 Programación por periodicidad y cierre | `PROGRAMADO`, `RUTA_DEL_DIA`, `marcar_entregadas` | `test_rn11_programacion_y_cierre_del_dia` |
| RN-12 Retiro sin borrar | `SuscripcionServicio.registrar_retiro` | `test_rn12_retiro_no_borra_y_sale_de_la_programacion` |

---

## 8. Decisiones de arquitectura

| ID | Decisión | Justificación | Consecuencia |
|---|---|---|---|
| AD-01 | Python + Tkinter + SQLite | Rapidez de desarrollo, instalación sencilla en Windows, sin servidor | Difiere de la Tabla 20 del informe (Java/JavaFX/JDBC): debe alinearse el informe o declararse el cambio |
| AD-02 | Estación local única | Coincide con la sección 6.3.3 del informe: un solo equipo, sin sede ni red | No hay concurrencia multiusuario real |
| AD-03 | Cifrado por campo + índice ciego | Permite buscar y detectar duplicados sin descifrar | El índice revela igualdad, no contenido |
| AD-04 | PBKDF2 en lugar de BCrypt | Disponible en la biblioteca estándar; sin dependencia adicional | Parámetros documentados y ajustables |
| AD-05 | Importación transaccional con rechazos | Cumple RN-06 y RNF-04 | Una fila inválida no obliga a rehacer todo |
| AD-06 | Mapeo de columnas configurable | El listado puede cambiar de encabezados o volver a llegar digital | Se edita `config.json`, no el código |
| AD-07 | Hilo secundario para importar | Mantiene la interfaz respondiendo | Una sola escritura simultánea; sin bloqueos complejos |
| AD-08 | Servicios con permisos | La seguridad no depende de ocultar botones | Código más explícito y testeable |
| AD-09 | Respaldo con cabecera `SRIBAK1` | Distingue el formato y permite validar antes de descifrar | Restauración segura y con doble confirmación |
| AD-10 | Respaldo diario disparado por la propia aplicación (cierre del día, de sesión o de la aplicación) | No depende del programador de tareas ni de que alguien lo recuerde | Si la aplicación no se abre en un día, ese día no hay respaldo (no hubo cambios) |
| AD-11 | Copia a la carpeta sincronizada de Google Drive, no a su API | Sin credenciales en el SRI ni conexión a Internet; la empresa ya eligió Drive | Requiere Google Drive para escritorio instalado |
| AD-12 | Periodicidad como máscara de 7 caracteres | La programación del día es una condición SQL simple | Periodicidades no semanales (p. ej. quincenal) quedan para revisión |
| AD-13 | Migración automática con `ALTER TABLE` | La base y los respaldos anteriores siguen sirviendo | Solo agrega columnas; cambios mayores requerirían un script de migración |

---

## 9. Configuración

`config.json` controla:

- `formatos_admitidos`: extensiones aceptadas.
- `columnas_obligatorias`: campos mínimos de cada hoja (`numero`, `nombre`, `direccion`, `tie`, `pt`, `ruta`).
- `mapeo_columnas`: sinónimos de encabezados por campo lógico (incluye `direccion_fs` y `novedades`, opcionales).
- `importacion.maximo_rechazos_detallados`: límite de rechazos y casos mostrados (500 por defecto).
- `respaldo.carpeta_por_defecto`: carpeta de los respaldos diarios.
- `respaldo.conservar_diarios`: respaldos diarios que se conservan (7).
- `respaldo.carpeta_google_drive`: carpeta sincronizada; se guarda al elegirla la primera vez.
- `respaldo.dias_copia_drive`: días máximos sin copia en Drive antes del aviso (7).

Variables de entorno útiles para pruebas o demostraciones aisladas:

| Variable | Efecto |
|---|---|
| `SRI_CONFIG` | Ruta alternativa de `config.json`. |
| `SRI_DATA_DIR` | Carpeta de la base y la clave. |
| `SRI_BACKUP_DIR` | Carpeta de respaldos. |
| `SRI_EXPORT_DIR` | Carpeta de reportes exportados. |

---

## 10. Estrategia de pruebas

- **Framework:** `unittest` de la biblioteca estándar.
- **Aislamiento:** cada prueba crea una carpeta temporal, una base y una clave propias; nunca usa la base de demostración.
- **Cobertura funcional:** autenticación, permisos, periodicidad, importación multihoja (XLSX y CSV), dos direcciones, códigos de ruta, archivo dañado, novedades de suscripción, programación y cierre del día, reporte, ruta imprimible, consultas, respaldo diario, retención, Google Drive, avisos, restauración y migración.
- **Prueba de humo de interfaz:** inicio de sesión con ambos roles y recorrido de las 9 vistas con acciones reales, sin excepciones; de ahí salen las capturas de `docs/capturas/`.

Comando:

```bat
python -m unittest discover -s pruebas -v
```

Resultado actual: **26 pruebas OK**.

### Rendimiento

- Los lectores XLSX usan modo `read_only`; CSV se procesa por líneas.
- La importación es O(n) con búsquedas indexadas por ruta e índice ciego.
- El reporte usa agregación SQL y no carga todas las entregas en memoria.
- La meta RNF-02 (10 000 registros en menos de 10 s) se verifica con `test_rnf02_10000_registros_en_10_segundos` (≈2,2 s en el equipo de desarrollo; la misma prueba verifica que una novedad se confirma en menos de 2 s). Debe repetirse en el computador de la gerente.

---

## 11. Operación y despliegue

1. Copiar la carpeta `sri_cam_dylan` al equipo destino.
2. Instalar Python y las dependencias (`pip install -r requirements.txt`).
3. Ejecutar `run.bat` o `python main.py`.
4. Verificar el ingreso con un usuario real y cambiar la contraseña inicial.
5. Registrar los distribuidores y cargar el listado de repartidores; revisar con la Gerencia los rechazos y los casos para revisar.
6. Instalar Google Drive para escritorio con la cuenta de la empresa (verificación en dos pasos) y hacer la primera copia desde **Respaldos**.

**Actualización de la aplicación:** reemplace el código conservando `datos/` y `respaldos/`. Las columnas nuevas se agregan solas al abrir la base; aun así, cree un respaldo antes de actualizar.

**Recuperación ante falla:** instale la aplicación, copie el respaldo `.sribak` y la clave `sri.key` original, inicie sesión como Gerencia y use **Restaurar respaldo**.

---

## 12. Riesgos, limitaciones y evolución

| Riesgo / limitación | Impacto | Evolución sugerida |
|---|---|---|
| Una sola estación | No hay concurrencia entre sedes | API central + base cliente-servidor |
| Copia a Drive manual (semanal) | Depende de la Gerencia, aunque se avisa | Subida automática con la API de Google Drive (sección 6.6 del informe) |
| Unión de dos direcciones por nombre | Puede unir homónimos | Se marca para revisión; confirmar con la Gerencia |
| Clave local sin HSM | Compromiso del equipo expone la clave | Almacén de secretos o KMS |
| PBKDF2 en lugar de Argon2/BCrypt | Menor resistencia teórica a GPU | Migrar el formato de hash |
| Exportación PDF vía navegador | Requiere interacción del usuario | Generación directa con WeasyPrint/ReportLab |
| Sin auditoría de lectura de datos | No se registra cada consulta | Eventos de consulta con seudónimos |

La arquitectura por capas permite incorporar una API, un programador de respaldos o una base central sin reescribir la lógica de negocio: bastaría sustituir la capa de datos y exponer los servicios.
