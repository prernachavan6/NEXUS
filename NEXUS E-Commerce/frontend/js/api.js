/**
 * NEXUS E-Commerce — Frontend API Client
 * Connects UI modules to Flask REST endpoints.
 */

const API_BASE = '/api';

const API = {
  async req(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const opts = {
      headers: { 'Content-Type': 'application/json' },
      ...options
    };
    if (opts.body && typeof opts.body !== 'string') {
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `HTTP ${res.status}`);
    }
    return data;
  },

  // Auth
  login: (email, password) => API.req('/auth/login', { method: 'POST', body: { email, password } }),
  register: (userData) => API.req('/auth/register', { method: 'POST', body: userData }),

  // Catalog
  getProducts: () => API.req('/products'),
  getProductDetail: (pid) => API.req(`/products/${pid}`),
  addProduct: (prod) => API.req('/products', { method: 'POST', body: prod }),
  updateProduct: (pid, prod) => API.req(`/products/${pid}`, { method: 'PUT', body: prod }),
  deleteProduct: (pid) => API.req(`/products/${pid}`, { method: 'DELETE' }),
  getProductReviews: (pid) => API.req(`/products/${pid}/reviews`),

  // Orders & Cart
  checkout: (orderData) => API.req('/orders/checkout', { method: 'POST', body: orderData }),
  getCustomerOrders: (cid) => API.req(`/orders/customer/${cid}`),
  getAdminOrders: () => API.req('/orders'),
  updateOrderStatus: (oid, status) => API.req(`/orders/${oid}/status`, { method: 'PUT', body: { status } }),

  // ETL
  runETL: () => API.req('/etl/run', { method: 'POST' }),
  getETLStatus: () => API.req('/etl/status'),

  // Warehouse Meta
  getWarehouseMeta: () => API.req('/warehouse/meta'),

  // Analytical Algorithms
  getAnalyticsOverview: () => API.req('/analytics/overview'),
  getOLAP: (params) => {
    const q = new URLSearchParams(params).toString();
    return API.req(`/analytics/olap?${q}`);
  },
  getClustering: (algorithm = 'kmeans', k = 4) => API.req(`/analytics/clustering?algorithm=${algorithm}&k=${k}`),
  getClassification: (k = 5) => API.req(`/analytics/classification?k=${k}`),
  predictClassification: (payload) => API.req('/analytics/classification/predict', { method: 'POST', body: payload }),
  getForecasting: () => API.req('/analytics/forecast'),
  getMarketBasket: (minSupport = 2.0, minConfidence = 30.0) =>
    API.req(`/analytics/market-basket?min_support=${minSupport}&min_confidence=${minConfidence}`),

  // Database Inspector (Show Ma'am the Backend Database Live)
  getDBTables: () => API.req('/db/tables'),
  getDBTableData: (table, limit = 50) => API.req(`/db/table/${table}?limit=${limit}`),
  runDBQuery: (query) => API.req('/db/query', { method: 'POST', body: { query } }),
  resetDatabase: () => API.req('/db/reset', { method: 'POST' })
};
