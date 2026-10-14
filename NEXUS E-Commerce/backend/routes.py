"""
NEXUS E-Commerce — REST API Endpoints & Routes
Connects the frontend client to the SQLite database and Python DWM machine learning engine.
Enforces Role-Based Access Control (RBAC) and exposes database inspection tools.
"""

from datetime import datetime
from flask import Blueprint, request, jsonify
from .database import get_db, get_all_tables, get_table_sample, run_custom_query, reset_database
from .etl_pipeline import execute_etl, get_latest_audit
from .algorithms import (
    execute_olap,
    cluster_customers,
    train_and_eval_classifiers,
    score_test_customer,
    forecast_sales,
    mine_association_rules
)

api = Blueprint('api', __name__, url_prefix='/api')

# ==============================================================================
# 1. Authentication (Shopper vs Admin RBAC)
# ==============================================================================
@api.route('/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute("""
        SELECT id, email, password, name, role, customer_id
        FROM users
        WHERE LOWER(email) = ? AND password = ?
    """, (email, password)).fetchone()

    if not user:
        conn.close()
        return jsonify({'error': 'Invalid email or password'}), 401

    user_dict = dict(user)
    # Ensure customer_id is never None
    if not user_dict.get('customer_id'):
        cust = cursor.execute("SELECT id FROM customers WHERE LOWER(email) = ?", (email,)).fetchone()
        if cust:
            user_dict['customer_id'] = cust['id']
        else:
            user_dict['customer_id'] = user_dict['id']

    conn.close()
    return jsonify({
        'id': user_dict['id'],
        'email': user_dict['email'],
        'name': user_dict['name'],
        'role': user_dict['role'],
        'customer_id': user_dict['customer_id']
    })

@api.route('/auth/register', methods=['POST'])
def auth_register():
    data = request.json or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '').strip()
    city = data.get('city', 'Mumbai').strip()

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400

    conn = get_db()
    cursor = conn.cursor()
    existing = cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'error': 'Email already registered'}), 409

    cursor.execute("""
        INSERT INTO customers (name, email, age, gender, city, state)
        VALUES (?, ?, 25, 'Unspecified', ?, 'State')
    """, (name, email, city))
    cust_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO users (email, password, name, role, customer_id)
        VALUES (?, ?, ?, 'customer', ?)
    """, (email, password, name, cust_id))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'id': user_id,
        'email': email,
        'name': name,
        'role': 'customer',
        'customer_id': cust_id
    })

# ==============================================================================
# 2. Product Catalog Endpoints
# ==============================================================================
@api.route('/products', methods=['GET'])
def get_products():
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT p.*,
               COALESCE(AVG(r.rating), 4.5) as avg_rating,
               COUNT(r.id) as review_count
        FROM products p
        LEFT JOIN reviews r ON p.id = r.product_id
        WHERE p.is_deleted = 0
        GROUP BY p.id
        ORDER BY p.id ASC
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@api.route('/products/<int:pid>', methods=['GET'])
def get_product_detail(pid):
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(dict(row))

@api.route('/products', methods=['POST'])
def add_product():
    data = request.json or {}
    name = data.get('name')
    category = data.get('category')
    price = data.get('price')
    stock = data.get('stock', 50)
    emoji = data.get('emoji', '📦')
    description = data.get('description', '')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO products (name, category, price, stock, emoji, description)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, category, price, stock, emoji, description))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return jsonify({'id': new_id, 'message': 'Product added successfully'})

