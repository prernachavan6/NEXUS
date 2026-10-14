"""
NEXUS E-Commerce — ETL (Extract, Transform, Load) Pipeline
Cleanses & standardizes dirty operational OLTP transaction records,
imputes missing dimensions, derives analytical business metrics,
and loads into the analytical Star Schema (FACT_SALES & Conformed Dimensions).
"""

import time
from datetime import datetime
from .database import get_db

PAYMENT_CANONICAL_MAP = {
    'upi': 'UPI',
    'u.p.i': 'UPI',
    'credit card': 'Credit/Debit Card',
    'cc': 'Credit/Debit Card',
    'debit card': 'Credit/Debit Card',
    'credit/debit card': 'Credit/Debit Card',
    'cod': 'COD',
    'cash on delivery': 'COD',
    'netbanking': 'NetBanking',
    'net banking': 'NetBanking',
    'wallet': 'NEXUS Wallet',
    'nexus wallet': 'NEXUS Wallet'
}

def canonicalize_payment(raw_str):
    if not raw_str:
        return 'UPI'
    key = str(raw_str).strip().lower()
    return PAYMENT_CANONICAL_MAP.get(key, 'UPI')

def execute_etl():
    """
    Executes full ETL cycle:
    1. Extract: Reads from orders, order_items, customers, and products.
    2. Transform: De-duplicates, imputes missing locations, standardizes strings, derives measures.
    3. Load: Upserts dimension tables and repopulates central FACT_SALES.
    """
    start_time = time.time()
    conn = get_db()
    cursor = conn.cursor()

    # Step 1: Extract
    raw_orders = cursor.execute("""
        SELECT o.id, o.customer_id, o.order_date, o.delivery_city, o.payment_method, o.total_amount, o.status,
               c.city as cust_city, c.state as cust_state
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
    """).fetchall()

    raw_items = cursor.execute("""
        SELECT oi.id, oi.order_id, oi.product_id, oi.quantity, oi.unit_price, oi.total_price,
               p.category as prod_cat, p.name as prod_name, p.price as prod_price
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
    """).fetchall()

    raw_orders_count = len(raw_orders)

    # Step 2: Transform
    # 2a. Deduplication
    seen_orders = set()
    unique_orders = []
    duplicates_removed = 0

    for ord_row in raw_orders:
        oid = ord_row['id']
        if oid in seen_orders:
            duplicates_removed += 1
            continue
        seen_orders.add(oid)
        unique_orders.append(ord_row)

    # 2b. Missing Location Imputation & Payment Canonicalization
    missing_imputed = 0
    standardized_payments = 0
    transformed_orders = {}

    for ord_row in unique_orders:
        oid = ord_row['id']
        deliv_city = ord_row['delivery_city']
        
        # Missing value imputation using Customer master city
        if not deliv_city or deliv_city.strip() == '':
            deliv_city = ord_row['cust_city']
            missing_imputed += 1

        # String canonicalization
        raw_pay = ord_row['payment_method']
        canon_pay = canonicalize_payment(raw_pay)
        if raw_pay != canon_pay:
            standardized_payments += 1

        transformed_orders[oid] = {
            'customer_id': ord_row['customer_id'],
            'order_date': ord_row['order_date'],
            'city': deliv_city,
            'payment': canon_pay
        }

    # 2c. Item Validation (Negative Qty Pruning) & Derived Measures
    invalid_qty_pruned = 0
    fact_rows = []

    for item in raw_items:
        oid = item['order_id']
        if oid not in transformed_orders:
            continue

        qty = item['quantity']
        if qty <= 0:
            invalid_qty_pruned += 1
            continue

        ord_meta = transformed_orders[oid]
        uprice = item['unit_price']
        sales_amt = round(qty * uprice, 2)
        # Derived business measure: Retail gross margin estimate (22%)
        profit_margin = round(sales_amt * 0.22, 2)

        fact_rows.append((
            oid,
            ord_meta['customer_id'],
            item['product_id'],
            ord_meta['order_date'],
            ord_meta['city'],
            ord_meta['payment'],
            qty,
            sales_amt,
            profit_margin
        ))

    # Step 3: Load into Star Schema
    # 3a. Sync DIM_CUSTOMER
    cursor.execute("""
        INSERT OR REPLACE INTO dim_customer (customer_key, customer_id, name, age, gender, city, state)
        SELECT id, id, name, age, gender, city, state FROM customers
    """)

    # 3b. Sync DIM_PRODUCT
    cursor.execute("""
        INSERT OR REPLACE INTO dim_product (product_key, product_id, name, category, price)
        SELECT id, id, name, category, price FROM products WHERE is_deleted = 0
    """)

    # 3c. Sync DIM_DATE (All unique dates extracted)
    cursor.execute("SELECT DISTINCT order_date FROM orders WHERE order_date IS NOT NULL")
    all_dates = [r[0] for r in cursor.fetchall()]
    date_tuples = []
    for d_str in all_dates:
        try:
            dt = datetime.strptime(d_str, "%Y-%m-%d")
            quarter = (dt.month - 1) // 3 + 1
            date_tuples.append((d_str, dt.day, dt.month, quarter, dt.year, dt.strftime("%A")))
        except ValueError:
            pass

    cursor.executemany("""
        INSERT OR IGNORE INTO dim_date (date_key, day, month, quarter, year, weekday)
        VALUES (?, ?, ?, ?, ?, ?)
    """, date_tuples)

    # 3d. Clear & Reload FACT_SALES
    cursor.execute("DELETE FROM fact_sales")
    cursor.executemany("""
        INSERT INTO fact_sales (
            order_id, customer_key, product_key, date_key, location_key, payment_key,
            quantity, sales_amount, profit_margin
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, fact_rows)

    duration_ms = round((time.time() - start_time) * 1000, 2)

    # 3e. Audit Log
    cursor.execute("""
        INSERT INTO etl_audit_log (
            run_timestamp, raw_orders_count, duplicates_removed, missing_imputed,
            standardized_payments, invalid_qty_pruned, facts_loaded, duration_ms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        raw_orders_count,
        duplicates_removed,
        missing_imputed,
        standardized_payments,
        invalid_qty_pruned,
        len(fact_rows),
        duration_ms
    ))

    conn.commit()
    conn.close()

    return {
        'status': 'SUCCESS',
        'raw_orders_count': raw_orders_count,
        'duplicates_removed': duplicates_removed,
        'missing_imputed': missing_imputed,
        'standardized_payments': standardized_payments,
        'invalid_qty_pruned': invalid_qty_pruned,
        'facts_loaded': len(fact_rows),
        'duration_ms': duration_ms,
        'run_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def get_latest_audit():
    conn = get_db()
    cursor = conn.cursor()
    row = cursor.execute("""
        SELECT * FROM etl_audit_log ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        'run_timestamp': 'Pending Initialization',
        'raw_orders_count': 0,
        'duplicates_removed': 0,
        'missing_imputed': 0,
        'standardized_payments': 0,
        'invalid_qty_pruned': 0,
        'facts_loaded': 0,
        'duration_ms': 0
    }
