from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from enum import Enum


# ============================================================================
# DEFINICIÓN DE ROLES DEL SISTEMA (RBAC)
# ============================================================================
class RolUsuario(str, Enum):
    ROLE_ADMIN = "ROLE_ADMIN"    # Administrador: control total
    ROLE_SELLER = "ROLE_SELLER"  # Vendedor: publica y gestiona sus subastas
    ROLE_BUYER = "ROLE_BUYER"    # Comprador: puja y gestiona favoritos
    ROLE_GUEST = "ROLE_GUEST"    # Visitante: solo lectura y autenticación


NIVEL_ROLES = {
    RolUsuario.ROLE_GUEST: 0,
    RolUsuario.ROLE_BUYER: 1,
    RolUsuario.ROLE_SELLER: 2,
    RolUsuario.ROLE_ADMIN: 3
}


# ============================================================================
# CLASES DE DOMINIO (POO CON JERARQUÍA DE ROLES)
# ============================================================================
class UsuarioBase:
    """Clase base de dominio para todos los usuarios del sistema."""
    def __init__(self, nombre: str, email: Optional[str] = None, rol: RolUsuario = RolUsuario.ROLE_GUEST, estado: str = "Activo", id: Optional[int] = None):
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        self.id = id
        self.nombre = nombre
        self.email = email
        self.rol = rol
        self.estado = estado

    @property
    def nivel(self) -> int:
        return NIVEL_ROLES.get(self.rol, 0)

    def tiene_permiso(self, rol_requerido: RolUsuario) -> bool:
        return self.nivel >= NIVEL_ROLES.get(rol_requerido, 0)

    def __str__(self):
        return f"{self.nombre} [{self.rol.value}] ({self.estado})"


class Administrador(UsuarioBase):
    """Rol ROLE_ADMIN: Acceso total, moderación de subastas y control de usuarios."""
    def __init__(self, nombre: str, email: Optional[str] = None, id: Optional[int] = None):
        super().__init__(nombre=nombre, email=email, rol=RolUsuario.ROLE_ADMIN, id=id)

    def suspender_usuario(self, usuario: UsuarioBase):
        usuario.estado = "Suspendido"

    def reactivar_usuario(self, usuario: UsuarioBase):
        usuario.estado = "Activo"


class Vendedor(UsuarioBase):
    """Rol ROLE_SELLER: Publica lotes, edita (sin pujas) y cancela (antes de ofertas)."""
    def __init__(self, nombre: str, email: Optional[str] = None, id: Optional[int] = None):
        super().__init__(nombre=nombre, email=email, rol=RolUsuario.ROLE_SELLER, id=id)

    def crear_subasta(self, producto: "Producto", duracion_minutos: int = 60) -> "Subasta":
        return Subasta(producto=producto, duracion_minutos=duracion_minutos, subastador=self)


class Comprador(UsuarioBase):
    """Rol ROLE_BUYER: Explora subastas, propone pujas manuales y gestiona favoritos."""
    def __init__(self, nombre: str, email: Optional[str] = None, id: Optional[int] = None):
        super().__init__(nombre=nombre, email=email, rol=RolUsuario.ROLE_BUYER, id=id)

    def pujar(self, subasta: "Subasta", monto: float):
        return subasta.registrar_oferta(self, monto)


class Visitante(UsuarioBase):
    """Rol ROLE_GUEST: Visitante no autenticado (solo lectura de catálogo y detalle)."""
    def __init__(self):
        super().__init__(nombre="Visitante", rol=RolUsuario.ROLE_GUEST)


# Alias compatibles con implementaciones anteriores y CLI
Usuario = UsuarioBase
Subastador = Vendedor
Postor = Comprador


# ============================================================================
# CLASES DE PRODUCTO Y SUBASTA (POO)
# ============================================================================
class Producto:
    """Representa un artículo que será subastado."""
    def __init__(self, nombre: str, descripcion: str, precio_inicial: float, categoria: str = "Tecnología", imagen_url: str = None):
        if not nombre.strip():
            raise ValueError("El nombre no puede estar vacío.")

        if precio_inicial <= 0:
            raise ValueError("El precio debe ser mayor que cero.")

        self.nombre = nombre
        self.descripcion = descripcion
        self.categoria = categoria
        self.precio_inicial = float(precio_inicial)
        self.imagen_url = imagen_url or "/static/img/laptop.jpg"

    def __str__(self):
        return f"{self.nombre} - {self.descripcion} (Precio inicial: ${self.precio_inicial:.2f})"


