/**
 * Suba Frontend Client
 */

// ============================================================================
// ESTADO GLOBAL DE LA APLICACIÓN
// ============================================================================
let auctions = [];
let activeFilter = 'todas';
let activeTag = '';
let currentSearch = '';
let activeTab = 'catalogo';
let activeAuctionForBid = null;
let pollInterval = null;

// Objeto de usuario actual y token (almacenado en localStorage)
let authState = {
    token: localStorage.getItem('subastahub_token') || null,
    user: JSON.parse(localStorage.getItem('subastahub_user') || 'null') || {
        id: null,
        nombre: 'Visitante',
        email: null,
        rol: 'ROLE_GUEST',
        estado: 'Activo'
    }
};

// Nombres de estado de subasta visibles (todo en español)
const STATUS_LABELS = {
    PROGRAMMED: 'Programada',
    ACTIVE: 'Activa',
    FINISHED: 'Finalizada',
    CANCELLED: 'Cancelada'
};

function nombreEstado(status) {
    return STATUS_LABELS[(status || '').toUpperCase()] || (status || 'Sin estado');
}

// ============================================================================
// CLIENTE API HTTP CON AUTORIZACIÓN AUTOMÁTICA
// ============================================================================
async function apiFetch(url, options = {}) {
    options.headers = options.headers || {};
    if (authState.token) {
        options.headers['Authorization'] = `Bearer ${authState.token}`;
    }
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(options.body);
    }

    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
        const errorMsg = data.detail || data.mensaje || `Error en la petición HTTP (${res.status})`;
        throw new Error(errorMsg);
    }
    return data;
}

// ============================================================================
// INICIALIZACIÓN
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    initAuthUI();
    fetchMetrics();
    fetchAuctions();
    setupEventListeners();

    // Ruta directa /admin/dashboard: abre el panel administrativo si el usuario es administrador
    if (window.location.pathname.replace(/\/$/, '') === '/admin/dashboard' && authState.user.rol === 'ROLE_ADMIN') {
        switchTab('panel-admin');
    }

    // Actualización automática cada 5 segundos de métricas y catálogo
    pollInterval = setInterval(() => {
        if (activeTab === 'catalogo') {
            fetchMetrics(true);
            fetchAuctions(true);
        }
    }, 5000);
});

// ============================================================================
// GESTIÓN DE ROLES & AUTENTICACIÓN
// ============================================================================
function initAuthUI() {
    updateUserWidget();
    updateRBACVisibility();
    updateRoleContextBanner();
}

function updateUserWidget() {
    const badge = document.getElementById('user-role-badge');
    const authBtn = document.getElementById('btn-auth-action');
    const rol = authState.user.rol;

    badge.className = `role-badge role-${rol.replace('ROLE_', '').toLowerCase()}`;
    badge.textContent = authState.token ? authState.user.nombre : '';
    badge.classList.toggle('hidden', !authState.token);

    if (authState.token) {
        authBtn.textContent = 'Cerrar Sesión';
        authBtn.onclick = logoutUser;
    } else {
        authBtn.textContent = 'Iniciar Sesión';
        authBtn.onclick = () => openModal('modal-auth');
    }
}

function updateRBACVisibility() {
    const rol = authState.user.rol;
    const isBuyerOrHigher = ['ROLE_BUYER', 'ROLE_SELLER', 'ROLE_ADMIN'].includes(rol);
    const isAdmin = rol === 'ROLE_ADMIN';

    // Tabs según permisos de la matriz RBAC
    toggleElement('tab-favoritos', isBuyerOrHigher);
    toggleElement('tab-mis-pujas', isBuyerOrHigher);
    toggleElement('tab-panel-vendedor', isBuyerOrHigher);
    toggleElement('tab-panel-admin', isAdmin);

    // Cualquier usuario registrado puede publicar y administrar sus propias subastas
    toggleElement('btn-open-create-modal', isBuyerOrHigher);
}

function updateRoleContextBanner() {
    const banner = document.getElementById('role-context-text');
    if (!banner) return;

    if (authState.token) {
        banner.innerHTML = `<strong>Hola, ${authState.user.nombre}</strong> — Explora el catálogo y gestiona tu actividad en la plataforma.`;
    } else {
        banner.innerHTML = '<strong>Bienvenido a Suba</strong> — Explora el catálogo. Inicia sesión para pujar, guardar favoritos o publicar tus artículos.';
    }
}

function toggleElement(id, visible) {
    const el = document.getElementById(id);
    if (!el) return;
    if (visible) el.classList.remove('hidden');
    else el.classList.add('hidden');
}

