-- =====================================================================
-- Documatch - Esquema de la base de datos (SQLite)
--
-- El backend ejecuta este archivo cada vez que inicia (app/db.py), así que
-- todo es idempotente: las tablas e índices usan IF NOT EXISTS y las vistas
-- y triggers se recrean (no guardan datos).
--
-- Una sola tabla guarda los tres tipos de documento:
--   orden_compra (OC) <-- guia_despacho (GD)
--                     <-- factura       (F)
-- Las guías y facturas apuntan a su OC con orden_id (clave foránea a la
-- misma tabla). Una OC puede tener varias guías y varias facturas.
-- =====================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documentos (
    id                 INTEGER PRIMARY KEY,

    -- Archivo subido
    nombre_original    VARCHAR(255) NOT NULL,
    nombre_guardado    VARCHAR(255) NOT NULL UNIQUE,   -- nombre en data/archivos
    tipo_contenido     VARCHAR(100) NOT NULL,
    tamano             INTEGER      NOT NULL CHECK (tamano >= 0),
    hash_archivo       CHAR(64),                       -- SHA-256 del archivo; NULL en los dummies

    -- Clasificación
    tipo               VARCHAR(50)  NOT NULL
                       CHECK (tipo IN ('orden_compra', 'guia_despacho', 'factura', 'desconocido')),
    numero             VARCHAR(50),                    -- NULL si el OCR no lo encontró
    confianza          REAL         NOT NULL CHECK (confianza BETWEEN 0 AND 1),
    puntajes           TEXT         NOT NULL DEFAULT '{}' CHECK (json_valid(puntajes)),
    coincidencias      TEXT         NOT NULL DEFAULT '{}' CHECK (json_valid(coincidencias)),
    texto              TEXT         NOT NULL,

    -- Mercancías: [{"descripcion": ..., "cantidad": ..., "total": ...}]
    items              TEXT         CHECK (items IS NULL OR json_valid(items)),
    cantidad_total     REAL,
    valor_total        REAL,
    neto_documento     REAL,
    valores_coinciden  BOOLEAN      CHECK (valores_coinciden IN (0, 1)),
    -- Cantidades corregidas a mano (guía de despacho leída con poca confianza)
    cantidades_editadas BOOLEAN     NOT NULL DEFAULT 0 CHECK (cantidades_editadas IN (0, 1)),

    -- Enlace de guías y facturas con su orden de compra.
    -- Al borrar la OC, sus guías y facturas quedan sin OC (siguen en el historial).
    orden_id           INTEGER      REFERENCES documentos (id) ON DELETE SET NULL,

    -- Cierre de una OC con despacho parcial
    finalizada         BOOLEAN      NOT NULL DEFAULT 0 CHECK (finalizada IN (0, 1)),
    motivo_cierre      VARCHAR(255),

    dummy              BOOLEAN      NOT NULL DEFAULT 0 CHECK (dummy IN (0, 1)),
    fecha_creacion     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Solo las guías y facturas se enlazan a una OC, y nunca a sí mismas
    CHECK (orden_id IS NULL OR (tipo IN ('guia_despacho', 'factura') AND orden_id <> id)),
    -- Solo una OC se puede finalizar
    CHECK (finalizada = 0 OR tipo = 'orden_compra'),
    -- Solo se corrigen a mano las cantidades de una guía de despacho con confianza menor al 65 %
    -- (el mismo umbral que CONFIANZA_EDICION en app/api/documentos.py)
    CHECK (cantidades_editadas = 0 OR (tipo = 'guia_despacho' AND confianza < 0.65))
);

-- ---------------------------------------------------------------------
-- Validación de duplicados
-- ---------------------------------------------------------------------

-- El mismo archivo no se sube dos veces
CREATE UNIQUE INDEX IF NOT EXISTS ux_documentos_hash
    ON documentos (hash_archivo) WHERE hash_archivo IS NOT NULL;

-- Un número de documento existe una sola vez por tipo (no puede haber dos F-123).
-- Los documentos sin número (el OCR no lo leyó) no se comparan.
CREATE UNIQUE INDEX IF NOT EXISTS ux_documentos_tipo_numero
    ON documentos (tipo, numero) WHERE numero IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_documentos_tipo     ON documentos (tipo);
