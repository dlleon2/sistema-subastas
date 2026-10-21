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

* **Control de acceso basado en roles:** Sistema integral de 4 roles (Administrador, Vendedor, Comprador y Visitante) con middlewares de autorización y jerarquía de permisos.
* **Aislamiento de Propiedad (Ownership):** Un usuario regular solo puede editar, cerrar o cancelar sus propias subastas (`auction.userId === currentUser.id`); intentar modificar una ajena retorna **403 Forbidden**.
* **Búsqueda Avanzada:** Filtro por **etiquetas (tags)** y búsqueda por palabra clave en título, descripción y etiquetas.
* **Backend Asíncrono:** Construido con FastAPI, tokens JWT / HMAC-SHA256 y documentación OpenAPI automática (/docs).
* **Persistencia NoSQL:** Base de datos MongoDB (colecciones `roles`, `usuarios`, `subastas`, `configuracion` y `counters`), con script SQL de respaldo en `backend/migrations/001_roles_y_permisos.sql`.
* **Pujas Inteligentes:** Validación de incremento mínimo garantizado (`precio_actual + incremento_minimo`).
* **Panel de Vendedor:** Panel para gestionar lotes, con permiso de edición y cancelación solo si el lote no tiene pujas activas.
* **Panel de Administración:** Control total sobre `/api/admin/*`, moderación de subastas, suspensión de usuarios y parámetros globales del sistema.
* **Interfaz en español:** Experiencia de usuario totalmente en español, con cambio de sesión desde el módulo de autenticación estándar (inicio de sesión y registro) y sin elementos de demostración incrustados.
* **Semilla automática:** La base de datos se puebla sola, en segundo plano, al arrancar el servidor si está vacía (usuarios y subastas de prueba operativas).

---

## Matriz de Roles y Permisos (RBAC)

| Funcionalidad | Visitante | Comprador | Vendedor | Administrador |
| :--- | :---: | :---: | :---: | :---: |
| Ver catálogo y detalle de subasta | Sí | Sí | Sí | Sí |
| Iniciar sesión / registrarse | Sí | Sí | Sí | Sí |
| Realizar pujas manuales (con incremento mínimo) | No | Sí | Sí | Sí |
| Guardar / quitar favoritos | No | Sí | Sí | Sí |
| Ver historial personal de pujas | No | Sí | Sí | Sí |
| Publicar nuevas subastas | No | Sí | Sí | Sí |
| Panel de mis subastas | No | Sí | Sí | Sí |
| Editar subasta (solo sin pujas) | No | Sí | Sí | Sí |
| Cancelar subasta (antes del primer incremento) | No | Sí | Sí | Sí |
| Moderar subastas (aprobar, suspender, cerrar, eliminar) | No | No | No | Sí |
| Suspender / reactivar usuarios | No | No | No | Sí |
| Definir parámetros globales (comisión, incremento) | No | No | No | Sí |

---

## Cuentas de Prueba Preconfiguradas

La base de datos se puebla automáticamente con estas cuentas al iniciar la aplicación si está vacía. El inicio de sesión se realiza desde el módulo de autenticación estándar (botón **Iniciar Sesión**).

| Rol | Correo Electrónico | Contraseña | Capacidades Clave |
| :--- | :--- | :--- | :--- |
| **Administrador** | `admin@subastas.com` | `admin123` | Control total, panel administrativo y moderación (aprobar/suspender/eliminar) |
| **Vendedor** | `carlos@subastas.com` | `carlos123` | Publicar y gestionar lotes con etiquetas y fechas |
| **Vendedor** | `lucia@subastas.com` | `lucia123` | Publicar y gestionar lotes con etiquetas y fechas |
| **Comprador** | `ana@subastas.com` | `ana123` | Pujar con incremento mínimo, favoritos y publicar subastas propias |
| **Comprador** | `mateo@subastas.com` | `mateo123` | Pujar con incremento mínimo, favoritos y publicar subastas propias |

---

## Datos Simulados (Seed)

La base de datos MongoDB se puebla automáticamente, en segundo plano, al iniciar la aplicación si está vacía
(1 administrador, 2 vendedores, 2 compradores y 8 subastas con etiquetas y fechas variadas, incluyendo subastas activas para probar las pujas).

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
* **Documentación API:** Disponible en [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Para ejecutar el modo clásico por terminal:
```bash
python main.py --cli
```