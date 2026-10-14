import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, DESCENDING
from bson import ObjectId

from backend.models import RolUsuario

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


def _parse_id_query(identificador: Any) -> dict:
    """Permite buscar documentos por ID numérico (ej. 1, 2) o por ObjectId de MongoDB."""
    queries = []
    try:
        queries.append({"id": int(identificador)})
    except (ValueError, TypeError):
        pass

    if isinstance(identificador, str) and ObjectId.is_valid(identificador):
        queries.append({"_id": ObjectId(identificador)})
    elif isinstance(identificador, ObjectId):
        queries.append({"_id": identificador})

    queries.append({"id": str(identificador)})

    if len(queries) == 1:
        return queries[0]
    return {"$or": queries}


# ============================================================================
# CONFIGURACIÓN GLOBAL DEL SISTEMA
# ============================================================================
def obtener_configuracion_global() -> Dict[str, Any]:
    db = get_db()
    cfg = db.configuracion.find_one({"_id": "global_config"})
    if not cfg:
        cfg = {
            "_id": "global_config",
            "incremento_minimo": 10.0,
            "comision_porcentaje": 5.0,
            "actualizado_en": datetime.now().isoformat()
        }
        db.configuracion.insert_one(cfg)
    return {
        "incremento_minimo": float(cfg.get("incremento_minimo", 10.0)),
        "comision_porcentaje": float(cfg.get("comision_porcentaje", 5.0)),
        "actualizado_en": cfg.get("actualizado_en")
    }


def actualizar_configuracion_global(incremento_minimo: Optional[float] = None, comision_porcentaje: Optional[float] = None) -> Dict[str, Any]:
    db = get_db()
    updates = {"actualizado_en": datetime.now().isoformat()}
    if incremento_minimo is not None:
        if incremento_minimo <= 0:
            raise ValueError("El incremento mínimo debe ser mayor a 0.")
        updates["incremento_minimo"] = float(incremento_minimo)
    if comision_porcentaje is not None:
        if not (0 <= comision_porcentaje <= 100):
            raise ValueError("La comisión debe estar entre 0% y 100%.")
        updates["comision_porcentaje"] = float(comision_porcentaje)

    db.configuracion.update_one(
        {"_id": "global_config"},
        {"$set": updates},
        upsert=True
    )
    return obtener_configuracion_global()


# ============================================================================
# GESTIÓN DE USUARIOS Y ROLES (RBAC)
# ============================================================================
def crear_usuario(nombre: str, email: str, password_hash: str, rol: str = RolUsuario.ROLE_BUYER.value) -> Dict[str, Any]:
    db = get_db()
    email_clean = email.strip().lower()

    if db.usuarios.find_one({"email": email_clean}):
        raise ValueError(f"Ya existe un usuario registrado con el correo: {email_clean}")

    if rol not in [r.value for r in RolUsuario]:
        raise ValueError(f"Rol inválido: {rol}")

    user_id = get_next_sequence("usuario_id")
    ahora = datetime.now().isoformat()

    doc = {
        "id": user_id,
        "nombre": nombre.strip(),
        "email": email_clean,
        "password_hash": password_hash,
        "rol": rol,
        "estado": "Activo",
        "favoritos": [],
        "creado_en": ahora
    }
    db.usuarios.insert_one(doc)
    return {
        "id": user_id,
        "nombre": doc["nombre"],
        "email": doc["email"],
        "rol": doc["rol"],
        "estado": doc["estado"],
        "creado_en": ahora
    }


def obtener_usuario_por_email(email: str) -> Optional[Dict[str, Any]]:
    db = get_db()
    return db.usuarios.find_one({"email": email.strip().lower()})


def obtener_usuario_por_id(usuario_id: Any) -> Optional[Dict[str, Any]]:
    db = get_db()
    query = _parse_id_query(usuario_id)
    doc = db.usuarios.find_one(query)
    if not doc:
        return None
    return {
        "id": doc.get("id"),
        "nombre": doc.get("nombre"),
        "email": doc.get("email"),
        "rol": doc.get("rol"),
        "estado": doc.get("estado", "Activo"),
        "favoritos": doc.get("favoritos", []),
        "creado_en": doc.get("creado_en")
    }


def listar_usuarios() -> List[Dict[str, Any]]:
    db = get_db()
    cursor = db.usuarios.find().sort("id", 1)
    res = []
    for doc in cursor:
        res.append({
            "id": doc.get("id"),
            "nombre": doc.get("nombre"),
            "email": doc.get("email"),
            "rol": doc.get("rol"),
            "estado": doc.get("estado", "Activo"),
            "favoritos_count": len(doc.get("favoritos", [])),
            "creado_en": doc.get("creado_en")
        })
    return res