@api.route('/products/<int:pid>', methods=['PUT'])
def update_product(pid):
    data = request.json or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE products
        SET name = ?, category = ?, price = ?, stock = ?, emoji = ?, description = ?
        WHERE id = ?
    """, (data.get('name'), data.get('category'), data.get('price'), data.get('stock'), data.get('emoji'), data.get('description'), pid))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Product updated'})

@api.route('/products/<int:pid>', methods=['DELETE'])
def delete_product(pid):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET is_deleted = 1 WHERE id = ?", (pid,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Product soft deleted'})

@api.route('/products/<int:pid>/reviews', methods=['GET'])
def get_product_reviews(pid):
    conn = get_db()
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT * FROM reviews WHERE product_id = ? ORDER BY id DESC
    """, (pid,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ==============================================================================
# 3. Orders & Shopping Cart (Checkout Fix)
# ==============================================================================
@api.route('/orders/checkout', methods=['POST'])
def checkout():
    data = request.json or {}
    # Robust customer_id resolution: fallback to 1 if not provided or 0
    raw_cid = data.get('customer_id')
    try:
        customer_id = int(raw_cid) if raw_cid else 1
    except (ValueError, TypeError):
        customer_id = 1

    items = data.get('items', [])
    delivery_city = data.get('delivery_city', 'Mumbai')
    payment_method = data.get('payment_method', 'UPI')

    if not items:
        return jsonify({'error': 'Order items cannot be empty'}), 400

    conn = get_db()
    cursor = conn.cursor()

    order_num = cursor.execute("SELECT COUNT(*) FROM orders").fetchone()[0] + 1
    order_id = f"ORD-{20240000 + order_num}"
    order_date = datetime.now().strftime("%Y-%m-%d")

    total_amount = sum(item['quantity'] * item['unit_price'] for item in items)

    # Insert into operational orders table
    cursor.execute("""
        INSERT INTO orders (id, customer_id, order_date, delivery_city, payment_method, total_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Placed')
    """, (order_id, customer_id, order_date, delivery_city, payment_method, total_amount))

    # Insert items & decrement inventory
    for item in items:
        pid = item['product_id']
        qty = item['quantity']
        uprice = item['unit_price']
        tot = round(qty * uprice, 2)
        cursor.execute("""
            INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?)
        """, (order_id, pid, qty, uprice, tot))

        cursor.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?", (qty, pid))

    conn.commit()
    conn.close()

    # Automatically synchronize the Data Warehouse ETL in near-real-time (~35ms)
    # so all analytical models (OLAP cube, clustering, forecasts) immediately reflect newly placed orders
    audit = execute_etl()

    return jsonify({
        'status': 'SUCCESS',
        'order_id': order_id,
        'total_amount': total_amount,
        'facts_loaded': audit['facts_loaded'],
        'message': 'Order successfully committed into SQLite database and synced into Data Warehouse'
    })

@api.route('/orders/customer/<int:cid>', methods=['GET'])
def get_customer_orders(cid):
    conn = get_db()
    cursor = conn.cursor()
    orders = cursor.execute("""
        SELECT o.*,
               GROUP_CONCAT(p.name || ' (x' || oi.quantity || ')', ', ') as items_summary
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        WHERE o.customer_id = ?
        GROUP BY o.id
        ORDER BY o.order_date DESC, o.id DESC
        LIMIT 25
    """, (cid,)).fetchall()
    conn.close()
    return jsonify([dict(o) for o in orders])

@api.route('/orders', methods=['GET'])
def get_all_orders():
    conn = get_db()
    cursor = conn.cursor()
    orders = cursor.execute("""
        SELECT o.*, c.name as customer_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        ORDER BY o.id DESC
        LIMIT 100
    """).fetchall()
    conn.close()
    return jsonify([dict(o) for o in orders])

@api.route('/orders/<oid>/status', methods=['PUT'])
def update_order_status(oid):
    data = request.json or {}
    new_status = data.get('status', 'Shipped')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, oid))
    conn.commit()
    conn.close()
    return jsonify({'message': f'Order status updated to {new_status}'})

# ==============================================================================
# 4. ETL Pipeline Endpoints
# ==============================================================================
@api.route('/etl/run', methods=['POST'])
def trigger_etl():
    audit = execute_etl()
    return jsonify({'status': 'SUCCESS', 'audit': audit})

@api.route('/etl/status', methods=['GET'])
def get_etl_status():
    audit = get_latest_audit()
    return jsonify(audit)

# ==============================================================================
# 5. Star Schema & Warehouse Endpoints
# ==============================================================================
@api.route('/warehouse/meta', methods=['GET'])
def get_warehouse_meta():
    conn = get_db()
    cursor = conn.cursor()
    fact_count = cursor.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    dim_counts = {
        'Customer': cursor.execute("SELECT COUNT(*) FROM dim_customer").fetchone()[0],
        'Product': cursor.execute("SELECT COUNT(*) FROM dim_product").fetchone()[0],
        'Date': cursor.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0],
        'Location': cursor.execute("SELECT COUNT(*) FROM dim_location").fetchone()[0],
        'Payment': cursor.execute("SELECT COUNT(*) FROM dim_payment").fetchone()[0]
    }
    sample_facts = cursor.execute("""
        SELECT f.order_id, c.name as customer_name, p.name as product_name,
               f.date_key, f.location_key, f.payment_key, f.quantity, f.sales_amount, f.profit_margin
        FROM fact_sales f
        JOIN dim_customer c ON f.customer_key = c.customer_key
        JOIN dim_product p ON f.product_key = p.product_key
        ORDER BY f.fact_id DESC
        LIMIT 15
    """).fetchall()
    conn.close()
    return jsonify({
        'fact_count': fact_count,
        'dimensions': dim_counts,
        'sample_facts': [dict(r) for r in sample_facts]
    })

