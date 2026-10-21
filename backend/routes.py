from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import Optional, List, Dict, Any

from backend.models import (
    RolUsuario,
    AuctionStatus,
    OfertarRequest,
    PujaRequest,
    CrearSubastaRequest,
    EditarSubastaRequest,
    ModerarSubastaRequest,
    AdminAuctionStatusRequest,
    CambiarEstadoUsuarioRequest,
    ConfiguracionGlobalRequest,
    LoginRequest,
    RegisterRequest
)
from backend import database
from backend.auth import get_current_user, require_role, hash_password, verify_password, crear_token

router = APIRouter(prefix="/api", tags=["Subastas & RBAC"])


# ============================================================================
# 1. AUTENTICACIÓN (LOGIN, REGISTRO Y PERFIL)
# ============================================================================
@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def registrar_usuario(req: RegisterRequest):
    try:
        nombre = req.nombre or req.name or "Usuario"
        rol = req.rol if req.rol in [r.value for r in RolUsuario] else RolUsuario.ROLE_BUYER.value
        pwd_hash = hash_password(req.password)
        nuevo_usuario = database.crear_usuario(
            nombre=nombre,
            email=req.email,
            password_hash=pwd_hash,
            rol=rol
        )
        token = crear_token(nuevo_usuario)
        return {
            "mensaje": f"Usuario registrado exitosamente. Ahora puedes proponer y participar en subastas.",
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

    if user.get("estado") in ["Suspendido", "Suspended"]:
        raise HTTPException(status_code=403, detail="Tu cuenta está suspendida por un administrador.")

    user_info = {
        "id": user.get("id"),
        "nombre": user.get("nombre") or user.get("name"),
        "name": user.get("name") or user.get("nombre"),
        "email": user.get("email"),
        "rol": user.get("rol") or user.get("role"),
        "role": user.get("role") or user.get("rol"),
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
# 2. CATÁLOGO PÚBLICO: FILTRO POR TAGS, PALABRAS CLAVE Y ESTADOS
# ============================================================================
@router.get("/subastas")
def listar_subastas(
    tag: Optional[str] = Query(None, description="Filtrar por etiqueta (ej. libros, arte, tecnologia)"),
    search: Optional[str] = Query(None, description="Búsqueda por palabra clave en título, descripción o tags"),
    status: Optional[str] = Query(None, description="Filtro de estado: PROGRAMMED, ACTIVE, FINISHED, CANCELLED"),
    estado: Optional[str] = Query(None, description="Alias: activas, cerradas o todas")
):
    try:
        filtro = status or estado
        return database.obtener_subastas(
            filtro_estado=filtro,
            tag=tag,
            search=search,
            solo_aprobadas=True
        )
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
# 3. CREACIÓN Y AISLAMIENTO DE PROPIEDAD (OWNERSHIP)
# ============================================================================
@router.post("/subastas", status_code=status.HTTP_201_CREATED)
@router.post("/subastas/nueva", status_code=status.HTTP_201_CREATED)
def crear_nueva_subasta(
    req: CrearSubastaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    """Cualquier usuario registrado puede publicar y proponer sus propias subastas."""
    try:
        title = req.title or req.nombre
        description = req.description or req.descripcion or ""
        starting_price = req.startingPrice or req.precio_inicial

        subasta = database.crear_subasta(
            title=title,
            description=description,
            starting_price=starting_price,
            start_date=req.startDate,
            end_date=req.endDate,
            tags=req.tags,
            duracion_minutos=req.duracion_minutos or 60,
            image_url=req.imageUrl or req.imagen_url,
            category=req.categoria or "General",
            seller_id=current_user["id"],
            seller_name=current_user["nombre"],
            incremento_minimo=req.incremento_minimo
        )
        return {
            "mensaje": f"Subasta '{title}' creada con éxito.",
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
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    """
    Aislamiento de propiedad:
    Un usuario regular SOLO puede editar las subastas donde auction.userId === currentUser.id.
    Si intenta modificar una subasta ajena, retorna 403 Forbidden.
    """
    try:
        subasta_editada = database.editar_subasta(
            subasta_id=subasta_id,
            current_user=current_user,
            datos=req.dict(exclude_unset=True)
        )
        return {
            "mensaje": "Subasta actualizada exitosamente.",
            "subasta": subasta_editada
        }
    except PermissionError as pe:
        # Aislamiento de propiedad estricto 403
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/subastas/{subasta_id}/cancelar")
def cancelar_subasta(
    subasta_id: str,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    """
    Aislamiento de propiedad:
    Un usuario regular SOLO puede cancelar las subastas donde auction.userId === currentUser.id.
    Si intenta cancelar una subasta ajena, retorna 403 Forbidden.
    """
    try:
        subasta_cancelada = database.cancelar_subasta(
            subasta_id=subasta_id,
            current_user=current_user
        )
        return {
            "mensaje": "Subasta cancelada con éxito.",
            "subasta": subasta_cancelada
        }
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subastas/{subasta_id}/cerrar")
def cerrar_subasta(
    subasta_id: str,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    """
    Cierra formalmente la subasta y adjudica al mayor postor.
    Aislamiento de propiedad: solo el dueño (o un admin) puede cerrarla. De lo contrario 403.
    """
    try:
        subasta_cerrada = database.cerrar_subasta(
            subasta_id=subasta_id,
            current_user=current_user
        )
        return {
            "mensaje": "Subasta cerrada con éxito.",
            "subasta": subasta_cerrada
        }
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 4. PUJAS Y SEGUIMIENTO (FAVORITOS Y MI CUENTA)
# ============================================================================
@router.post("/subastas/{subasta_id}/pujar")
def realizar_puja(
    subasta_id: str,
    req: PujaRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))
):
    monto = req.monto if req.monto is not None else req.amount
    if monto is None or monto <= 0:
        raise HTTPException(status_code=400, detail="Monto de puja no especificado o inválido.")
    try:
        subasta_actualizada = database.registrar_oferta(
            subasta_id=subasta_id,
            usuario_nombre=current_user["nombre"],
            monto=monto,
            usuario_id=current_user["id"]
        )
        return {
            "mensaje": f"¡Puja de ${monto:.2f} registrada exitosamente!",
            "subasta": subasta_actualizada
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subastas/{subasta_id}/ofertar")
def realizar_oferta_legacy(
    subasta_id: str,
    req: OfertarRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    nombre = current_user.get("nombre") if current_user.get("id") else (getattr(req, 'usuario', None) or "Participante")
    monto = req.monto if req.monto is not None else req.amount
    try:
        subasta_actualizada = database.registrar_oferta(
            subasta_id=subasta_id,
            usuario_nombre=nombre,
            monto=monto,
            usuario_id=current_user.get("id")
        )
        return {
            "mensaje": f"Oferta de ${monto:.2f} registrada exitosamente por {nombre}.",
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


@router.get("/panel-vendedor/subastas")
def dashboard_vendedor_subastas(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_BUYER))):
    try:
        return database.obtener_subastas(filtro_estado=None, solo_aprobadas=False, seller_id=current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 5. DASHBOARD ADMINISTRATIVO (/admin/dashboard Y ACCIONES)
# ============================================================================
@router.get("/admin/dashboard")
def admin_dashboard_data(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))):
    """Endpoint del Dashboard Administrativo con métricas generales y tabla de todas las subastas."""
    try:
        return database.obtener_dashboard_admin()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/subastas/{subasta_id}/moderar")
@router.put("/admin/subastas/{subasta_id}/estado")
def admin_moderar_subasta(
    subasta_id: str,
    req: AdminAuctionStatusRequest,
    current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))
):
    """Acciones de moderación: Aprobar, Suspender, Finalizar/Cerrar o Eliminar."""
    try:
        accion = req.accion_efectiva()
        resultado = database.moderar_subasta_admin(
            subasta_id=subasta_id,
            nuevo_estado=accion,
            motivo=req.motivo
        )
        return {
            "mensaje": f"Estado de la subasta modificado a '{accion}'.",
            "resultado": resultado
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/subastas")
def admin_listar_subastas(current_user: Dict[str, Any] = Depends(require_role(RolUsuario.ROLE_ADMIN))):
    """Vista global: TODAS las subastas creadas por cualquier usuario (solo administradores)."""
    try:
        return database.obtener_subastas(filtro_estado=None, solo_aprobadas=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
