import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient, DESCENDING
from bson import ObjectId

from backend.models import RolUsuario, AuctionStatus

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
# CÁLCULO DINÁMICO DE ESTADO SEGÚN FECHAS
# ============================================================================
def calcular_estado_por_fechas(start_date_str: str, end_date_str: str, estado_actual: str) -> str:
    """
    Calcula dinámicamente el estado de la subasta a partir de las fechas:
    - CANCELLED / SUSPENDED: Mantiene cancelación manual.
    - FINISHED: Mantiene el cierre manual aunque la fecha límite sea futura.
    - PROGRAMMED: Fecha actual < startDate.
    - ACTIVE: startDate <= Fecha actual <= endDate.
    - FINISHED: Fecha actual > endDate.
    """
    if estado_actual in [AuctionStatus.CANCELLED.value, "Cancelada", "SUSPENDED", "Rechazada"]:
        return AuctionStatus.CANCELLED.value

    # Si la subasta fue finalizada/cerrada explícitamente (por el dueño o un admin),
    # mantenemos ese estado aunque la fecha límite todavía no haya pasado.
    if estado_actual in [AuctionStatus.FINISHED.value, "Finalizada", "CERRADA"]:
        return AuctionStatus.FINISHED.value

    try:
        ahora = datetime.now()
        start = datetime.fromisoformat(start_date_str)
        end = datetime.fromisoformat(end_date_str)

        if ahora < start:
            return AuctionStatus.PROGRAMMED.value
        elif start <= ahora <= end:
            return AuctionStatus.ACTIVE.value
        else:
            return AuctionStatus.FINISHED.value
    except Exception:
        return estado_actual or AuctionStatus.ACTIVE.value


# ============================================================================
# FORMATEO DE SUBASTAS (ATRIBUTOS DE ESPECIFICACIÓN & COMPATIBILIDAD)
# ============================================================================
def _format_subasta(doc: dict) -> dict:
    if not doc:
        return None

    cfg = obtener_configuracion_global()
    inc_min = float(doc.get("startingPrice") or doc.get("minIncrement") or doc.get("incremento_minimo") or cfg["incremento_minimo"])

    title = doc.get("title") or doc.get("producto", {}).get("nombre") or "Subasta sin título"
    description = doc.get("description") or doc.get("producto", {}).get("descripcion") or ""
    starting_price = float(doc.get("startingPrice") or doc.get("producto", {}).get("precio_inicial") or 0.0)
    start_date = doc.get("startDate") or doc.get("creada_en") or datetime.now().isoformat()
    end_date = doc.get("endDate") or (datetime.fromisoformat(start_date) + timedelta(minutes=doc.get("duracion_minutos", 60))).isoformat()
    tags = [t.lower().strip() for t in doc.get("tags", []) if t.strip()]
    seller_id = doc.get("sellerId") or doc.get("userId") or doc.get("vendedor_id")
    seller_name = doc.get("sellerName") or doc.get("vendedor_nombre") or "Sin nombre"
    image_url = doc.get("imageUrl") or doc.get("producto", {}).get("imagen_url") or "/static/img/laptop.jpg"
    category = doc.get("category") or doc.get("producto", {}).get("categoria") or "General"

    # Determinar estado
    status_db = doc.get("status") or ("ACTIVE" if doc.get("abierta") else "FINISHED")
    calculated_status = calcular_estado_por_fechas(start_date, end_date, status_db)

    # Ofertas / Bids
    bids_raw = doc.get("bids") or doc.get("ofertas") or []
    sorted_bids = sorted(
        bids_raw,
        key=lambda x: (float(x.get("amount") or x.get("monto") or 0.0), str(x.get("createdAt") or x.get("fecha") or "")),
        reverse=True
    )

    current_price = float(sorted_bids[0].get("amount") or sorted_bids[0].get("monto")) if sorted_bids else starting_price
    leader_name = sorted_bids[0].get("bidderName") or sorted_bids[0].get("usuario_nombre") if sorted_bids else None
    leader_id = sorted_bids[0].get("bidderId") or sorted_bids[0].get("usuario_id") if sorted_bids else None

    # Normalizar historial
    historial = []
    for idx, b in enumerate(sorted_bids, 1):
        amt = float(b.get("amount") or b.get("monto") or 0.0)
        dt = b.get("createdAt") or b.get("fecha") or ""
        u_name = b.get("bidderName") or b.get("usuario_nombre") or "Participante"
        u_id = b.get("bidderId") or b.get("usuario_id")
        historial.append({
            "id": b.get("id", idx),
            "bidderId": u_id,
            "usuario_id": u_id,
            "bidderName": u_name,
            "usuario_nombre": u_name,
            "amount": amt,
            "monto": amt,
            "createdAt": dt,
            "fecha": dt
        })

    is_active = calculated_status == AuctionStatus.ACTIVE.value

    return {
        "id": doc.get("id", str(doc.get("_id"))),
        "mongo_id": str(doc.get("_id")),
        # Atributos solicitados
        "title": title,
        "description": description,
        "startingPrice": starting_price,
        "currentPrice": current_price,
        "startDate": start_date,
        "endDate": end_date,
        "tags": tags,
        "sellerId": seller_id,
        "userId": seller_id,  # Para comprobación estricta de propiedad auction.userId === currentUser.id
        "sellerName": seller_name,
        "status": calculated_status,
        "imageUrl": image_url,
        "category": category,
        "minIncrement": inc_min,
        "bids": historial,
        "highestBidder": leader_name,
        "totalBids": len(historial),
        # Compatibilidad con UI existente
        "abierta": is_active,
        "estado_moderacion": "Aprobada" if calculated_status in ["ACTIVE", "PROGRAMMED"] else calculated_status,
        "vendedor_id": seller_id,
        "vendedor_nombre": seller_name,
        "producto": {
            "id": doc.get("id", 1),
            "nombre": title,
            "descripcion": description,
            "categoria": category,
            "precio_inicial": starting_price,
            "imagen_url": image_url
        },
        "precio_actual": current_price,
        "incremento_minimo": inc_min,
        "puja_minima_sugerida": current_price + inc_min if historial else starting_price,
        "mayor_postor": leader_name,
        "total_ofertas": len(historial),
        "historial_ofertas": historial
    }


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
# GESTIÓN DE USUARIOS Y ROLES (RBAC & OWNERSHIP)
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
        "name": nombre.strip(),
        "nombre": nombre.strip(),
        "email": email_clean,
        "password_hash": password_hash,
        "rol": rol,
        "role": rol,
        "estado": "Activo",
        "status": "Active",
        "favoritos": [],
        "creado_en": ahora
    }
    db.usuarios.insert_one(doc)
    return {
        "id": user_id,
        "nombre": doc["nombre"],
        "name": doc["name"],
        "email": doc["email"],
        "rol": doc["rol"],
        "role": doc["role"],
        "estado": doc["estado"],
        "status": doc["status"],
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
        "nombre": doc.get("nombre") or doc.get("name"),
        "name": doc.get("name") or doc.get("nombre"),
        "email": doc.get("email"),
        "rol": doc.get("rol") or doc.get("role"),
        "role": doc.get("role") or doc.get("rol"),
        "estado": doc.get("estado", "Activo"),
        "status": doc.get("status", "Active"),
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
            "nombre": doc.get("nombre") or doc.get("name"),
            "name": doc.get("name") or doc.get("nombre"),
            "email": doc.get("email"),
            "rol": doc.get("rol") or doc.get("role"),
            "role": doc.get("role") or doc.get("rol"),
            "estado": doc.get("estado", "Activo"),
            "status": doc.get("status", "Active"),
            "favoritos_count": len(doc.get("favoritos", [])),
            "creado_en": doc.get("creado_en")
        })
    return res


