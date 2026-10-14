from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


# ============================================================================
# ENUMS DEL SISTEMA (ROLES Y ESTADOS DE SUBASTA)
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


class AuctionStatus(str, Enum):
    PROGRAMMED = "PROGRAMMED"  # Fecha de inicio a futuro
    ACTIVE = "ACTIVE"          # En curso actualmente
    FINISHED = "FINISHED"      # Culminada por fecha límite o adjudicación
    CANCELLED = "CANCELLED"    # Cancelada por vendedor o admin


# ============================================================================
# MODELOS DE DOMINIO (POO: USER, AUCTION, BID)
# ============================================================================
class User:
    """Modelo de Usuario en el dominio."""
    def __init__(self, name: str, email: str, role: RolUsuario = RolUsuario.ROLE_BUYER, status: str = "Active", id: Optional[Any] = None):
        self.id = id
        self.name = name.strip()
        self.email = email.strip().lower()
        self.role = role
        self.status = status

    @property
    def is_active(self) -> bool:
        return self.status in ["Active", "Activo"]

    def can_moderate(self) -> bool:
        return self.role == RolUsuario.ROLE_ADMIN

    def is_owner_of(self, auction: "Auction") -> bool:
        return str(auction.seller_id) == str(self.id)

    def __str__(self):
        return f"{self.name} <{self.email}> [{self.role.value}]"


class Bid:
    """Modelo de Puja/Oferta en el dominio."""
    def __init__(self, bidder_id: Any, bidder_name: str, amount: float, created_at: Optional[str] = None, id: Optional[Any] = None):
        self.id = id
        self.bidder_id = bidder_id
        self.bidder_name = bidder_name
        self.amount = float(amount)
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "bidderId": self.bidder_id,
            "usuario_id": self.bidder_id,
            "bidderName": self.bidder_name,
            "usuario_nombre": self.bidder_name,
            "amount": self.amount,
            "monto": self.amount,
            "createdAt": self.created_at,
            "fecha": self.created_at
        }


class Auction:
    """Modelo de Subasta con fechas, tags, status y reglas de puja."""
    def __init__(
        self,
        title: str,
        description: str,
        starting_price: float,
        start_date: str,
        end_date: str,
        tags: Optional[List[str]] = None,
        seller_id: Optional[Any] = None,
        seller_name: Optional[str] = None,
        status: AuctionStatus = AuctionStatus.ACTIVE,
        image_url: Optional[str] = None,
        category: str = "General",
        min_increment: float = 10.0,
        id: Optional[Any] = None
    ):
        self.id = id
        self.title = title.strip()
        self.description = description.strip()
        self.starting_price = float(starting_price)
        self.start_date = start_date
        self.end_date = end_date
        self.tags = [t.strip().lower() for t in (tags or []) if t.strip()]
        self.seller_id = seller_id
        self.seller_name = seller_name or "Vendedor"
        self.status = status
        self.image_url = image_url or "/static/img/laptop.jpg"
        self.category = category
        self.min_increment = float(min_increment)
        self.bids: List[Bid] = []
        self.winner_id = None
        self.winner_name = None
        self.final_amount = None

    @property
    def current_price(self) -> float:
        if self.bids:
            return max(b.amount for b in self.bids)
        return self.starting_price

    @property
    def highest_bidder(self) -> Optional[str]:
        if self.bids:
            sorted_bids = sorted(self.bids, key=lambda b: b.amount, reverse=True)
            return sorted_bids[0].bidder_name
        return None

    def register_bid(self, user: User, amount: float) -> Bid:
        if self.status != AuctionStatus.ACTIVE:
            raise ValueError(f"No se pueden realizar pujas. La subasta se encuentra en estado '{self.status.value}'.")

        min_required = self.current_price + self.min_increment if self.bids else self.starting_price
        if amount < min_required:
            raise ValueError(
                f"La puja debe ser de al menos ${min_required:.2f} (Precio actual: ${self.current_price:.2f} + incremento mínimo: ${self.min_increment:.2f})."
            )

        bid = Bid(bidder_id=user.id, bidder_name=user.name, amount=amount)
        self.bids.append(bid)
        return bid