def cambiar_estado_usuario(usuario_id: Any, nuevo_estado: str) -> Dict[str, Any]:
    if nuevo_estado not in ["Activo", "Suspendido"]:
        raise ValueError("Estado inválido. Debe ser 'Activo' o 'Suspendido'.")

    db = get_db()
    query = _parse_id_query(usuario_id)
    user = db.usuarios.find_one(query)
    if not user:
        raise ValueError("Usuario no encontrado.")

    if user.get("rol") == RolUsuario.ROLE_ADMIN.value:
        raise ValueError("No está permitido suspender a un usuario con rol Administrador.")

    db.usuarios.update_one(query, {"$set": {"estado": nuevo_estado}})
    return obtener_usuario_por_id(usuario_id)


def toggle_favorito(usuario_id: Any, subasta_id: Any) -> Dict[str, Any]:
    db = get_db()
    user_query = _parse_id_query(usuario_id)
    user = db.usuarios.find_one(user_query)
    if not user:
        raise ValueError("Usuario no encontrado.")

    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta especificada no existe.")

    sid = int(subasta["id"])
    favoritos = user.get("favoritos", [])
    if sid in favoritos:
        db.usuarios.update_one(user_query, {"$pull": {"favoritos": sid}})
        es_favorito = False
        mensaje = "Subasta removida de tus favoritos."
    else:
        db.usuarios.update_one(user_query, {"$addToSet": {"favoritos": sid}})
        es_favorito = True
        mensaje = "Subasta agregada a tus favoritos."

    return {
        "subasta_id": sid,
        "es_favorito": es_favorito,
        "mensaje": mensaje
    }


def obtener_favoritos_usuario(usuario_id: Any) -> List[Dict[str, Any]]:
    db = get_db()
    user_query = _parse_id_query(usuario_id)
    user = db.usuarios.find_one(user_query)
    if not user:
        return []

    fav_ids = user.get("favoritos", [])
    if not fav_ids:
        return []

    return [obtener_subasta_por_id(sid) for sid in fav_ids if obtener_subasta_por_id(sid) is not None]


def obtener_pujas_usuario(usuario_id: Any, usuario_nombre: Optional[str] = None) -> List[Dict[str, Any]]:
    """Obtiene el historial de pujas realizadas por un comprador en particular."""
    db = get_db()
    query_conditions = []
    if usuario_id is not None:
        query_conditions.append({"ofertas.usuario_id": usuario_id})
    if usuario_nombre:
        query_conditions.append({"ofertas.usuario_nombre": usuario_nombre})

    if not query_conditions:
        return []

    cursor = db.subastas.find({"$or": query_conditions}).sort("id", -1)
    historial = []
    for doc in cursor:
        subasta_formateada = _format_subasta(doc)
        for oferta in doc.get("ofertas", []):
            coincide = False
            if usuario_id is not None and oferta.get("usuario_id") == usuario_id:
                coincide = True
            elif usuario_nombre and oferta.get("usuario_nombre") == usuario_nombre:
                coincide = True

            if coincide:
                historial.append({
                    "subasta_id": subasta_formateada["id"],
                    "producto_nombre": subasta_formateada["producto"]["nombre"],
                    "monto_puja": float(oferta.get("monto", 0.0)),
                    "fecha": oferta.get("fecha"),
                    "es_ganador_actual": subasta_formateada["mayor_postor"] == oferta.get("usuario_nombre"),
                    "precio_actual_subasta": subasta_formateada["precio_actual"],
                    "subasta_abierta": subasta_formateada["abierta"]
                })
    historial.sort(key=lambda x: str(x.get("fecha", "")), reverse=True)
    return historial


