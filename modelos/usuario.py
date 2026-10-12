
class Usuario:
    def __init__(self, nombre):
        nombre = nombre.strip()

        if not nombre:
            raise ValueError("El nombre no puede estar vacío.")

        self.nombre = nombre

    def __str__(self):
        return self.nombre
