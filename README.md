# SubastaHub — Sistema de Subastas

Plataforma fullstack para gestión y participación en subastas en tiempo real, construida con **Python (FastAPI)** en el backend y una interfaz web moderna en el frontend.

---

## Arquitectura del Proyecto

El proyecto sigue una **arquitectura modular de capas (Layered / Three-Tier)**, ideal para mantener un código limpio, mantenible y desacoplado:

```text
sistema-subastas/
│
├── backend/                       # Capa del servidor y lógica del negocio
│   ├── __init__.py
│   ├── app.py                     # Configuración de FastAPI, middlewares y rutas
│   ├── auth.py                    # Hashing PBKDF2, tokens HMAC-SHA256 y RBAC (guardias)
│   ├── database.py                # Conexión MongoDB (NoSQL), colecciones y persistencia
│   ├── models.py                  # Clases de dominio (POO) y esquemas DTO (Pydantic)
│   └── routes.py                  # Endpoints de la API REST (/api/auth, /api/subastas, /api/admin)
│
├── frontend/                      # Capa del cliente (interfaz de usuario)
│   ├── index.html                 # Estructura semántica de la aplicación web
│   ├── styles.css                 # Sistema de diseño, glassmorphism y modo oscuro
│   ├── app.js                     # Cliente JavaScript con actualización en tiempo real
│   └── img/                       # Recursos e imágenes de los productos
│
├── seed.py                        # Seed MongoDB en Python (recomendado)
├── seed.js                        # Seed alternativo para mongosh
├── main.py                        # Punto de entrada unificado para ejecutar la aplicación
├── requirements.txt               # Dependencias del proyecto
└── README.md                      # Documentación del proyecto
```

---

## Características Principales

* **Control de Acceso Basado en Roles (RBAC):** Sistema integral de 4 roles (`ROLE_ADMIN`, `ROLE_SELLER`, `ROLE_BUYER`, `ROLE_GUEST`) con middlewares de autorización y jerarquía de permisos.
* **Aislamiento de Propiedad (Ownership):** Un usuario regular solo puede editar, cerrar o cancelar sus propias subastas (`auction.userId === currentUser.id`); intentar modificar una ajena retorna **403 Forbidden**.
* **Búsqueda Avanzada:** Filtro por **etiquetas (tags)** y búsqueda por palabra clave en título, descripción y etiquetas.
* **Backend Asíncrono:** Construido con FastAPI, tokens JWT / HMAC-SHA256 y documentación OpenAPI automática (/docs).
* **Persistencia NoSQL:** Base de datos MongoDB (colecciones `roles`, `usuarios`, `subastas`, `configuracion` y `counters`), con script SQL de respaldo en `backend/migrations/001_roles_y_permisos.sql`.
* **Pujas Inteligentes:** Validación de incremento mínimo garantizado (`precio_actual + incremento_minimo`).
* **Panel de Vendedor:** Dashboard para gestionar lotes, con permiso de edición y cancelación solo si el lote no tiene pujas activas.
* **Panel de Administración:** Control total sobre `/api/admin/*`, moderación de subastas, suspensión de usuarios y parámetros globales del sistema.
* **Frontend Interactivo:** Simulador de roles 1-Click integrado para probar de forma inmediata los 4 perfiles sin necesidad de logins manuales.

---

## Matriz de Roles y Permisos (RBAC)

| Funcionalidad | Visitante (`ROLE_GUEST`) | Comprador (`ROLE_BUYER`) | Vendedor (`ROLE_SELLER`) | Administrador (`ROLE_ADMIN`) |
| :--- | :---: | :---: | :---: | :---: |
| Ver Catálogo y Detalle de Subasta | ✅ | ✅ | ✅ | ✅ |
| Iniciar Sesión / Registrarse | ✅ | ✅ | ✅ | ✅ |
| Realizar Pujas Manuales (con inc. mín.) | ❌ | ✅ | ✅ | ✅ |
| Guardar / Quitar Favoritos | ❌ | ✅ | ✅ | ✅ |
| Ver Historial Personal de Pujas | ❌ | ✅ | ✅ | ✅ |
| Publicar Nuevas Subastas | ❌ | ❌ | ✅ | ✅ |
| Dashboard de Mis Subastas | ❌ | ❌ | ✅ | ✅ |
| Editar Subasta (Solo sin pujas) | ❌ | ❌ | ✅ | ✅ |
| Cancelar Subasta (Antes de 1er incremento) | ❌ | ❌ | ✅ | ✅ |
| Moderar Subastas (Aprobar, Rechazar, Cerrar) | ❌ | ❌ | ❌ | ✅ |
| Suspender / Reactivar Usuarios | ❌ | ❌ | ❌ | ✅ |
| Definir Parámetros Globales (comisión, inc.) | ❌ | ❌ | ❌ | ✅ |

---

## Cuentas de Prueba Preconfiguradas (1-Click en el Simulador)

| Rol | Correo Electrónico | Contraseña | Capacidades Clave |
| :--- | :--- | :--- | :--- |
| **ROLE_ADMIN** | `admin@subastas.com` | `admin123` | Control total, `/admin/dashboard`, moderación (Aprobar/Suspender/Eliminar) |
| **ROLE_SELLER** | `carlos@subastas.com` | `carlos123` | Publicar subastas con etiquetas/fechas y panel de gestión |
| **ROLE_BUYER** | `ana@subastas.com` | `ana123` | Pujar con incremento mínimo, favoritos y publicar sus propias subastas |
| **ROLE_BUYER** | `mateo@subastas.com` | `mateo123` | Pujar con incremento mínimo, favoritos y publicar sus propias subastas |
| **ROLE_GUEST** | *(No autenticado)* | *(Sin clave)* | Solo lectura y autenticación |

---

## Datos Simulados (Seed)

La base de datos MongoDB se puebla automáticamente al iniciar la aplicación si está vacía
(1 administrador, 3 usuarios y 8 subastas con etiquetas y fechas variadas).

Para forzar una regeneración limpia de los datos de prueba:

```bash
python seed.py        # Script Python (recomendado, hashes de contraseña reales)
```

Alternativamente, con `mongosh`:

```bash
mongosh "mongodb://localhost:27017/sistema_subastas" seed.js
```


---

## Requisitos Previos

* **Python 3.10 o superior**
* **MongoDB Server** (corriendo localmente en `localhost:27017` o configurado vía `MONGO_URI`)
* Gestor de paquetes **pip**

---

## Guía de Ejecución Local

### 1. Clonar el repositorio
```bash
git clone https://github.com/dlleon2/sistema-subastas.git
cd sistema-subastas
```

### 2. Crear y activar el entorno virtual
En Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Iniciar la aplicación
```bash
python main.py
```

* **Interfaz Web:** Abre tu navegador en [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Documentación API (Swagger):** Disponible en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Para ejecutar el modo clásico por terminal:
```bash
python main.py --cli
```