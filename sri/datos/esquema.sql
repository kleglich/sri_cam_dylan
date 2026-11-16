-- Esquema de la base de datos local SQLite (Tabla 19 del informe v5.3).
-- Las bases creadas con versiones anteriores se actualizan en BaseDatos._migrar().
-- Los datos personales de los suscriptores se guardan cifrados; el índice ciego
-- permite detectar duplicados sin descifrar (RNF-01).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS usuario (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    rol             TEXT NOT NULL CHECK (rol IN ('Secretaria', 'Gerencia')),
    contrasena_hash TEXT NOT NULL,
    activo          INTEGER NOT NULL DEFAULT 1,
    creado_en       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS distribuidor (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL COLLATE NOCASE,
    telefono   TEXT NOT NULL,
    activo     INTEGER NOT NULL DEFAULT 1,
    creado_en  TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_distribuidor_nombre ON distribuidor (nombre);

CREATE TABLE IF NOT EXISTS ruta (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    zona              TEXT NOT NULL,
    zona_normalizada  TEXT NOT NULL UNIQUE,
    distribuidor_id   INTEGER REFERENCES distribuidor (id),
    creado_en         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ruta_distribuidor ON ruta (distribuidor_id);

CREATE TABLE IF NOT EXISTS archivo_importacion (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_archivo     TEXT NOT NULL,
    fecha_carga        TEXT NOT NULL,
    total_leidos       INTEGER NOT NULL DEFAULT 0,
    total_importados   INTEGER NOT NULL DEFAULT 0,
    total_actualizados INTEGER NOT NULL DEFAULT 0,
    total_rechazados   INTEGER NOT NULL DEFAULT 0,
    usuario_id         INTEGER NOT NULL REFERENCES usuario (id)
);

CREATE TABLE IF NOT EXISTS suscriptor (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_cifrado     TEXT NOT NULL,
    direccion_cifrada  TEXT NOT NULL,
    novedades_cifrada  TEXT NOT NULL DEFAULT '',
    indice_busqueda    TEXT NOT NULL,
    ruta_id            INTEGER NOT NULL REFERENCES ruta (id),
    archivo_id         INTEGER REFERENCES archivo_importacion (id),
    creado_en          TEXT NOT NULL,
    actualizado_en     TEXT NOT NULL,
    direccion_fs_cifrada TEXT NOT NULL DEFAULT '',
    productos          TEXT NOT NULL DEFAULT 'TIE',
    periodicidad       TEXT NOT NULL DEFAULT '1111111',
    estado             TEXT NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'RETIRADO')),
    fecha_ingreso      TEXT,
    fecha_retiro       TEXT,
    indice_nombre      TEXT NOT NULL DEFAULT '',
    numero             INTEGER,
    ruta_fs_id         INTEGER REFERENCES ruta (id)
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_suscriptor_indice ON suscriptor (indice_busqueda);
CREATE INDEX IF NOT EXISTS ix_suscriptor_ruta ON suscriptor (ruta_id);
CREATE INDEX IF NOT EXISTS ix_suscriptor_nombre ON suscriptor (indice_nombre);

-- Novedades de suscripción tomadas de los listados impresos (RF-09, RN-12).
CREATE TABLE IF NOT EXISTS novedad_suscripcion (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha          TEXT NOT NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('INGRESO', 'RETIRO', 'CAMBIO')),
    detalle        TEXT NOT NULL DEFAULT '',
    suscriptor_id  INTEGER NOT NULL REFERENCES suscriptor (id),
    usuario_id     INTEGER NOT NULL REFERENCES usuario (id),
    registrado_en  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_novedad_fecha ON novedad_suscripcion (fecha);

CREATE TABLE IF NOT EXISTS entrega (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha          TEXT NOT NULL,
    suscriptor_id  INTEGER NOT NULL REFERENCES suscriptor (id) ON DELETE CASCADE,
    estado         TEXT NOT NULL CHECK (estado IN ('PENDIENTE', 'ENTREGADA', 'NO ENTREGADA', 'CON NOVEDAD')),
    novedad        TEXT NOT NULL DEFAULT '',
    registrado_por INTEGER REFERENCES usuario (id),
    actualizado_en TEXT NOT NULL,
    UNIQUE (suscriptor_id, fecha)
);
CREATE INDEX IF NOT EXISTS ix_entrega_fecha ON entrega (fecha);

CREATE TABLE IF NOT EXISTS reporte_diario (
    fecha                   TEXT PRIMARY KEY,
    total_entregas          INTEGER NOT NULL,
    entregas_efectivas      INTEGER NOT NULL,
    porcentaje_efectividad  REAL,
    usuario_id              INTEGER NOT NULL REFERENCES usuario (id),
    generado_en             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS respaldo (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha       TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    usuario_id  INTEGER NOT NULL REFERENCES usuario (id),
    tipo        TEXT NOT NULL DEFAULT 'MANUAL' CHECK (tipo IN ('DIARIO', 'MANUAL', 'DRIVE'))
);

CREATE TABLE IF NOT EXISTS evento (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha      TEXT NOT NULL,
    usuario_id INTEGER REFERENCES usuario (id),
    tipo       TEXT NOT NULL,
    detalle    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evento_fecha ON evento (fecha);
