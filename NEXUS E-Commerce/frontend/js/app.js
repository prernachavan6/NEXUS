/**
 * NEXUS E-Commerce — Frontend Application Controller
 * Features:
 *   - Role-Based Access Control (RBAC): Admin analytics restricted to store managers
 *   - Bulletproof checkout with automatic customer ID resolution
 *   - Database Inspector & SQL Console for live database verification
 *   - 16:9 presentation fit mode & mauve / off-white design
 */

const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const fmtMoney = n => '₹' + Math.round(n || 0).toLocaleString('en-IN');
const sum = (arr, fn) => arr.reduce((acc, x, i) => acc + fn(x, i), 0);
const pad = n => String(n).padStart(2, '0');

const CATEGORIES = ['Electronics', 'Fashion', 'Home & Living', 'Books & Learning', 'Beauty & Care', 'Gourmet Grocery'];
const CITY_LOOKUP = [
  ['Mumbai', 'Maharashtra'], ['Pune', 'Maharashtra'], ['Bengaluru', 'Karnataka'],
  ['Hyderabad', 'Telangana'], ['Delhi', 'Delhi'], ['Chennai', 'Tamil Nadu'],
  ['Kolkata', 'West Bengal'], ['Ahmedabad', 'Gujarat']
];
const PAYMENT_METHODS = ['UPI', 'Credit/Debit Card', 'COD', 'NetBanking', 'NEXUS Wallet'];
const ORDER_STATUSES = ['Placed', 'Packed', 'Shipped', 'Delivered'];

// Global State
const STATE = {
  view: 'store',
  adminTab: 'overview',
  theme: localStorage.getItem('nexus_theme') || 'light',
  isPresentationMode: false,
  currentUser: JSON.parse(localStorage.getItem('nexus_user') || 'null'),
  cart: {},
  wishlist: new Set(),
  products: [],
  searchQuery: '',
  selectedCategory: '',
  sortBy: 'rel',

  // Database Inspector state
  selectedTable: 'orders',

  // OLAP parameters
  olapLevel: 'year',
  olapGroupBy: 'cat',
  olapMeasure: 'sales',
  olapCatFilter: '',
  olapCityFilter: '',
  olapYearFilter: '',

  // Mining parameters
  clusterK: 4,
  clusterAlg: 'kmeans',
  knnK: 5,
  assocMinSup: 2.0,
  assocMinConf: 30.0
};

// Storage Keys Scoped Per User (Prevents Cart Bleeding Across Admin / Shoppers)
function getCartStorageKey(user) {
  if (!user) return 'nexus_cart_guest';
  const uid = user.id || user.customer_id || user.email || 'guest';
  return `nexus_cart_user_${uid}`;
}

function getWishStorageKey(user) {
  if (!user) return 'nexus_wish_guest';
  const uid = user.id || user.customer_id || user.email || 'guest';
  return `nexus_wish_user_${uid}`;
}

function loadUserCartAndWish(user) {
  try {
    const cartKey = getCartStorageKey(user);
    const wishKey = getWishStorageKey(user);
    STATE.cart = JSON.parse(localStorage.getItem(cartKey) || '{}');
    const savedWish = JSON.parse(localStorage.getItem(wishKey) || '[]');
    STATE.wishlist = new Set(savedWish);
  } catch (e) {
    STATE.cart = {};
    STATE.wishlist = new Set();
  }
}

function saveUserCartAndWish() {
  const cartKey = getCartStorageKey(STATE.currentUser);
  const wishKey = getWishStorageKey(STATE.currentUser);
  localStorage.setItem(cartKey, JSON.stringify(STATE.cart));
  localStorage.setItem(wishKey, JSON.stringify([...STATE.wishlist]));
}

function clearCart(silent = false) {
  STATE.cart = {};
  saveUserCartAndWish();
  updateNavCounters();
  if (!silent) {
    showToast('Shopping cart emptied');
    if ($('#modalOverlay') && $('#modalOverlay').classList.contains('active')) {
      openCartModal();
    }
  }
}

// Theme Switching
function applyTheme(theme) {
  STATE.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('nexus_theme', theme);
  const icon = $('#themeIcon');
  const label = $('#themeLabel');
  if (icon && label) {
    if (theme === 'light') {
      icon.textContent = '🌙';
      label.textContent = 'Dark';
    } else {
      icon.textContent = '☀️';
      label.textContent = 'Light';
    }
  }
}

function toggleTheme() {
  const next = STATE.theme === 'light' ? 'dark' : 'light';
  applyTheme(next);
  if (STATE.view === 'admin') renderMain();
}

// 16:9 Presentation Fit Controller
function togglePresentationMode() {
  STATE.isPresentationMode = !STATE.isPresentationMode;
  document.body.classList.toggle('presentation-mode', STATE.isPresentationMode);
  
  const bar = $('#presentationBar');
  const btn = $('#btnPresentation');
  const label = $('#presLabel');
  
  if (bar) bar.style.display = STATE.isPresentationMode ? 'flex' : 'none';
  if (btn) btn.classList.toggle('active', STATE.isPresentationMode);
  if (label) label.textContent = STATE.isPresentationMode ? 'Fit Active' : '16:9 Fit';
  
  showToast(STATE.isPresentationMode ? '16:9 Presentation Fit On (Press Esc to exit)' : 'Standard layout restored');

  // Trigger chart resize after layout reflow
  setTimeout(() => {
    Object.values(CHART_INSTANCES).forEach(c => {
      if (c && typeof c.resize === 'function') c.resize();
    });
  }, 100);
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().catch(err => {
      showToast('Fullscreen notice: ' + err.message);
    });
  } else {
    if (document.exitFullscreen) document.exitFullscreen();
  }
}

// Hotkey listener (P = 16:9 fit, Escape = exit)
window.addEventListener('keydown', (e) => {
  if (e.target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
  if (e.key === 'p' || e.key === 'P') {
    togglePresentationMode();
  } else if (e.key === 'Escape' && STATE.isPresentationMode) {
    togglePresentationMode();
  }
});

let CHART_INSTANCES = {};
function renderChart(id, config) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  if (CHART_INSTANCES[id]) {
    CHART_INSTANCES[id].destroy();
  }

  const isLight = (STATE.theme === 'light');
  Chart.defaults.color = isLight ? '#5e4d70' : '#c4b5d6';
  Chart.defaults.borderColor = isLight ? '#e8dcf1' : '#36274e';

  config.options = Object.assign({
    responsive: true,
    maintainAspectRatio: false
  }, config.options);
  CHART_INSTANCES[id] = new Chart(canvas, config);
}

function showToast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(t.timer);
  t.timer = setTimeout(() => { t.style.display = 'none'; }, 2200);
}

/* ==========================================================================
   ROLE-BASED VIEW SWITCHER (RBAC ENFORCEMENT)
   ========================================================================== */
