/**
 * Script de Inicialización y Seed en MongoDB (Suba)
 * Puede ejecutarse con mongosh o Node.js
 * mongosh mongodb://localhost:27017/sistema_subastas seed.js
 */

const dbName = "sistema_subastas";
const conn = new Mongo("mongodb://localhost:27017");
const db = conn.getDB(dbName);

// Genera hashes PBKDF2-HMAC-SHA256 compatibles con backend/auth.py (formato: salt_hex$hash_hex)
const crypto = require("crypto");
function hashPassword(password) {
  const salt = crypto.randomBytes(16).toString("hex");
  const dk = crypto.pbkdf2Sync(password, salt, 100000, 32, "sha256").toString("hex");
  return `${salt}$${dk}`;
}

print("=== INICIANDO SEED MONGODB (SUBA) ===");

// 1. Roles
db.roles.deleteMany({});
db.roles.insertMany([
  { nombre: "ROLE_GUEST", descripcion: "Visitante no autenticado", nivel: 0 },
  { nombre: "ROLE_BUYER", descripcion: "Comprador con capacidad de puja y favoritos", nivel: 1 },
  { nombre: "ROLE_SELLER", descripcion: "Vendedor con capacidad de publicación y panel", nivel: 2 },
  { nombre: "ROLE_ADMIN", descripcion: "Administrador con control total /admin/*", nivel: 3 }
]);

// 2. Parámetros Globales
db.configuracion.updateOne(
  { _id: "global_config" },
  { $set: { incremento_minimo: 10.0, comision_porcentaje: 5.0, actualizado_en: new Date().toISOString() } },
  { upsert: true }
);

// 3. Usuarios de prueba (1 administrador, 2 vendedores, 2 compradores)
//    Contraseñas reales: admin123, carlos123, lucia123, ana123, mateo123
db.usuarios.deleteMany({});
db.usuarios.insertMany([
  {
    id: 1,
    name: "Andrés",
    nombre: "Andrés",
    email: "admin@subastas.com",
    password_hash: hashPassword("admin123"),
    rol: "ROLE_ADMIN",
    role: "ROLE_ADMIN",
    estado: "Activo",
    status: "Active",
    favoritos: [1, 3],
    creado_en: new Date().toISOString()
  },
  {
    id: 2,
    name: "Carlos",
    nombre: "Carlos",
    email: "carlos@subastas.com",
    password_hash: hashPassword("carlos123"),
    rol: "ROLE_SELLER",
    role: "ROLE_SELLER",
    estado: "Activo",
    status: "Active",
    favoritos: [],
    creado_en: new Date().toISOString()
  },
  {
    id: 3,
    name: "Ana",
    nombre: "Ana",
    email: "ana@subastas.com",
    password_hash: hashPassword("ana123"),
    rol: "ROLE_BUYER",
    role: "ROLE_BUYER",
    estado: "Activo",
    status: "Active",
    favoritos: [1, 2, 4],
    creado_en: new Date().toISOString()
  },
  {
    id: 4,
    name: "Mateo",
    nombre: "Mateo",
    email: "mateo@subastas.com",
    password_hash: hashPassword("mateo123"),
    rol: "ROLE_BUYER",
    role: "ROLE_BUYER",
    estado: "Activo",
    status: "Active",
    favoritos: [2, 6],
    creado_en: new Date().toISOString()
  },
  {
    id: 5,
    name: "Lucía",
    nombre: "Lucía",
    email: "lucia@subastas.com",
    password_hash: hashPassword("lucia123"),
    rol: "ROLE_SELLER",
    role: "ROLE_SELLER",
    estado: "Activo",
    status: "Active",
    favoritos: [1, 5],
    creado_en: new Date().toISOString()
  }
]);

