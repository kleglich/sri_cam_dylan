# Guion de sustentación

**SRI · Sistema de Respaldo de Información — Distribuciones Cam Dylan S.A.S.** (informe v5.3)

Duración objetivo: **10 a 12 minutos** (8 de exposición y demostración + 3 de preguntas). Ajuste los tiempos según el límite de la asignatura.

---

## 1. Antes de presentar (checklist de 5 minutos)

- [ ] Ejecutar `python -m unittest discover -s pruebas -v` y confirmar **31 pruebas OK**.
- [ ] Reconstruir la demo si se hizo una prueba previa: `python herramientas\preparar_demo.py --reiniciar` (las fechas de la demo son relativas al día en que se prepara).
- [ ] Abrir `run.bat` y verificar el login con `secretaria` / `Sri2026*` y `gerencia` / `Sri2026*`.
- [ ] Tener a mano `datos_ejemplo/listado_repartidores_actualizado.xlsx`.
- [ ] Tener una carpeta de prueba que haga de «Google Drive» si el equipo no tiene Google Drive para escritorio.
- [ ] Cerrar ventanas y notificaciones; tener abiertas las capturas de `docs/capturas/` como respaldo visual.

> **No** ejecute `--reiniciar` durante la sustentación: borra la base actual.

---

## 2. Guion minuto a minuto

| Tiempo | Bloque | Qué decir / hacer |
|---|---|---|
| 0:00–1:00 | Problema | La editorial entrega listados impresos; la única base es un Excel mantenido a mano en un computador personal. |
| 1:00–2:00 | Solución y arquitectura | SRI, 9 RF, 12 RN, capas y seguridad. |
| 2:00–2:30 | Login y avisos | Entrar como Secretaría: aparece el aviso de respaldos en Google Drive. |
| 2:30–4:00 | Listado de repartidores | Importar el listado actualizado: hojas, periodicidad, códigos de ruta, casos para revisar. |
| 4:00–5:00 | Pasar el listado impreso | Registrar un ingreso; mostrar el rechazo por dirección incompleta y el retiro sin borrar. |
| 5:00–6:15 | Lo que reportan los repartidores | Entregas programadas por periodicidad, una novedad y **Cerrar el día**. |
| 6:15–7:00 | Ruta imprimible | Imprimir la ruta de un distribuidor con sus tres secciones. |
| 7:00–8:30 | Gerencia | Reporte sobre entregas programadas y copia a Google Drive. |
| 8:30–9:30 | Pruebas y trazabilidad | Las 31 pruebas y la matriz RF/RN. |
| 9:30–10:00 | Cierre | Logros, limitaciones y evolución. |

---

## 3. Texto sugerido por bloque

### 3.1 Problema (1 min)

> «Cam Dylan opera hoy con tres personas desde la casa de la gerente. La editorial ya no envía archivos: entrega cada día los listados impresos con ingresos, retiros y cambios, y la gerente los pasa a mano a un Excel con una hoja por distribuidor. Ese Excel es la única base de datos de la empresa y está en un computador personal, con copias informales. Si se pierde, habría que reconstruir los suscriptores desde papeles. Además, cuántos periódicos se entregan y a quién depende solo de la experiencia de la gerente.»

### 3.2 Solución y arquitectura (1 min)

> «El SRI carga una vez ese Excel, registra a diario las novedades del listado impreso y las de entrega, conserva el historial en una base local cifrada y hace un respaldo automático cada día, con una copia semanal en Google Drive. Está construido en capas: presentación, servicios, dominio y datos. La presentación nunca ejecuta SQL; los servicios aplican permisos y las doce reglas de negocio; los datos personales se cifran con AES-256-GCM.»

### 3.3 Login y avisos (0,5 min)

- Entrar como **Secretaría**: aparece *«Aún no se ha copiado ningún respaldo a Google Drive»*.
- «El RF-07 pide que una falla del respaldo no pase inadvertida: por eso se avisa al iniciar sesión.»
- Señalar el menú filtrado: no aparecen reportes ni respaldos.

### 3.4 Listado de repartidores (1,5 min)

1. **Importar listado de repartidores** → `listado_repartidores_actualizado.xlsx` → **Importar**.
2. Leer el resumen: «86 leídos = 3 nuevos + 81 actualizados + 2 rechazados. El conteo cuadra (RNF-04).»
3. En la tabla inferior:
   - Rechazos: «una fila sin dirección y otra sin producto marcado».
   - Para revisar: «“(quincenal)” no es una periodicidad conocida; el código AL está en la hoja de Marta pero ya es de Luis; un suscriptor retirado no se reactiva al recargar el Excel».
4. Explicar: «El sistema separa la periodicidad escrita junto al nombre, asocia cada código de ruta a su distribuidor por las iniciales y une en un solo suscriptor a quien recibe en la oficina entre semana y en la casa el fin de semana. Todo es una sola transacción.»

### 3.5 Pasar el listado impreso (1 min)