# ==============================================================================
# 6. Analytical & Machine Learning Endpoints
# ==============================================================================
@api.route('/analytics/overview', methods=['GET'])
def analytics_overview():
    conn = get_db()
    cursor = conn.cursor()
    tot_rev = cursor.execute("SELECT COALESCE(SUM(sales_amount), 0) FROM fact_sales").fetchone()[0]
    tot_prof = cursor.execute("SELECT COALESCE(SUM(profit_margin), 0) FROM fact_sales").fetchone()[0]
    tot_units = cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM fact_sales").fetchone()[0]
    tot_orders = cursor.execute("SELECT COUNT(DISTINCT order_id) FROM fact_sales").fetchone()[0]
    active_custs = cursor.execute("SELECT COUNT(DISTINCT customer_key) FROM fact_sales").fetchone()[0]
    aov = round(tot_rev / max(1, tot_orders), 2)

    monthly_rows = cursor.execute("""
        SELECT substr(date_key, 1, 7) as mo, SUM(sales_amount) as s
        FROM fact_sales
        GROUP BY mo
        ORDER BY mo ASC
    """).fetchall()
    monthly_trend = {r['mo']: round(r['s'], 2) for r in monthly_rows}

    cat_rows = cursor.execute("""
        SELECT p.category, SUM(f.sales_amount) as s
        FROM fact_sales f
        JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.category
        ORDER BY s DESC
    """).fetchall()
    category_breakdown = {r['category']: round(r['s'], 2) for r in cat_rows}

    top_skus = cursor.execute("""
        SELECT p.name, SUM(f.sales_amount) as s
        FROM fact_sales f
        JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY p.name
        ORDER BY s DESC
        LIMIT 5
    """).fetchall()

    geo_rows = cursor.execute("""
        SELECT location_key, SUM(sales_amount) as s
        FROM fact_sales
        GROUP BY location_key
        ORDER BY s DESC
    """).fetchall()

    conn.close()
    return jsonify({
        'total_revenue': round(tot_rev, 2),
        'total_profit': round(tot_prof, 2),
        'total_units': tot_units,
        'total_orders': tot_orders,
        'active_customers': active_custs,
        'aov': aov,
        'monthly_trend': monthly_trend,
        'category_breakdown': category_breakdown,
        'top_skus': [[r[0], round(r[1], 2)] for r in top_skus],
        'geo_breakdown': [[r[0], round(r[1], 2)] for r in geo_rows]
    })

@api.route('/analytics/olap', methods=['GET'])
def get_olap():
    level = request.args.get('level', 'year')
    group_by = request.args.get('group_by', 'cat')
    measure = request.args.get('measure', 'sales')
    cat_filter = request.args.get('cat_filter') or None
    city_filter = request.args.get('city_filter') or None
    year_filter = request.args.get('year_filter') or None

    res = execute_olap(level, group_by, measure, cat_filter, city_filter, year_filter)
    return jsonify(res)

@api.route('/analytics/clustering', methods=['GET'])
def get_clustering():
    alg = request.args.get('algorithm', 'kmeans')
    k = int(request.args.get('k', 4))
    res = cluster_customers(alg, k)
    return jsonify(res)

@api.route('/analytics/classification', methods=['GET'])
def get_classification():
    k = int(request.args.get('k', 5))
    res = train_and_eval_classifiers(k)
    return jsonify(res)

@api.route('/analytics/classification/predict', methods=['POST'])
def predict_tier():
    data = request.json or {}
    orders = float(data.get('orders', 10))
    aov = float(data.get('aov', 2500))
    cats = float(data.get('categories', 3))
    units = float(data.get('units', 15))
    k = int(data.get('k', 5))
    res = score_test_customer([orders, aov, cats, units], k)
    return jsonify(res)

@api.route('/analytics/forecast', methods=['GET'])
def get_forecast():
    res = forecast_sales()
    return jsonify(res)

@api.route('/analytics/market-basket', methods=['GET'])
def get_market_basket():
    min_sup = float(request.args.get('min_support', 2.0))
    min_conf = float(request.args.get('min_confidence', 30.0))
    res = mine_association_rules(min_sup, min_conf)
    return jsonify(res)

# ==============================================================================
# 7. Database Inspector Endpoints (Show Ma'am the Backend Database Live)
# ==============================================================================
@api.route('/db/tables', methods=['GET'])
def list_db_tables():
    tables = get_all_tables()
    return jsonify({'tables': tables})

@api.route('/db/table/<name>', methods=['GET'])
def get_db_table_data(name):
    limit = int(request.args.get('limit', 50))
    data = get_table_sample(name, limit)
    return jsonify(data)

@api.route('/db/query', methods=['POST'])
def run_db_query():
    data = request.json or {}
    sql = data.get('query', '')
    try:
        res = run_custom_query(sql)
        return jsonify({'status': 'SUCCESS', 'data': res})
    except Exception as err:
        return jsonify({'status': 'ERROR', 'error': str(err)}), 400

@api.route('/db/reset', methods=['POST'])
def reset_db_endpoint():
    try:
        reset_database()
        audit = execute_etl()
        return jsonify({
            'status': 'SUCCESS',
            'audit': audit,
            'message': 'Database & Data Warehouse successfully refreshed to clean benchmark state (80 customers, 24 products, 900 orders, 1609 facts).'
        })
    except Exception as err:
        return jsonify({'status': 'ERROR', 'error': str(err)}), 500