// 4. Subastas de prueba con diferentes fechas, estados y etiquetas
const ahora = new Date();
const haceDosDias = new Date(ahora.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString();
const enTresDias = new Date(ahora.getTime() + 3 * 24 * 60 * 60 * 1000).toISOString();
const enUnaSemana = new Date(ahora.getTime() + 7 * 24 * 60 * 60 * 1000).toISOString();
const haceUnaSemana = new Date(ahora.getTime() - 7 * 24 * 60 * 60 * 1000).toISOString();
const ayer = new Date(ahora.getTime() - 1 * 24 * 60 * 60 * 1000).toISOString();
const manana = new Date(ahora.getTime() + 1 * 24 * 60 * 60 * 1000).toISOString();

db.subastas.deleteMany({});
db.subastas.insertMany([
  {
    id: 1,
    title: "Edición Antigua de Don Quijote (1890)",
    description: "Tomo de lujo con encuadernación en piel y grabados originales en excelente estado.",
    startingPrice: 220.00,
    startDate: haceDosDias,
    endDate: enTresDias,
    tags: ["libros", "coleccion", "antiguedades", "literatura"],
    sellerId: 2,
    userId: 2,
    sellerName: "Carlos",
    status: "ACTIVE",
    imageUrl: "/static/img/laptop.jpg",
    category: "Libros",
    minIncrement: 15.00,
    bids: [
      { id: 1, bidderId: 3, bidderName: "Ana", amount: 250.00, createdAt: ayer },
      { id: 2, bidderId: 4, bidderName: "Mateo", amount: 280.00, createdAt: ahora.toISOString() }
    ],
    creada_en: haceDosDias
  },
  {
    id: 2,
    title: "MacBook Pro M3 Max 64GB 1TB",
    description: "Portátil Apple Silicon de alto rendimiento, pantalla Liquid Retina XDR de 16 pulgadas.",
    startingPrice: 1800.00,
    startDate: ayer,
    endDate: enTresDias,
    tags: ["tecnologia", "electronica", "computacion", "apple"],
    sellerId: 2,
    userId: 2,
    sellerName: "Carlos",
    status: "ACTIVE",
    imageUrl: "/static/img/laptop.jpg",
    category: "Tecnología",
    minIncrement: 50.00,
    bids: [
      { id: 1, bidderId: 3, bidderName: "Ana", amount: 1900.00, createdAt: ahora.toISOString() }
    ],
    creada_en: ayer
  },
  {
    id: 3,
    title: "Óleo Sobre Lienzo: Paisaje Andino",
    description: "Obra original certificada de maestro andino contemporáneo, marco tallado a mano.",
    startingPrice: 450.00,
    startDate: ayer,
    endDate: enTresDias,
    tags: ["arte", "pintura", "coleccion", "decoracion"],
    sellerId: 5,
    userId: 5,
    sellerName: "Lucía",
    status: "ACTIVE",
    imageUrl: "/static/img/reloj.jpg",
    category: "Arte",
    minIncrement: 25.00,
    bids: [],
    creada_en: ayer
  },
  {
    id: 4,
    title: "Reloj Cronógrafo Suizo Speedmaster",
    description: "Cronómetro mecánico automático con caja en acero quirúrgico y cristal de zafiro.",
    startingPrice: 600.00,
    startDate: haceDosDias,
    endDate: enTresDias,
    tags: ["relojes", "coleccion", "lujo", "joyeria"],
    sellerId: 2,
    userId: 2,
    sellerName: "Carlos",
    status: "ACTIVE",
    imageUrl: "/static/img/reloj.jpg",
    category: "Coleccionables",
    minIncrement: 20.00,
    bids: [
      { id: 1, bidderId: 4, bidderName: "Mateo", amount: 650.00, createdAt: haceDosDias },
      { id: 2, bidderId: 3, bidderName: "Ana", amount: 700.00, createdAt: ayer }
    ],
    creada_en: haceDosDias
  },
  {
    id: 5,
    title: "Cámara Clásica Leica M6 Rangefinder 35mm",
    description: "Cámara analógica mítica para fotógrafos documentalistas. Incluye lente Summicron 50mm f/2.",
    startingPrice: 1200.00,
    startDate: manana,
    endDate: enUnaSemana,
    tags: ["fotografia", "coleccion", "electronica", "vintage"],
    sellerId: 5,
    userId: 5,
    sellerName: "Lucía",
    status: "PROGRAMMED",
    imageUrl: "/static/img/auriculares.jpg",
    category: "Fotografía",
    minIncrement: 50.00,
    bids: [],
    creada_en: ahora.toISOString()
  },
  {
    id: 6,
    title: "Primera Edición Cien Años de Soledad (1967)",
    description: "Editorial Sudamericana de Buenos Aires con portada ilustrada original. Pieza de museo.",
    startingPrice: 950.00,
    startDate: manana,
    endDate: enUnaSemana,
    tags: ["libros", "literatura", "coleccion", "antiguedades"],
    sellerId: 2,
    userId: 2,
    sellerName: "Carlos",
    status: "PROGRAMMED",
    imageUrl: "/static/img/laptop.jpg",
    category: "Libros",
    minIncrement: 30.00,
    bids: [],
    creada_en: ahora.toISOString()
  },
  {
    id: 7,
    title: "Consola Retro Nintendo NES en Caja Original",
    description: "Sistema completo con manuales, dos mandos originales y cartucho Super Mario Bros / Duck Hunt.",
    startingPrice: 300.00,
    startDate: haceUnaSemana,
    endDate: ayer,
    tags: ["videojuegos", "coleccion", "retro", "electronica"],
    sellerId: 2,
    userId: 2,
    sellerName: "Carlos",
    status: "FINISHED",
    imageUrl: "/static/img/auriculares.jpg",
    category: "Videojuegos",
    minIncrement: 10.00,
    bids: [
      { id: 1, bidderId: 3, bidderName: "Ana", amount: 340.00, createdAt: haceDosDias },
      { id: 2, bidderId: 4, bidderName: "Mateo", amount: 390.00, createdAt: ayer }
    ],
    creada_en: haceUnaSemana
  },
  {
    id: 8,
    title: "Drone Profesional DJI Mavic 3 Pro Cine",
    description: "Sistema de triple cámara Hasselblad con soporte Apple ProRes y sensores omnidireccionales.",
    startingPrice: 1400.00,
    startDate: ayer,
    endDate: enUnaSemana,
    tags: ["tecnologia", "drones", "fotografia", "electronica"],
    sellerId: 5,
    userId: 5,
    sellerName: "Lucía",
    status: "ACTIVE",
    imageUrl: "/static/img/auriculares.jpg",
    category: "Tecnología",
    minIncrement: 50.00,
    bids: [],
    creada_en: ayer
  }
]);

db.counters.updateOne({ _id: "subasta_id" }, { $set: { seq: 8 } }, { upsert: true });
db.counters.updateOne({ _id: "usuario_id" }, { $set: { seq: 5 } }, { upsert: true });

print("=== SEED COMPLETADO CON ÉXITO ===");
