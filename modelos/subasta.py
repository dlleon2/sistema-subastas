
class Subasta:
    def __init__(self, producto):
        self.producto = producto
        self.ofertas = []
        self.abierta = True

    def precio_actual(self):
        if self.ofertas:
            return self.ofertas[-1]["monto"]
        return self.producto.precio_inicial

    def registrar_oferta(self, usuario, monto):
        if not self.abierta:
            raise ValueError("La subasta está cerrada.")

        if monto <= self.precio_actual():
            raise ValueError("La oferta debe superar el precio actual.")

        self.ofertas.append({
            "usuario": usuario,
            "monto": monto
        })

    def cerrar(self):
        self.abierta = False

    def mostrar_ofertas(self):
        if not self.ofertas:
            print("Todavía no hay ofertas.")
            return

        for oferta in self.ofertas:
            print(f"{oferta['usuario']}: ${oferta['monto']:.2f}")
