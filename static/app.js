/**
 * SubastaHub Frontend Client
 * Handles real-time auction polling, interactive bidding, creation, and modal management.
 */

// Application State
let auctions = [];
let activeFilter = 'todas';
let currentSearch = '';
let activeAuctionForBid = null;
let pollInterval = null;

// DOM Elements
const auctionsGrid = document.getElementById('auctions-grid');
const emptyState = document.getElementById('empty-state');
const counterSubastas = document.getElementById('counter-subastas');
const inputSearch = document.getElementById('input-search');
const filterButtons = document.querySelectorAll('.filter-btn');

// Metrics DOM
const statTotalSubastas = document.getElementById('stat-total-subastas');
const statActivas = document.getElementById('stat-activas');
const statTotalOfertas = document.getElementById('stat-total-ofertas');
const statVolumen = document.getElementById('stat-volumen');

// Modals
const modalBid = document.getElementById('modal-bid');
const formBid = document.getElementById('form-bid');
const bidProductName = document.getElementById('bid-modal-product-name');
const bidProductImg = document.getElementById('bid-modal-product-img');
const bidCurrentPrice = document.getElementById('bid-modal-current-price');
const bidHighestBidder = document.getElementById('bid-modal-highest-bidder');
const bidMinAmount = document.getElementById('bid-modal-min-amount');
const bidUserName = document.getElementById('bid-user-name');
const bidAmount = document.getElementById('bid-amount');

const modalHistory = document.getElementById('modal-history');
const historyProductName = document.getElementById('history-modal-product-name');
const historyInitialPrice = document.getElementById('history-initial-price');
const historyCurrentPrice = document.getElementById('history-current-price');
const historyTotalBids = document.getElementById('history-total-bids');
const historyLeader = document.getElementById('history-leader');
const historyTableBody = document.getElementById('history-table-body');

const modalCreate = document.getElementById('modal-create');
const formCreate = document.getElementById('form-create-auction');
const btnOpenCreate = document.getElementById('btn-open-create-modal');
const btnEmptyCreate = document.getElementById('btn-empty-create');

// Toast Container
const toastContainer = document.getElementById('toast-container');

// ============================================================================
// INITIALIZATION
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    fetchMetrics();
    fetchAuctions();
    setupEventListeners();

    // Auto-poll every 5 seconds for live bidding changes
    pollInterval = setInterval(() => {
        fetchMetrics(true);
        fetchAuctions(true);
    }, 5000);
});