CREATE INDEX IF NOT EXISTS ix_documentos_orden_id ON documentos (orden_id);

-- ---------------------------------------------------------------------
-- Enlace OC - GD - F: orden_id debe apuntar a una orden de compra
-- (la clave foránea solo asegura que el documento exista).
-- ---------------------------------------------------------------------

DROP TRIGGER IF EXISTS trg_documentos_enlace_insert;
CREATE TRIGGER trg_documentos_enlace_insert
BEFORE INSERT ON documentos
WHEN NEW.orden_id IS NOT NULL
 AND (SELECT tipo FROM documentos WHERE id = NEW.orden_id) IS NOT 'orden_compra'
BEGIN
    SELECT RAISE(ABORT, 'orden_id debe apuntar a una orden de compra');
END;

DROP TRIGGER IF EXISTS trg_documentos_enlace_update;
CREATE TRIGGER trg_documentos_enlace_update
BEFORE UPDATE OF orden_id ON documentos
WHEN NEW.orden_id IS NOT NULL
 AND (SELECT tipo FROM documentos WHERE id = NEW.orden_id) IS NOT 'orden_compra'
BEGIN
    SELECT RAISE(ABORT, 'orden_id debe apuntar a una orden de compra');
END;

-- Una OC con guías o facturas enlazadas no puede cambiar de tipo
DROP TRIGGER IF EXISTS trg_documentos_orden_cambia_tipo;
CREATE TRIGGER trg_documentos_orden_cambia_tipo
BEFORE UPDATE OF tipo ON documentos
WHEN OLD.tipo = 'orden_compra' AND NEW.tipo <> 'orden_compra'
 AND EXISTS (SELECT 1 FROM documentos WHERE orden_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'La orden de compra tiene guías o facturas enlazadas');
END;

-- ---------------------------------------------------------------------
-- Vistas
-- ---------------------------------------------------------------------

-- Código del documento: "OC-123", "G-123", "F-123" (igual que codigo() en el backend)
DROP VIEW IF EXISTS v_documentos;
CREATE VIEW v_documentos AS
SELECT d.*,
       CASE
           WHEN d.numero IS NULL OR d.tipo = 'desconocido' THEN NULL
           WHEN d.numero LIKE p.prefijo || '-%' THEN d.numero
           ELSE p.prefijo || '-' || d.numero
       END AS codigo
FROM documentos d
LEFT JOIN (SELECT 'orden_compra' AS tipo, 'OC' AS prefijo
           UNION ALL SELECT 'guia_despacho', 'G'
           UNION ALL SELECT 'factura', 'F') p ON p.tipo = d.tipo;

-- Cada guía y factura con la OC a la que está enlazada
DROP VIEW IF EXISTS v_enlaces;
CREATE VIEW v_enlaces AS
SELECT oc.id     AS orden_id,
       oc.codigo AS orden,
       d.id      AS documento_id,
       d.tipo,
       d.codigo,
       d.cantidad_total,
       d.valor_total
FROM v_documentos d
JOIN v_documentos oc ON oc.id = d.orden_id;

-- Una fila por OC: lo pedido, lo despachado (guías) y lo facturado
DROP VIEW IF EXISTS v_conciliacion;
CREATE VIEW v_conciliacion AS
SELECT oc.id                 AS orden_id,
       oc.codigo             AS orden,
       oc.cantidad_total     AS pedido,
       (SELECT group_concat(codigo, ', ') FROM v_enlaces
         WHERE orden_id = oc.id AND tipo = 'guia_despacho') AS guias,
       (SELECT sum(cantidad_total) FROM v_enlaces
         WHERE orden_id = oc.id AND tipo = 'guia_despacho') AS despachado,
       (SELECT group_concat(codigo, ', ') FROM v_enlaces
         WHERE orden_id = oc.id AND tipo = 'factura')       AS facturas,
       (SELECT sum(cantidad_total) FROM v_enlaces
         WHERE orden_id = oc.id AND tipo = 'factura')       AS facturado,
       oc.finalizada,
       oc.motivo_cierre
FROM v_documentos oc
WHERE oc.tipo = 'orden_compra';
