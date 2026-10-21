#!/usr/bin/env python3
"""
Script de Inicialización y Carga de Datos de Prueba (Seed) para Suba.
Puebla MongoDB con:
- 1 Usuario Administrador (admin@subastas.com / admin123)
- 2 Usuarios Vendedores (carlos@subastas.com / carlos123, lucia@subastas.com / lucia123)
- 2 Usuarios Compradores (ana@subastas.com / ana123, mateo@subastas.com / mateo123)
- 8 Subastas de prueba con tags (libros, arte, electronica, tecnologia, relojes, etc.),
  fechas pasadas/presentes/futuras y estados (ACTIVE, PROGRAMMED, FINISHED).

Nota: la aplicación ejecuta esta semilla de forma automática y silenciosa al arrancar
si la base de datos está vacía. Este script permite forzar una regeneración limpia.
"""
import sys
import os

# Asegurar path para importar backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.database import get_db, seed_database, init_db, obtener_subastas, listar_usuarios


def run_seed():
    print("=" * 65)
    print("INICIANDO CARGA DE DATOS DE PRUEBA EN MONGODB (SUBA)")
    print("=" * 65)

    db = get_db()
    print(f"-> Conectado a MongoDB: {db.name}")

    print("-> Inicializando colecciones, índices y roles...")
    init_db()

    print("-> Forzando regeneración limpia de usuarios y subastas...")
    seed_database()

    usuarios = listar_usuarios()
    subastas = obtener_subastas(filtro_estado=None, solo_aprobadas=False)

    print("\n[OK] USUARIOS DE PRUEBA CREADOS:")
    for u in usuarios:
        print(f"  • #{u['id']} - {u['nombre']} ({u['email']}) -> Rol: {u['rol']}")

    print("\n[OK] SUBASTAS DE PRUEBA CREADAS:")
    for s in subastas:
        tags_str = ", ".join(f"#{t}" for t in s['tags'])
        print(f"  • #{s['id']} [{s['status']}] {s['title']} | Precio: ${s['currentPrice']:.2f} | Tags: [{tags_str}]")

    print("\n" + "=" * 65)
    print("¡SEMILLA DE DATOS COMPLETADA EXITOSAMENTE!")
    print("=" * 65)


if __name__ == "__main__":
    run_seed()
