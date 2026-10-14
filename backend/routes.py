from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional, List, Dict, Any

from backend.models import (
    RolUsuario,
    OfertarRequest,
    PujaRequest,
    CrearSubastaRequest,
    EditarSubastaRequest,
    ModerarSubastaRequest,
    CambiarEstadoUsuarioRequest,
    ConfiguracionGlobalRequest,
    LoginRequest,
    RegisterRequest
)
from backend import database
from backend.auth import get_current_user, require_role, hash_password, verify_password, crear_token

router = APIRouter(prefix="/api", tags=["Subastas & RBAC"])


# ============================================================================
# 1. RUTAS DE AUTENTICACIÓN (VISITANTE / ROLE_GUEST)
# ============================================================================
@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def registrar_usuario(req: RegisterRequest):
    try:
        rol = req.rol if req.rol in [RolUsuario.ROLE_BUYER.value, RolUsuario.ROLE_SELLER.value] else RolUsuario.ROLE_BUYER.value
        pwd_hash = hash_password(req.password)
        nuevo_usuario = database.crear_usuario(
            nombre=req.nombre,
            email=req.email,
            password_hash=pwd_hash,
            rol=rol
        )
        token = crear_token(nuevo_usuario)
        return {
            "mensaje": f"Usuario registrado exitosamente con rol {nuevo_usuario['rol']}.",
            "token": token,
            "usuario": nuevo_usuario
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/login")
def iniciar_sesion(req: LoginRequest):
    user = database.obtener_usuario_por_email(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas (correo no encontrado).")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas (contraseña inválida).")

    if user.get("estado") == "Suspendido":
        raise HTTPException(status_code=403, detail="Tu cuenta está suspendida por un administrador.")

    user_info = {
        "id": user.get("id"),
        "nombre": user.get("nombre"),
        "email": user.get("email"),
        "rol": user.get("rol"),
        "estado": user.get("estado", "Activo")
    }
    token = crear_token(user_info)
    return {
        "mensaje": f"Bienvenido/a {user_info['nombre']}",
        "token": token,
        "usuario": user_info
    }


@router.get("/auth/me")
def obtener_perfil_actual(user: Dict[str, Any] = Depends(get_current_user)):
    return {
        "autenticado": user.get("id") is not None,
        "usuario": user
    }


# ============================================================================
# 2. RUTAS PÚBLICAS (ROLE_GUEST & SUPERIORES)
# ============================================================================
@router.get("/subastas")
def listar_subastas(estado: Optional[str] = Query(None, description="Filtro: activas, cerradas o todas")):
    try:
        return database.obtener_subastas(filtro_estado=estado, solo_aprobadas=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subastas/{subasta_id}")
def obtener_subasta(subasta_id: str):
    subasta = database.obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise HTTPException(status_code=404, detail="Subasta no encontrada")
    return subasta


@router.get("/metricas")
def metricas_globales():
    try:
        return database.metricas_globales()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 3. RUTAS DE COMPRADOR (ROLE_BUYER)
# ============================================================================
@router.post("/subastas/{subasta_id}/pujar")
def realizar_puja(
    subasta_id: str,
    req: PujaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    try:
        subasta_actualizada = database.registrar_oferta(
            subasta_id=subasta_id,
            usuario_nombre=current_user["nombre"],
            monto=req.monto,
            usuario_id=current_user["id"]
        )
        return {
            "mensaje": f"¡Puja de ${req.monto:.2f} registrada exitosamente!",
            "subasta": subasta_actualizada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Compatibilidad con endpoint legacy de pujas
@router.post("/subastas/{subasta_id}/ofertar")
def realizar_oferta_legacy(
    subasta_id: str,
    req: OfertarRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    nombre_postor = current_user.get("nombre") if current_user.get("id") else (req.usuario or "Comprador Anónimo")
    usuario_id = current_user.get("id")
    try:
        subasta_actualizada = database.registrar_oferta(
            subasta_id=subasta_id,
            usuario_nombre=nombre_postor,
            monto=req.monto,
            usuario_id=usuario_id
        )
        return {
            "mensaje": f"Oferta de ${req.monto:.2f} registrada exitosamente por {nombre_postor}.",
            "subasta": subasta_actualizada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subastas/{subasta_id}/favoritos")
def toggle_favoritos(
    subasta_id: str,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    try:
        return database.toggle_favorito(usuario_id=current_user["id"], subasta_id=subasta_id)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mi-cuenta/pujas")
def ver_mis_pujas(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))):
    try:
        return database.obtener_pujas_usuario(usuario_id=current_user["id"], usuario_nombre=current_user["nombre"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mi-cuenta/favoritos")
def ver_mis_favoritos(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))):
    try:
        return database.obtener_favoritos_usuario(usuario_id=current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 4. RUTAS DE VENDEDOR (ROLE_SELLER)
# ============================================================================
@router.get("/panel-vendedor/subastas")
def dashboard_vendedor_subastas(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_SELLER))):
    try:
        # El vendedor ve todas sus subastas (aprobadas, pendientes o cerradas)
        return database.obtener_subastas(filtro_estado=None, solo_aprobadas=False, vendedor_id=current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subastas/nueva")
@router.post("/subastas")
def publicar_nueva_subasta(
    req: CrearSubastaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_SELLER))
):
    try:
        subasta = database.crear_subasta(
            nombre=req.nombre,
            descripcion=req.descripcion,
            categoria=req.categoria,
            precio_inicial=req.precio_inicial,
            duracion_minutos=req.duracion_minutos,
            imagen_url=req.imagen_url,
            vendedor_id=current_user["id"],
            vendedor_nombre=current_user["nombre"],
            incremento_minimo=req.incremento_minimo
        )
        return {
            "mensaje": f"Subasta '{req.nombre}' creada con éxito.",
            "subasta": subasta
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/subastas/{subasta_id}/editar")
def editar_subasta(
    subasta_id: str,
    req: EditarSubastaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_SELLER))
):
    es_admin = current_user.get("rol") == RolUsuario.ROLE_ADMIN.value
    try:
        subasta_editada = database.editar_subasta(
            subasta_id=subasta_id,
            vendedor_id=current_user["id"],
            datos=req.dict(exclude_unset=True),
            es_admin=es_admin
        )
        return {
            "mensaje": "Subasta actualizada exitosamente.",
            "subasta": subasta_editada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subastas/{subasta_id}/cancelar")
def cancelar_subasta(
    subasta_id: str,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_SELLER))
):
    es_admin = current_user.get("rol") == RolUsuario.ROLE_ADMIN.value
    try:
        subasta_cancelada = database.cancelar_subasta_vendedor(
            subasta_id=subasta_id,
            vendedor_id=current_user["id"],
            es_admin=es_admin
        )
        return {
            "mensaje": "Subasta cancelada con éxito.",
            "subasta": subasta_cancelada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subastas/{subasta_id}/cerrar")
def finalizar_subasta(
    subasta_id: str,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_SELLER))
):
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


