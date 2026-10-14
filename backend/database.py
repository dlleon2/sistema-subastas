import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, DESCENDING
from bson import ObjectId

# Configuración de conexión a MongoDB (Local o variable de entorno para Atlas)
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "sistema_subastas")

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """Retorna una instancia singleton del cliente MongoClient."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Retorna la base de datos de MongoDB."""
    client = get_client()
    return client[MONGO_DB_NAME]


def get_next_sequence(name: str) -> int:
    """Genera secuencias numéricas correlativas (1, 2, 3...) para IDs legibles."""
    db = get_db()
    ret = db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    return ret["seq"]


def _parse_id_query(subasta_id: Any) -> dict:
    """Permite buscar subastas tanto por ID numérico (ej. 1, 2) como por ObjectId de MongoDB."""
    queries = []
    try:
        queries.append({"id": int(subasta_id)})
    except (ValueError, TypeError):
        pass

    if isinstance(subasta_id, str) and ObjectId.is_valid(subasta_id):
        queries.append({"_id": ObjectId(subasta_id)})
    elif isinstance(subasta_id, ObjectId):
        queries.append({"_id": subasta_id})

    queries.append({"id": str(subasta_id)})

    if len(queries) == 1:
        return queries[0]
    return {"$or": queries}


def _format_subasta(doc: dict) -> dict:
    """Estandariza el documento NoSQL al formato JSON esperado por el frontend y la API."""
    if not doc:
        return None

    ofertas = doc.get("ofertas", [])
    # Ordenar ofertas de mayor a menor monto
    sorted_ofertas = sorted(
        ofertas,
        key=lambda x: (float(x.get("monto", 0.0)), str(x.get("fecha", ""))),
        reverse=True
    )

    precio_inicial = float(doc.get("producto", {}).get("precio_inicial", 0.0))
    precio_actual = float(sorted_ofertas[0]["monto"]) if sorted_ofertas else precio_inicial
    mayor_postor = sorted_ofertas[0]["usuario_nombre"] if sorted_ofertas else None

    # Normalizar historial de ofertas
    historial = []
    for idx, o in enumerate(sorted_ofertas, 1):
        historial.append({
            "id": o.get("id", idx),
            "usuario_nombre": o.get("usuario_nombre"),
            "monto": float(o.get("monto", 0.0)),
            "fecha": o.get("fecha", "")
        })

    return {
        "id": doc.get("id", str(doc.get("_id"))),
        "mongo_id": str(doc.get("_id")),
        "abierta": bool(doc.get("abierta", True)),
        "duracion_minutos": doc.get("duracion_minutos", 60),
        "creada_en": doc.get("creada_en"),
        "cerrada_en": doc.get("cerrada_en"),
        "ganador_nombre": doc.get("ganador_nombre"),
        "monto_final": float(doc["monto_final"]) if doc.get("monto_final") is not None else None,
        "producto": {
            "id": doc.get("id", 1),
            "nombre": doc.get("producto", {}).get("nombre", ""),
            "descripcion": doc.get("producto", {}).get("descripcion", ""),
            "categoria": doc.get("producto", {}).get("categoria", "Tecnología"),
            "precio_inicial": precio_inicial,
            "imagen_url": doc.get("producto", {}).get("imagen_url") or "/static/img/laptop.jpg"
        },
        "precio_actual": precio_actual,
        "mayor_postor": mayor_postor,
        "total_ofertas": len(ofertas),
        "historial_ofertas": historial
    }


def init_db():
    """Inicializa la conexión y crea los índices y datos iniciales en MongoDB."""
    db = get_db()
    # Crear índice único para el campo id correlativo
    db.subastas.create_index("id", unique=True)
    db.subastas.create_index("abierta")

    # Poblar datos semilla si la colección está vacía
    if db.subastas.count_documents({}) == 0:
        seed_data(db)


def seed_data(db):
    """Inserta productos iniciales en MongoDB si la base de datos está vacía."""
    ahora = datetime.now().isoformat()
    subastas_iniciales = [
        {
            "id": 1,
            "abierta": True,
            "duracion_minutos": 120,
            "creada_en": ahora,
            "cerrada_en": None,
            "ganador_nombre": None,
            "monto_final": None,
            "producto": {
                "nombre": "Laptop Gaming RTX 4070",
                "descripcion": "Portátil ultra potente con pantalla QHD de 165Hz, teclado RGB y chasis de aluminio.",
                "categoria": "Tecnología",
                "precio_inicial": 850.00,
                "imagen_url": "/static/img/laptop.jpg"
            },
            "ofertas": [
                {
                    "id": 1,
                    "usuario_nombre": "Carlos Ramos",
                    "monto": 900.00,
                    "fecha": ahora
                },
                {
                    "id": 2,
                    "usuario_nombre": "Ana Gómez",
                    "monto": 950.00,
                    "fecha": ahora
                }
            ]
        },
        {
            "id": 2,
            "abierta": True,
            "duracion_minutos": 120,
            "creada_en": ahora,
            "cerrada_en": None,
            "ganador_nombre": None,
            "monto_final": None,
            "producto": {
                "nombre": "Reloj Cronógrafo Suizo Speedmaster",
                "descripcion": "Edición de colección con detalles en oro rosa, cristal de zafiro y correa de cuero genuino.",
                "categoria": "Coleccionables",
                "precio_inicial": 450.00,
                "imagen_url": "/static/img/reloj.jpg"
            },
            "ofertas": [
                {
                    "id": 1,
                    "usuario_nombre": "Mateo Silva",
                    "monto": 480.00,
                    "fecha": ahora
                }
            ]
        },
        {
            "id": 3,
            "abierta": True,
            "duracion_minutos": 120,
            "creada_en": ahora,
            "cerrada_en": None,
            "ganador_nombre": None,
            "monto_final": None,
            "producto": {
                "nombre": "Auriculares Hi-Fi Wireless ANC",
                "descripcion": "Auriculares inalámbricos con cancelación de ruido activa adaptativa y sonido de estudio.",
                "categoria": "Audio",
                "precio_inicial": 120.00,
                "imagen_url": "/static/img/auriculares.jpg"
            },
            "ofertas": []
        }
    ]

    db.subastas.insert_many(subastas_iniciales)
    db.counters.update_one({"_id": "subasta_id"}, {"$set": {"seq": 3}}, upsert=True)