def cambiar_estado_usuario(usuario_id: Any, nuevo_estado: str) -> Dict[str, Any]:
    if nuevo_estado not in ["Activo", "Suspendido", "Active", "Suspended"]:
        raise ValueError("Estado inválido. Debe ser 'Activo' o 'Suspendido'.")

    std_estado = "Suspendido" if nuevo_estado in ["Suspendido", "Suspended"] else "Activo"

    db = get_db()
    query = _parse_id_query(usuario_id)
    user = db.usuarios.find_one(query)
    if not user:
        raise ValueError("Usuario no encontrado.")

    if user.get("rol") == RolUsuario.ROLE_ADMIN.value or user.get("role") == RolUsuario.ROLE_ADMIN.value:
        raise ValueError("No está permitido suspender a la cuenta principal.")

    db.usuarios.update_one(query, {"$set": {"estado": std_estado, "status": std_estado}})
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
    db = get_db()
    query_conditions = []
    if usuario_id is not None:
        query_conditions.append({"bids.bidderId": usuario_id})
        query_conditions.append({"ofertas.usuario_id": usuario_id})
    if usuario_nombre:
        query_conditions.append({"bids.bidderName": usuario_nombre})
        query_conditions.append({"ofertas.usuario_nombre": usuario_nombre})

    if not query_conditions:
        return []

    cursor = db.subastas.find({"$or": query_conditions}).sort("id", -1)
    historial = []
    for doc in cursor:
        subasta_formateada = _format_subasta(doc)
        bids = doc.get("bids") or doc.get("ofertas") or []
        for oferta in bids:
            u_id = oferta.get("bidderId") or oferta.get("usuario_id")
            u_name = oferta.get("bidderName") or oferta.get("usuario_nombre")
            coincide = False
            if usuario_id is not None and str(u_id) == str(usuario_id):
                coincide = True
            elif usuario_nombre and u_name == usuario_nombre:
                coincide = True

            if coincide:
                amt = float(oferta.get("amount") or oferta.get("monto") or 0.0)
                dt = oferta.get("createdAt") or oferta.get("fecha")
                historial.append({
                    "subasta_id": subasta_formateada["id"],
                    "producto_nombre": subasta_formateada["title"],
                    "monto_puja": amt,
                    "fecha": dt,
                    "es_ganador_actual": subasta_formateada["highestBidder"] == u_name,
                    "precio_actual_subasta": subasta_formateada["currentPrice"],
                    "subasta_abierta": subasta_formateada["abierta"],
                    "status": subasta_formateada["status"]
                })
    historial.sort(key=lambda x: str(x.get("fecha", "")), reverse=True)
    return historial