1. **Pasar el listado impreso** → Ingreso con dirección «Centro» → mensaje: dirección incompleta, consultar a la editorial.
2. Corregir la dirección («Calle 40 # 2-15»), marcar El Tiempo, periodicidad `L-V`, ruta y guardar.
3. Mostrar la lista **Novedades del día** (la que se usa para avisar a los distribuidores) y explicar: «Un retiro no borra: el suscriptor queda inactivo y su historial se conserva (RN-12).»

### 3.6 Lo que reportan los repartidores y cierre (1,25 min)

1. **Lo que reportan los repartidores**: «Aquí están las entregas de hoy según la periodicidad; un suscriptor `S-D` no aparece un martes.»
2. Tocar a un suscriptor → motivo rápido «Ejemplar faltante en el paquete» → botón **Entregado con novedad**. Mostrar el mensaje «Listo…».
3. **Cerrar el día**: «Los distribuidores solo reportan novedades; al cerrar, las demás se dan por entregadas y se genera el respaldo diario automático.»

### 3.7 Ruta imprimible (0,75 min)

- **Rutas** → seleccionar una ruta → **Imprimir ruta del distribuidor**.
- «Reemplaza las hojas corregidas a mano: se genera desde la base, con las secciones de entregas diarias, sábados y domingos y Portafolio, y con el aviso de datos personales.»

### 3.8 Gerencia: reporte y Google Drive (1,5 min)

1. Cerrar sesión y entrar como **Gerencia**.
2. **Reporte diario de entregas** de ayer: «Programadas, efectivas y efectividad = efectivas ÷ programadas (RN-05), por ruta y distribuidor, con la lista de novedades del día. Deja por escrito lo que hoy solo está en la experiencia de la gerente.»
3. **Respaldos**: mostrar el respaldo diario automático y pulsar **Copiar a Google Drive** (elegir la carpeta). «Se copia el archivo ya cifrado; en la nube no se puede leer sin la clave. Se conservan siete respaldos diarios; en el peor caso se pierde un día de registros.»

### 3.9 Pruebas y trazabilidad (1 min)

```text
Ran 31 tests
OK
```

> «Las pruebas usan bases temporales: listado multihoja, periodicidad, dos direcciones, novedades de suscripción, programación y cierre del día, reporte, ruta imprimible, respaldo diario, retención, Google Drive, avisos, restauración y migración de la base anterior. La matriz de `docs/ENTREGABLE.md` relaciona cada RF y RN con su código y su prueba.»

### 3.10 Cierre (0,5 min)

> «El SRI le da a la empresa una base propia, con historial, protegida y respaldada cada día fuera del computador. Limitaciones: opera en un solo equipo, la copia a Drive es semanal y manual (aunque se avisa) y la unión de dos direcciones se basa en el nombre, por eso se marca para revisión.»

---

## 4. Preguntas probables y respuestas

**¿Por qué Python y no Java, como dice el informe?**
> Por rapidez de desarrollo e instalación sencilla en el computador de la gerente. La arquitectura es la del informe (capas, DAO, servicios, estrategia de lectores), así que la presentación o el lenguaje podrían cambiarse sin tocar las reglas. *(Conviene alinear la Tabla 20 del informe con esta decisión.)*

**Si la editorial entrega papel, ¿qué se importa?**
> El Excel de repartidores de la empresa, una vez, para la carga inicial. Las novedades diarias se pasan en la pantalla de novedades de suscripción. Si la editorial vuelve a enviar archivos, el mapeo de columnas es configurable.

**¿Cómo sabe el sistema qué entregas hay cada día?**
> La periodicidad se guarda como siete días (lunes a domingo). Un suscriptor está programado si estaba activo en la fecha y ese día está en su periodicidad.

**¿Qué pasa con quien recibe en la oficina y en la casa?**
> Es un solo suscriptor con dos direcciones (RN-07). Entre semana la entrega va a la oficina; el fin de semana, a la casa y por la ruta que corresponda.

**¿Cómo se protegen los datos personales?**
> Nombre, direcciones y novedades se cifran con AES-256-GCM; los duplicados se detectan con un índice ciego (HMAC); las contraseñas usan PBKDF2; los respaldos, también en Drive, van cifrados; la bitácora no guarda datos personales; la ruta impresa lleva el aviso de la Ley 1581.

**¿Qué pasa si se pierde `sri.key`?**
> No se pueden leer los datos ni los respaldos. Debe guardarse aparte, fuera del computador.

**¿Y si el respaldo diario falla?**
> Queda registrado y, al iniciar la siguiente sesión, aparece un aviso. Lo mismo si pasan más de siete días sin copia en Google Drive.

**¿Cómo saben que funciona?**
> Con 31 pruebas automatizadas y una prueba de humo de la interfaz con ambos roles y las 9 pantallas.

**¿Qué falta?**
> Subida automática a Google Drive por su API, empaquetado `.exe`, validación con el listado real anonimizado en el equipo de la gerente y la observación directa de una jornada.

---

## 5. Plan de contingencia

| Falla | Alternativa |
|---|---|
| La aplicación no abre | `pip install -r requirements.txt`; mostrar capturas y explicar el flujo. |
| Los conteos de la importación no coinciden | El listado ya se importó o la demo cambió: reiniciar la demo antes de la sesión. |
| No hay Google Drive en el equipo | Elegir cualquier carpeta para mostrar la copia; explicar que en la empresa es la carpeta sincronizada. |
| El día ya está cerrado | Registrar la novedad en otra fecha o mostrar el reporte de ayer. |
| Se acaba el tiempo | Saltar la ruta imprimible y pasar a reporte, respaldo y pruebas. |

---

## 6. Frases de cierre

- «La empresa deja de depender de un único Excel en un computador personal.»
- «Lo que hoy está en la memoria de la gerente queda registrado día a día.»
- «Cada día hay un respaldo cifrado, y cada semana una copia fuera de la casa.»
