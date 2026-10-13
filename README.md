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
│   ├── database.py                # Conexión SQLite, esquemas y persistencia
│   ├── models.py                  # Clases de dominio (POO) y esquemas DTO (Pydantic)
│   └── routes.py                  # Endpoints de la API REST (/api/subastas, /api/metricas)
│
├── frontend/                      # Capa del cliente (interfaz de usuario)
│   ├── index.html                 # Estructura semántica de la aplicación web
│   ├── styles.css                 # Sistema de diseño, glassmorphism y modo oscuro
│   ├── app.js                     # Cliente JavaScript con actualización en tiempo real
│   └── img/                       # Recursos e imágenes de los productos
│
├── main.py                        # Punto de entrada unificado para ejecutar la aplicación
├── requirements.txt               # Dependencias del proyecto
└── README.md                      # Documentación del proyecto
```

---

## Características Principales

* **Backend Asíncrono:** Construido con FastAPI, con validación de esquemas y documentación OpenAPI automática.
* **Persistencia Relacional:** Base de datos SQLite integrada, manteniendo el histórico de lotes, participantes y ofertas.
* **Frontend:** Interfaz web sin dependencias externas pesadas, con actualización automática de estado.
* **Múltiples Lotes:** Soporte para crear y subastar productos en diversas categorías con imágenes y descripciones.
* **Pujas Interactivas:** Validaciones para ofertas mayores al precio actual, pujas rápidas e historial de postores.
* **Cierre y Adjudicación:** Declaración formal del ganador al culminar una subasta.
* **Modo Consola:** Mantiene compatibilidad con el modo CLI clásico ejecutando `python main.py --cli`.

---

## Requisitos Previos

* **Python 3.10 o superior**
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