# ============================================================================
# BÚSQUEDA AVANZADA, FILTROS POR TAGS Y PALABRAS CLAVE
# ============================================================================
def obtener_subastas(
    filtro_estado: Optional[str] = None,
    tag: Optional[str] = None,
    search: Optional[str] = None,
    solo_aprobadas: bool = True,
    seller_id: Optional[Any] = None
) -> List[Dict[str, Any]]:
    db = get_db()
    query: Dict[str, Any] = {}

    if seller_id is not None:
        try:
            seller_val = int(seller_id)
        except (ValueError, TypeError):
            seller_val = seller_id
        query["$or"] = [
            {"sellerId": seller_val},
            {"userId": seller_val},
            {"vendedor_id": seller_val}
        ]

    # Filtrar por Tag
    if tag and tag.strip():
        tag_clean = tag.strip().lower()
        if tag_clean != "todos":
            query["tags"] = tag_clean

    # Búsqueda por palabras clave en título, descripción y tags
    if search and search.strip():
        s = search.strip()
        search_or = [
            {"title": {"$regex": s, "$options": "i"}},
            {"description": {"$regex": s, "$options": "i"}},
            {"tags": {"$regex": s, "$options": "i"}},
            {"producto.nombre": {"$regex": s, "$options": "i"}},
            {"producto.descripcion": {"$regex": s, "$options": "i"}}
        ]
        if "$or" in query:
            query = {"$and": [{"$or": query["$or"]}, {"$or": search_or}]}
        else:
            query["$or"] = search_or

    cursor = db.subastas.find(query).sort("id", DESCENDING)
    subastas_formateadas = [_format_subasta(doc) for doc in cursor]

    # Filtrado por estado post-cálculo de fechas
    if filtro_estado:
        filtro_upper = filtro_estado.upper()
        if filtro_upper in ["ACTIVAS", "ACTIVE"]:
            subastas_formateadas = [s for s in subastas_formateadas if s["status"] == AuctionStatus.ACTIVE.value]
        elif filtro_upper in ["CERRADAS", "FINISHED"]:
            subastas_formateadas = [s for s in subastas_formateadas if s["status"] in [AuctionStatus.FINISHED.value, AuctionStatus.CANCELLED.value]]
        elif filtro_upper in ["PROGRAMMED", "PROGRAMADAS"]:
            subastas_formateadas = [s for s in subastas_formateadas if s["status"] == AuctionStatus.PROGRAMMED.value]
        elif filtro_upper in ["CANCELLED", "CANCELADAS"]:
            subastas_formateadas = [s for s in subastas_formateadas if s["status"] == AuctionStatus.CANCELLED.value]

    return subastas_formateadas


def obtener_subasta_por_id(subasta_id: Any) -> Optional[Dict[str, Any]]:
    db = get_db()
    query = _parse_id_query(subasta_id)
    doc = db.subastas.find_one(query)
    return _format_subasta(doc) if doc else None


# ============================================================================
# CREACIÓN DE SUBASTAS (CUALQUIER USUARIO REGISTRADO)
# ============================================================================
def crear_subasta(
    title: str,
    description: str,
    starting_price: float,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tags: Optional[List[str]] = None,
    duracion_minutos: int = 60,
    image_url: Optional[str] = None,
    category: str = "General",
    seller_id: Optional[Any] = None,
    seller_name: Optional[str] = None,
    incremento_minimo: Optional[float] = None
) -> Dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValueError("El título del producto no puede estar vacío.")

    if starting_price <= 0:
        raise ValueError("El precio inicial debe ser mayor a 0.")

    ahora = datetime.now()
    start_iso = start_date if start_date else ahora.isoformat()
    if end_date:
        end_iso = end_date
    else:
        end_iso = (ahora + timedelta(minutes=duracion_minutos)).isoformat()

    if not image_url or not image_url.strip():
        image_url = "/static/img/laptop.jpg"

    cfg = obtener_configuracion_global()
    inc = float(incremento_minimo) if incremento_minimo and incremento_minimo > 0 else cfg["incremento_minimo"]

    clean_tags = [t.strip().lower() for t in (tags or []) if t.strip()]

    status_calc = calcular_estado_por_fechas(start_iso, end_iso, AuctionStatus.ACTIVE.value)

    seq_id = get_next_sequence("subasta_id")

    doc = {
        "id": seq_id,
        "title": title,
        "description": description.strip(),
        "startingPrice": float(starting_price),
        "startDate": start_iso,
        "endDate": end_iso,
        "tags": clean_tags,
        "sellerId": seller_id,
        "userId": seller_id,  # Para cumplir auction.userId === currentUser.id
        "sellerName": seller_name or "Usuario",
        "status": status_calc,
        "imageUrl": image_url,
        "category": category or "General",
        "minIncrement": inc,
        "bids": [],
        "creada_en": ahora.isoformat(),
        # Compatibilidad
        "abierta": status_calc == AuctionStatus.ACTIVE.value,
        "producto": {
            "nombre": title,
            "descripcion": description,
            "categoria": category,
            "precio_inicial": float(starting_price),
            "imagen_url": image_url
        },
        "ofertas": []
    }

    db = get_db()
    db.subastas.insert_one(doc)
    return obtener_subasta_por_id(seq_id)