async function loginUser(email, password) {
    try {
        const data = await apiFetch('/api/auth/login', {
            method: 'POST',
            body: { email, password }
        });
        authState.token = data.token;
        authState.user = data.usuario;
        localStorage.setItem('subastahub_token', data.token);
        localStorage.setItem('subastahub_user', JSON.stringify(data.usuario));

        closeModal('modal-auth');
        initAuthUI();
        showToast(data.mensaje, 'success');

        // Refrescar vista
        switchTab('catalogo');
        fetchAuctions();
        fetchMetrics();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function logoutUser() {
    authState.token = null;
    authState.user = {
        id: null,
        nombre: 'Visitante',
        email: null,
        rol: 'ROLE_GUEST',
        estado: 'Activo'
    };
    localStorage.removeItem('subastahub_token');
    localStorage.removeItem('subastahub_user');

    initAuthUI();
    switchTab('catalogo');
    showToast('Sesión cerrada.', 'info');
    fetchAuctions();
}

// ============================================================================
// CARGA DE DATOS & MÉTRICAS
// ============================================================================
async function fetchMetrics(silent = false) {
    try {
        const data = await apiFetch('/api/metricas');
        document.getElementById('stat-total-subastas').textContent = data.total_subastas;
        document.getElementById('stat-activas').textContent = data.subastas_activas;
        document.getElementById('stat-ofertas').textContent = data.total_ofertas;
        document.getElementById('stat-volumen').textContent = `$${data.volumen_total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    } catch (err) {
        if (!silent) console.error('Error al cargar métricas:', err);
    }
}

async function fetchAuctions(silent = false) {
    try {
        auctions = await apiFetch('/api/subastas');
        if (activeTab === 'catalogo') {
            renderAuctionsGrid(auctions);
        }
    } catch (err) {
        if (!silent) showToast(err.message, 'error');
    }
}

// ============================================================================
// GESTIÓN DE PESTAÑAS Y VISTAS
// ============================================================================
const tabButtons = document.querySelectorAll('.nav-tab-btn');
tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        const targetTab = btn.getAttribute('data-tab');
        switchTab(targetTab);
    });
});

function switchTab(tab) {
    activeTab = tab;
    tabButtons.forEach(b => {
        if (b.getAttribute('data-tab') === tab) b.classList.add('active');
        else b.classList.remove('active');
    });

    const grid = document.getElementById('auctions-grid');
    const controls = document.getElementById('controls-bar');
    const customView = document.getElementById('custom-view-container');
    const empty = document.getElementById('empty-state');
    empty.classList.add('hidden');

    if (tab === 'catalogo') {
        controls.classList.remove('hidden');
        grid.classList.remove('hidden');
        customView.classList.add('hidden');
        renderAuctionsGrid(auctions);
    } else {
        controls.classList.add('hidden');
        grid.classList.add('hidden');
        customView.classList.remove('hidden');

        if (tab === 'favoritos') loadFavoritosView();
        else if (tab === 'mis-pujas') loadMisPujasView();
        else if (tab === 'panel-vendedor') loadPanelVendedorView();
        else if (tab === 'panel-admin') loadPanelAdminView();
    }
}

// ============================================================================
// RENDERIZADO DEL CATÁLOGO GENERAL
// ============================================================================
function renderAuctionsGrid(lista) {
    const grid = document.getElementById('auctions-grid');
    const empty = document.getElementById('empty-state');

    let filtered = lista.filter(item => {
        const st = (item.status || '').toUpperCase();
        if (activeFilter === 'activas' && st !== 'ACTIVE') return false;
        if (activeFilter === 'programadas' && st !== 'PROGRAMMED') return false;
        if (activeFilter === 'cerradas' && !['FINISHED', 'CANCELLED'].includes(st)) return false;

        // Filtro por etiqueta (tag)
        if (activeTag) {
            const tags = (item.tags || []).map(t => t.toLowerCase());
            if (!tags.includes(activeTag.toLowerCase())) return false;
        }

        if (currentSearch) {
            const query = currentSearch.toLowerCase();
            const tagsText = (item.tags || []).join(' ').toLowerCase();
            const matchName = (item.title || item.producto.nombre || '').toLowerCase().includes(query);
            const matchCat = (item.producto.categoria || '').toLowerCase().includes(query);
            const matchDesc = (item.producto.descripcion || '').toLowerCase().includes(query);
            const matchTags = tagsText.includes(query);
            const matchSeller = (item.sellerName || item.vendedor_nombre || '').toLowerCase().includes(query);
            return matchName || matchCat || matchDesc || matchTags || matchSeller;
        }
        return true;
    });

    if (filtered.length === 0) {
        grid.innerHTML = '';
        empty.classList.remove('hidden');
        return;
    }

    empty.classList.add('hidden');
    const userFavs = authState.user.favoritos || [];
    const rol = authState.user.rol;
    const canBid = ['ROLE_BUYER', 'ROLE_SELLER', 'ROLE_ADMIN'].includes(rol);
    const canFav = canBid;

    grid.innerHTML = filtered.map(item => {
        const st = (item.status || '').toUpperCase();
        const isActiva = st === 'ACTIVE';
        const statusLabels = {
            ACTIVE: `<span class="badge badge-active">Activa</span>`,
            PROGRAMMED: `<span class="badge badge-programmed">Programada</span>`,
            FINISHED: `<span class="badge badge-closed">Finalizada</span>`,
            CANCELLED: `<span class="badge badge-closed">Cancelada</span>`
        };
        const badgeStatus = statusLabels[st] || `<span class="badge badge-closed">${nombreEstado(st)}</span>`;

        const leaderText = item.mayor_postor ? `Líder: ${item.mayor_postor}` : 'Sin postores aún';
        const finalPriceLabel = isActiva ? 'Precio Actual' : (st === 'PROGRAMMED' ? 'Precio Inicial' : 'Adjudicado Por');
        const isFav = userFavs.includes(item.id);
        const tagsHtml = (item.tags && item.tags.length)
            ? `<div class="card-tags">${item.tags.map(t => `<span class="card-tag" onclick="filtrarPorTag('${t}')">#${t}</span>`).join('')}</div>`
            : '';

        return `
            <article class="auction-card" data-id="${item.id}">
                ${canFav ? `
                <button class="btn-fav ${isFav ? 'active' : ''}" onclick="toggleFavorito(${item.id})" title="${isFav ? 'Quitar de favoritos' : 'Agregar a favoritos'}">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="${isFav ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                    </svg>
                </button>` : ''}
                
                <div class="card-image-wrap">
                    <img src="${item.producto.imagen_url}" alt="${item.producto.nombre}" class="card-image" loading="lazy">
                    <div class="card-badges">
                        ${badgeStatus}
                        <span class="badge badge-category">${item.producto.categoria}</span>
                    </div>
                </div>

                <div class="card-content">
                    <h3 class="card-title">${item.producto.nombre}</h3>
                    ${tagsHtml}
                    <p class="card-description">${item.producto.descripcion}</p>

                    <div class="card-pricing">
                        <div>
                            <span class="price-label">Precio Base</span>
                            <span class="price-value-subtle">$${item.producto.precio_inicial.toFixed(2)}</span>
                        </div>
                        <div class="text-right">
                            <span class="price-label text-emerald">${finalPriceLabel}</span>
                            <span class="price-value-primary">$${item.precio_actual.toFixed(2)}</span>
                        </div>
                    </div>

                    <div class="card-meta">
                        <div class="meta-item">
                            <span class="meta-icon">
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
                            </span>
                            <span>${leaderText}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-icon">
                                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                            </span>
                            <span>Inc. mín: +$${item.incremento_minimo.toFixed(2)}</span>
                        </div>
                    </div>

                    <div class="card-actions">
                        <button class="btn btn-outline btn-block btn-ver-historial" onclick="verHistorialSubasta(${item.id})">
                            Historial (${item.total_ofertas})
                        </button>
                        ${isActiva ? `
                            <button class="btn btn-primary btn-block" onclick="abrirModalPuja(${item.id})">
                                Pujar
                            </button>
                        ` : `
                            <button class="btn btn-outline btn-block" disabled style="opacity: 0.5;">
                                ${st === 'PROGRAMMED' ? 'Próximamente' : 'Cerrada'}
                            </button>
                        `}
                    </div>
                </div>
            </article>
        `;
    }).join('');
}

// Filtra el catálogo por una etiqueta (desde las tarjetas o la barra de tags)
function filtrarPorTag(tag) {
    activeTag = (activeTag === tag) ? '' : tag;
    document.querySelectorAll('.tag-filter-chip').forEach(chip => {
        chip.classList.toggle('active', chip.getAttribute('data-tag') === activeTag || (!activeTag && chip.getAttribute('data-tag') === ''));
    });
    if (activeTab !== 'catalogo') switchTab('catalogo');
    else renderAuctionsGrid(auctions);
}

// ============================================================================
// VISTA: MIS FAVORITOS (ROLE_BUYER+)
// ============================================================================
async function loadFavoritosView() {
    const container = document.getElementById('custom-view-container');
    container.innerHTML = `<h2 style="margin-bottom: 1rem;">Mis Subastas Favoritas</h2><p>Cargando lista de seguimiento...</p>`;
    try {
        const favs = await apiFetch('/api/mi-cuenta/favoritos');
        if (favs.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No tienes subastas en favoritos</h3>
                    <p>Explora el catálogo y presiona la estrella en los artículos que deseas seguir.</p>
                    <button class="btn btn-primary" onclick="switchTab('catalogo')">Ir al Catálogo</button>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2>Mis Subastas Favoritas (${favs.length})</h2>
                <button class="btn btn-outline" onclick="switchTab('catalogo')">Volver al Catálogo</button>
            </div>
            <div class="auctions-grid" id="favs-grid"></div>
        `;
        const favsGrid = document.getElementById('favs-grid');
        favsGrid.innerHTML = favs.map(item => `
            <article class="auction-card">
                <button class="btn-fav active" onclick="toggleFavorito(${item.id})" title="Quitar de favoritos">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" stroke="currentColor" stroke-width="2">
                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                    </svg>
                </button>
                <div class="card-image-wrap">
                    <img src="${item.producto.imagen_url}" alt="${item.producto.nombre}" class="card-image">
                </div>
                <div class="card-content">
                    <h3 class="card-title">${item.producto.nombre}</h3>
                    <p class="card-description">${item.producto.descripcion}</p>
                    <div class="card-pricing">
                        <div><span class="price-label">Precio Actual</span><span class="price-value-primary">$${item.precio_actual.toFixed(2)}</span></div>
                    </div>
                    <div class="card-actions" style="margin-top: 1rem;">
                        <button class="btn btn-primary btn-block" onclick="abrirModalPuja(${item.id})">Pujar Ahora</button>
                    </div>
                </div>
            </article>
        `).join('');
    } catch (err) {
        container.innerHTML = `<p style="color: var(--rose);">Error: ${err.message}</p>`;
    }
}

// ============================================================================
// VISTA: MIS PUJAS (ROLE_BUYER+)
// ============================================================================
async function loadMisPujasView() {
    const container = document.getElementById('custom-view-container');
    container.innerHTML = `<h2 style="margin-bottom: 1rem;">Mi Historial Personal de Pujas</h2><p>Cargando ofertas...</p>`;
    try {
        const pujas = await apiFetch('/api/mi-cuenta/pujas');
        if (pujas.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <h3>No has realizado pujas aún</h3>
                    <p>Encuentra productos en el catálogo y participa proponiendo tu precio.</p>
                    <button class="btn btn-primary" onclick="switchTab('catalogo')">Ver Catálogo</button>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <h2>Mi Historial Personal de Pujas (${pujas.length})</h2>
                <button class="btn btn-outline" onclick="switchTab('catalogo')">Volver al Catálogo</button>
            </div>
            <div class="history-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>Subasta</th>
                            <th>Mi Oferta</th>
                            <th>Precio Actual</th>
                            <th>Fecha</th>
                            <th>Estado</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${pujas.map(p => `
                            <tr>
                                <td><strong>#${p.subasta_id}</strong> - ${p.producto_nombre}</td>
                                <td style="font-weight: 700; color: var(--emerald);">$${p.monto_puja.toFixed(2)}</td>
                                <td>$${p.precio_actual_subasta.toFixed(2)}</td>
                                <td>${new Date(p.fecha).toLocaleString()}</td>
                                <td>
                                    ${p.es_ganador_actual 
                                        ? '<span class="badge-status badge-activo">Vas ganando</span>' 
                                        : '<span class="badge-status badge-suspendido">Superado</span>'}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<p style="color: var(--rose);">Error: ${err.message}</p>`;
    }
}

// ============================================================================
// VISTA: PANEL VENDEDOR (ROLE_SELLER+)
// ============================================================================
async function loadPanelVendedorView() {
    const container = document.getElementById('custom-view-container');
    container.innerHTML = `<h2 style="margin-bottom: 1rem;">Mis Subastas</h2><p>Cargando panel...</p>`;
    try {
        const misSubastas = await apiFetch('/api/panel-vendedor/subastas');
        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h2>Mis Subastas</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">Gestiona tus lotes. Puedes editar y cancelar artículos mientras no tengan ofertas registradas.</p>
                </div>
                <button class="btn btn-primary" onclick="openModal('modal-create')">+ Publicar Nueva Subasta</button>
            </div>
            <div class="history-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>Lote</th>
                            <th>Producto</th>
                            <th>Precio Base</th>
                            <th>Precio Actual</th>
                            <th>Pujas</th>
                            <th>Estado</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${misSubastas.length === 0 ? '<tr><td colspan="7" style="text-align:center;">No has publicado ninguna subasta aún.</td></tr>' : ''}
                        ${misSubastas.map(item => {
                            const sinPujas = item.total_ofertas === 0 && item.abierta;
                            return `
                                <tr>
                                    <td><strong>#${item.id}</strong></td>
                                    <td>${item.producto.nombre}</td>
                                    <td>$${item.producto.precio_inicial.toFixed(2)}</td>
                                    <td style="font-weight: 700; color: var(--emerald);">$${item.precio_actual.toFixed(2)}</td>
                                    <td>${item.total_ofertas} ofertas</td>
                                    <td>
                                        ${item.abierta ? '<span class="badge-status badge-activo">Activa</span>' : '<span class="badge-status badge-suspendido">Cerrada</span>'}
                                    </td>
                                    <td>
                                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                                            <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.78rem;" onclick="verHistorialSubasta(${item.id})">Ver</button>
                                            ${sinPujas ? `
                                                <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.78rem;" onclick="abrirModalEditar(${item.id})">Editar</button>
                                                <button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.78rem; border-color: var(--rose); color: var(--rose);" onclick="cancelarSubastaVendedor(${item.id})">Cancelar</button>
                                            ` : `
                                                ${item.abierta ? `<button class="btn btn-outline" style="padding: 0.3rem 0.6rem; font-size: 0.78rem; border-color: var(--amber); color: var(--amber);" onclick="cerrarSubastaVendedor(${item.id})">Cerrar</button>` : ''}
                                            `}
                                        </div>
                                    </td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<p style="color: var(--rose);">Error: ${err.message}</p>`;
    }
}

// ============================================================================
// VISTA: PANEL ADMINISTRADOR (ROLE_ADMIN)
// ============================================================================
async function loadPanelAdminView() {
    const container = document.getElementById('custom-view-container');
    container.innerHTML = `<h2 style="margin-bottom: 1rem;">Panel de Control</h2><p>Cargando datos del sistema...</p>`;
    try {
        const dashboard = await apiFetch('/api/admin/dashboard');
        const metricas = dashboard.metricas || {};
        const subastas = dashboard.subastas || [];
        const usuarios = dashboard.usuarios || [];
        const config = await apiFetch('/api/admin/configuracion');

        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                <div>
                    <h2>Panel de Control</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem;">Vista global: todas las subastas de la plataforma, métricas y moderación.</p>
                </div>
                <button class="btn btn-outline" onclick="switchTab('catalogo')">Volver al Catálogo</button>
            </div>

            <!-- Métricas generales del panel -->
            <section class="metrics-grid" style="margin-bottom: 2rem;">
                <div class="metric-card">
                    <div class="metric-info">
                        <span class="metric-label">Total Usuarios</span>
                        <h2 class="metric-value">${metricas.total_usuarios ?? 0}</h2>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-info">
                        <span class="metric-label">Subastas Activas</span>
                        <h2 class="metric-value text-emerald">${metricas.subastas_activas ?? 0}</h2>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-info">
                        <span class="metric-label">Subastas Finalizadas</span>
                        <h2 class="metric-value">${metricas.subastas_finalizadas ?? 0}</h2>
                    </div>
                </div>
                <div class="metric-card">
                    <div class="metric-info">
                        <span class="metric-label">Volumen Total Pujado</span>
                        <h2 class="metric-value text-amber">$${(metricas.volumen_total ?? 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</h2>
                    </div>
                </div>
            </section>

            <!-- Parámetros Globales -->
            <div style="background: var(--bg-surface-elevated); padding: 1.25rem; border-radius: 12px; margin-bottom: 2rem; border: 1px solid var(--border-subtle);">
                <h3 style="margin-bottom: 1rem; color: var(--cyan);">Parámetros Globales del Sistema</h3>
                <form id="form-admin-config" style="display: flex; gap: 1.5rem; align-items: flex-end; flex-wrap: wrap;">
                    <div class="form-group" style="margin-bottom: 0;">
                        <label>Incremento Mínimo Global ($):</label>
                        <input type="number" id="admin-inc-min" value="${config.incremento_minimo}" min="1" step="0.5" required style="width: 150px;">
                    </div>
                    <div class="form-group" style="margin-bottom: 0;">
                        <label>Comisión de Subastas (%):</label>
                        <input type="number" id="admin-comision" value="${config.comision_porcentaje}" min="0" max="100" step="0.1" required style="width: 150px;">
                    </div>
                    <button type="submit" class="btn btn-primary">Guardar Parámetros</button>
                </form>
            </div>

            <!-- Moderación de Subastas (Vista Global) -->
            <div style="margin-bottom: 2.5rem;">
                <h3 style="margin-bottom: 1rem;">Moderación de Subastas — Vista Global (${subastas.length})</h3>
                <div class="history-table-container">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Producto</th>
                                <th>Publicado por</th>
                                <th>Precio Actual</th>
                                <th>Etiquetas</th>
                                <th>Estado</th>
                                <th>Acciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${subastas.map(s => {
                                const st = (s.status || '').toUpperCase();
                                const estadoBadge = ['ACTIVE', 'PROGRAMMED'].includes(st) ? 'badge-activo' : 'badge-suspendido';
                                const tagsRow = (s.tags || []).map(t => `<span class="card-tag">#${t}</span>`).join(' ') || '<span style="color: var(--text-muted);">—</span>';
                                return `
                                <tr>
                                    <td><strong>#${s.id}</strong></td>
                                    <td>${s.title || s.producto.nombre}</td>
                                    <td>${s.sellerName || s.vendedor_nombre || 'Sin datos'}</td>
                                    <td>$${s.currentPrice.toFixed(2)}</td>
                                    <td style="max-width: 200px;">${tagsRow}</td>
                                    <td>
                                        <span class="badge-status ${estadoBadge}">${nombreEstado(st)}</span>
                                    </td>
                                    <td>
                                        <div style="display: flex; gap: 0.35rem; flex-wrap: wrap;">
                                            <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-color: var(--emerald); color: var(--emerald);" onclick="adminModerarSubasta(${s.id}, 'Aprobar')">Aprobar</button>
                                            <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-color: var(--amber); color: var(--amber);" onclick="adminModerarSubasta(${s.id}, 'Suspender')">Suspender</button>
                                            <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem; border-color: var(--rose); color: var(--rose);" onclick="adminModerarSubasta(${s.id}, 'Eliminar')">Eliminar</button>
                                        </div>
                                    </td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Gestión de Usuarios -->
            <div>
                <h3 style="margin-bottom: 1rem;">Usuarios Registrados (${usuarios.length})</h3>
                <div class="history-table-container">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Nombre</th>
                                <th>Email</th>
                                <th>Estado</th>
                                <th>Acción</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${usuarios.map(u => `
                                <tr>
                                    <td><strong>#${u.id}</strong></td>
                                    <td>${u.nombre}</td>
                                    <td>${u.email}</td>
                                    <td>
                                        <span class="badge-status ${u.estado === 'Activo' ? 'badge-activo' : 'badge-suspendido'}">
                                            ${u.estado}
                                        </span>
                                    </td>
                                    <td>
                                        ${u.rol !== 'ROLE_ADMIN' ? `
                                            <button class="btn btn-outline" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;" onclick="adminCambiarEstadoUsuario(${u.id}, '${u.estado === 'Activo' ? 'Suspendido' : 'Activo'}')">
                                                ${u.estado === 'Activo' ? 'Suspender' : 'Reactivar'}
                                            </button>
                                        ` : '<span style="color: var(--text-muted); font-size: 0.8rem;">Protegido</span>'}
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        document.getElementById('form-admin-config').addEventListener('submit', async (e) => {
            e.preventDefault();
            try {
                const inc = parseFloat(document.getElementById('admin-inc-min').value);
                const com = parseFloat(document.getElementById('admin-comision').value);
                const res = await apiFetch('/api/admin/configuracion', {
                    method: 'PUT',
                    body: { incremento_minimo: inc, comision_porcentaje: com }
                });
                showToast(res.mensaje, 'success');
            } catch (err) {
                showToast(err.message, 'error');
            }
        });

    } catch (err) {
        container.innerHTML = `<p style="color: var(--rose);">Error al cargar panel admin: ${err.message}</p>`;
    }
}

// ============================================================================
// ACCIONES DE USUARIO (FAVORITOS, PUJAS, MODERACIÓN)
// ============================================================================
async function toggleFavorito(subastaId) {
    if (!['ROLE_BUYER', 'ROLE_SELLER', 'ROLE_ADMIN'].includes(authState.user.rol)) {
        showToast('Debes iniciar sesión para guardar favoritos.', 'warning');
        openModal('modal-auth');
        return;
    }

    try {
        const res = await apiFetch(`/api/subastas/${subastaId}/favoritos`, { method: 'POST' });
        showToast(res.mensaje, 'success');

        // Actualizar array local de favoritos
        authState.user.favoritos = authState.user.favoritos || [];
        if (res.es_favorito) {
            if (!authState.user.favoritos.includes(subastaId)) authState.user.favoritos.push(subastaId);
        } else {
            authState.user.favoritos = authState.user.favoritos.filter(id => id !== subastaId);
        }
        localStorage.setItem('subastahub_user', JSON.stringify(authState.user));

        if (activeTab === 'catalogo') renderAuctionsGrid(auctions);
        else if (activeTab === 'favoritos') loadFavoritosView();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function abrirModalPuja(subastaId) {
    if (!['ROLE_BUYER', 'ROLE_SELLER', 'ROLE_ADMIN'].includes(authState.user.rol)) {
        showToast('Debes iniciar sesión para realizar una puja.', 'warning');
        openModal('modal-auth');
        return;
    }

    const item = auctions.find(a => a.id === subastaId);
    if (!item) return;

    activeAuctionForBid = item;
    document.getElementById('modal-product-name').textContent = item.producto.nombre;
    document.getElementById('modal-current-price').textContent = `$${item.precio_actual.toFixed(2)}`;
    document.getElementById('modal-min-increment').textContent = `+$${item.incremento_minimo.toFixed(2)}`;

    const minRequired = item.total_ofertas > 0 ? item.precio_actual + item.incremento_minimo : item.producto.precio_inicial;
    document.getElementById('modal-min-required').textContent = `$${minRequired.toFixed(2)}`;

    document.getElementById('bid-user-name').value = authState.user.nombre;
    const bidAmountInput = document.getElementById('bid-amount');
    bidAmountInput.value = minRequired.toFixed(2);
    bidAmountInput.min = minRequired;

    openModal('modal-bid');
}

document.getElementById('form-bid').addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!activeAuctionForBid) return;

    const monto = parseFloat(document.getElementById('bid-amount').value);
    try {
        const res = await apiFetch(`/api/subastas/${activeAuctionForBid.id}/pujar`, {
            method: 'POST',
            body: { monto }
        });
        showToast(res.mensaje, 'success');
        closeModal('modal-bid');

        fetchMetrics(true);
        fetchAuctions(true);
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// Incrementos rápidos
document.querySelectorAll('.btn-increment').forEach(btn => {
    btn.addEventListener('click', () => {
        const inc = parseFloat(btn.getAttribute('data-increment'));
        const input = document.getElementById('bid-amount');
        const current = parseFloat(input.value) || (activeAuctionForBid ? activeAuctionForBid.precio_actual : 0);
        input.value = (current + inc).toFixed(2);
    });
});

// Modal de Historial
async function verHistorialSubasta(subastaId) {
    try {
        const item = await apiFetch(`/api/subastas/${subastaId}`);
        document.getElementById('history-modal-product-name').textContent = item.producto.nombre;
        document.getElementById('history-initial-price').textContent = `$${item.producto.precio_inicial.toFixed(2)}`;
        document.getElementById('history-current-price').textContent = `$${item.precio_actual.toFixed(2)}`;
        document.getElementById('history-total-bids').textContent = item.total_ofertas;
        document.getElementById('history-leader').textContent = item.mayor_postor || 'Sin postores';

        const tbody = document.getElementById('history-table-body');
        if (!item.historial_ofertas || item.historial_ofertas.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 2rem;">No hay ofertas registradas todavía.</td></tr>`;
        } else {
            tbody.innerHTML = item.historial_ofertas.map((o, idx) => `
                <tr>
                    <td><strong>#${idx + 1}</strong></td>
                    <td>${o.usuario_nombre}</td>
                    <td style="font-weight: 700; color: var(--emerald);">$${o.monto.toFixed(2)}</td>
                    <td>${new Date(o.fecha).toLocaleString()}</td>
                    <td>${idx === 0 ? '<span class="badge-status badge-activo">Mayor Oferta</span>' : '<span class="badge-status badge-suspendido">Superada</span>'}</td>
                </tr>
            `).join('');
        }
        openModal('modal-history');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Publicar Nueva Subasta
document.getElementById('form-create-auction').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
        const nombre = document.getElementById('create-name').value;
        const categoria = document.getElementById('create-category').value;
        const precio_inicial = parseFloat(document.getElementById('create-starting-price').value);
        const duracion_minutos = parseInt(document.getElementById('create-duration').value) || 60;
        const incremento_minimo = parseFloat(document.getElementById('create-increment').value) || 10;
        const imagen_url = document.querySelector('input[name="image-choice"]:checked').value;
        const descripcion = document.getElementById('create-description').value;
        const tags = document.getElementById('create-tags').value
            .split(',')
            .map(t => t.trim().toLowerCase())
            .filter(t => t.length > 0);
        const startDate = document.getElementById('create-start-date').value || null;
        const endDate = document.getElementById('create-end-date').value || null;

        const res = await apiFetch('/api/subastas/nueva', {
            method: 'POST',
            body: { nombre, descripcion, categoria, precio_inicial, duracion_minutos, incremento_minimo, imagen_url, tags, startDate, endDate }
        });
        showToast(res.mensaje, 'success');
        closeModal('modal-create');
        document.getElementById('form-create-auction').reset();

        fetchMetrics();
        fetchAuctions();
        if (activeTab === 'panel-vendedor') loadPanelVendedorView();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// Editar Subasta (Solo sin ofertas)
function abrirModalEditar(subastaId) {
    const item = auctions.find(a => a.id === subastaId);
    if (!item) return;

    document.getElementById('edit-subasta-id').value = item.id;
    document.getElementById('edit-name').value = item.producto.nombre;
    document.getElementById('edit-category').value = item.producto.categoria;
    document.getElementById('edit-price').value = item.producto.precio_inicial;
    document.getElementById('edit-description').value = item.producto.descripcion;
    document.getElementById('edit-tags').value = (item.tags || []).join(', ');
    document.getElementById('edit-start-date').value = toDatetimeLocalValue(item.startDate);
    document.getElementById('edit-end-date').value = toDatetimeLocalValue(item.endDate);

    openModal('modal-edit');
}

// Convierte una fecha ISO a formato aceptado por <input type="datetime-local">
function toDatetimeLocalValue(isoStr) {
    if (!isoStr) return '';
    const d = new Date(isoStr);
    if (isNaN(d.getTime())) return '';
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

document.getElementById('form-edit-auction').addEventListener('submit', async (e) => {
    e.preventDefault();
    const id = document.getElementById('edit-subasta-id').value;
    try {
        const tags = document.getElementById('edit-tags').value
            .split(',')
            .map(t => t.trim().toLowerCase())
            .filter(t => t.length > 0);
        const res = await apiFetch(`/api/subastas/${id}/editar`, {
            method: 'PUT',
            body: {
                nombre: document.getElementById('edit-name').value,
                categoria: document.getElementById('edit-category').value,
                precio_inicial: parseFloat(document.getElementById('edit-price').value),
                descripcion: document.getElementById('edit-description').value,
                tags,
                startDate: document.getElementById('edit-start-date').value || undefined,
                endDate: document.getElementById('edit-end-date').value || undefined
            }
        });
        showToast(res.mensaje, 'success');
        closeModal('modal-edit');
        fetchAuctions();
        if (activeTab === 'panel-vendedor') loadPanelVendedorView();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// Cancelar Subasta (Vendedor, antes del primer incremento)
async function cancelarSubastaVendedor(subastaId) {
    if (!confirm('¿Estás seguro de cancelar esta subasta antes del primer incremento?')) return;
    try {
        const res = await apiFetch(`/api/subastas/${subastaId}/cancelar`, { method: 'DELETE' });
        showToast(res.mensaje, 'success');
        fetchAuctions();
        if (activeTab === 'panel-vendedor') loadPanelVendedorView();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Cerrar Subasta (Vendedor)
async function cerrarSubastaVendedor(subastaId) {
    if (!confirm('¿Deseas cerrar formalmente la subasta y declarar al ganador?')) return;
    try {
        const res = await apiFetch(`/api/subastas/${subastaId}/cerrar`, { method: 'POST' });
        showToast(res.mensaje, 'success');
        fetchAuctions();
        if (activeTab === 'panel-vendedor') loadPanelVendedorView();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Admin: Moderación de Subastas (Aprobar, Suspender, Eliminar)
async function adminModerarSubasta(subastaId, accion) {
    if (accion === 'Eliminar' && !confirm('¿Eliminar DEFINITIVAMENTE esta subasta? Esta acción no se puede deshacer.')) return;
    const motivo = prompt(`Motivo para la acción '${accion}' (opcional):`, 'Acción realizada desde el panel');
    if (motivo === null) return;
    try {
        const res = await apiFetch(`/api/admin/subastas/${subastaId}/moderar`, {
            method: 'PUT',
            body: { status: accion, accion, motivo }
        });
        showToast(res.mensaje, 'success');
        loadPanelAdminView();
        fetchAuctions(true);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Admin: Cambiar Estado Usuario
async function adminCambiarEstadoUsuario(usuarioId, nuevoEstado) {
    try {
        const res = await apiFetch(`/api/admin/usuarios/${usuarioId}/estado`, {
            method: 'PUT',
            body: { estado: nuevoEstado }
        });
        showToast(res.mensaje, 'success');
        loadPanelAdminView();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ============================================================================
// EVENT LISTENERS & MODAL UTILITIES
// ============================================================================
function setupEventListeners() {
    // Filtros
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.getAttribute('data-filter');
            renderAuctionsGrid(auctions);
        });
    });

    // Búsqueda en tiempo real
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            currentSearch = e.target.value.trim();
            renderAuctionsGrid(auctions);
        });
    }

    // Filtro rápido por Etiquetas (Tags)
    document.querySelectorAll('.tag-filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            activeTag = chip.getAttribute('data-tag') || '';
            document.querySelectorAll('.tag-filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            if (activeTab !== 'catalogo') switchTab('catalogo');
            else renderAuctionsGrid(auctions);
        });
    });

    // Modal Create
    const btnOpenCreate = document.getElementById('btn-open-create-modal');
    if (btnOpenCreate) btnOpenCreate.addEventListener('click', () => openModal('modal-create'));
    document.getElementById('btn-close-create-modal')?.addEventListener('click', () => closeModal('modal-create'));
    document.getElementById('btn-cancel-create')?.addEventListener('click', () => closeModal('modal-create'));

    // Modal Bid
    document.getElementById('btn-close-bid-modal')?.addEventListener('click', () => closeModal('modal-bid'));
    document.getElementById('btn-cancel-bid')?.addEventListener('click', () => closeModal('modal-bid'));

    // Modal History
    document.getElementById('btn-close-history-modal')?.addEventListener('click', () => closeModal('modal-history'));

    // Modal Edit
    document.getElementById('btn-close-edit-modal')?.addEventListener('click', () => closeModal('modal-edit'));
    document.getElementById('btn-cancel-edit')?.addEventListener('click', () => closeModal('modal-edit'));

    // Modal Auth
    document.getElementById('btn-close-auth-modal')?.addEventListener('click', () => closeModal('modal-auth'));
    document.getElementById('tab-login-btn')?.addEventListener('click', () => {
        document.getElementById('tab-login-btn').classList.add('active');
        document.getElementById('tab-register-btn').classList.remove('active');
        document.getElementById('form-login').classList.remove('hidden');
        document.getElementById('form-register').classList.add('hidden');
        document.getElementById('auth-modal-title').textContent = 'Iniciar Sesión';
    });
    document.getElementById('tab-register-btn')?.addEventListener('click', () => {
        document.getElementById('tab-register-btn').classList.add('active');
        document.getElementById('tab-login-btn').classList.remove('active');
        document.getElementById('form-register').classList.remove('hidden');
        document.getElementById('form-login').classList.add('hidden');
        document.getElementById('auth-modal-title').textContent = 'Crear Cuenta';
    });

    // Submit Login Manual
    document.getElementById('form-login')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        await loginUser(email, password);
    });

    // Submit Register Manual
    document.getElementById('form-register')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const nombre = document.getElementById('reg-name').value;
            const email = document.getElementById('reg-email').value;
            const password = document.getElementById('reg-password').value;
            const rol = document.getElementById('reg-role').value;

            const res = await apiFetch('/api/auth/register', {
                method: 'POST',
                body: { nombre, email, password, rol }
            });

            authState.token = res.token;
            authState.user = res.usuario;
            localStorage.setItem('subastahub_token', res.token);
            localStorage.setItem('subastahub_user', JSON.stringify(res.usuario));

            closeModal('modal-auth');
            initAuthUI();
            showToast(res.mensaje, 'success');
            fetchAuctions();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Cerrar modales con tecla Escape
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-backdrop:not(.hidden)').forEach(modal => {
                modal.classList.add('hidden');
            });
        }
    });
}

function openModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.remove('hidden');
}

function closeModal(modalId) {
    const m = document.getElementById(modalId);
    if (m) m.classList.add('hidden');
}

// Toast Notifier
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icons = {
        success: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#34d399" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
        error: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fb7185" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
        warning: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fbbf24" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#60a5fa" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };
    toast.innerHTML = `${icons[type] || icons.info} <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