class Subasta:
    """Gestiona el ciclo de vida de una subasta y sus ofertas."""
    def __init__(self, producto: Producto, duracion_minutos: int = 60, subastador: Optional[Vendedor] = None, incremento_minimo: float = 10.0):
        self.producto = producto
        self.duracion_minutos = duracion_minutos
        self.subastador = subastador
        self.incremento_minimo = incremento_minimo
        self.ofertas = []
        self.abierta = True
        self.estado_moderacion = "Aprobada"  # Aprobada, Pendiente, Rechazada, Cancelada
        self.ganador = None

    def precio_actual(self) -> float:
        if self.ofertas:
            return self.ofertas[-1]["monto"]
        return self.producto.precio_inicial

    def mayor_postor(self) -> Optional[str]:
        if self.ofertas:
            return self.ofertas[-1]["usuario"].nombre if hasattr(self.ofertas[-1]["usuario"], "nombre") else self.ofertas[-1]["usuario"]
        return None

    def registrar_oferta(self, usuario: UsuarioBase, monto: float):
        if not self.abierta:
            raise ValueError("La subasta está cerrada.")

        if self.estado_moderacion != "Aprobada":
            raise ValueError(f"La subasta no está disponible para pujas (Estado: {self.estado_moderacion}).")

        min_requerido = self.precio_actual() + self.incremento_minimo
        if monto < min_requerido:
            raise ValueError(
                f"La puja debe ser de al menos ${min_requerido:.2f} (Precio actual: ${self.precio_actual():.2f} + incremento mínimo de ${self.incremento_minimo:.2f})."
            )

        self.ofertas.append({
            "usuario": usuario,
            "monto": monto
        })
        return self.ofertas[-1]

    def cerrar(self):
        self.abierta = False
        if self.ofertas:
            self.ganador = self.ofertas[-1]

    def mostrar_ofertas(self):
        if not self.ofertas:
            print("Todavía no hay ofertas.")
            return

        for oferta in self.ofertas:
            user_str = oferta['usuario'].nombre if hasattr(oferta['usuario'], 'nombre') else oferta['usuario']
            print(f"{user_str}: ${oferta['monto']:.2f}")


# ============================================================================
# ESQUEMAS DTO (DATA TRANSFER OBJECTS / PYDANTIC)
# ============================================================================
class LoginRequest(BaseModel):
    email: str = Field(..., description="Correo electrónico registrado")
    password: str = Field(..., min_length=4, description="Contraseña de usuario")


class RegisterRequest(BaseModel):
    nombre: str = Field(..., min_length=2, description="Nombre completo o seudónimo")
    email: str = Field(..., description="Correo electrónico único")
    password: str = Field(..., min_length=4, description="Contraseña de acceso")
    rol: Optional[str] = Field(default="ROLE_BUYER", description="Rol inicial: ROLE_BUYER o ROLE_SELLER")


class PujaRequest(BaseModel):
    monto: float = Field(..., gt=0, description="Monto ofrecido en USD")


# Compatibilidad con endpoint legacy
class OfertarRequest(BaseModel):
    usuario: Optional[str] = Field(default=None, description="Nombre del participante (opcional si autenticado)")
    monto: float = Field(..., gt=0, description="Monto ofrecido en USD")


class CrearSubastaRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del producto")
    descripcion: str = Field(..., min_length=1, description="Descripción detallada")
    categoria: str = Field(default="Tecnología", description="Categoría del producto")
    precio_inicial: float = Field(..., gt=0, description="Precio inicial de partida")
    duracion_minutos: int = Field(default=60, gt=0, description="Duración estimada en minutos")
    imagen_url: Optional[str] = Field(default=None, description="Ruta o URL de la imagen")
    incremento_minimo: Optional[float] = Field(default=None, gt=0, description="Incremento mínimo opcional")


class EditarSubastaRequest(BaseModel):
    nombre: Optional[str] = Field(None, min_length=1)
    descripcion: Optional[str] = Field(None, min_length=1)
    categoria: Optional[str] = Field(None)
    precio_inicial: Optional[float] = Field(None, gt=0)
    duracion_minutos: Optional[int] = Field(None, gt=0)
    imagen_url: Optional[str] = Field(None)


class ModerarSubastaRequest(BaseModel):
    accion: str = Field(..., description="Acción administrativa: 'Aprobar', 'Rechazar', 'ForzarCierre', 'Cancelar'")
    motivo: Optional[str] = Field(None, description="Motivo de la moderación")


class CambiarEstadoUsuarioRequest(BaseModel):
    estado: str = Field(..., description="Nuevo estado del usuario: 'Activo' o 'Suspendido'")


class ConfiguracionGlobalRequest(BaseModel):
    incremento_minimo: Optional[float] = Field(None, gt=0, description="Incremento mínimo global en USD")
    comision_porcentaje: Optional[float] = Field(None, ge=0, le=100, description="Porcentaje de comisión")