# ============================================================================
# AISLAMIENTO DE PROPIEDAD: EDICIÓN Y CANCELACIÓN (OWNERSHIP 403)
# ============================================================================
def verificar_propiedad_subasta(subasta: Dict[str, Any], current_user: Dict[str, Any]) -> bool:
    """Verifica si el usuario actual es el propietario de la subasta o administrador."""
    if current_user.get("rol") == RolUsuario.ROLE_ADMIN.value or current_user.get("role") == RolUsuario.ROLE_ADMIN.value:
        return True

    user_id = str(current_user.get("id"))
    seller_id = str(subasta.get("sellerId") or subasta.get("userId") or subasta.get("vendedor_id"))
    return user_id == seller_id


def editar_subasta(subasta_id: Any, current_user: Dict[str, Any], datos: Dict[str, Any]) -> Dict[str, Any]:
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    # Aislamiento de propiedad: solo el dueño o admin
    if not verificar_propiedad_subasta(subasta, current_user):
        raise PermissionError("Aislamiento de propiedad: No tienes autorización para editar una subasta ajena.")

    # Restricción: No editable si ya tiene ofertas
    if subasta["totalBids"] > 0:
        raise ValueError("No se puede editar una subasta que ya cuenta con ofertas/pujas registradas.")

    updates: Dict[str, Any] = {}
    if datos.get("title") or datos.get("nombre"):
        val = (datos.get("title") or datos.get("nombre")).strip()
        updates["title"] = val
        updates["producto.nombre"] = val
    if datos.get("description") or datos.get("descripcion"):
        val = (datos.get("description") or datos.get("descripcion")).strip()
        updates["description"] = val
        updates["producto.descripcion"] = val
    if datos.get("startingPrice") is not None or datos.get("precio_inicial") is not None:
        val = float(datos.get("startingPrice") or datos.get("precio_inicial"))
        updates["startingPrice"] = val
        updates["producto.precio_inicial"] = val
    if datos.get("startDate"):
        updates["startDate"] = datos["startDate"]
    if datos.get("endDate"):
        updates["endDate"] = datos["endDate"]
    if datos.get("tags") is not None:
        updates["tags"] = [t.strip().lower() for t in datos["tags"] if t.strip()]
    if datos.get("category") or datos.get("categoria"):
        val = datos.get("category") or datos.get("categoria")
        updates["category"] = val
        updates["producto.categoria"] = val
    if datos.get("imageUrl") or datos.get("imagen_url"):
        val = datos.get("imageUrl") or datos.get("imagen_url")
        updates["imageUrl"] = val
        updates["producto.imagen_url"] = val

    if updates:
        db = get_db()
        query = _parse_id_query(subasta_id)
        db.subastas.update_one(query, {"$set": updates})

    return obtener_subasta_por_id(subasta_id)


def cancelar_subasta(subasta_id: Any, current_user: Dict[str, Any]) -> Dict[str, Any]:
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    # Aislamiento de propiedad
    if not verificar_propiedad_subasta(subasta, current_user):
        raise PermissionError("Aislamiento de propiedad: No tienes autorización para cancelar una subasta ajena.")

    es_admin = current_user.get("rol") == RolUsuario.ROLE_ADMIN.value
    if subasta["totalBids"] > 0 and not es_admin:
        raise ValueError("No se puede cancelar una subasta que ya cuenta con ofertas registradas.")

    ahora = datetime.now().isoformat()
    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {
        "$set": {
            "status": AuctionStatus.CANCELLED.value,
            "abierta": False,
            "cerrada_en": ahora,
            "motivo_cancelacion": "Cancelada por el creador de la subasta" if not es_admin else "Cancelada desde administración"
        }
    })
    return obtener_subasta_por_id(subasta_id)


