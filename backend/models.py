from pydantic import BaseModel, Field
from typing import Optional, List


# ============================================================================
# CLASES DE DOMINIO (POO)
# ============================================================================
class Usuario:
    """Representa a un participante o usuario en el sistema."""
    def __init__(self, nombre: str):
        nombre = nombre.strip()
        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")
        self.nombre = nombre

    def __str__(self):
        return self.nombre


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
    def __init__(self, producto: Producto, duracion_minutos: int = 60):
        self.producto = producto
        self.duracion_minutos = duracion_minutos
        self.ofertas = []
        self.abierta = True
        self.ganador = None

    def precio_actual(self) -> float:
        if self.ofertas:
            return self.ofertas[-1]["monto"]
        return self.producto.precio_inicial

    def mayor_postor(self) -> Optional[str]:
        if self.ofertas:
            return self.ofertas[-1]["usuario"].nombre
        return None

    def registrar_oferta(self, usuario: Usuario, monto: float):
        if not self.abierta:
            raise ValueError("La subasta está cerrada.")

        if monto <= self.precio_actual():
            raise ValueError(f"La oferta debe superar el precio actual (${self.precio_actual():.2f}).")

        self.ofertas.append({
            "usuario": usuario,
            "monto": monto
        })

    def cerrar(self):
        self.abierta = False
        if self.ofertas:
            self.ganador = self.ofertas[-1]

    def mostrar_ofertas(self):
        if not self.ofertas:
            print("Todavía no hay ofertas.")
            return

        for oferta in self.ofertas:
            print(f"{oferta['usuario']}: ${oferta['monto']:.2f}")


# ============================================================================
# ESQUEMAS DTO (DATA TRANSFER OBJECTS / PYDANTIC)
# ============================================================================
class OfertarRequest(BaseModel):
    usuario: str = Field(..., min_length=1, description="Nombre del participante")
    monto: float = Field(..., gt=0, description="Monto ofrecido en USD")


class CrearSubastaRequest(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del producto")
    descripcion: str = Field(..., min_length=1, description="Descripción detallada")
    categoria: str = Field(default="Tecnología", description="Categoría del producto")
    precio_inicial: float = Field(..., gt=0, description="Precio inicial de partida")
    duracion_minutos: int = Field(default=60, gt=0, description="Duración estimada en minutos")
    imagen_url: Optional[str] = Field(default=None, description="Ruta o URL de la imagen")
