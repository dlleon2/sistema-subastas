import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "subastas.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        descripcion TEXT,
        categoria TEXT DEFAULT 'Tecnología',
        precio_inicial REAL NOT NULL,
        imagen_url TEXT,
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS subastas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        producto_id INTEGER NOT NULL,
        abierta INTEGER DEFAULT 1,
        duracion_minutos INTEGER DEFAULT 60,
        creada_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cerrada_en TIMESTAMP,
        ganador_nombre TEXT,
        monto_final REAL,
        FOREIGN KEY (producto_id) REFERENCES productos(id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ofertas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subasta_id INTEGER NOT NULL,
        usuario_nombre TEXT NOT NULL,
        monto REAL NOT NULL,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (subasta_id) REFERENCES subastas(id)
    );
    """)

    # Seed data if empty
    cursor.execute("SELECT COUNT(*) AS count FROM subastas;")
    if cursor.fetchone()["count"] == 0:
        seed_data(cursor)

    conn.commit()
    conn.close()


def seed_data(cursor):
    productos = [
        (
            "Laptop Gaming RTX 4070",
            "Portátil ultra potente con pantalla QHD de 165Hz, teclado RGB y chasis de aluminio.",
            "Tecnología",
            850.00,
            "/static/img/laptop.jpg"
        ),
        (
            "Reloj Cronógrafo Suizo Speedmaster",
            "Edición de colección con detalles en oro rosa, cristal de zafiro y correa de cuero genuino.",
            "Coleccionables",
            450.00,
            "/static/img/reloj.jpg"
        ),
        (
            "Auriculares Hi-Fi Wireless ANC",
            "Auriculares inalámbricos con cancelación de ruido activa adaptativa y sonido de estudio.",
            "Audio",
            120.00,
            "/static/img/auriculares.jpg"
        ),
    ]

    for prod in productos:
        cursor.execute("""
            INSERT INTO productos (nombre, descripcion, categoria, precio_inicial, imagen_url)
            VALUES (?, ?, ?, ?, ?);
        """, prod)
        prod_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO subastas (producto_id, abierta, duracion_minutos)
            VALUES (?, 1, 120);
        """, (prod_id,))
        subasta_id = cursor.lastrowid

        # Insert some initial sample bids
        if prod[0].startswith("Laptop"):
            cursor.execute("""
                INSERT INTO ofertas (subasta_id, usuario_nombre, monto)
                VALUES (?, ?, ?), (?, ?, ?);
            """, (subasta_id, "Carlos Ramos", 900.00, subasta_id, "Ana Gómez", 950.00))
        elif prod[0].startswith("Reloj"):
            cursor.execute("""
                INSERT INTO ofertas (subasta_id, usuario_nombre, monto)
                VALUES (?, ?, ?);
            """, (subasta_id, "Mateo Silva", 480.00))