def cerrar_subasta(subasta_id: Any, current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Cierra formalmente una subasta y adjudica al mayor postor (dueño o admin)."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    # Aislamiento de propiedad
    if not verificar_propiedad_subasta(subasta, current_user):
        raise PermissionError("Aislamiento de propiedad: No tienes autorización para cerrar una subasta ajena.")

    if subasta["status"] == AuctionStatus.CANCELLED.value:
        raise ValueError("No es posible cerrar una subasta cancelada.")

    bids = subasta.get("bids") or []
    mayor = bids[0] if bids else None

    ahora = datetime.now().isoformat()
    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {
        "$set": {
            "status": AuctionStatus.FINISHED.value,
            "abierta": False,
            "cerrada_en": ahora,
            "ganador_id": (mayor.get("bidderId") if mayor else None),
            "ganador_nombre": (mayor.get("bidderName") if mayor else None),
            "monto_final": subasta["currentPrice"],
            "motivo_cierre": "Cerrada por el creador de la subasta"
        }
    })
    return obtener_subasta_por_id(subasta_id)

def registrar_oferta(subasta_id: Any, usuario_nombre: str, monto: float, usuario_id: Optional[Any] = None) -> Dict[str, Any]:
    usuario_nombre = usuario_nombre.strip() if usuario_nombre else "Participante"
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta especificada no existe.")

    if subasta["status"] != AuctionStatus.ACTIVE.value:
        raise ValueError(f"No es posible pujar: la subasta se encuentra en estado '{subasta['status']}'.")

    inc_min = subasta["minIncrement"]
    minimo_requerido = subasta["currentPrice"] + inc_min if subasta["totalBids"] > 0 else subasta["startingPrice"]

    if monto < minimo_requerido:
        raise ValueError(
            f"Puja no válida. La oferta mínima requerida es de ${minimo_requerido:.2f} (Precio actual: ${subasta['currentPrice']:.2f} + incremento mínimo de ${inc_min:.2f})."
        )

    nueva_oferta = {
        "id": subasta["totalBids"] + 1,
        "bidderId": usuario_id,
        "usuario_id": usuario_id,
        "bidderName": usuario_nombre,
        "usuario_nombre": usuario_nombre,
        "amount": float(monto),
        "monto": float(monto),
        "createdAt": datetime.now().isoformat(),
        "fecha": datetime.now().isoformat()
    }

    db = get_db()
    query = _parse_id_query(subasta_id)
    db.subastas.update_one(query, {
        "$push": {
            "bids": nueva_oferta,
            "ofertas": nueva_oferta
        }
    })

    return obtener_subasta_por_id(subasta_id)


# ============================================================================
# DASHBOARD DE ADMINISTRACIÓN Y MODERACIÓN
# ============================================================================
def obtener_dashboard_admin() -> Dict[str, Any]:
    db = get_db()
    total_usuarios = db.usuarios.count_documents({})

    all_subastas = obtener_subastas(filtro_estado=None, solo_aprobadas=False)

    activas = sum(1 for s in all_subastas if s["status"] == AuctionStatus.ACTIVE.value)
    finalizadas = sum(1 for s in all_subastas if s["status"] == AuctionStatus.FINISHED.value)
    programadas = sum(1 for s in all_subastas if s["status"] == AuctionStatus.PROGRAMMED.value)
    canceladas = sum(1 for s in all_subastas if s["status"] == AuctionStatus.CANCELLED.value)

    # Calcular volumen total pujado
    pipeline = [
        {"$unwind": "$bids"},
        {"$group": {
            "_id": None,
            "volumen": {"$sum": "$bids.amount"}
        }}
    ]
    agg = list(db.subastas.aggregate(pipeline))
    volumen = float(agg[0]["volumen"]) if agg else 0.0

    return {
        "metricas": {
            "total_usuarios": total_usuarios,
            "subastas_activas": activas,
            "subastas_finalizadas": finalizadas,
            "subastas_programadas": programadas,
            "subastas_canceladas": canceladas,
            "total_subastas": len(all_subastas),
            "volumen_total": round(volumen, 2)
        },
        "subastas": all_subastas,
        "usuarios": listar_usuarios()
    }


