
class Producto:
    def __init__(self, nombre, descripcion, precio_inicial):
        if not nombre.strip():
            raise ValueError("El nombre no puede estar vacío.")

        if precio_inicial <= 0:
            raise ValueError("El precio debe ser mayor que cero.")

        self.nombre = nombre
        self.descripcion = descripcion
        self.precio_inicial = float(precio_inicial)

    def __str__(self):
        return (
            f"{self.nombre} - {self.descripcion} "
            f"(Precio inicial: ${self.precio_inicial:.2f})"
        )