def obtener_subastas(filtro_estado: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene y retorna la lista de subastas con filtros opcionales."""
    db = get_db()
    query = {}
    if filtro_estado == "activas":
        query["abierta"] = True
    elif filtro_estado == "cerradas":
        query["abierta"] = False

    cursor = db.subastas.find(query).sort([("abierta", DESCENDING), ("id", DESCENDING)])
    return [_format_subasta(doc) for doc in cursor]


def obtener_subasta_por_id(subasta_id: Any) -> Optional[Dict[str, Any]]:
    """Busca una subasta específica por su identificador."""
    db = get_db()
    query = _parse_id_query(subasta_id)
    doc = db.subastas.find_one(query)
    return _format_subasta(doc) if doc else None


def registrar_oferta(subasta_id: Any, usuario_nombre: str, monto: float) -> Dict[str, Any]:
    """Registra una nueva oferta en la subasta en MongoDB tras validar las condiciones."""
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

    nueva_oferta = {
        "id": subasta["total_ofertas"] + 1,
        "usuario_nombre": usuario_nombre,
        "monto": float(monto),
        "fecha": datetime.now().isoformat()
    }

    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {"$push": {"ofertas": nueva_oferta}})

    return obtener_subasta_por_id(subasta_id)


def cerrar_subasta(subasta_id: Any) -> Dict[str, Any]:
    """Cierra la subasta, adjudicando el ganador con la mayor oferta registrada."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    if not subasta["abierta"]:
        raise ValueError("La subasta ya se encuentra cerrada.")

    ganador = subasta["mayor_postor"]
    monto_final = subasta["precio_actual"] if ganador else None
    ahora = datetime.now().isoformat()

    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {
        "$set": {
            "abierta": False,
            "cerrada_en": ahora,
            "ganador_nombre": ganador,
            "monto_final": monto_final
        }
    })

    return obtener_subasta_por_id(subasta_id)


def crear_subasta(
    nombre: str,
    descripcion: str,
    categoria: str,
    precio_inicial: float,
    duracion_minutos: int = 60,
    imagen_url: str = None
) -> Dict[str, Any]:
    """Crea un nuevo documento de subasta en MongoDB con su producto asociado."""
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")

    if precio_inicial <= 0:
        raise ValueError("El precio inicial debe ser mayor a 0.")

    if not imagen_url or not imagen_url.strip():
        imagen_url = "/static/img/laptop.jpg"

    seq_id = get_next_sequence("subasta_id")
    ahora = datetime.now().isoformat()

    nuevo_doc = {
        "id": seq_id,
        "abierta": True,
        "duracion_minutos": duracion_minutos,
        "creada_en": ahora,
        "cerrada_en": None,
        "ganador_nombre": None,
        "monto_final": None,
        "producto": {
            "nombre": nombre,
            "descripcion": descripcion,
            "categoria": categoria or "Varios",
            "precio_inicial": float(precio_inicial),
            "imagen_url": imagen_url
        },
        "ofertas": []
    }

    db = get_db()
    db.subastas.insert_one(nuevo_doc)
    return obtener_subasta_por_id(seq_id)


def metricas_globales() -> Dict[str, Any]:
    """Calcula las métricas de la plataforma mediante agregaciones en MongoDB."""
    db = get_db()
    total_subastas = db.subastas.count_documents({})
    activas = db.subastas.count_documents({"abierta": True})

    pipeline = [
        {"$unwind": "$ofertas"},
        {"$group": {
            "_id": None,
            "total_ofertas": {"$sum": 1},
            "volumen": {"$sum": "$ofertas.monto"}
        }}
    ]
    agg = list(db.subastas.aggregate(pipeline))
    total_ofertas = agg[0]["total_ofertas"] if agg else 0
    volumen = agg[0]["volumen"] if agg else 0.0

    return {
        "total_subastas": total_subastas,
        "subastas_activas": activas,
        "total_ofertas": total_ofertas,
        "volumen_total": round(volumen, 2)
    }