def moderar_subasta_admin(subasta_id: Any, nuevo_estado: str, motivo: Optional[str] = None) -> Dict[str, Any]:
    """Acciones administrativas: Aprobar, Suspender, Eliminar o cambio a estados estándar."""
    subasta = obtener_subasta_por_id(subasta_id)
    if not subasta:
        raise ValueError("La subasta no existe.")

    db = get_db()
    query = _parse_id_query(subasta_id)
    ahora = datetime.now().isoformat()

    accion_upper = nuevo_estado.upper()
    if accion_upper in ["APROBAR", "APPROVE", "ACTIVE"]:
        status_final = AuctionStatus.ACTIVE.value
        db.subastas.update_one(query, {
            "$set": {
                "status": status_final,
                "abierta": True,
                "motivo_moderacion": motivo or "Aprobada desde administración"
            }
        })
    elif accion_upper in ["SUSPENDER", "SUSPEND", "SUSPENDED", "CANCELLED", "CANCELAR"]:
        status_final = AuctionStatus.CANCELLED.value
        db.subastas.update_one(query, {
            "$set": {
                "status": status_final,
                "abierta": False,
                "cerrada_en": ahora,
                "motivo_moderacion": motivo or "Suspendida desde administración"
            }
        })
    elif accion_upper in ["FINALIZAR", "FORZARCIERRE", "FORZAR_CIERRE", "CERRAR", "FINISHED", "FINALIZADA"]:
        status_final = AuctionStatus.FINISHED.value
        bids = subasta.get("bids") or []
        mayor = bids[0] if bids else None
        db.subastas.update_one(query, {
            "$set": {
                "status": status_final,
                "abierta": False,
                "cerrada_en": ahora,
                "ganador_id": (mayor.get("bidderId") if mayor else None),
                "ganador_nombre": (mayor.get("bidderName") if mayor else None),
                "monto_final": subasta["currentPrice"],
                "motivo_moderacion": motivo or "Cerrada desde administración"
            }
        })
    elif accion_upper in ["ELIMINAR", "DELETE"]:
        db.subastas.delete_one(query)
        return {"id": subasta_id, "eliminada": True, "mensaje": "Subasta eliminada definitivamente."}
    else:
        status_final = accion_upper
        db.subastas.update_one(query, {
            "$set": {
                "status": status_final,
                "motivo_moderacion": motivo or f"Estado modificado a {status_final}"
            }
        })

    return obtener_subasta_por_id(subasta_id)


def metricas_globales() -> Dict[str, Any]:
    db = get_db()
    all_subastas = obtener_subastas(filtro_estado=None, solo_aprobadas=True)
    activas = sum(1 for s in all_subastas if s["status"] == AuctionStatus.ACTIVE.value)

    pipeline = [
        {"$unwind": "$bids"},
        {"$group": {
            "_id": None,
            "total_ofertas": {"$sum": 1},
            "volumen": {"$sum": "$bids.amount"}
        }}
    ]
    agg = list(db.subastas.aggregate(pipeline))
    total_ofertas = agg[0]["total_ofertas"] if agg else 0
    volumen = float(agg[0]["volumen"]) if agg else 0.0

    return {
        "total_subastas": len(all_subastas),
        "subastas_activas": activas,
        "total_ofertas": total_ofertas,
        "volumen_total": round(volumen, 2)
    }


# ============================================================================
# INICIALIZACIÓN Y SEMILLA DE DATOS MOCK
# ============================================================================
def init_db():
    db = get_db()
    db.subastas.create_index("id", unique=True)
    db.subastas.create_index("tags")
    db.usuarios.create_index("email", unique=True)
    db.usuarios.create_index("id", unique=True)
    db.roles.create_index("nombre", unique=True)

    # 1. Catálogo de roles
    roles_def = [
        {"nombre": RolUsuario.ROLE_GUEST.value, "descripcion": "Visitante no autenticado", "nivel": 0},
        {"nombre": RolUsuario.ROLE_BUYER.value, "descripcion": "Comprador con permisos de puja y favoritos", "nivel": 1},
        {"nombre": RolUsuario.ROLE_SELLER.value, "descripcion": "Vendedor con permisos de creación y gestión", "nivel": 2},
        {"nombre": RolUsuario.ROLE_ADMIN.value, "descripcion": "Administrador con control total /admin/*", "nivel": 3},
    ]
    for r in roles_def:
        db.roles.update_one({"nombre": r["nombre"]}, {"$set": r}, upsert=True)

    # 2. Configuración global
    obtener_configuracion_global()

    # 3. Semilla automática y silenciosa: puebla únicamente las colecciones vacías
    if db.usuarios.count_documents({}) == 0:
        seed_usuarios()
    if db.subastas.count_documents({}) == 0:
        seed_subastas()


def seed_database():
    """Regenera por completo los datos de prueba (seed manual forzado)."""
    seed_usuarios()
    seed_subastas()


