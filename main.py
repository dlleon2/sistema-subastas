import sys
import uvicorn
from modelos.producto import Producto
from modelos.subasta import Subasta
from modelos.usuario import Usuario


def run_cli():
    """Ejecuta el modo clásico interactivo por consola."""
    producto = Producto(
        "Laptop",
        "Laptop usada en buen estado",
        300
    )
    subasta = Subasta(producto)

    while True:
        print("\n=== SISTEMA DE SUBASTAS (MODO CONSOLA) ===")
        print(f"Producto: {producto.nombre}")
        print(f"Precio actual: ${subasta.precio_actual():.2f}")
        print("1. Registrar oferta")
        print("2. Ver ofertas")
        print("3. Cerrar subasta")
        print("4. Salir")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            try:
                nombre = input("Nombre del participante: ")
                usuario = Usuario(nombre)
                monto = float(input("Monto de la oferta: $"))

                subasta.registrar_oferta(usuario, monto)
                print("¡Oferta registrada!")

            except ValueError as error:
                print(f"Error: {error}")

        elif opcion == "2":
            subasta.mostrar_ofertas()

        elif opcion == "3":
            subasta.cerrar()
            print("Subasta cerrada.")

        elif opcion == "4":
            print("Hasta luego.")
            break

        else:
            print("Opción no válida.")


def run_server():
    """Ejecuta el servidor Backend FastAPI y sirve la interfaz Web moderna."""
    print("=" * 60)
    print("INICIANDO SISTEMA DE SUBASTAS (FULLSTACK)")
    print("=" * 60)
    print("Aplicación Web disponible en: http://127.0.0.1:8000")
    print("Documentación interactiva API: http://127.0.0.1:8000/docs")
    print("Presiona CTRL + C para detener el servidor.")
    print("=" * 60)

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        run_server()