# ============================================================================
# GESTIÓN DE SUBASTAS (CON ROLES, INCREMENTO MÍNIMO Y MODERACIÓN)
# ============================================================================
def _format_subasta(doc: dict) -> dict:
    if not doc:
        return None

    cfg = obtener_configuracion_global()
    inc_min = float(doc.get("incremento_minimo") or cfg["incremento_minimo"])

    ofertas = doc.get("ofertas", [])
    sorted_ofertas = sorted(
        ofertas,
        key=lambda x: (float(x.get("monto", 0.0)), str(x.get("fecha", ""))),
        reverse=True
    )

    precio_inicial = float(doc.get("producto", {}).get("precio_inicial", 0.0))
    precio_actual = float(sorted_ofertas[0]["monto"]) if sorted_ofertas else precio_inicial
    mayor_postor = sorted_ofertas[0]["usuario_nombre"] if sorted_ofertas else None

    historial = []
    for idx, o in enumerate(sorted_ofertas, 1):
        historial.append({
            "id": o.get("id", idx),
            "usuario_id": o.get("usuario_id"),
            "usuario_nombre": o.get("usuario_nombre"),
            "monto": float(o.get("monto", 0.0)),
            "fecha": o.get("fecha", "")
        })

    return {
        "id": doc.get("id", str(doc.get("_id"))),
        "mongo_id": str(doc.get("_id")),
        "abierta": bool(doc.get("abierta", True)),
        "estado_moderacion": doc.get("estado_moderacion", "Aprobada"),
        "motivo_moderacion": doc.get("motivo_moderacion"),
        "vendedor_id": doc.get("vendedor_id"),
        "vendedor_nombre": doc.get("vendedor_nombre", "Vendedor Oficial"),
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
        "incremento_minimo": inc_min,
        "puja_minima_sugerida": precio_actual + inc_min if sorted_ofertas else precio_inicial,
        "mayor_postor": mayor_postor,
        "total_ofertas": len(ofertas),
        "historial_ofertas": historial
    }


def obtener_subastas(filtro_estado: Optional[str] = None, solo_aprobadas: bool = True, vendedor_id: Optional[Any] = None) -> List[Dict[str, Any]]:
    db = get_db()
    query = {}
    if solo_aprobadas:
        query["estado_moderacion"] = "Aprobada"

    if filtro_estado == "activas":
        query["abierta"] = True
    elif filtro_estado == "cerradas":
        query["abierta"] = False

    if vendedor_id is not None:
        try:
            query["vendedor_id"] = int(vendedor_id)
        except (ValueError, TypeError):
            query["vendedor_id"] = vendedor_id

    cursor = db.subastas.find(query).sort([("abierta", DESCENDING), ("id", DESCENDING)])
    return [_format_subasta(doc) for doc in cursor]


def obtener_subasta_por_id(subasta_id: Any) -> Optional[Dict[str, Any]]:
    db = get_db()
    query = _parse_id_query(subasta_id)
    doc = db.subastas.find_one(query)
    return _format_subasta(doc) if doc else None


def registrar_oferta(subasta_id: Any, usuario_nombre: str, monto: float, usuario_id: Optional[int] = None) -> Dict[str, Any]:
    """Registra una puja validando que supere precio actual + incremento mínimo."""
    usuario_nombre = usuario_nombre.strip() if usuario_nombre else "Comprador"
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta especificada no existe.")

    if not subasta["abierta"]:
        raise ValueError("La subasta ya está cerrada.")

    if subasta["estado_moderacion"] != "Aprobada":
        raise ValueError(f"Esta subasta se encuentra en estado '{subasta['estado_moderacion']}' y no admite pujas.")

    inc_min = subasta["incremento_minimo"]
    minimo_requerido = subasta["precio_actual"] + inc_min if subasta["total_ofertas"] > 0 else subasta["producto"]["precio_inicial"]

    if monto < minimo_requerido:
        raise ValueError(
            f"Puja no válida. La oferta mínima permitida es de ${minimo_requerido:.2f} (Precio actual: ${subasta['precio_actual']:.2f} + incremento mínimo de ${inc_min:.2f})."
        )

    nueva_oferta = {
        "id": subasta["total_ofertas"] + 1,
        "usuario_id": usuario_id,
        "usuario_nombre": usuario_nombre,
        "monto": float(monto),
        "fecha": datetime.now().isoformat()
    }

    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {"$push": {"ofertas": nueva_oferta}})

    return obtener_subasta_por_id(subasta_id)


