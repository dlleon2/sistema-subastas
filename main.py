import sys
import uvicorn
from backend.models import Producto, Subasta, Usuario, Subastador, Postor


def menu_subastador(subastador: Subastador, subasta: Subasta):
    """Menú exclusivo para el perfil de quien subasta (vendedor/administrador del lote)."""
    while True:
        print("\n" + "-" * 50)
        print(f"--- PANEL DEL SUBASTADOR: {subastador.nombre.upper()} ---")
        print("-" * 50)
        print(f"Artículo: {subasta.producto.nombre}")
        print(f"Descripción: {subasta.producto.descripcion}")
        print(f"Precio inicial: ${subasta.producto.precio_inicial:.2f}")
        print(f"Precio actual: ${subasta.precio_actual():.2f}")
        print(f"Estado de la subasta: {'Abierta' if subasta.abierta else 'Cerrada'}")
        if not subasta.abierta and subasta.ganador:
            print(f"Ganador adjudicado: {subasta.ganador['usuario']} con ${subasta.ganador['monto']:.2f}")

        print("\nOpciones de Subastador:")
        print("1. Ver ofertas recibidas")
        print("2. Modificar lote / Crear nueva subasta")
        print("3. Cerrar subasta y declarar ganador")
        print("4. Volver al selector de perfiles")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            print("\n--- Historial de Ofertas Recibidas ---")
            subasta.mostrar_ofertas()

        elif opcion == "2":
            if subasta.abierta and subasta.ofertas:
                print("\n[Aviso]: La subasta actual tiene ofertas registradas.")
                confirmar = input("¿Deseas reemplazar el lote e iniciar una nueva subasta? (s/n): ").strip().lower()
                if confirmar != "s":
                    continue

            print("\n--- Configurar Nuevo Lote a Subastar ---")
            nombre_p = input("Nombre del artículo: ").strip()
            desc_p = input("Descripción del artículo: ").strip()
            try:
                precio_p = float(input("Precio base de partida ($): "))
                nuevo_prod = Producto(nombre=nombre_p, descripcion=desc_p, precio_inicial=precio_p)
                subasta.producto = nuevo_prod
                subasta.ofertas = []
                subasta.abierta = True
                subasta.ganador = None
                print(f"\n¡Lote '{nuevo_prod.nombre}' publicado exitosamente con precio base de ${precio_p:.2f}!")
            except ValueError as error:
                print(f"[Error al configurar el lote]: {error}")

        elif opcion == "3":
            if not subasta.abierta:
                print("\n[Info]: La subasta ya se encuentra cerrada.")
            else:
                ganador = subastador.cerrar_subasta(subasta)
                print("\n" + "=" * 50)
                print("¡SUBASTA CERRADA POR EL SUBASTADOR!")
                if ganador:
                    print(f"Artículo adjudicado a: {ganador['usuario']}")
                    print(f"Monto final ganador: ${ganador['monto']:.2f}")
                else:
                    print("La subasta finalizó sin ofertas registradas.")
                print("=" * 50)

        elif opcion == "4":
            break
        else:
            print("Opción no válida.")


def menu_postor(subasta: Subasta):
    """Menú exclusivo para el perfil de quien quiere ver las subastas y proponer precio (postor)."""
    print("\n" + "-" * 50)
    print("--- IDENTIFICACIÓN DEL POSTOR / PARTICIPANTE ---")
    print("-" * 50)
    nombre = input("Ingresa tu nombre: ").strip()
    if not nombre:
        print("[Error]: El nombre no puede estar vacío.")
        return

    postor = Postor(nombre)

    while True:
        print("\n" + "-" * 50)
        print(f"--- PANEL DEL POSTOR: {postor.nombre.upper()} ---")
        print("-" * 50)
        print(f"Artículo en subasta: {subasta.producto.nombre}")
        print(f"Descripción: {subasta.producto.descripcion}")
        print(f"Precio actual: ${subasta.precio_actual():.2f}")
        lider = subasta.mayor_postor()
        print(f"Mayor postor hasta ahora: {lider if lider else 'Sin ofertas aún'}")
        print(f"Estado: {'Abierta para ofertas' if subasta.abierta else 'Cerrada / Finalizada'}")

        print("\nOpciones de Postor:")
        print("1. Proponer un precio (Registrar oferta)")
        print("2. Ver todas las ofertas de la subasta")
        print("3. Volver al selector de perfiles")

        opcion = input("Selecciona una opción: ").strip()

        if opcion == "1":
            if not subasta.abierta:
                print("\n[No disponible]: La subasta está cerrada, ya no se aceptan más ofertas.")
                continue

            try:
                monto = float(input(f"Monto de tu oferta (debe ser mayor a ${subasta.precio_actual():.2f}): $"))
                postor.proponer_precio(subasta, monto)
                print(f"\n¡Oferta de ${monto:.2f} propuesta y registrada exitosamente por {postor.nombre}!")
            except ValueError as error:
                print(f"\n[Error en la oferta]: {error}")

        elif opcion == "2":
            print("\n--- Historial de Ofertas ---")
            subasta.mostrar_ofertas()

        elif opcion == "3":
            break
        else:
            print("Opción no válida.")


def run_cli():
    """Ejecuta el modo interactivo por consola con perfiles separados."""
    subastador_default = Subastador("Casa de Subastas")
    producto_inicial = Producto(
        nombre="Laptop Gaming RTX 4070",
        descripcion="Portátil ultra potente de última generación",
        precio_inicial=300
    )
    subasta_activa = subastador_default.crear_subasta(producto_inicial)

    while True:
        print("\n" + "=" * 60)
        print("SISTEMA DE SUBASTAS — SELECCIÓN DE PERFIL")
        print("=" * 60)
        print(f"Lote actual: {subasta_activa.producto.nombre} | Precio actual: ${subasta_activa.precio_actual():.2f}")
        print(f"Estado: {'Abierta' if subasta_activa.abierta else 'Cerrada'}")
        print("-" * 60)
        print("1. [Perfil Subastador] -> Publicar, administrar o cerrar la subasta")
        print("2. [Perfil Postor]     -> Ver las subastas y proponer un precio")
        print("3. Salir")
        print("-" * 60)

        opcion = input("Selecciona tu perfil o acción: ").strip()

        if opcion == "1":
            menu_subastador(subastador_default, subasta_activa)

        elif opcion == "2":
            menu_postor(subasta_activa)

        elif opcion == "3":
            print("Gracias por usar el Sistema de Subastas. ¡Hasta luego!")
            break

        else:
            print("Opción no válida. Intenta de nuevo.")


def run_server():
    """Ejecuta el servidor Backend FastAPI y sirve la interfaz Web moderna."""
    print("=" * 60)
    print("INICIANDO SISTEMA DE SUBASTAS (FULLSTACK)")
    print("=" * 60)
    print("Aplicación Web disponible en: http://127.0.0.1:8000")
    print("Documentación interactiva API: http://127.0.0.1:8000/docs")
    print("Presiona CTRL + C para detener el servidor.")
    print("=" * 60)

    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli()
    else:
        run_server()