# ============================================================================
# 5. RUTAS DE ADMINISTRADOR (ROLE_ADMIN) - PREFIJO /admin/*
# ============================================================================
@router.get("/admin/usuarios")
def admin_listar_usuarios(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))):
    try:
        return database.listar_usuarios()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/usuarios/{usuario_id}/estado")
def admin_cambiar_estado_usuario(
    usuario_id: str,
    req: CambiarEstadoUsuarioRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))
):
    try:
        usuario_actualizado = database.cambiar_estado_usuario(usuario_id=usuario_id, nuevo_estado=req.estado)
        return {
            "mensaje": f"Estado del usuario actualizado a '{req.estado}'.",
            "usuario": usuario_actualizado
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/subastas")
def admin_listar_todas_subastas(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))):
    try:
        return database.obtener_subastas(filtro_estado=None, solo_aprobadas=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/subastas/{subasta_id}/moderar")
def admin_moderar_subasta(
    subasta_id: str,
    req: ModerarSubastaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))
):
    try:
        subasta_moderada = database.moderar_subasta_admin(
            subasta_id=subasta_id,
            accion=req.accion,
            motivo=req.motivo
        )
        return {
            "mensaje": f"Acción '{req.accion}' ejecutada en la subasta.",
            "subasta": subasta_moderada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/configuracion")
def admin_obtener_configuracion(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))):
    try:
        return database.obtener_configuracion_global()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/configuracion")
def admin_actualizar_configuracion(
    req: ConfiguracionGlobalRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))
):
    try:
        cfg = database.actualizar_configuracion_global(
            incremento_minimo=req.incremento_minimo,
            comision_porcentaje=req.comision_porcentaje
        )
        return {
            "mensaje": "Parámetros globales actualizados correctamente.",
            "configuracion": cfg
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