def crear_subasta(
    nombre: str,
    descripcion: str,
    categoria: str,
    precio_inicial: float,
    duracion_minutos: int = 60,
    imagen_url: str = None,
    vendedor_id: Optional[int] = None,
    vendedor_nombre: Optional[str] = None,
    incremento_minimo: Optional[float] = None
) -> Dict[str, Any]:
    nombre = nombre.strip()
    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío.")

    if precio_inicial <= 0:
        raise ValueError("El precio inicial debe ser mayor a 0.")

    if not imagen_url or not imagen_url.strip():
        imagen_url = "/static/img/laptop.jpg"

    cfg = obtener_configuracion_global()
    inc = float(incremento_minimo) if incremento_minimo and incremento_minimo > 0 else cfg["incremento_minimo"]

    seq_id = get_next_sequence("subasta_id")
    ahora = datetime.now().isoformat()

    doc = {
        "id": seq_id,
        "abierta": True,
        "estado_moderacion": "Aprobada",
        "motivo_moderacion": None,
        "vendedor_id": vendedor_id,
        "vendedor_nombre": vendedor_nombre or "Vendedor Oficial",
        "duracion_minutos": duracion_minutos,
        "incremento_minimo": inc,
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
    db.subastas.insert_one(doc)
    return obtener_subasta_por_id(seq_id)


def editar_subasta(subasta_id: Any, vendedor_id: Optional[int], datos: Dict[str, Any], es_admin: bool = False) -> Dict[str, Any]:
    """Permite editar una subasta únicamente si no tiene pujas activas."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    # Validar propiedad (a menos que sea admin)
    if not es_admin and subasta.get("vendedor_id") and vendedor_id and subasta["vendedor_id"] != vendedor_id:
        raise ValueError("No tienes permisos para editar esta subasta (solo el vendedor propietario o un admin).")

    # Regla RBAC Vendedor: solo si no tiene pujas activas
    if subasta["total_ofertas"] > 0:
        raise ValueError("No se puede editar una subasta que ya cuenta con ofertas/pujas registradas.")

    updates = {}
    if datos.get("nombre"):
        updates["producto.nombre"] = datos["nombre"].strip()
    if datos.get("descripcion"):
        updates["producto.descripcion"] = datos["descripcion"].strip()
    if datos.get("categoria"):
        updates["producto.categoria"] = datos["categoria"].strip()
    if datos.get("precio_inicial") is not None and datos["precio_inicial"] > 0:
        updates["producto.precio_inicial"] = float(datos["precio_inicial"])
    if datos.get("duracion_minutos") is not None and datos["duracion_minutos"] > 0:
        updates["duracion_minutos"] = int(datos["duracion_minutos"])
    if datos.get("imagen_url"):
        updates["producto.imagen_url"] = datos["imagen_url"].strip()

    if updates:
        db = get_db()
        query = _parse_id_query(subasta_id)
        db.subastas.update_one(query, {"$set": updates})

    return obtener_subasta_por_id(subasta_id)


def cancelar_subasta_vendedor(subasta_id: Any, vendedor_id: Optional[int], es_admin: bool = False) -> Dict[str, Any]:
    """Cancela una subasta antes del primer incremento (0 pujas registradas)."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    if not es_admin and subasta.get("vendedor_id") and vendedor_id and subasta["vendedor_id"] != vendedor_id:
        raise ValueError("No tienes permisos para cancelar esta subasta.")

    if subasta["total_ofertas"] > 0 and not es_admin:
        raise ValueError("No se puede cancelar una subasta que ya ha iniciado con ofertas de compradores.")

    ahora = datetime.now().isoformat()
    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {
        "$set": {
            "abierta": False,
            "estado_moderacion": "Cancelada",
            "cerrada_en": ahora,
            "motivo_moderacion": "Cancelada por el vendedor antes de la primera puja"
        }
    })
    return obtener_subasta_por_id(subasta_id)