def seed_usuarios():
    """Inserta los usuarios de prueba si la colección está vacía (semilla silenciosa)."""
    from backend.auth import hash_password
    db = get_db()

    # Usuarios de prueba requeridos: 1 Admin + 2 Vendedores + 2 Compradores (5 usuarios)
    usuarios_mock = [
        {
            "id": 1,
            "name": "Andrés",
            "nombre": "Andrés",
            "email": "admin@subastas.com",
            "password_hash": hash_password("admin123"),
            "rol": RolUsuario.ROLE_ADMIN.value,
            "role": RolUsuario.ROLE_ADMIN.value,
            "estado": "Activo",
            "status": "Active",
            "favoritos": [1, 3],
            "creado_en": datetime.now().isoformat()
        },
        {
            "id": 2,
            "name": "Carlos",
            "nombre": "Carlos",
            "email": "carlos@subastas.com",
            "password_hash": hash_password("carlos123"),
            "rol": RolUsuario.ROLE_SELLER.value,
            "role": RolUsuario.ROLE_SELLER.value,
            "estado": "Activo",
            "status": "Active",
            "favoritos": [],
            "creado_en": datetime.now().isoformat()
        },
        {
            "id": 3,
            "name": "Ana",
            "nombre": "Ana",
            "email": "ana@subastas.com",
            "password_hash": hash_password("ana123"),
            "rol": RolUsuario.ROLE_BUYER.value,
            "role": RolUsuario.ROLE_BUYER.value,
            "estado": "Activo",
            "status": "Active",
            "favoritos": [1, 2, 4],
            "creado_en": datetime.now().isoformat()
        },
        {
            "id": 4,
            "name": "Mateo",
            "nombre": "Mateo",
            "email": "mateo@subastas.com",
            "password_hash": hash_password("mateo123"),
            "rol": RolUsuario.ROLE_BUYER.value,
            "role": RolUsuario.ROLE_BUYER.value,
            "estado": "Activo",
            "status": "Active",
            "favoritos": [2, 6],
            "creado_en": datetime.now().isoformat()
        },
        {
            "id": 5,
            "name": "Lucía",
            "nombre": "Lucía",
            "email": "lucia@subastas.com",
            "password_hash": hash_password("lucia123"),
            "rol": RolUsuario.ROLE_SELLER.value,
            "role": RolUsuario.ROLE_SELLER.value,
            "estado": "Activo",
            "status": "Active",
            "favoritos": [1, 5],
            "creado_en": datetime.now().isoformat()
        }
    ]

    db.usuarios.delete_many({})
    for u in usuarios_mock:
        db.usuarios.update_one({"email": u["email"]}, {"$set": u}, upsert=True)
    db.counters.update_one({"_id": "usuario_id"}, {"$set": {"seq": 5}}, upsert=True)