# ============================================================================
# ALIASES COMPATIBLES (POO LEGACY Y CLI)
# ============================================================================
UsuarioBase = User
Administrador = User
Vendedor = User
Comprador = User
Visitante = User
Usuario = User
Subastador = User
Postor = User
Producto = lambda nombre, descripcion, precio_inicial, categoria="Tecnología", imagen_url=None: type('Prod', (), {
    'nombre': nombre,
    'descripcion': descripcion,
    'precio_inicial': float(precio_inicial),
    'categoria': categoria,
    'imagen_url': imagen_url or "/static/img/laptop.jpg"
})()
Subasta = Auction


# ============================================================================
# ESQUEMAS DTO (DATA TRANSFER OBJECTS / PYDANTIC)
# ============================================================================
class LoginRequest(BaseModel):
    email: str = Field(..., description="Correo registrado del usuario")
    password: str = Field(..., min_length=4, description="Contraseña")


class RegisterRequest(BaseModel):
    nombre: Optional[str] = None
    name: Optional[str] = None
    email: str = Field(..., description="Correo electrónico único")
    password: str = Field(..., min_length=4, description="Contraseña de acceso")
    rol: Optional[str] = Field(default="ROLE_BUYER", description="Rol inicial (ROLE_BUYER o ROLE_SELLER)")


class PujaRequest(BaseModel):
    monto: Optional[float] = None
    amount: Optional[float] = None


# Alias DTO legacy
OfertarRequest = PujaRequest


class CrearSubastaRequest(BaseModel):
    title: Optional[str] = None
    nombre: Optional[str] = None
    description: Optional[str] = None
    descripcion: Optional[str] = None
    startingPrice: Optional[float] = None
    precio_inicial: Optional[float] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    duracion_minutos: Optional[int] = 60
    tags: Optional[List[str]] = Field(default_factory=list)
    categoria: Optional[str] = "General"
    imageUrl: Optional[str] = None
    imagen_url: Optional[str] = None
    incremento_minimo: Optional[float] = None


class EditarSubastaRequest(BaseModel):
    title: Optional[str] = None
    nombre: Optional[str] = None
    description: Optional[str] = None
    descripcion: Optional[str] = None
    startingPrice: Optional[float] = None
    precio_inicial: Optional[float] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    tags: Optional[List[str]] = None
    categoria: Optional[str] = None
    imageUrl: Optional[str] = None
    imagen_url: Optional[str] = None


class ModerarSubastaRequest(BaseModel):
    accion: Optional[str] = None
    status: Optional[str] = None
    motivo: Optional[str] = None


class AdminAuctionStatusRequest(BaseModel):
    # Acepta tanto 'status' (nuevo) como 'accion' (alias legacy del frontend)
    status: Optional[str] = Field(None, description="Estado administrativo: 'Aprobar', 'Suspender', 'Eliminar', 'PROGRAMMED', 'ACTIVE', 'FINISHED', 'CANCELLED'")
    accion: Optional[str] = Field(None, description="Alias de 'status'")
    motivo: Optional[str] = None

    def accion_efectiva(self) -> str:
        valor = self.status or self.accion
        if not valor:
            raise ValueError("Debes indicar 'status' o 'accion' para moderar la subasta.")
        return valor


class CambiarEstadoUsuarioRequest(BaseModel):
    estado: str = Field(..., description="Nuevo estado: 'Activo' o 'Suspendido'")


class ConfiguracionGlobalRequest(BaseModel):
    incremento_minimo: Optional[float] = Field(None, gt=0)
    comision_porcentaje: Optional[float] = Field(None, ge=0, le=100)