def moderar_subasta_admin(subasta_id: Any, accion: str, motivo: Optional[str] = None) -> Dict[str, Any]:
    """Acciones de moderación para Administradores: Aprobar, Rechazar, ForzarCierre, Cancelar."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    ahora = datetime.now().isoformat()
    updates = {"motivo_moderacion": motivo or f"Acción administrativa: {accion}"}

    if accion == "Aprobar":
        updates["estado_moderacion"] = "Aprobada"
        updates["abierta"] = True
    elif accion == "Rechazar":
        updates["estado_moderacion"] = "Rechazada"
        updates["abierta"] = False
        updates["cerrada_en"] = ahora
    elif accion == "ForzarCierre":
        updates["abierta"] = False
        updates["cerrada_en"] = ahora
        ganador = subasta["mayor_postor"]
        updates["ganador_nombre"] = ganador
        updates["monto_final"] = subasta["precio_actual"] if ganador else None
    elif accion == "Cancelar":
        updates["abierta"] = False
        updates["estado_moderacion"] = "Cancelada"
        updates["cerrada_en"] = ahora
    else:
        raise ValueError(f"Acción de moderación no reconocida: {accion}")

    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {"$set": updates})

    return obtener_subasta_por_id(subasta_id)


def cerrar_subasta(subasta_id: Any) -> Dict[str, Any]:
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


def metricas_globales() -> Dict[str, Any]:
    db = get_db()
    total_subastas = db.subastas.count_documents({})
    activas = db.subastas.count_documents({"abierta": True, "estado_moderacion": "Aprobada"})

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


# ============================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS Y DATOS SEMILLA (ROLES Y USUARIOS DEMO)
# ============================================================================
def init_db():
    db = get_db()
    db.subastas.create_index("id", unique=True)
    db.subastas.create_index("abierta")
    db.usuarios.create_index("email", unique=True)
    db.usuarios.create_index("id", unique=True)
    db.roles.create_index("nombre", unique=True)

    # 1. Asegurar catálogo de roles en MongoDB
    roles_def = [
        {"nombre": RolUsuario.ROLE_GUEST.value, "descripcion": "Visitante sin autenticar", "nivel": 0},
        {"nombre": RolUsuario.ROLE_BUYER.value, "descripcion": "Comprador con permisos de puja y favoritos", "nivel": 1},
        {"nombre": RolUsuario.ROLE_SELLER.value, "descripcion": "Vendedor con permisos de creación y gestión de lotes", "nivel": 2},
        {"nombre": RolUsuario.ROLE_ADMIN.value, "descripcion": "Administrador con control total del sistema y moderación", "nivel": 3},
    ]
    for r in roles_def:
        db.roles.update_one({"nombre": r["nombre"]}, {"$set": r}, upsert=True)

    # 2. Configuración global por defecto
    obtener_configuracion_global()

    # 3. Usuarios de demostración para pruebas inmediatas
    from backend.auth import hash_password

    usuarios_demo = [
        ("Administrador Principal", "admin@subastahub.com", "admin123", RolUsuario.ROLE_ADMIN.value),
        ("Carlos Vendedor", "vendedor@subastahub.com", "vendedor123", RolUsuario.ROLE_SELLER.value),
        ("Ana Compradora", "comprador@subastahub.com", "comprador123", RolUsuario.ROLE_BUYER.value),
    ]

    for nombre, email, pwd, rol in usuarios_demo:
        if not db.usuarios.find_one({"email": email}):
            uid = get_next_sequence("usuario_id")
            db.usuarios.insert_one({
                "id": uid,
                "nombre": nombre,
                "email": email,
                "password_hash": hash_password(pwd),
                "rol": rol,
                "estado": "Activo",
                "favoritos": [],
                "creado_en": datetime.now().isoformat()
            })

    # 4. Asegurar que las subastas existentes tengan estado_moderacion e incremento_minimo
    db.subastas.update_many(
        {"estado_moderacion": {"$exists": False}},
        {"$set": {"estado_moderacion": "Aprobada", "incremento_minimo": 10.0}}
    )

    # 5. Semilla de subastas si está vacía
    if db.subastas.count_documents({}) == 0:
        seed_data(db)


def seed_data(db):
    ahora = datetime.now().isoformat()
    # Buscar el id del vendedor demo
    vendedor_doc = db.usuarios.find_one({"email": "vendedor@subastahub.com"})
    vendedor_id = vendedor_doc["id"] if vendedor_doc else 2
    vendedor_nombre = vendedor_doc["nombre"] if vendedor_doc else "Carlos Vendedor"

    subastas_iniciales = [
        {
            "id": 1,
            "abierta": True,
            "estado_moderacion": "Aprobada",
            "vendedor_id": vendedor_id,
            "vendedor_nombre": vendedor_nombre,
            "duracion_minutos": 120,
            "incremento_minimo": 10.0,
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
                    "usuario_id": 3,
                    "usuario_nombre": "Carlos Ramos",
                    "monto": 900.00,
                    "fecha": ahora
                },
                {
                    "id": 2,
                    "usuario_id": 3,
                    "usuario_nombre": "Ana Gómez",
                    "monto": 950.00,
                    "fecha": ahora
                }
            ]
        },
        {
            "id": 2,
            "abierta": True,
            "estado_moderacion": "Aprobada",
            "vendedor_id": vendedor_id,
            "vendedor_nombre": vendedor_nombre,
            "duracion_minutos": 120,
            "incremento_minimo": 10.0,
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
                    "usuario_id": 3,
                    "usuario_nombre": "Mateo Silva",
                    "monto": 480.00,
                    "fecha": ahora
                }
            ]
        },
        {
            "id": 3,
            "abierta": True,
            "estado_moderacion": "Aprobada",
            "vendedor_id": vendedor_id,
            "vendedor_nombre": vendedor_nombre,
            "duracion_minutos": 120,
            "incremento_minimo": 10.0,
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