def seed_subastas():
    """Inserta las subastas de prueba si la colección está vacía (semilla silenciosa)."""
    db = get_db()

    # 8 Subastas de prueba con tags, fechas y diferentes estados
    ahora = datetime.now()
    subastas_mock = [
        {
            "id": 1,
            "title": "Edición Antigua de Don Quijote (1890)",
            "description": "Tomo de lujo con encuadernación en piel y grabados originales en excelente estado.",
            "startingPrice": 220.00,
            "startDate": (ahora - timedelta(days=2)).isoformat(),
            "endDate": (ahora + timedelta(days=3)).isoformat(),
            "tags": ["libros", "coleccion", "antiguedades", "literatura"],
            "sellerId": 2,
            "userId": 2,
            "sellerName": "Carlos",
            "status": AuctionStatus.ACTIVE.value,
            "imageUrl": "/static/img/laptop.jpg",
            "category": "Libros",
            "minIncrement": 15.00,
            "bids": [
                {"id": 1, "bidderId": 3, "bidderName": "Ana", "amount": 250.00, "createdAt": (ahora - timedelta(days=1)).isoformat()},
                {"id": 2, "bidderId": 4, "bidderName": "Mateo", "amount": 280.00, "createdAt": (ahora - timedelta(hours=4)).isoformat()}
            ],
            "creada_en": (ahora - timedelta(days=2)).isoformat()
        },
        {
            "id": 2,
            "title": "MacBook Pro M3 Max 64GB 1TB",
            "description": "Portátil Apple Silicon de alto rendimiento, pantalla Liquid Retina XDR de 16 pulgadas.",
            "startingPrice": 1800.00,
            "startDate": (ahora - timedelta(days=1)).isoformat(),
            "endDate": (ahora + timedelta(days=5)).isoformat(),
            "tags": ["tecnologia", "electronica", "computacion", "apple"],
            "sellerId": 2,
            "userId": 2,
            "sellerName": "Carlos",
            "status": AuctionStatus.ACTIVE.value,
            "imageUrl": "/static/img/laptop.jpg",
            "category": "Tecnología",
            "minIncrement": 50.00,
            "bids": [
                {"id": 1, "bidderId": 3, "bidderName": "Ana", "amount": 1900.00, "createdAt": (ahora - timedelta(hours=12)).isoformat()}
            ],
            "creada_en": (ahora - timedelta(days=1)).isoformat()
        },
        {
            "id": 3,
            "title": "Óleo Sobre Lienzo: Paisaje Andino",
            "description": "Obra original certificada de maestro andino contemporáneo, marco tallado a mano.",
            "startingPrice": 450.00,
            "startDate": (ahora - timedelta(hours=8)).isoformat(),
            "endDate": (ahora + timedelta(days=4)).isoformat(),
            "tags": ["arte", "pintura", "coleccion", "decoracion"],
            "sellerId": 5,
            "userId": 5,
            "sellerName": "Lucía",
            "status": AuctionStatus.ACTIVE.value,
            "imageUrl": "/static/img/reloj.jpg",
            "category": "Arte",
            "minIncrement": 25.00,
            "bids": [],
            "creada_en": (ahora - timedelta(hours=8)).isoformat()
        },
        {
            "id": 4,
            "title": "Reloj Cronógrafo Suizo Speedmaster",
            "description": "Cronómetro mecánico automático con caja en acero quirúrgico y cristal de zafiro.",
            "startingPrice": 600.00,
            "startDate": (ahora - timedelta(days=3)).isoformat(),
            "endDate": (ahora + timedelta(days=2)).isoformat(),
            "tags": ["relojes", "coleccion", "lujo", "joyeria"],
            "sellerId": 2,
            "userId": 2,
            "sellerName": "Carlos",
            "status": AuctionStatus.ACTIVE.value,
            "imageUrl": "/static/img/reloj.jpg",
            "category": "Coleccionables",
            "minIncrement": 20.00,
            "bids": [
                {"id": 1, "bidderId": 4, "bidderName": "Mateo", "amount": 650.00, "createdAt": (ahora - timedelta(days=2)).isoformat()},
                {"id": 2, "bidderId": 3, "bidderName": "Ana", "amount": 700.00, "createdAt": (ahora - timedelta(days=1)).isoformat()}
            ],
            "creada_en": (ahora - timedelta(days=3)).isoformat()
        },
        {
            "id": 5,
            "title": "Cámara Clásica Leica M6 Rangefinder 35mm",
            "description": "Cámara analógica mítica para fotógrafos documentalistas. Incluye lente Summicron 50mm f/2.",
            "startingPrice": 1200.00,
            "startDate": (ahora + timedelta(days=1)).isoformat(),  # Futuro -> PROGRAMMED
            "endDate": (ahora + timedelta(days=7)).isoformat(),
            "tags": ["fotografia", "coleccion", "electronica", "vintage"],
            "sellerId": 5,
            "userId": 5,
            "sellerName": "Lucía",
            "status": AuctionStatus.PROGRAMMED.value,
            "imageUrl": "/static/img/auriculares.jpg",
            "category": "Fotografía",
            "minIncrement": 50.00,
            "bids": [],
            "creada_en": ahora.isoformat()
        },
        {
            "id": 6,
            "title": "Primera Edición Cien Años de Soledad (1967)",
            "description": "Editorial Sudamericana de Buenos Aires con portada ilustrada original. Pieza de museo.",
            "startingPrice": 950.00,
            "startDate": (ahora + timedelta(days=2)).isoformat(),  # Futuro -> PROGRAMMED
            "endDate": (ahora + timedelta(days=8)).isoformat(),
            "tags": ["libros", "literatura", "coleccion", "antiguedades"],
            "sellerId": 2,
            "userId": 2,
            "sellerName": "Carlos",
            "status": AuctionStatus.PROGRAMMED.value,
            "imageUrl": "/static/img/laptop.jpg",
            "category": "Libros",
            "minIncrement": 30.00,
            "bids": [],
            "creada_en": ahora.isoformat()
        },
        {
            "id": 7,
            "title": "Consola Retro Nintendo NES en Caja Original",
            "description": "Sistema completo con manuales, dos mandos originales y cartucho Super Mario Bros / Duck Hunt.",
            "startingPrice": 300.00,
            "startDate": (ahora - timedelta(days=7)).isoformat(),
            "endDate": (ahora - timedelta(days=1)).isoformat(),  # Pasado -> FINISHED
            "tags": ["videojuegos", "coleccion", "retro", "electronica"],
            "sellerId": 2,
            "userId": 2,
            "sellerName": "Carlos",
            "status": AuctionStatus.FINISHED.value,
            "imageUrl": "/static/img/auriculares.jpg",
            "category": "Videojuegos",
            "minIncrement": 10.00,
            "bids": [
                {"id": 1, "bidderId": 3, "bidderName": "Ana", "amount": 340.00, "createdAt": (ahora - timedelta(days=4)).isoformat()},
                {"id": 2, "bidderId": 4, "bidderName": "Mateo", "amount": 390.00, "createdAt": (ahora - timedelta(days=2)).isoformat()}
            ],
            "creada_en": (ahora - timedelta(days=7)).isoformat()
        },
        {
            "id": 8,
            "title": "Drone Profesional DJI Mavic 3 Pro Cine",
            "description": "Sistema de triple cámara Hasselblad con soporte Apple ProRes y sensores omnidireccionales.",
            "startingPrice": 1400.00,
            "startDate": (ahora - timedelta(hours=10)).isoformat(),
            "endDate": (ahora + timedelta(days=6)).isoformat(),
            "tags": ["tecnologia", "drones", "fotografia", "electronica"],
            "sellerId": 5,
            "userId": 5,
            "sellerName": "Lucía",
            "status": AuctionStatus.ACTIVE.value,
            "imageUrl": "/static/img/auriculares.jpg",
            "category": "Tecnología",
            "minIncrement": 50.00,
            "bids": [],
            "creada_en": (ahora - timedelta(hours=10)).isoformat()
        }
    ]

    # Limpiar y regenerar subastas para seed limpio
    db.subastas.delete_many({})
    db.subastas.insert_many(subastas_mock)
    db.counters.update_one({"_id": "subasta_id"}, {"$set": {"seq": 8}}, upsert=True)