function switchView(viewName) {
  // If attempting to enter admin view without admin privileges, prompt admin login
  if (viewName === 'admin') {
    if (!STATE.currentUser || STATE.currentUser.role !== 'admin') {
      showToast('Restricted: Administrator credentials required.');
      openAuthModal('admin');
      return;
    }
  }

  STATE.view = viewName;
  updateNavState();
  renderMain();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function updateNavState() {
  const isAdmin = STATE.currentUser && STATE.currentUser.role === 'admin';

  // Sub-bar mode switch is strictly visible for administrators
  const modeBar = $('#modeBar');
  if (modeBar) {
    modeBar.style.display = isAdmin ? 'block' : 'none';
  }

  // Analytics & Admin button in top nav
  const navAdmin = $('#navAdmin');
  if (navAdmin) {
    navAdmin.style.display = isAdmin ? 'inline-flex' : 'none';
    navAdmin.classList.toggle('active', STATE.view === 'admin');
  }

  const navStore = $('#navStore');
  if (navStore) {
    navStore.classList.toggle('active', STATE.view === 'store');
  }

  const btnModeStore = $('#btnModeStore');
  const btnModeAdmin = $('#btnModeAdmin');
  if (btnModeStore) btnModeStore.classList.toggle('active', STATE.view === 'store');
  if (btnModeAdmin) btnModeAdmin.classList.toggle('active', STATE.view === 'admin');
}

async function renderMain() {
  const container = $('#appContainer');
  if (STATE.view === 'store') {
    container.innerHTML = await viewStorefront();
  } else {
    // Double safeguard: only render admin if authenticated as admin
    if (!STATE.currentUser || STATE.currentUser.role !== 'admin') {
      STATE.view = 'store';
      container.innerHTML = await viewStorefront();
    } else {
      container.innerHTML = await viewAdminSuite();
    }
  }
  updateNavCounters();
  updateNavState();
}

function updateNavCounters() {
  const cartQty = sum(Object.values(STATE.cart), q => q);
  if ($('#cartCount')) $('#cartCount').textContent = cartQty;
  if ($('#wishCount')) $('#wishCount').textContent = STATE.wishlist.size;

  saveUserCartAndWish();

  const authNav = $('#authNav');
  if (STATE.currentUser) {
    const isAdmin = STATE.currentUser.role === 'admin';
    authNav.innerHTML = `
      <span class="pill ${isAdmin ? 'pill-green' : 'pill-blue'}">
        ${isAdmin ? '🛡️ Admin' : STATE.currentUser.name.split(' ')[0]}
      </span>
      <button class="btn btn-sm btn-outline" onclick="userLogout()">Logout</button>
    `;
    if ($('#navOrders')) $('#navOrders').style.display = 'inline-flex';
  } else {
    authNav.innerHTML = `
      <button class="btn btn-sm btn-outline" onclick="openAuthModal('login')">Sign In</button>
    `;
    if ($('#navOrders')) $('#navOrders').style.display = 'none';
  }
}

/* ==========================================================================
   STOREFRONT CONTROLLER (CONSUMER EXPERIENCE)
   ========================================================================== */
async function loadProducts() {
  try {
    STATE.products = await API.getProducts();
  } catch (err) {
    console.error('API Error loading products:', err);
  }
}

async function viewStorefront() {
  if (!STATE.products.length) await loadProducts();

  const q = STATE.searchQuery.toLowerCase();
  let prods = STATE.products.filter(p => !p.is_deleted &&
    (!STATE.selectedCategory || p.category === STATE.selectedCategory) &&
    (!q || (p.name + ' ' + p.category + ' ' + (p.description || '')).toLowerCase().includes(q))
  );

  if (STATE.sortBy === 'lo') prods.sort((a, b) => a.price - b.price);
  else if (STATE.sortBy === 'hi') prods.sort((a, b) => b.price - a.price);
  else if (STATE.sortBy === 'rt') prods.sort((a, b) => (b.avg_rating || 0) - (a.avg_rating || 0));

  return `
    <div class="category-chips">
      <button class="cat-chip ${STATE.selectedCategory===''?'active':''}" onclick="setCategory('')">All Categories</button>
      ${CATEGORIES.map(c => `
        <button class="cat-chip ${STATE.selectedCategory===c?'active':''}" onclick="setCategory('${c}')">${c}</button>
      `).join('')}
    </div>

    <div class="card-header">
      <div>
        <h2>Catalog Browse</h2>
        <p class="sub">${prods.length} products available for immediate order</p>
      </div>
      <div class="flex-row">
        <label style="font-size:11px;color:var(--text-muted);font-weight:600">SORT BY:</label>
        <select style="width:140px;font-size:12px;padding:4px 8px;" onchange="setSort(this.value)">
          <option value="rel" ${STATE.sortBy==='rel'?'selected':''}>Relevance</option>
          <option value="lo" ${STATE.sortBy==='lo'?'selected':''}>Price: Low to High</option>
          <option value="hi" ${STATE.sortBy==='hi'?'selected':''}>Price: High to Low</option>
          <option value="rt" ${STATE.sortBy==='rt'?'selected':''}>Highest Rated</option>
        </select>
      </div>
    </div>

    <div class="store-grid">
      ${prods.map(p => `
        <div class="product-card" onclick="openProductDetail(${p.id})">
          <div class="product-thumb">
            <span>${p.emoji}</span>
            <div class="wish-toggle" onclick="event.stopPropagation();toggleWish(${p.id})">
              ${STATE.wishlist.has(p.id) ? '❤️' : '🤍'}
            </div>
          </div>
          <span class="p-cat">${p.category}</span>
          <h3 class="p-title">${p.name}</h3>
          <div class="p-rating">
            <span style="color:var(--warning)">★</span>
            <strong>${(p.avg_rating || 4.5).toFixed(1)}</strong>
            <span style="color:var(--text-subtle)">(${p.review_count || 12})</span>
          </div>
          <div class="p-price-row">
            <span class="p-price">${fmtMoney(p.price)}</span>
            <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();addToCart(${p.id})">Add</button>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

function setCategory(cat) {
  STATE.selectedCategory = cat;
  renderMain();
}

function setSort(s) {
  STATE.sortBy = s;
  renderMain();
}

function onSearch(val) {
  STATE.searchQuery = val;
  renderMain();
}

function addToCart(pid) {
  const prod = STATE.products.find(p => p.id === pid);
  if (!prod) return;
  const current = STATE.cart[pid] || 0;
  if (current >= prod.stock) {
    showToast(`Maximum stock limit (${prod.stock}) reached`);
    return;
  }
  STATE.cart[pid] = current + 1;
  updateNavCounters();
  showToast(`Added "${prod.name}" to cart`);
}

function toggleWish(pid) {
  if (STATE.wishlist.has(pid)) {
    STATE.wishlist.delete(pid);
    showToast('Removed from saved items');
  } else {
    STATE.wishlist.add(pid);
    showToast('Added to saved items');
  }
  updateNavCounters();
  renderMain();
}

async function openProductDetail(pid) {
  const p = STATE.products.find(x => x.id === pid);
  if (!p) return;

  let reviews = [];
  try {
    reviews = await API.getProductReviews(pid);
  } catch (e) {}

  let suggestedPids = [];
  try {
    const rules = await API.getMarketBasket(1.5, 20.0);
    const matches = (rules.rules || []).filter(r => r.antecedents.includes(pid));
    if (matches.length) {
      suggestedPids = [...new Set(matches.flatMap(m => m.consequents))].slice(0, 2);
    }
  } catch (e) {}

  const modalHtml = `
    <button class="modal-close" onclick="closeModal()">×</button>
    <div class="flex-row" style="align-items:flex-start;gap:18px;">
      <div style="font-size:64px;background:var(--bg-subtle);border-radius:var(--radius-md);width:110px;height:110px;display:grid;place-items:center;">
        ${p.emoji}
      </div>
      <div style="flex:1;">
        <span class="pill pill-blue">${p.category}</span>
        <h2 style="font-size:18px;margin:6px 0 4px;">${p.name}</h2>
        <div class="p-rating">
          <span style="color:var(--warning)">★</span>
          <strong>${(p.avg_rating || 4.5).toFixed(1)}</strong>
          <span style="color:var(--text-subtle)">(${p.review_count || 12} customer reviews)</span>
        </div>
        <div style="font-size:22px;font-weight:700;margin:8px 0;color:var(--text-main);">
          ${fmtMoney(p.price)}
        </div>
        <p style="font-size:12.5px;color:var(--text-muted);margin-bottom:14px;line-height:1.4;">
          ${p.description || 'Enterprise grade merchandise with verified supplier quality.'}
        </p>
        <div class="flex-row">
          <button class="btn btn-primary" onclick="addToCart(${p.id});closeModal()">Add to Cart</button>
          <button class="btn btn-outline" onclick="toggleWish(${p.id})">
            ${STATE.wishlist.has(p.id) ? 'Saved ❤️' : 'Save 🤍'}
          </button>
        </div>
      </div>
    </div>

    ${suggestedPids.length ? `
      <div style="margin-top:16px;padding:10px;border-radius:var(--radius-md);background:var(--bg-subtle);border:1px solid var(--border-main);">
        <div class="flex-row" style="justify-content:space-between;margin-bottom:6px;">
          <h4 style="font-size:11.5px;color:var(--text-main);font-weight:700;">Frequently Bought Together (Association Mining)</h4>
        </div>
        <div class="flex-row">
          ${suggestedPids.map(sid => {
            const sp = STATE.products.find(x => x.id === sid);
            if (!sp) return '';
            return `
              <div style="background:var(--bg-surface);border:1px solid var(--border-main);padding:5px 8px;border-radius:var(--radius-sm);display:flex;align-items:center;gap:6px;">
                <span style="font-size:16px">${sp.emoji}</span>
                <div>
                  <div style="font-size:11.5px;font-weight:600">${sp.name}</div>
                  <div style="font-size:10.5px;color:var(--text-muted)">${fmtMoney(sp.price)}</div>
                </div>
              </div>
            `;
          }).join('')}
          <button class="btn btn-sm btn-primary" onclick="addBundleToCart(${pid}, [${suggestedPids.join(',')}])">+ Add Bundle</button>
        </div>
      </div>
    ` : ''}

    <div style="margin-top:16px;border-top:1px solid var(--border-main);padding-top:12px;">
      <h3 style="font-size:12.5px;font-weight:700;margin-bottom:8px;">Customer Reviews</h3>
      ${reviews.length ? reviews.map(rv => `
        <div style="border-bottom:1px solid var(--border-main);padding:6px 0;">
          <div class="flex-row" style="justify-content:space-between;font-size:11.5px;">
            <strong>${rv.author}</strong>
            <span style="color:var(--warning)">${'★'.repeat(rv.rating)}${'☆'.repeat(5-rv.rating)}</span>
          </div>
          <p style="font-size:11.5px;color:var(--text-muted);margin-top:2px;">${rv.comment}</p>
        </div>
      `).join('') : '<p style="font-size:11.5px;color:var(--text-muted)">No reviews yet.</p>'}
    </div>
  `;
  showModal(modalHtml);
}

function addBundleToCart(mainPid, addlPids) {
  addToCart(mainPid);
  addlPids.forEach(id => addToCart(id));
  closeModal();
  showToast('Bundle added to shopping cart');
}

function openCartModal() {
  const pids = Object.keys(STATE.cart).map(Number);
  const total = sum(pids, id => {
    const p = STATE.products.find(x => x.id === id);
    return p ? STATE.cart[id] * p.price : 0;
  });

  if (!pids.length) {
    showModal(`
      <button class="modal-close" onclick="closeModal()">×</button>
      <div style="text-align:center;padding:24px 10px;">
        <div style="font-size:36px;margin-bottom:8px;">🛒</div>
        <h3>Your Cart is Empty</h3>
        <p style="color:var(--text-muted);font-size:12.5px;margin:8px 0 16px;">Add items to your cart to proceed.</p>
        <button class="btn btn-primary" onclick="closeModal()">Browse Catalog</button>
      </div>
    `);
    return;
  }

  const modalHtml = `
    <button class="modal-close" onclick="closeModal()">×</button>
    <div class="flex-row" style="justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h3 style="margin:0;">Shopping Cart</h3>
      <button class="btn btn-sm btn-outline" style="color:var(--danger);border-color:var(--danger-subtle);" onclick="clearCart()">Empty Cart 🗑️</button>
    </div>
    <div style="max-height:260px;overflow-y:auto;border-bottom:1px solid var(--border-main);padding-bottom:10px;">
      ${pids.map(id => {
        const prod = STATE.products.find(x => x.id === id);
        if (!prod) return '';
        const qty = STATE.cart[id];
        return `
          <div class="flex-row" style="justify-content:space-between;border-bottom:1px solid var(--border-main);padding:6px 0;">
            <div class="flex-row" style="gap:8px;">
              <span style="font-size:22px">${prod.emoji}</span>
              <div>
                <strong style="font-size:12.5px">${prod.name}</strong>
                <div style="font-size:10.5px;color:var(--text-muted)">${fmtMoney(prod.price)}</div>
              </div>
            </div>
            <div class="flex-row">
              <button class="btn btn-sm btn-outline" onclick="modifyCartQty(${id}, -1)">-</button>
              <strong style="min-width:20px;text-align:center">${qty}</strong>
              <button class="btn btn-sm btn-outline" onclick="modifyCartQty(${id}, 1)">+</button>
              <strong style="min-width:65px;text-align:right">${fmtMoney(prod.price * qty)}</strong>
            </div>
          </div>
        `;
      }).join('')}
    </div>

    <div class="flex-row" style="justify-content:space-between;margin:12px 0;">
      <span style="font-weight:600;">Total:</span>
      <span style="font-size:18px;font-weight:700;color:var(--text-main)">${fmtMoney(total)}</span>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px;">
      <div>
        <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">DELIVERY CITY</label>
        <select id="checkoutCity">
          ${CITY_LOOKUP.map(c => `<option value="${c[0]}">${c[0]}, ${c[1]}</option>`).join('')}
        </select>
      </div>
      <div>
        <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">PAYMENT METHOD</label>
        <select id="checkoutPay">
          ${PAYMENT_METHODS.map(m => `<option value="${m}">${m}</option>`).join('')}
        </select>
      </div>
    </div>

    <button class="btn btn-primary" style="width:100%;padding:9px;" onclick="executeCheckout()">
      Place Order
    </button>
  `;
  showModal(modalHtml);
}

function modifyCartQty(pid, delta) {
  const current = STATE.cart[pid] || 0;
  const next = current + delta;
  const prod = STATE.products.find(x => x.id === pid);
  if (next <= 0) delete STATE.cart[pid];
  else if (prod && next > prod.stock) {
    showToast(`Stock limit: ${prod.stock}`);
    return;
  } else {
    STATE.cart[pid] = next;
  }
  updateNavCounters();
  openCartModal();
}

/**
 * Bulletproof Checkout Fix:
 * Resolves customer_id reliably from active session or fallback.
 */
async function executeCheckout() {
  if (!STATE.currentUser) {
    closeModal();
    openAuthModal('login');
    showToast('Please sign in to place an order');
    return;
  }

  // Guaranteed Customer ID resolution
  const resolvedCustomerId = (STATE.currentUser.customer_id || STATE.currentUser.id || 1);

  const pids = Object.keys(STATE.cart).map(Number);
  const city = $('#checkoutCity').value;
  const pay = $('#checkoutPay').value;

  const items = pids.map(id => {
    const p = STATE.products.find(x => x.id === id);
    return {
      product_id: id,
      quantity: STATE.cart[id],
      unit_price: p.price
    };
  });

  try {
    const res = await API.checkout({
      customer_id: resolvedCustomerId,
      items,
      delivery_city: city,
      payment_method: pay
    });

    STATE.cart = {};
    updateNavCounters();
    await loadProducts();

    const isAdmin = STATE.currentUser.role === 'admin';

    showModal(`
      <button class="modal-close" onclick="closeModal()">×</button>
      <div style="text-align:center;padding:16px 6px;">
        <div style="font-size:36px;margin-bottom:8px;">✅</div>
        <span class="pill pill-green" style="margin-bottom:6px">Order Confirmed</span>
        <h3 style="margin-bottom:8px;">Order ${res.order_id} Placed</h3>
        <p style="color:var(--text-muted);font-size:12.5px;max-width:380px;margin:0 auto 14px;">
          Your order has been recorded into the operational database for delivery to <strong>${city}</strong>.
        </p>
        <div class="flex-row" style="justify-content:center;gap:10px;">
          <button class="btn btn-outline" onclick="closeModal();openOrdersModal();">Track My Orders</button>
          ${isAdmin ? `
            <button class="btn btn-primary" onclick="closeModal();switchView('admin');">View in Warehouse ➔</button>
          ` : `
            <button class="btn btn-primary" onclick="closeModal();">Continue Shopping</button>
          `}
        </div>
      </div>
    `);
  } catch (err) {
    showToast(err.message);
  }
}

async function openOrdersModal() {
  if (!STATE.currentUser) return;
  const cid = STATE.currentUser.customer_id || STATE.currentUser.id || 1;
  let orders = [];
  try {
    orders = await API.getCustomerOrders(cid);
  } catch (err) {
    showToast('Failed to fetch order history');
  }

  const modalHtml = `
    <button class="modal-close" onclick="closeModal()">×</button>
    <h3>My Orders</h3>
    <p style="font-size:11.5px;color:var(--text-muted);margin-bottom:12px;">Order history for ${STATE.currentUser.name}</p>
    
    <div style="max-height:380px;overflow-y:auto;">
      ${orders.length ? orders.map(o => {
        const statusIdx = ORDER_STATUSES.indexOf(o.status);
        return `
          <div class="card" style="margin-bottom:10px;padding:10px;">
            <div class="flex-row" style="justify-content:space-between;margin-bottom:4px;">
              <div>
                <strong>${o.id}</strong>
                <span style="font-size:10.5px;color:var(--text-muted);margin-left:6px;">${o.order_date} • ${o.delivery_city}</span>
              </div>
              <span class="pill ${statusIdx===3?'pill-green':'pill-blue'}">${o.status}</span>
            </div>

            <div style="display:flex;gap:4px;margin:6px 0;">
              ${ORDER_STATUSES.map((st, i) => `
                <div style="flex:1;height:3px;border-radius:2px;background:${i<=statusIdx?'var(--success)':'var(--border-main)'}"></div>
              `).join('')}
            </div>
            <div style="display:flex;justify-content:space-between;font-size:10px;color:var(--text-subtle);margin-bottom:6px;">
              ${ORDER_STATUSES.map(st => `<span>${st}</span>`).join('')}
            </div>

            <div style="font-size:11.5px;color:var(--text-muted);">
              ${o.items_summary || ''}
            </div>
            <div style="text-align:right;font-size:12.5px;font-weight:700;margin-top:4px;color:var(--text-main);">
              Total: ${fmtMoney(o.total_amount)}
            </div>
          </div>
        `;
      }).join('') : '<p style="color:var(--text-muted);padding:14px 0;">No orders found.</p>'}
    </div>
  `;
  showModal(modalHtml);
}

function openWishModal() {
  const pids = [...STATE.wishlist];
  const prods = pids.map(id => STATE.products.find(p => p.id === id)).filter(Boolean);

  const modalHtml = `
    <button class="modal-close" onclick="closeModal()">×</button>
    <h3>Saved Items (${prods.length})</h3>
    <div style="max-height:340px;overflow-y:auto;margin-top:10px;">
      ${prods.length ? prods.map(p => `
        <div class="flex-row" style="justify-content:space-between;border-bottom:1px solid var(--border-main);padding:6px 0;">
          <div class="flex-row" style="gap:8px;">
            <span style="font-size:20px">${p.emoji}</span>
            <div>
              <strong>${p.name}</strong>
              <div style="font-size:10.5px;color:var(--text-muted)">${p.category} • ${fmtMoney(p.price)}</div>
            </div>
          </div>
          <div class="flex-row">
            <button class="btn btn-sm btn-primary" onclick="addToCart(${p.id});closeModal()">Add to Cart</button>
            <button class="btn btn-sm btn-outline" onclick="toggleWish(${p.id});openWishModal()">Remove</button>
          </div>
        </div>
      `).join('') : '<p style="color:var(--text-muted);padding:14px 0;">No saved items.</p>'}
    </div>
  `;
  showModal(modalHtml);
}

/* Authentication with RBAC */
function openAuthModal(mode = 'login') {
  showModal(`
    <button class="modal-close" onclick="closeModal()">×</button>
    <div class="flex-row" style="margin-bottom:12px;gap:8px;">
      <button class="btn btn-sm ${mode==='login'?'btn-primary':'btn-outline'}" onclick="openAuthModal('login')">Customer Sign In</button>
      <button class="btn btn-sm ${mode==='admin'?'btn-primary':'btn-outline'}" onclick="openAuthModal('admin')">Admin Portal</button>
      <button class="btn btn-sm ${mode==='register'?'btn-primary':'btn-outline'}" onclick="openAuthModal('register')">Register</button>
    </div>
    
    ${mode === 'admin' ? `
      <h3>Administrator Portal</h3>
      <p style="font-size:11.5px;color:var(--text-muted);margin-bottom:12px;">Access Data Warehouse, Machine Learning algorithms, and Database Inspector.</p>
      <div style="display:grid;gap:8px;">
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">ADMIN EMAIL</label>
          <input id="authEmail" value="admin@shop.in">
        </div>
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">PASSWORD</label>
          <input id="authPw" type="password" value="admin123">
        </div>
        <button class="btn btn-primary" style="padding:8px;" onclick="userLogin(true)">Access Admin &amp; Analytics</button>
      </div>
      <div style="margin-top:10px;padding:8px;background:var(--bg-subtle);border-radius:var(--radius-sm);font-size:11px;color:var(--text-muted);">
        Default Admin credentials: <code>admin@shop.in</code> / <code>admin123</code>
      </div>
    ` : mode === 'login' ? `
      <h3>Customer Sign In</h3>
      <p style="font-size:11.5px;color:var(--text-muted);margin-bottom:12px;">Sign in to view your orders and shop.</p>
      <div style="display:grid;gap:8px;">
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">EMAIL</label>
          <input id="authEmail" value="demo@shop.in">
        </div>
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">PASSWORD</label>
          <input id="authPw" type="password" value="demo123">
        </div>
        <button class="btn btn-primary" style="padding:8px;" onclick="userLogin(false)">Sign In</button>
      </div>
      <div style="margin-top:10px;padding:8px;background:var(--bg-subtle);border-radius:var(--radius-sm);font-size:11px;color:var(--text-muted);">
        Demo customer credentials: <code>demo@shop.in</code> / <code>demo123</code>
      </div>
    ` : `
      <h3>Create Customer Account</h3>
      <div style="display:grid;gap:8px;">
        <input id="regName" placeholder="Full Name">
        <input id="regEmail" placeholder="Email address">
        <input id="regPw" type="password" placeholder="Password">
        <select id="regCity">
          ${CITY_LOOKUP.map(c => `<option value="${c[0]}">${c[0]}, ${c[1]}</option>`).join('')}
        </select>
        <button class="btn btn-primary" style="padding:8px;" onclick="userRegister()">Register</button>
      </div>
    `}
  `);
}

async function userLogin(intendedForAdmin = false) {
  const email = $('#authEmail').value.trim();
  const password = $('#authPw').value;
  try {
    const user = await API.login(email, password);
    STATE.currentUser = user;
    localStorage.setItem('nexus_user', JSON.stringify(user));
    loadUserCartAndWish(user);
    closeModal();
    showToast(`Signed in as ${user.name}`);
    updateNavCounters();
    updateNavState();

    if (user.role === 'admin' && intendedForAdmin) {
      switchView('admin');
    } else {
      switchView('store');
    }
  } catch (err) {
    showToast(err.message);
  }
}

async function userRegister() {
  const name = $('#regName').value.trim();
  const email = $('#regEmail').value.trim();
  const password = $('#regPw').value;
  const city = $('#regCity').value;

  if (!name || !email || !password) {
    showToast('All fields required');
    return;
  }

  try {
    const user = await API.register({ name, email, password, city });
    STATE.currentUser = user;
    localStorage.setItem('nexus_user', JSON.stringify(user));
    STATE.cart = {};
    STATE.wishlist = new Set();
    saveUserCartAndWish();
    closeModal();
    showToast(`Account created for ${name}`);
    updateNavCounters();
    updateNavState();
    switchView('store');
  } catch (err) {
    showToast(err.message);
  }
}

function userLogout() {
  saveUserCartAndWish();
  STATE.currentUser = null;
  localStorage.removeItem('nexus_user');
  STATE.cart = {};
  STATE.wishlist = new Set();
  saveUserCartAndWish();
  showToast('Signed out');
  updateNavCounters();
  updateNavState();
  switchView('store');
}

function showModal(content) {
  const ov = $('#modalOverlay');
  ov.innerHTML = `<div class="modal-box">${content}</div>`;
  ov.classList.add('active');
}
function closeModal() {
  $('#modalOverlay').classList.remove('active');
}

/* ==========================================================================
   ADMIN & DATA WAREHOUSING / MINING CONTROLLER (RESTRICTED TO ADMIN)
   Landscape 16:9 Aspect Ratio Architecture
   ========================================================================== */
async function viewAdminSuite() {
  // Strict access verification
  if (!STATE.currentUser || STATE.currentUser.role !== 'admin') {
    return `<div class="card" style="text-align:center;padding:40px;"><h3>Access Restricted</h3></div>`;
  }

  // NOTE: Dedicated documentation tab removed per user directive
  const tabs = [
    ['overview', 'Overview & KPIs'],
    ['etl', 'ETL Pipeline'],
    ['dw', 'Star Schema'],
    ['olap', 'OLAP Cube'],
    ['loyalty', 'Customer Clusters'],
    ['predict', 'Classification'],
    ['forecast', 'Sales Forecast'],
    ['basket', 'Market Basket'],
    ['catalog', 'Catalog & Orders'],
    ['db', 'Database Inspector']
  ];

  return `
    <div class="card-header">
      <div>
        <h2>Data Warehouse &amp; Executive Analytics</h2>
        <p class="sub">Dynamic calculations live from SQLite operational &amp; star schema tables</p>
      </div>
      <div class="flex-row">
        <button class="btn btn-sm btn-outline" onclick="switchView('store')">Browse Storefront</button>
        <button class="btn btn-sm btn-primary" onclick="triggerETLRefresh()">⚡ Re-run ETL Pipeline</button>
      </div>
    </div>

    <div class="admin-tabs">
      ${tabs.map(t => `
        <button class="tab-btn ${STATE.adminTab===t[0]?'active':''}" onclick="STATE.adminTab='${t[0]}';renderMain()">${t[1]}</button>
      `).join('')}
    </div>

    <div id="adminModuleContainer">
      ${await renderAdminTabModule()}
    </div>
  `;
}

async function triggerETLRefresh() {
  try {
    const res = await API.runETL();
    showToast(`ETL Completed: ${res.audit.facts_loaded} fact rows loaded in ${res.audit.duration_ms} ms`);
    await renderMain();
  } catch (err) {
    showToast('ETL failed: ' + err.message);
  }
}

async function renderAdminTabModule() {
  switch (STATE.adminTab) {
    case 'overview': return await moduleOverview();
    case 'etl': return await moduleETL();
    case 'dw': return await moduleWarehouse();
    case 'olap': return await moduleOLAP();
    case 'loyalty': return await moduleLoyaltyClustering();
    case 'predict': return await moduleClassification();
    case 'forecast': return await moduleForecasting();
    case 'basket': return await moduleMarketBasket();
    case 'catalog': return await moduleCatalogAdmin();
    case 'db': return await moduleDatabaseInspector();
    default: return await moduleOverview();
  }
}

/* 1. Overview & KPIs */
async function moduleOverview() {
  let data = { total_revenue: 0, total_profit: 0, total_units: 0, total_orders: 0, active_customers: 0, aov: 0, monthly_trend: {}, category_breakdown: {}, top_skus: [], geo_breakdown: [] };
  try { data = await API.getAnalyticsOverview(); } catch (e) {}

  setTimeout(() => {
    const months = Object.keys(data.monthly_trend).sort();
    renderChart('chartSalesTrend', {
      type: 'line',
      data: {
        labels: months,
        datasets: [{
          label: 'Revenue (₹)',
          data: months.map(m => data.monthly_trend[m]),
          borderColor: '#7c3aed',
          backgroundColor: 'rgba(124, 58, 237, 0.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 2
        }]
      }
    });

    const cats = Object.keys(data.category_breakdown);
    renderChart('chartCatDoughnut', {
      type: 'doughnut',
      data: {
        labels: cats,
        datasets: [{
          data: cats.map(c => data.category_breakdown[c]),
          backgroundColor: ['#7c3aed', '#a78bfa', '#059669', '#d97706', '#ec4899', '#64748b']
        }]
      },
      options: { plugins: { legend: { position: 'right' } } }
    });

    renderChart('chartTopProducts', {
      type: 'bar',
      data: {
        labels: data.top_skus.map(x => x[0]),
        datasets: [{
          label: 'Sales (₹)',
          data: data.top_skus.map(x => x[1]),
          backgroundColor: '#7c3aed'
        }]
      },
      options: { indexAxis: 'y', plugins: { legend: { display: false } } }
    });

    renderChart('chartGeoSales', {
      type: 'bar',
      data: {
        labels: data.geo_breakdown.map(x => x[0]),
        datasets: [{
          label: 'Revenue by City (₹)',
          data: data.geo_breakdown.map(x => x[1]),
          backgroundColor: '#059669'
        }]
      },
      options: { plugins: { legend: { display: false } } }
    });
  }, 50);

  return `
    <div class="grid-kpis">
      <div class="kpi-tile">
        <span class="lbl">Total Revenue</span>
        <div class="val">${fmtMoney(data.total_revenue)}</div>
        <span class="sub">Dynamic calculation</span>
      </div>
      <div class="kpi-tile">
        <span class="lbl">Gross Profit (22%)</span>
        <div class="val">${fmtMoney(data.total_profit)}</div>
        <span class="sub">Derived measure</span>
      </div>
      <div class="kpi-tile">
        <span class="lbl">Fulfilled Orders</span>
        <div class="val">${data.total_orders}</div>
        <span class="sub">${data.total_units} units sold</span>
      </div>
      <div class="kpi-tile">
        <span class="lbl">Avg Order Value (AOV)</span>
        <div class="val">${fmtMoney(data.aov)}</div>
        <span class="sub">${data.active_customers} active customers</span>
      </div>
    </div>

    <div class="overview-4-grid">
      <div class="card">
        <h3>Sales Trend (24 Months)</h3>
        <div class="chart-box"><canvas id="chartSalesTrend"></canvas></div>
      </div>
      <div class="card">
        <h3>Revenue by Category</h3>
        <div class="chart-box"><canvas id="chartCatDoughnut"></canvas></div>
      </div>
      <div class="card">
        <h3>Top SKUs</h3>
        <div class="chart-box"><canvas id="chartTopProducts"></canvas></div>
      </div>
      <div class="card">
        <h3>Revenue by City</h3>
        <div class="chart-box"><canvas id="chartGeoSales"></canvas></div>
      </div>
    </div>
  `;
}

/* 2. ETL Pipeline */
async function moduleETL() {
  let e = { raw_orders_count: 0, duplicates_removed: 0, missing_imputed: 0, standardized_payments: 0, invalid_qty_pruned: 0, facts_loaded: 0, duration_ms: 0, run_timestamp: '' };
  try { e = await API.getETLStatus(); } catch (err) {}

  const auditSteps = [
    ['1. Operational De-Duplication', `${e.duplicates_removed} duplicate order rows identified & purged`],
    ['2. Missing Location Imputation', `${e.missing_imputed} missing delivery cities imputed from customer dimensional master`],
    ['3. Payment Key Canonicalization', `${e.standardized_payments} string discrepancies normalized into canonical keys`],
    ['4. Integrity Validation & Filtering', `${e.invalid_qty_pruned} invalid line items (qty ≤ 0) flagged and pruned`],
    ['5. Derived Measure Construction', `${e.facts_loaded} fact rows computed with derived sales_amount and profit_margin`],
    ['6. Star Schema Loading Latency', `Transformation & pipeline execution concluded in ${e.duration_ms} ms`]
  ];

  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:12px;margin-bottom:12px;">
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div class="card">
          <span class="pill pill-blue">Step 1 · Extract</span>
          <h3 style="margin:6px 0 2px">OLTP Database</h3>
          <div style="font-size:22px;font-weight:700;margin:4px 0;">
            ${e.raw_orders_count || 900} records
          </div>
          <p style="font-size:11.5px;color:var(--text-muted);">Extracted from orders, items, customers, and products.</p>
        </div>

        <div class="card">
          <span class="pill pill-green">Step 2 · Load</span>
          <h3 style="margin:6px 0 2px">Star Schema Warehouse</h3>
          <div style="font-size:22px;font-weight:700;margin:4px 0;">
            ${e.facts_loaded} fact rows
          </div>
          <p style="font-size:11.5px;color:var(--text-muted);">Loaded into central FACT_SALES in ${e.duration_ms} ms.</p>
        </div>

        <button class="btn btn-primary" style="padding:8px;" onclick="triggerETLRefresh()">⚡ Re-run Pipeline</button>
      </div>

      <div class="card" style="grid-column: span 2;">
        <div class="card-header">
          <div>
            <h3>Pipeline Transformation Audit Log</h3>
            <p class="sub">Latest execution: ${e.run_timestamp || 'Active'}</p>
          </div>
        </div>
        <div class="table-responsive" style="max-height:260px;overflow-y:auto;">
          <table>
            <thead>
              <tr><th>Stage</th><th>Result</th></tr>
            </thead>
            <tbody>
              ${auditSteps.map(s => `<tr><td><strong>${s[0]}</strong></td><td>${s[1]}</td></tr>`).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/* 3. Star Schema Architecture */
async function moduleWarehouse() {
  let meta = { fact_count: 0, dimensions: {}, sample_facts: [] };
  try { meta = await API.getWarehouseMeta(); } catch (err) {}
  const d = meta.dimensions || { Customer: 80, Product: 24, Date: 400, Location: 8, Payment: 5 };

  return `
    <div class="card" style="margin-bottom:12px;">
      <h3 style="margin-bottom:10px;">Star Schema Architecture</h3>
      <div class="star-diagram">
        <div style="display:grid;gap:10px;">
          <div class="dim-card">
            <h4>DIM_CUSTOMER (${d.Customer || 80} Rows)</h4>
            <p>PK: customer_id<br>name, age, gender, city, state</p>
          </div>
          <div class="dim-card">
            <h4>DIM_PRODUCT (${d.Product || 24} Rows)</h4>
            <p>PK: product_id<br>name, category, price</p>
          </div>
        </div>

        <div class="fact-card">
          <h3>FACT_SALES</h3>
          <div class="fact-pill">${meta.fact_count} Fact Rows</div>
          <p style="font-size:11px;color:var(--text-muted);text-align:left;line-height:1.4;">
            <strong>Foreign Keys:</strong> customer_id, product_id, date_key, location_key, payment_key<br>
            <strong>Measures:</strong> quantity, sales_amount, profit_margin
          </p>
        </div>

        <div style="display:grid;gap:10px;">
          <div class="dim-card">
            <h4>DIM_DATE (${d.Date || 0} Dates)</h4>
            <p>PK: date_key<br>day, month, quarter, year, weekday</p>
          </div>
          <div class="dim-card">
            <h4>DIM_LOCATION (${d.Location || 8} Cities)</h4>
            <p>PK: city<br>state, region</p>
          </div>
          <div class="dim-card">
            <h4>DIM_PAYMENT (${d.Payment || 5} Methods)</h4>
            <p>PK: payment_key<br>method_name</p>
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3>Fact Table Sample (FACT_SALES)</h3>
          <p class="sub">Direct view from analytical star schema</p>
        </div>
      </div>
      <div class="table-responsive" style="max-height:200px;overflow-y:auto;">
        <table>
          <thead>
            <tr><th>Order ID</th><th>Customer</th><th>Product</th><th>Date</th><th>Location</th><th>Payment</th><th>Qty</th><th>Sales (₹)</th><th>Margin (₹)</th></tr>
          </thead>
          <tbody>
            ${(meta.sample_facts || []).map(f => `
              <tr>
                <td><strong>${f.order_id}</strong></td>
                <td>${f.customer_name}</td>
                <td>${f.product_name}</td>
                <td>${f.date_key}</td>
                <td>${f.location_key}</td>
                <td><span class="pill pill-blue">${f.payment_key}</span></td>
                <td>${f.quantity}</td>
                <td><strong>${fmtMoney(f.sales_amount)}</strong></td>
                <td style="color:var(--success)">${fmtMoney(f.profit_margin)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/* 4. OLAP Multidimensional Cube */
async function moduleOLAP() {
  let olapData = { operation_type: '', level: 'year', group_by: 'Category', measure: 'sales', time_keys: [], dim_groups: [], grid: {} };
  try {
    olapData = await API.getOLAP({
      level: STATE.olapLevel,
      group_by: STATE.olapGroupBy,
      measure: STATE.olapMeasure,
      cat_filter: STATE.olapCatFilter,
      city_filter: STATE.olapCityFilter,
      year_filter: STATE.olapYearFilter
    });
  } catch (err) {}

  setTimeout(() => {
    const palette = ['#7c3aed', '#a78bfa', '#059669', '#d97706', '#ec4899', '#64748b'];
    renderChart('chartOlapCube', {
      type: 'bar',
      data: {
        labels: olapData.time_keys,
        datasets: olapData.dim_groups.map((s, idx) => ({
          label: s,
          data: olapData.time_keys.map(t => (olapData.grid[t] && olapData.grid[t][s]) || 0),
          backgroundColor: palette[idx % palette.length]
        }))
      },
      options: { scales: { x: { stacked: true }, y: { stacked: true } } }
    });
  }, 50);

  const measureFmt = v => STATE.olapMeasure === 'qty' ? (v + ' units') : fmtMoney(v);

  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(290px, 1fr));gap:12px;">
      <!-- Left Column: Controls -->
      <div class="card" style="display:flex;flex-direction:column;gap:10px;">
        <div class="flex-row" style="justify-content:space-between;border-bottom:1px solid var(--border-main);padding-bottom:8px;">
          <span class="pill pill-blue">${olapData.operation_type}</span>
          <strong style="font-size:12px">${STATE.olapLevel.toUpperCase()}</strong>
        </div>
        <div class="flex-row" style="gap:6px;">
          <button class="btn btn-sm btn-outline" style="flex:1" ${STATE.olapLevel==='year'?'disabled':''} onclick="STATE.olapLevel = (STATE.olapLevel==='month'?'quarter':'year');renderMain()">⬆ Roll-up</button>
          <button class="btn btn-sm btn-outline" style="flex:1" ${STATE.olapLevel==='month'?'disabled':''} onclick="STATE.olapLevel = (STATE.olapLevel==='year'?'quarter':'month');renderMain()">⬇ Drill-down</button>
        </div>
        <div>
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">MEASURE:</label>
          <select style="font-size:11.5px;" onchange="STATE.olapMeasure=this.value;renderMain()">
            <option value="sales" ${STATE.olapMeasure==='sales'?'selected':''}>Revenue (₹)</option>
            <option value="qty" ${STATE.olapMeasure==='qty'?'selected':''}>Units Sold</option>
            <option value="profit" ${STATE.olapMeasure==='profit'?'selected':''}>Profit Margin (₹)</option>
          </select>
        </div>
        <div>
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">PIVOT GROUP BY:</label>
          <select style="font-size:11.5px;" onchange="STATE.olapGroupBy=this.value;renderMain()">
            <option value="cat" ${STATE.olapGroupBy==='cat'?'selected':''}>Category</option>
            <option value="city" ${STATE.olapGroupBy==='city'?'selected':''}>City</option>
            <option value="pay" ${STATE.olapGroupBy==='pay'?'selected':''}>Payment Method</option>
            <option value="gender" ${STATE.olapGroupBy==='gender'?'selected':''}>Gender</option>
            <option value="none" ${STATE.olapGroupBy==='none'?'selected':''}>Total</option>
          </select>
        </div>
        <div>
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">CATEGORY SLICE:</label>
          <select style="font-size:11.5px;" onchange="STATE.olapCatFilter=this.value;renderMain()">
            <option value="">(All Categories)</option>
            ${CATEGORIES.map(c => `<option value="${c}" ${STATE.olapCatFilter===c?'selected':''}>${c}</option>`).join('')}
          </select>
        </div>
        <div>
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">LOCATION SLICE:</label>
          <select style="font-size:11.5px;" onchange="STATE.olapCityFilter=this.value;renderMain()">
            <option value="">(All Cities)</option>
            ${CITY_LOOKUP.map(c => `<option value="${c[0]}" ${STATE.olapCityFilter===c[0]?'selected':''}>${c[0]}</option>`).join('')}
          </select>
        </div>
        <div>
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">YEAR SLICE:</label>
          <select style="font-size:11.5px;" onchange="STATE.olapYearFilter=this.value;renderMain()">
            <option value="">(All Years)</option>
            <option value="2024" ${STATE.olapYearFilter==='2024'?'selected':''}>2024</option>
            <option value="2025" ${STATE.olapYearFilter==='2025'?'selected':''}>2025</option>
          </select>
        </div>
      </div>

      <!-- Right Column: Chart + Table -->
      <div style="grid-column: span 2; display:flex; flex-direction:column; gap:12px;">
        <div class="card">
          <div class="card-header">
            <h3>Multidimensional Stacked Chart</h3>
            <span class="pill pill-blue">${STATE.olapLevel.toUpperCase()} View</span>
          </div>
          <div class="chart-box" style="height:190px;"><canvas id="chartOlapCube"></canvas></div>
        </div>

        <div class="card">
          <div class="card-header">
            <h3>Cross-Tabulation Pivot Grid</h3>
          </div>
          <div class="table-responsive" style="max-height:160px;overflow-y:auto;">
            <table>
              <thead>
                <tr><th>${STATE.olapLevel.toUpperCase()}</th>${olapData.dim_groups.map(s => `<th>${s}</th>`).join('')}</tr>
              </thead>
              <tbody>
                ${olapData.time_keys.map(t => `
                  <tr>
                    <td><strong>${t}</strong></td>
                    ${olapData.dim_groups.map(s => `<td>${measureFmt(olapData.grid[t][s] || 0)}</td>`).join('')}
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;
}

/* 5. Customer Clusters */
async function moduleLoyaltyClustering() {
  let clusterData = { segments: [], scatter_points: [], algorithm: 'kmeans', k: 4 };
  try {
    clusterData = await API.getClustering(STATE.clusterAlg, STATE.clusterK);
  } catch (err) {}

  setTimeout(() => {
    const palette = ['#7c3aed', '#a78bfa', '#059669', '#d97706', '#ec4899', '#64748b'];
    renderChart('chartClusterScatter', {
      type: 'scatter',
      data: {
        datasets: clusterData.segments.map((seg, idx) => ({
          label: seg.persona,
          data: (clusterData.scatter_points || []).filter(p => p.cluster === seg.persona).map(p => ({ x: p.orders, y: p.spend })),
          backgroundColor: palette[idx % palette.length],
          pointRadius: 5
        }))
      },
      options: {
        scales: {
          x: { title: { display: true, text: 'Order Count' } },
          y: { title: { display: true, text: 'Spend (₹)' } }
        }
      }
    });
  }, 50);

  return `
    <div class="card" style="margin-bottom:10px;padding:8px 14px;">
      <div class="flex-row" style="gap:16px;">
        <div style="flex:1;">
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">CLUSTERING ALGORITHM:</label>
          <select onchange="STATE.clusterAlg=this.value;renderMain()" style="font-size:11.5px;">
            <option value="kmeans" ${STATE.clusterAlg==='kmeans'?'selected':''}>K-Means (Partitioning)</option>
            <option value="agglo" ${STATE.clusterAlg==='agglo'?'selected':''}>Agglomerative (Hierarchical Bottom-Up)</option>
            <option value="divisive" ${STATE.clusterAlg==='divisive'?'selected':''}>Divisive (Hierarchical Top-Down)</option>
          </select>
        </div>
        <div style="flex:1;">
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">CLUSTERS (k = ${STATE.clusterK}):</label>
          <input type="range" min="2" max="6" value="${STATE.clusterK}" onchange="STATE.clusterK=+this.value;renderMain()">
        </div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <h3>Customer Behavioral Map</h3>
        <div class="chart-box" style="height:210px;"><canvas id="chartClusterScatter"></canvas></div>
      </div>
      <div class="card">
        <h3>Segment Profiles</h3>
        <div class="table-responsive" style="max-height:210px;overflow-y:auto;">
          <table>
            <thead>
              <tr><th>Segment</th><th>Size</th><th>Avg Spend</th><th>Avg Orders</th><th>Strategy</th></tr>
            </thead>
            <tbody>
              ${clusterData.segments.map(g => `
                <tr>
                  <td><strong>${g.persona}</strong></td>
                  <td><span class="pill pill-blue">${g.size}</span></td>
                  <td><strong>${fmtMoney(g.avg_spend)}</strong></td>
                  <td>${g.avg_orders}</td>
                  <td style="font-size:10.5px;color:var(--text-muted)">${g.strategy}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

/* 6. Classification */
async function moduleClassification() {
  let cls = { classes: ['Low-Tier Budget', 'Mid-Tier Core', 'High-Value VIP'], nb_accuracy: 0, nb_confusion_matrix: [[0,0,0],[0,0,0],[0,0,0]], knn_accuracy: 0, k_neighbors: 5, train_samples: 0, test_samples: 0 };
  try {
    cls = await API.getClassification(STATE.knnK);
  } catch (err) {}

  return `
    <div class="grid-2">
      <!-- Left Column: Naive Bayes & KNN metrics -->
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div class="card">
          <div class="card-header">
            <div>
              <h3>Gaussian Naive Bayes</h3>
              <p class="sub">Trained: ${cls.train_samples} | Tested: ${cls.test_samples}</p>
            </div>
            <span class="pill pill-green">${cls.nb_accuracy}% Accuracy</span>
          </div>
          <div class="table-responsive">
            <table>
              <thead>
                <tr><th>Actual \\ Predicted</th>${cls.classes.map(c => `<th>${c}</th>`).join('')}</tr>
              </thead>
              <tbody>
                ${cls.nb_confusion_matrix.map((row, r) => `
                  <tr>
                    <td><strong>${cls.classes[r]}</strong></td>
                    ${row.map((val, c) => `<td style="${r===c?'color:var(--success);font-weight:700;':''}">${val}</td>`).join('')}
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <div class="card-header">
            <div>
              <h3>K-Nearest Neighbors (KNN)</h3>
              <p class="sub">Euclidean distance voting</p>
            </div>
            <span class="pill pill-blue">${cls.knn_accuracy}% Accuracy</span>
          </div>
          <div class="flex-row" style="gap:10px;">
            <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">K-NEIGHBORS (K = ${STATE.knnK}):</label>
            <input type="range" min="1" max="9" step="2" value="${STATE.knnK}" onchange="STATE.knnK=+this.value;renderMain()" style="flex:1;">
          </div>
        </div>
      </div>

      <!-- Right Column: Interactive Predictor Sandbox -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3>Customer Tier Predictor</h3>
            <p class="sub">Simulate classification on custom parameters</p>
          </div>
        </div>
        <div style="display:grid;gap:10px;">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div>
              <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">ORDERS</label>
              <input id="testOrders" type="number" value="12">
            </div>
            <div>
              <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">AOV (₹)</label>
              <input id="testAov" type="number" value="3200">
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div>
              <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">CATEGORIES</label>
              <input id="testCats" type="number" value="4">
            </div>
            <div>
              <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">UNITS</label>
              <input id="testUnits" type="number" value="18">
            </div>
          </div>
          <button class="btn btn-primary" onclick="executeClassificationTest()">Run Classification Prediction</button>
          <div id="predictResultBox"></div>
        </div>
      </div>
    </div>
  `;
}

async function executeClassificationTest() {
  const o = +$('#testOrders').value;
  const a = +$('#testAov').value;
  const c = +$('#testCats').value;
  const u = +$('#testUnits').value;

  try {
    const res = await API.predictClassification({ orders: o, aov: a, categories: c, units: u, k: STATE.knnK });
    $('#predictResultBox').innerHTML = `
      <div style="padding:10px 14px;background:var(--bg-subtle);border:1px solid var(--border-main);border-radius:var(--radius-md);margin-top:6px;" class="flex-row">
        <div style="flex:1">
          <span style="font-size:10.5px;color:var(--text-muted)">NAIVE BAYES:</span>
          <div style="font-size:13px;font-weight:700;color:var(--text-main)">${res.nb_prediction}</div>
        </div>
        <div style="flex:1">
          <span style="font-size:10.5px;color:var(--text-muted)">KNN (K=${STATE.knnK}):</span>
          <div style="font-size:13px;font-weight:700;color:var(--text-main)">${res.knn_prediction}</div>
        </div>
        <div class="pill ${res.consensus?'pill-green':'pill-warning'}">${res.consensus?'Consensus':'Divergent'}</div>
      </div>
    `;
  } catch (err) {
    showToast('Prediction failed: ' + err.message);
  }
}

/* 7. Forecast */
async function moduleForecasting() {
  let reg = { months: [], actual_sales: [], trend_line: [], slope: 0, intercept: 0, r_squared: 0, forecast_months: [], forecast_sales: [] };
  try {
    reg = await API.getForecasting();
  } catch (err) {}

  setTimeout(() => {
    const allLabels = [...reg.months, ...reg.forecast_months];
    renderChart('chartRegression', {
      type: 'line',
      data: {
        labels: allLabels,
        datasets: [
          {
            label: 'Actual (₹)',
            data: reg.actual_sales,
            borderColor: '#7c3aed',
            tension: 0.3,
            pointRadius: 2
          },
          {
            label: 'Trend',
            data: allLabels.map((_, idx) => reg.intercept + reg.slope * idx),
            borderColor: '#059669',
            borderDash: [5, 4],
            pointRadius: 0
          },
          {
            label: 'Forecast',
            data: [...new Array(reg.months.length).fill(null), ...reg.forecast_sales],
            borderColor: '#d97706',
            backgroundColor: '#d97706',
            pointRadius: 5,
            pointStyle: 'triangle',
            showLine: false
          }
        ]
      }
    });
  }, 50);

  return `
    <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(340px, 1fr));gap:12px;">
      <div class="card" style="grid-column: span 1;">
        <div class="card-header">
          <div>
            <h3>Monthly Sales Forecast (Linear Regression)</h3>
            <p class="sub">Slope: +${fmtMoney(reg.slope)}/mo | Intercept: ${fmtMoney(reg.intercept)}</p>
          </div>
          <span class="pill pill-green">R² = ${reg.r_squared}</span>
        </div>
        <div class="chart-box" style="height:230px;"><canvas id="chartRegression"></canvas></div>
      </div>

      <div style="display:flex;flex-direction:column;gap:10px;">
        <div class="card">
          <div class="card-header">
            <h3>Forecast Projections</h3>
            <span class="pill pill-blue">Next 3 Months</span>
          </div>
          <div style="display:grid;gap:8px;">
            ${reg.forecast_months.map((m, idx) => `
              <div style="padding:10px 12px;background:var(--bg-subtle);border-radius:var(--radius-sm);border:1px solid var(--border-main);display:flex;justify-content:space-between;align-items:center;">
                <div>
                  <div style="font-size:10.5px;font-weight:600;color:var(--text-muted)">${m} Forecast</div>
                  <div style="font-size:16px;font-weight:700;color:var(--text-main);margin-top:2px;">${fmtMoney(reg.forecast_sales[idx])}</div>
                </div>
                <span class="pill pill-green">+Growth</span>
              </div>
            `).join('')}
          </div>
        </div>

        <div class="card" style="padding:12px;">
          <div style="font-size:10.5px;font-weight:600;color:var(--text-muted);margin-bottom:6px;">REGRESSION PARAMETERS</div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px;margin-bottom:4px;">
            <span>Coefficient of Determination (R²):</span>
            <strong>${reg.r_squared}</strong>
          </div>
          <div style="display:flex;justify-content:space-between;font-size:11.5px;">
            <span>Monthly Trend Velocity:</span>
            <strong style="color:var(--success)">+${fmtMoney(reg.slope)}/mo</strong>
          </div>
        </div>
      </div>
    </div>
  `;
}

/* 8. Market Basket Analysis */
async function moduleMarketBasket() {
  let mb = { total_transactions: 0, min_support_count: 0, benchmark: { apriori: {}, fpgrowth: {}, eclat: {} }, rules: [] };
  try {
    mb = await API.getMarketBasket(STATE.assocMinSup, STATE.assocMinConf);
  } catch (err) {}

  const bm = mb.benchmark || {};

  return `
    <div class="card" style="margin-bottom:10px;padding:8px 14px;">
      <div class="flex-row" style="gap:14px;justify-content:space-between;">
        <div style="flex:1;min-width:180px;">
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">MIN SUPPORT: ${STATE.assocMinSup}% (${mb.min_support_count} baskets)</label>
          <input type="range" min="0.5" max="5.0" step="0.5" value="${STATE.assocMinSup}" onchange="STATE.assocMinSup=+this.value;renderMain()">
        </div>
        <div style="flex:1;min-width:180px;">
          <label style="font-size:10.5px;color:var(--text-muted);font-weight:600">MIN CONFIDENCE: ${STATE.assocMinConf}%</label>
          <input type="range" min="15" max="80" step="5" value="${STATE.assocMinConf}" onchange="STATE.assocMinConf=+this.value;renderMain()">
        </div>
        <div class="flex-row" style="gap:8px;">
          <span class="pill pill-blue">Apriori: ${bm.apriori ? bm.apriori.latency_ms : 0}ms</span>
          <span class="pill pill-green">FP-Growth: ${bm.fpgrowth ? bm.fpgrowth.latency_ms : 0}ms</span>
          <span class="pill pill-warning">Eclat: ${bm.eclat ? bm.eclat.latency_ms : 0}ms</span>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3>Mined Association Rules (Ranked by Lift)</h3>
          <p class="sub">${(mb.rules || []).length} cross-sell rules discovered</p>
        </div>
      </div>
      <div class="table-responsive" style="max-height:270px;overflow-y:auto;">
        <table>
          <thead>
            <tr><th>Antecedent</th><th>Consequent</th><th>Support</th><th>Confidence</th><th>Lift</th></tr>
          </thead>
          <tbody>
            ${(mb.rules || []).slice(0, 15).map(r => `
              <tr>
                <td><strong>${r.antecedent_names.join(' + ')}</strong></td>
                <td><strong>${r.consequent_names.join(' + ')}</strong></td>
                <td>${r.support}%</td>
                <td>${r.confidence}%</td>
                <td><span class="pill pill-blue">${r.lift}x</span></td>
            `).join('') || '<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-muted);"><div style="font-size:22px;margin-bottom:6px;">🔍</div><strong>No association rules meet current filter criteria.</strong><br><span style="font-size:11px;">Adjust <strong>Min Support</strong> (e.g. 1.5% - 2%) or <strong>Min Confidence</strong> (e.g. 25% - 35%) to discover cross-sell pairs.</span></td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/* 9. Catalog & Live Operational Orders */
async function moduleCatalogAdmin() {
  let orders = [];
  try { orders = await API.getAdminOrders(); } catch (e) {}

  return `
    <div class="grid-2">
      <!-- Left Column: Catalog -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3>Catalog Management</h3>
            <p class="sub">Manage SKUs in SQLite operational DB</p>
          </div>
          <button class="btn btn-sm btn-primary" onclick="openProductEditModal(null)">+ Add Product</button>
        </div>
        <div class="table-responsive" style="max-height:300px;overflow-y:auto;">
          <table>
            <thead>
              <tr><th>SKU</th><th>Name</th><th>Category</th><th>Price</th><th>Stock</th><th>Action</th></tr>
            </thead>
            <tbody>
              ${STATE.products.filter(p => !p.is_deleted).map(p => `
                <tr>
                  <td><strong>#SKU-${pad(p.id)}</strong></td>
                  <td>${p.emoji} ${p.name}</td>
                  <td><span class="pill pill-blue">${p.category}</span></td>
                  <td>${fmtMoney(p.price)}</td>
                  <td>${p.stock}</td>
                  <td>
                    <button class="btn btn-sm btn-outline" onclick="openProductEditModal(${p.id})">Edit</button>
                    <button class="btn btn-sm btn-outline" style="color:var(--danger)" onclick="deleteProduct(${p.id})">Delete</button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right Column: Orders -->
      <div class="card">
        <div class="card-header">
          <div>
            <h3>Live Operational Orders</h3>
            <p class="sub">Real-time status tracking & updates</p>
          </div>
        </div>
        <div class="table-responsive" style="max-height:300px;overflow-y:auto;">
          <table>
            <thead>
              <tr><th>Order ID</th><th>Customer</th><th>Date</th><th>City</th><th>Total</th><th>Status</th></tr>
            </thead>
            <tbody>
              ${orders.map(o => `
                <tr>
                  <td><strong>${o.id}</strong></td>
                  <td>${o.customer_name}</td>
                  <td>${o.order_date}</td>
                  <td>${o.delivery_city}</td>
                  <td>${fmtMoney(o.total_amount)}</td>
                  <td>
                    <select onchange="changeOrderStatus('${o.id}', this.value)" style="padding:3px 5px;font-size:11px;">
                      ${ORDER_STATUSES.map(st => `<option value="${st}" ${st===o.status?'selected':''}>${st}</option>`).join('')}
                    </select>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function openProductEditModal(pid) {
  const p = pid === null ? { name: '', category: CATEGORIES[0], price: 999, stock: 50, emoji: '📦', description: '' } : STATE.products.find(x => x.id === pid);
  showModal(`
    <button class="modal-close" onclick="closeModal()">×</button>
    <h3>${pid===null?'Add New Product':'Edit Product'}</h3>
    <div style="display:grid;gap:8px;margin-top:10px;">
      <div>
        <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">NAME</label>
        <input id="editName" value="${p.name}">
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">CATEGORY</label>
          <select id="editCat">
            ${CATEGORIES.map(c => `<option value="${c}" ${p.category===c?'selected':''}>${c}</option>`).join('')}
          </select>
        </div>
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">PRICE (₹)</label>
          <input id="editPrice" type="number" value="${p.price}">
        </div>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">STOCK UNITS</label>
          <input id="editStock" type="number" value="${p.stock}">
        </div>
        <div>
          <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">ICON / EMOJI</label>
          <input id="editEmo" value="${p.emoji}">
        </div>
      </div>
      <div>
        <label style="font-size:10.5px;font-weight:600;color:var(--text-muted)">DESCRIPTION</label>
        <textarea id="editDesc">${p.description || ''}</textarea>
      </div>
      <button class="btn btn-primary" onclick="saveProduct(${pid})">Save</button>
    </div>
  `);
}

async function saveProduct(pid) {
  const name = $('#editName').value.trim();
  const price = +$('#editPrice').value;
  const stock = +$('#editStock').value;
  const category = $('#editCat').value;
  const emoji = $('#editEmo').value.trim() || '📦';
  const description = $('#editDesc').value.trim();

  if (!name || price <= 0) {
    showToast('Valid name and price required');
    return;
  }

  try {
    if (pid === null) {
      await API.addProduct({ name, category, price, stock, emoji, description });
      showToast('Product added to database');
    } else {
      await API.updateProduct(pid, { name, category, price, stock, emoji, description });
      showToast('Product updated');
    }
    closeModal();
    await loadProducts();
    renderMain();
  } catch (err) {
    showToast(err.message);
  }
}

async function deleteProduct(pid) {
  if (confirm('Delete this product?')) {
    try {
      await API.deleteProduct(pid);
      showToast('Product deleted');
      await loadProducts();
      renderMain();
    } catch (err) {
      showToast(err.message);
    }
  }
}

async function changeOrderStatus(oid, status) {
  try {
    await API.updateOrderStatus(oid, status);
    showToast(`Order status updated`);
  } catch (err) {
    showToast(err.message);
  }
}

/* ==========================================================================
   10. Database Inspector & SQL Console (Answers "Show Ma'am the Backend DB")
   ========================================================================== */
async function moduleDatabaseInspector() {
  let tablesList = [];
  try {
    const res = await API.getDBTables();
    tablesList = res.tables || [];
  } catch (e) {}

  if (!tablesList.includes(STATE.selectedTable) && tablesList.length) {
    STATE.selectedTable = tablesList.includes('orders') ? 'orders' : tablesList[0];
  }

  let tableData = { columns: [], rows: [] };
  try {
    tableData = await API.getDBTableData(STATE.selectedTable, 50);
  } catch (e) {}

  return `
    <div class="card" style="margin-bottom:12px;">
      <div class="card-header">
        <div>
          <h3>Backend Database Inspector (SQLite Relational Store)</h3>
          <p class="sub">Direct live inspection of database tables: <code>backend/nexus_ecommerce.db</code></p>
        </div>
        <div class="flex-row" style="gap:10px;">
          <button class="btn btn-sm btn-outline" style="color:var(--danger);border-color:var(--danger-subtle);" onclick="resetSystemDatabase()" title="Wipe custom test orders and restore clean 900-order benchmark">Reset DB to Demo State 🔄</button>
          <div class="flex-row" style="gap:4px;">
            <label style="font-size:11px;font-weight:600;color:var(--text-muted)">SELECT TABLE:</label>
            <select style="width:160px;font-size:12px;" onchange="inspectTable(this.value)">
              ${tablesList.map(t => `<option value="${t}" ${t===STATE.selectedTable?'selected':''}>${t}</option>`).join('')}
            </select>
          </div>
        </div>
      </div>

      <div class="flex-row" style="margin-bottom:10px;gap:8px;">
        <span class="pill pill-blue">Active Table: <strong>${STATE.selectedTable}</strong></span>
        <span class="pill pill-green">Rows Displayed: ${tableData.rows.length}</span>
        <span class="pill">Columns: ${tableData.columns.length}</span>
      </div>

      <div class="table-responsive" style="max-height:280px;overflow-y:auto;" id="dbInspectorTableWrap">
        <table>
          <thead>
            <tr>
              ${tableData.columns.map(c => `<th>${c}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${tableData.rows.length ? tableData.rows.map(row => `
              <tr>
                ${row.map(cell => `<td>${cell === null ? '<em style="color:var(--text-subtle)">NULL</em>' : String(cell)}</td>`).join('')}
              </tr>
            `).join('') : `<tr><td colspan="${tableData.columns.length || 1}" style="color:var(--text-muted)">No rows in table.</td></tr>`}
          </tbody>
        </table>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h3>Interactive SQL Query Sandbox</h3>
          <p class="sub">Run live SELECT queries directly against the operational and analytical tables</p>
        </div>
      </div>
      <div style="display:flex;gap:10px;margin-bottom:10px;">
        <input id="customSqlInput" value="SELECT id, customer_id, order_date, delivery_city, total_amount, status FROM orders ORDER BY id DESC LIMIT 10">
        <button class="btn btn-primary" onclick="executeCustomSql()">Run Query</button>
      </div>
      <div id="sqlQueryResultBox"></div>
    </div>
  `;
}

async function inspectTable(tableName) {
  STATE.selectedTable = tableName;
  renderMain();
}

async function executeCustomSql() {
  const query = $('#customSqlInput').value.trim();
  if (!query) return;

  try {
    const res = await API.runDBQuery(query);
    const data = res.data;
    $('#sqlQueryResultBox').innerHTML = `
      <div style="font-size:11px;color:var(--success);font-weight:600;margin-bottom:6px;">✓ Query executed: ${data.rows.length} rows returned</div>
      <div class="table-responsive" style="max-height:240px;overflow-y:auto;">
        <table>
          <thead>
            <tr>${data.columns.map(c => `<th>${c}</th>`).join('')}</tr>
          </thead>
          <tbody>
            ${data.rows.map(r => `
              <tr>${r.map(v => `<td>${v===null?'<em>NULL</em>':v}</td>`).join('')}</tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    $('#sqlQueryResultBox').innerHTML = `
      <div style="color:var(--danger);font-size:12px;padding:8px;background:var(--danger-soft);border-radius:var(--radius-sm);">
        Error: ${err.message}
      </div>
    `;
  }
}

async function resetSystemDatabase() {
  if (!confirm("Are you sure you want to reset the database and warehouse to clean demo state? This will clear all test orders.")) return;
  try {
    showToast('Resetting database and running ETL...');
    const res = await API.resetDatabase();
    localStorage.removeItem('nexus_cart');
    STATE.cart = {};
    saveUserCartAndWish();
    updateNavCounters();
    await loadProducts();
    showToast(res.message);
    renderMain();
  } catch (err) {
    showToast('Reset error: ' + err.message);
  }
}

// Initialization
window.addEventListener('DOMContentLoaded', async () => {
  applyTheme(STATE.theme);
  // Clear any legacy un-scoped shared cart to prevent cart bleed
  localStorage.removeItem('nexus_cart');
  localStorage.removeItem('nexus_wish');
  loadUserCartAndWish(STATE.currentUser);
  updateNavCounters();
  await loadProducts();
  updateNavState();
  renderMain();
});