def obtener_subastas(filtro_estado=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        s.id,
        s.abierta,
        s.duracion_minutos,
        s.creada_en,
        s.cerrada_en,
        s.ganador_nombre,
        s.monto_final,
        p.id AS producto_id,
        p.nombre,
        p.descripcion,
        p.categoria,
        p.precio_inicial,
        p.imagen_url,
        (SELECT MAX(monto) FROM ofertas WHERE subasta_id = s.id) AS max_oferta,
        (SELECT usuario_nombre FROM ofertas WHERE subasta_id = s.id ORDER BY monto DESC, id DESC LIMIT 1) AS mayor_postor,
        (SELECT COUNT(*) FROM ofertas WHERE subasta_id = s.id) AS total_ofertas
    FROM subastas s
    JOIN productos p ON s.producto_id = p.id
    """

    params = []
    if filtro_estado == "activas":
        query += " WHERE s.abierta = 1"
    elif filtro_estado == "cerradas":
        query += " WHERE s.abierta = 0"

    query += " ORDER BY s.abierta DESC, s.id DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    resultado = []
    for r in rows:
        precio_actual = r["max_oferta"] if r["max_oferta"] is not None else r["precio_inicial"]
        resultado.append({
            "id": r["id"],
            "abierta": bool(r["abierta"]),
            "duracion_minutos": r["duracion_minutos"],
            "creada_en": r["creada_en"],
            "cerrada_en": r["cerrada_en"],
            "ganador_nombre": r["ganador_nombre"],
            "monto_final": r["monto_final"],
            "producto": {
                "id": r["producto_id"],
                "nombre": r["nombre"],
                "descripcion": r["descripcion"],
                "categoria": r["categoria"],
                "precio_inicial": r["precio_inicial"],
                "imagen_url": r["imagen_url"] or "/static/img/laptop.jpg"
            },
            "precio_actual": precio_actual,
            "mayor_postor": r["mayor_postor"],
            "total_ofertas": r["total_ofertas"]
        })
    return resultado


def obtener_subasta_por_id(subasta_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        s.id,
        s.abierta,
        s.duracion_minutos,
        s.creada_en,
        s.cerrada_en,
        s.ganador_nombre,
        s.monto_final,
        p.id AS producto_id,
        p.nombre,
        p.descripcion,
        p.categoria,
        p.precio_inicial,
        p.imagen_url
    FROM subastas s
    JOIN productos p ON s.producto_id = p.id
    WHERE s.id = ?;
    """, (subasta_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    cursor.execute("""
    SELECT id, usuario_nombre, monto, fecha
    FROM ofertas
    WHERE subasta_id = ?
    ORDER BY monto DESC, id DESC;
    """, (subasta_id,))
    ofertas = [dict(o) for o in cursor.fetchall()]

    conn.close()

    precio_actual = ofertas[0]["monto"] if ofertas else row["precio_inicial"]
    mayor_postor = ofertas[0]["usuario_nombre"] if ofertas else None

    return {
        "id": row["id"],
        "abierta": bool(row["abierta"]),
        "duracion_minutos": row["duracion_minutos"],
        "creada_en": row["creada_en"],
        "cerrada_en": row["cerrada_en"],
        "ganador_nombre": row["ganador_nombre"],
        "monto_final": row["monto_final"],
        "producto": {
            "id": row["producto_id"],
            "nombre": row["nombre"],
            "descripcion": row["descripcion"],
            "categoria": row["categoria"],
            "precio_inicial": row["precio_inicial"],
            "imagen_url": row["imagen_url"] or "/static/img/laptop.jpg"
        },
        "precio_actual": precio_actual,
        "mayor_postor": mayor_postor,
        "total_ofertas": len(ofertas),
        "historial_ofertas": ofertas
    }


def registrar_oferta(subasta_id: int, usuario_nombre: str, monto: float):
    usuario_nombre = usuario_nombre.strip()
    if not usuario_nombre:
        raise ValueError("El nombre del usuario no puede estar vacío.")

    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta especificada no existe.")

    if not subasta["abierta"]:
        raise ValueError("La subasta ya está cerrada.")

    if monto <= subasta["precio_actual"]:
        raise ValueError(
            f"La oferta debe ser mayor al precio actual (${subasta['precio_actual']:.2f})."
        )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ofertas (subasta_id, usuario_nombre, monto)
    VALUES (?, ?, ?);
    """, (subasta_id, usuario_nombre, monto))
    conn.commit()
    conn.close()

    return obtener_subasta_por_id(subasta_id)


def cerrar_subasta(subasta_id: int):
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    if not subasta["abierta"]:
        raise ValueError("La subasta ya se encuentra cerrada.")

    ganador = subasta["mayor_postor"]
    monto_final = subasta["precio_actual"] if ganador else None

    conn = get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().isoformat()
    cursor.execute("""
    UPDATE subastas
    SET abierta = 0, cerrada_en = ?, ganador_nombre = ?, monto_final = ?
    WHERE id = ?;
    """, (ahora, ganador, monto_final, subasta_id))
    conn.commit()
    conn.close()

    return obtener_subasta_por_id(subasta_id)


def crear_subasta(nombre: str, descripcion: str, categoria: str, precio_inicial: float, duracion_minutos: int = 60, imagen_url: str = None):
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")

    if precio_inicial <= 0:
        raise ValueError("El precio inicial debe ser mayor a 0.")

    if not imagen_url or not imagen_url.strip():
        imagen_url = "/static/img/laptop.jpg"

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO productos (nombre, descripcion, categoria, precio_inicial, imagen_url)
    VALUES (?, ?, ?, ?, ?);
    """, (nombre, descripcion, categoria or "Varios", precio_inicial, imagen_url))
    prod_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO subastas (producto_id, abierta, duracion_minutos)
    VALUES (?, 1, ?);
    """, (prod_id, duracion_minutos))
    subasta_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return obtener_subasta_por_id(subasta_id)