// ============================================================================
// DATA FETCHING
// ============================================================================
async function fetchMetrics(silent = false) {
    try {
        const res = await fetch('/api/metricas');
        if (!res.ok) return;
        const data = await res.json();

        statTotalSubastas.textContent = data.total_subastas;
        statActivas.textContent = data.subastas_activas;
        statTotalOfertas.textContent = data.total_ofertas;
        statVolumen.textContent = `$${data.volumen_total.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    } catch (err) {
        if (!silent) console.error('Error al cargar métricas:', err);
    }
}

async function fetchAuctions(silent = false) {
    try {
        const res = await fetch('/api/subastas');
        if (!res.ok) throw new Error('No se pudo conectar al servidor.');
        auctions = await res.json();
        renderAuctions();
    } catch (err) {
        if (!silent) showToast(err.message, 'error');
    }
}

// ============================================================================
// RENDERING AUCTIONS
// ============================================================================
function renderAuctions() {
    // Filter by status and search keyword
    const filtered = auctions.filter(item => {
        const matchesStatus = 
            activeFilter === 'todas' ? true :
            activeFilter === 'activas' ? item.abierta :
            !item.abierta;

        const term = currentSearch.toLowerCase();
        const matchesSearch = 
            item.producto.nombre.toLowerCase().includes(term) ||
            item.producto.descripcion.toLowerCase().includes(term) ||
            item.producto.categoria.toLowerCase().includes(term);

        return matchesStatus && matchesSearch;
    });

    counterSubastas.textContent = `${filtered.length} subasta(s) disponible(s)`;

    if (filtered.length === 0) {
        auctionsGrid.innerHTML = '';
        emptyState.classList.remove('hidden');
        return;
    }

    emptyState.classList.add('hidden');
    auctionsGrid.innerHTML = filtered.map(item => createAuctionCardHtml(item)).join('');

    // Reattach listeners to action buttons on each card
    attachCardListeners();
}

function createAuctionCardHtml(item) {
    const isActiva = item.abierta;
    const badgeStatus = isActiva
        ? `<span class="badge badge-active">🔥 En Vivo</span>`
        : `<span class="badge badge-closed">🔒 Finalizada</span>`;

    const leaderText = item.mayor_postor ? `👑 ${item.mayor_postor}` : 'Sin postores aún';
    const finalPriceLabel = isActiva ? 'Precio Actual' : 'Adjudicado Por';
    const winnerLabel = !isActiva && item.ganador_nombre ? `🏆 Ganador: ${item.ganador_nombre}` : leaderText;

    return `
        <article class="auction-card" data-id="${item.id}">
            <div class="card-image-wrap">
                <img src="${item.producto.imagen_url}" alt="${item.producto.nombre}" class="card-image" loading="lazy">
                <div class="card-badges">
                    ${badgeStatus}
                    <span class="badge badge-category">${item.producto.categoria}</span>
                </div>
            </div>

            <div class="card-content">
                <h3 class="card-title">${escapeHtml(item.producto.nombre)}</h3>
                <p class="card-description">${escapeHtml(item.producto.descripcion)}</p>

                <div class="card-price-box">
                    <div>
                        <span class="price-sublabel">${finalPriceLabel}</span>
                        <div class="card-current-price">$${item.precio_actual.toFixed(2)}</div>
                    </div>
                    <div class="card-initial-price">
                        <span class="price-sublabel">Base:</span>
                        <div>$${item.producto.precio_inicial.toFixed(2)}</div>
                    </div>
                </div>

                <div class="card-bidder-info">
                    <span class="bidder-chip" title="Postor al frente">${winnerLabel}</span>
                    <span class="bids-count">💬 ${item.total_ofertas} pujas</span>
                </div>

                <div class="card-actions">
                    ${isActiva ? `
                        <button class="btn btn-primary btn-bid-action" data-id="${item.id}">
                            ⚡ Pujar Ahora
                        </button>
                        <button class="btn btn-outline btn-icon btn-history-action" data-id="${item.id}" title="Ver Historial">
                            📋
                        </button>
                        <button class="btn btn-danger btn-icon btn-close-action" data-id="${item.id}" title="Cerrar Subasta">
                            ⏹
                        </button>
                    ` : `
                        <button class="btn btn-outline btn-history-action" data-id="${item.id}" style="width: 100%;">
                            📋 Ver Resultado e Historial
                        </button>
                    `}
                </div>
            </div>
        </article>
    `;
}

function attachCardListeners() {
    // Bid Action
    document.querySelectorAll('.btn-bid-action').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = parseInt(btn.dataset.id, 10);
            openBidModal(id);
        });
    });

    // History Action
    document.querySelectorAll('.btn-history-action').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = parseInt(btn.dataset.id, 10);
            openHistoryModal(id);
        });
    });

    // Close Auction Action
    document.querySelectorAll('.btn-close-action').forEach(btn => {
        btn.addEventListener('click', () => {
            const id = parseInt(btn.dataset.id, 10);
            handleCloseAuction(id);
        });
    });
}

// ============================================================================
// MODAL LOGIC & ACTIONS
// ============================================================================

// --- BID MODAL ---
function openBidModal(auctionId) {
    const item = auctions.find(a => a.id === auctionId);
    if (!item) return;

    activeAuctionForBid = item;
    bidProductName.textContent = item.producto.nombre;
    bidProductImg.src = item.producto.imagen_url;
    bidCurrentPrice.textContent = `$${item.precio_actual.toFixed(2)}`;
    bidHighestBidder.textContent = item.mayor_postor ? item.mayor_postor : 'Sin ofertas';

    const minBid = item.precio_actual + 1.0;
    bidMinAmount.textContent = `$${minBid.toFixed(2)}`;
    bidAmount.value = minBid.toFixed(2);
    bidAmount.min = (item.precio_actual + 0.01).toFixed(2);

    modalBid.classList.remove('hidden');
    bidUserName.focus();
}

function closeBidModal() {
    modalBid.classList.add('hidden');
    activeAuctionForBid = null;
    formBid.reset();
}

// Quick increments
document.querySelectorAll('.btn-increment').forEach(btn => {
    btn.addEventListener('click', () => {
        if (!activeAuctionForBid) return;
        const inc = parseFloat(btn.dataset.increment);
        const newBid = activeAuctionForBid.precio_actual + inc;
        bidAmount.value = newBid.toFixed(2);
    });
});

formBid.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!activeAuctionForBid) return;

    const usuario = bidUserName.value.trim();
    const monto = parseFloat(bidAmount.value);

    if (!usuario) {
        showToast('Ingresa tu nombre o apodo.', 'error');
        return;
    }

    if (isNaN(monto) || monto <= activeAuctionForBid.precio_actual) {
        showToast(`La oferta debe superar $${activeAuctionForBid.precio_actual.toFixed(2)}`, 'error');
        return;
    }

    try {
        const res = await fetch(`/api/subastas/${activeAuctionForBid.id}/ofertar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario, monto })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al procesar la oferta');

        showToast(data.mensaje, 'success');
        closeBidModal();
        fetchMetrics(true);
        await fetchAuctions();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// --- HISTORY MODAL ---
