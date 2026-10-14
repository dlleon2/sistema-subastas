from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from backend.models import OfertarRequest, CrearSubastaRequest
from backend import database

router = APIRouter(prefix="/api", tags=["Subastas"])


@router.get("/subastas")
def listar_subastas(estado: Optional[str] = Query(None, description="Filtro: activas, cerradas o todas")):
    try:
        return database.obtener_subastas(filtro_estado=estado)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subastas/{subasta_id}")
def obtener_subasta(subasta_id: str):
    subasta = database.obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise HTTPException(status_code=404, detail="Subasta no encontrada")
    return subasta


@router.post("/subastas/{subasta_id}/ofertar")
def realizar_oferta(subasta_id: str, req: OfertarRequest):
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


@router.post("/subastas/{subasta_id}/cerrar")
def finalizar_subasta(subasta_id: str):
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


@router.post("/subastas")
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


@router.get("/metricas")
def metricas_globales():
    try:
        return database.metricas_globales()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
