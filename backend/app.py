import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend import database
from backend.routes import router

app = FastAPI(
    title="Sistema de Subastas API",
    description="Backend REST API para la plataforma interactiva de subastas en tiempo real",
    version="2.1.0"
)

# Enable CORS for flexible integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Startup: siembra automática y silenciosa si las colecciones están vacías
@app.on_event("startup")
def startup_event():
    try:
        database.init_db()
    except Exception as exc:  # no bloquear el arranque si MongoDB no está disponible
        print(f"[Semilla automática] No se pudo inicializar MongoDB: {exc}")


# Include API Routers
app.include_router(router)

# Mount Frontend static assets
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
@app.get("/admin/dashboard")
def servir_frontend():
    index_file = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"mensaje": "Backend API activo. Visita /docs para la documentación interactiva."}

