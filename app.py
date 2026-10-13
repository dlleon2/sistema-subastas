from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import os

import database

app = FastAPI(
    title="Sistema de Subastas API",
    description="Backend REST API para la plataforma interactiva de subastas en tiempo real",
    version="2.0.0"
)

# Enable CORS for flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
def startup_event():
    database.init_db()


# Models for request validation
class OfertarRequest(BaseModel):
    usuario: str = Field(..., min_length=1, description="Nombre del participante")
    monto: float = Field(..., gt=0, description="Monto ofrecido")


class CrearSubastaRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del producto")
    descripcion: str = Field(..., min_length=1, description="Descripción detallada")
    categoria: str = Field(default="Tecnología", description="Categoría del producto")
    precio_inicial: float = Field(..., gt=0, description="Precio inicial de partida")
    duracion_minutos: int = Field(default=60, gt=0, description="Duración en minutos")
    imagen_url: Optional[str] = Field(default=None, description="Ruta o URL de la imagen")


# API Routes
@app.get("/api/subastas")
def listar_subastas(estado: Optional[str] = Query(None, description="Filtro: activas, cerradas o todas")):
    try:
        return database.obtener_subastas(filtro_estado=estado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/subastas/{subasta_id}")
def obtener_subasta(subasta_id: int):
    subasta = database.obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise HTTPException(status_code=404, detail="Subasta no encontrada")
    return subasta


@app.post("/api/subastas/{subasta_id}/ofertar")
def realizar_oferta(subasta_id: int, req: OfertarRequest):
    try:
        subasta_actualizada = database.registrar_oferta(
            subasta_id=subasta_id,
            usuario_nombre=req.usuario,
            monto=req.monto
        )
        return {
            "mensaje": f"Oferta de ${req.monto:.2f} registrada exitosamente por {req.usuario}.",
            "subasta": subasta_actualizada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subastas/{subasta_id}/cerrar")
def finalizar_subasta(subasta_id: int):
    try:
        subasta_cerrada = database.cerrar_subasta(subasta_id)
        ganador = subasta_cerrada["ganador_nombre"]
        monto = subasta_cerrada["monto_final"]
        
        detalle = f"Subasta cerrada. Ganador: {ganador} por ${monto:.2f}" if ganador else "Subasta cerrada sin ofertas."
        return {
            "mensaje": detalle,
            "subasta": subasta_cerrada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/subastas")
def nueva_subasta(req: CrearSubastaRequest):
    try:
        subasta = database.crear_subasta(
            nombre=req.nombre,
            descripcion=req.descripcion,
            categoria=req.categoria,
            precio_inicial=req.precio_inicial,
            duracion_minutos=req.duracion_minutos,
            imagen_url=req.imagen_url
        )
        return {
            "mensaje": "Subasta creada con éxito.",
            "subasta": subasta
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/metricas")
def metricas_globales():
    conn = database.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as total_subastas FROM subastas;")
    total_subastas = cursor.fetchone()["total_subastas"]

    cursor.execute("SELECT COUNT(*) as activas FROM subastas WHERE abierta = 1;")
    activas = cursor.fetchone()["activas"]

    cursor.execute("SELECT COUNT(*) as total_ofertas, COALESCE(SUM(monto), 0) as volumen FROM ofertas;")
    ofertas_row = cursor.fetchone()
    conn.close()

    return {
        "total_subastas": total_subastas,
        "subastas_activas": activas,
        "total_ofertas": ofertas_row["total_ofertas"],
        "volumen_total": round(ofertas_row["volumen"], 2)
    }


# Static Files and UI Route
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def servir_frontend():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"mensaje": "Backend API activo. Por favor crea static/index.html"}