async function openHistoryModal(auctionId) {
    try {
        const res = await fetch(`/api/subastas/${auctionId}`);
        if (!res.ok) throw new Error('No se pudo obtener el historial.');
        const subasta = await res.json();

        historyProductName.textContent = subasta.producto.nombre;
        historyInitialPrice.textContent = `$${subasta.producto.precio_inicial.toFixed(2)}`;
        historyCurrentPrice.textContent = `$${subasta.precio_actual.toFixed(2)}`;
        historyTotalBids.textContent = subasta.total_ofertas;
        historyLeader.textContent = subasta.abierta
            ? (subasta.mayor_postor || 'Sin postores')
            : (subasta.ganador_nombre ? `🏆 ${subasta.ganador_nombre}` : 'Sin adjudicar');

        if (!subasta.historial_ofertas || subasta.historial_ofertas.length === 0) {
            historyTableBody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        Aún no se han registrado ofertas para este lote.
                    </td>
                </tr>
            `;
        } else {
            historyTableBody.innerHTML = subasta.historial_ofertas.map((of, idx) => {
                const isFirst = idx === 0;
                const statusTag = isFirst 
                    ? (subasta.abierta ? '🟢 Puja Líder' : '🏆 Ganadora')
                    : '⚪ Superada';

                return `
                    <tr class="${isFirst ? 'highest-bid' : ''}">
                        <td>#${subasta.historial_ofertas.length - idx}</td>
                        <td><strong>${escapeHtml(of.usuario_nombre)}</strong></td>
                        <td style="color: var(--emerald); font-weight: 700;">$${of.monto.toFixed(2)}</td>
                        <td>${formatDate(of.fecha)}</td>
                        <td>${statusTag}</td>
                    </tr>
                `;
            }).join('');
        }

        modalHistory.classList.remove('hidden');
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function closeHistoryModal() {
    modalHistory.classList.add('hidden');
}

// --- CLOSE AUCTION ---
async function handleCloseAuction(auctionId) {
    const item = auctions.find(a => a.id === auctionId);
    if (!item) return;

    const confirmClose = confirm(
        `¿Estás seguro de cerrar la subasta de "${item.producto.nombre}"?\n` +
        (item.mayor_postor ? `Se declarará ganador a ${item.mayor_postor} por $${item.precio_actual.toFixed(2)}.` : 'No hay ofertas registradas.')
    );

    if (!confirmClose) return;

    try {
        const res = await fetch(`/api/subastas/${auctionId}/cerrar`, {
            method: 'POST'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al cerrar la subasta');

        showToast(data.mensaje, 'success');
        fetchMetrics(true);
        await fetchAuctions();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// --- CREATE AUCTION MODAL ---
function openCreateModal() {
    modalCreate.classList.remove('hidden');
}

function closeCreateModal() {
    modalCreate.classList.add('hidden');
    formCreate.reset();
}

formCreate.addEventListener('submit', async (e) => {
    e.preventDefault();

    const nombre = document.getElementById('create-name').value.trim();
    const categoria = document.getElementById('create-category').value;
    const precio_inicial = parseFloat(document.getElementById('create-starting-price').value);
    const duracion_minutos = parseInt(document.getElementById('create-duration').value, 10) || 60;
    const descripcion = document.getElementById('create-description').value.trim();
    
    const selectedImage = document.querySelector('input[name="image-choice"]:checked')?.value || '/static/img/laptop.jpg';

    if (!nombre || isNaN(precio_inicial) || precio_inicial <= 0 || !descripcion) {
        showToast('Por favor completa todos los campos requeridos correctamente.', 'error');
        return;
    }

    try {
        const res = await fetch('/api/subastas', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                nombre,
                categoria,
                precio_inicial,
                duracion_minutos,
                descripcion,
                imagen_url: selectedImage
            })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Error al crear la subasta');

        showToast(data.mensaje, 'success');
        closeCreateModal();
        fetchMetrics(true);
        await fetchAuctions();
    } catch (err) {
        showToast(err.message, 'error');
    }
});

// ============================================================================
// EVENT LISTENERS & FILTERS
// ============================================================================
function setupEventListeners() {
    // Search input
    inputSearch.addEventListener('input', (e) => {
        currentSearch = e.target.value.trim();
        renderAuctions();
    });

    // Filter status buttons
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            filterButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeFilter = btn.dataset.filter;
            renderAuctions();
        });
    });

    // Modal Close Buttons
    document.getElementById('btn-close-bid-modal').addEventListener('click', closeBidModal);
    document.getElementById('btn-cancel-bid').addEventListener('click', closeBidModal);

    document.getElementById('btn-close-history-modal').addEventListener('click', closeHistoryModal);

    document.getElementById('btn-close-create-modal').addEventListener('click', closeCreateModal);
    document.getElementById('btn-cancel-create').addEventListener('click', closeCreateModal);

    // Open Create Modal
    btnOpenCreate.addEventListener('click', openCreateModal);
    btnEmptyCreate.addEventListener('click', openCreateModal);

    // Close Modals on backdrop click
    [modalBid, modalHistory, modalCreate].forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeBidModal();
                closeHistoryModal();
                closeCreateModal();
            }
        });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeBidModal();
            closeHistoryModal();
            closeCreateModal();
        }
    });
}

// ============================================================================
// HELPERS & TOASTS
// ============================================================================
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✅' : '⚠️';
    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;

    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
        const date = new Date(dateStr);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
        return dateStr;
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
