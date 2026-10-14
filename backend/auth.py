import os
import hmac
import hashlib
import json
import base64
import time
from typing import Optional, Dict, Any, List
from fastapi import Header, HTTPException, status, Depends
from backend.models import RolUsuario, NIVEL_ROLES

# Clave secreta para firma de tokens (configurable mediante variable de entorno)
SECRET_KEY = os.getenv("SECRET_KEY", "subastahub_jwt_secret_key_super_segura_2026")
TOKEN_EXPIRY_SECONDS = 86400 * 7  # 7 días


def hash_password(password: str) -> str:
    """Genera un hash seguro PBKDF2-HMAC-SHA256 con salt aleatorio."""
    salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${dk}"


def verify_password(password: str, hashed: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    try:
        salt, dk = hashed.split('$')
        computed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return hmac.compare_digest(dk, computed)
    except Exception:
        return False


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')


def _b64url_decode(s: str) -> bytes:
    padding = '=' * (4 - len(s) % 4) if len(s) % 4 != 0 else ''
    return base64.urlsafe_b64decode(s + padding)


def crear_token(usuario: Dict[str, Any]) -> str:
    """Crea un token firmado HMAC-SHA256 con payload del usuario y expiración."""
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(usuario["id"]),
        "nombre": usuario.get("nombre", ""),
        "email": usuario.get("email", ""),
        "rol": usuario.get("rol", RolUsuario.ROLE_GUEST.value),
        "estado": usuario.get("estado", "Activo"),
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
    }

    header_b64 = _b64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = _b64url_encode(json.dumps(payload).encode('utf-8'))
    mensaje = f"{header_b64}.{payload_b64}".encode('utf-8')

    firma = hmac.new(SECRET_KEY.encode('utf-8'), mensaje, hashlib.sha256).digest()
    firma_b64 = _b64url_encode(firma)

    return f"{header_b64}.{payload_b64}.{firma_b64}"


def verificar_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica la firma y la fecha de expiración del token."""
    try:
        partes = token.strip().split('.')
        if len(partes) != 3:
            return None
        header_b64, payload_b64, firma_b64 = partes

        mensaje = f"{header_b64}.{payload_b64}".encode('utf-8')
        firma_esperada = hmac.new(SECRET_KEY.encode('utf-8'), mensaje, hashlib.sha256).digest()
        firma_recibida = _b64url_decode(firma_b64)

        if not hmac.compare_digest(firma_esperada, firma_recibida):
            return None

        payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))
        if payload.get("exp", 0) < int(time.time()):
            return None  # Token expirado

        return payload
    except Exception:
        return None


def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")
) -> Dict[str, Any]:
    """
    Middleware/dependencia FastAPI para extraer el usuario actual.
    Si no hay token o es inválido, retorna el rol por defecto ROLE_GUEST.
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_auth_token:
        token = x_auth_token.strip()

    if not token:
        return {
            "id": None,
            "nombre": "Visitante",
            "email": None,
            "rol": RolUsuario.ROLE_GUEST.value,
            "estado": "Activo"
        }

    payload = verificar_token(token)
    if not payload:
        return {
            "id": None,
            "nombre": "Visitante",
            "email": None,
            "rol": RolUsuario.ROLE_GUEST.value,
            "estado": "Activo"
        }

    from backend import database
    user = database.obtener_usuario_por_id(payload.get("sub"))
    if not user:
        return {
            "id": None,
            "nombre": "Visitante",
            "email": None,
            "rol": RolUsuario.ROLE_GUEST.value,
            "estado": "Activo"
        }

    if user.get("estado") == "Suspendido":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu cuenta ha sido suspendida. Comunícate con un administrador."
        )

    return user


def require_role(rol_minimo: RolUsuario):
    """
    Verificador de control de acceso jerárquico basado en roles (RBAC).
    Permite el acceso si el rol del usuario es igual o superior en la jerarquía:
    ROLE_ADMIN (3) >= ROLE_SELLER (2) >= ROLE_BUYER (1) >= ROLE_GUEST (0).
    """
    def dependency(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("rol", RolUsuario.ROLE_GUEST.value)
        nivel_usuario = NIVEL_ROLES.get(user_role, 0)
        nivel_requerido = NIVEL_ROLES.get(rol_minimo, 0)

        # Si requiere autenticación y es visitante
        if nivel_requerido > 0 and (current_user.get("id") is None or user_role == RolUsuario.ROLE_GUEST.value):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Autenticación requerida. Debes iniciar sesión con rol {rol_minimo.value} o superior."
            )

        if nivel_usuario < nivel_requerido:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado. Permisos insuficientes (requiere {rol_minimo.value})."
            )

        return current_user

    return dependency
