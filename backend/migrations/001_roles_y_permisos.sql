-- ============================================================================
-- MIGRACIÓN RBAC: CONTROL DE ACCESO BASADO EN ROLES PARA EL SISTEMA DE SUBASTAS
-- ============================================================================

-- 1. Tabla de Catálogo de Roles
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(50) NOT NULL UNIQUE,       -- ROLE_ADMIN, ROLE_SELLER, ROLE_BUYER, ROLE_GUEST
    descripcion VARCHAR(255) NOT NULL,
    nivel INTEGER NOT NULL DEFAULT 0,         -- 0: Guest, 1: Buyer, 2: Seller, 3: Admin
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de Usuarios
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre VARCHAR(120) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    estado VARCHAR(20) DEFAULT 'Activo',      -- Activo, Suspendido
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tabla Relacional de Asignación: usuario_rol (Muchos a Muchos / Rol Principal)
CREATE TABLE IF NOT EXISTS usuario_rol (
    usuario_id INTEGER NOT NULL,
    rol_id INTEGER NOT NULL,
    asignado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, rol_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (rol_id) REFERENCES roles(id) ON DELETE CASCADE
);

-- 4. Tabla de Favoritos / Seguimiento (Comprador)
CREATE TABLE IF NOT EXISTS favoritos (
    usuario_id INTEGER NOT NULL,
    subasta_id INTEGER NOT NULL,
    agregado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (usuario_id, subasta_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (subasta_id) REFERENCES subastas(id) ON DELETE CASCADE
);

-- 5. Tabla de Parámetros Globales del Sistema (Administrador)
CREATE TABLE IF NOT EXISTS configuracion_global (
    clave VARCHAR(50) PRIMARY KEY,
    valor_numerico REAL,
    valor_texto VARCHAR(255),
    actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INSERCIÓN DE DATOS SEMILLA (ROLES Y CONFIGURACIÓN)
-- ============================================================================
INSERT OR IGNORE INTO roles (id, nombre, descripcion, nivel) VALUES
(1, 'ROLE_GUEST', 'Visitante sin autenticar (lectura de catálogo y detalle)', 0),
(2, 'ROLE_BUYER', 'Comprador (puja manual superior a puja actual + incremento, favoritos)', 1),
(3, 'ROLE_SELLER', 'Vendedor (publicación, edición sin pujas y cancelación antes de incremento)', 2),
(4, 'ROLE_ADMIN', 'Administrador (control total /admin/*, moderación, estados y configuración)', 3);

INSERT OR IGNORE INTO configuracion_global (clave, valor_numerico, valor_texto) VALUES
('incremento_minimo', 10.0, 'Incremento mínimo global por defecto'),
('comision_porcentaje', 5.0, 'Comisión porcentual por venta de subasta');
