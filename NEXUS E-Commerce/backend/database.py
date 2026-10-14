"""
NEXUS E-Commerce — Database Engine (SQLite OLTP & Star Schema OLAP)
Supports Operational Transactions (OLTP), Star Schema Dimensional Modeling (OLAP),
and Direct Schema/Table Inspection for administrative review.
"""

import sqlite3
import os
import math
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nexus_ecommerce.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # ==========================================================================
    # 1. OLTP Operational Schema (Flipkart / Amazon Normalized Tables)
    # ==========================================================================
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer',
        customer_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        city TEXT NOT NULL,
        state TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL DEFAULT 50,
        emoji TEXT NOT NULL DEFAULT '📦',
        description TEXT,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS orders (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
        id TEXT NOT NULL,
        customer_id INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        delivery_city TEXT,
        payment_method TEXT,
        total_amount REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'Placed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        total_price REAL NOT NULL,
        FOREIGN KEY (product_id) REFERENCES products(id)
    );

    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        customer_id INTEGER NOT NULL,
        author TEXT NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );

    -- ==========================================================================
    -- 2. OLAP Analytical Star Schema (Warehouse Tables)
    -- ==========================================================================
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_key INTEGER PRIMARY KEY,
        customer_id INTEGER UNIQUE,
        name TEXT,
        age INTEGER,
        gender TEXT,
        city TEXT,
        state TEXT
    );

    CREATE TABLE IF NOT EXISTS dim_product (
        product_key INTEGER PRIMARY KEY,
        product_id INTEGER UNIQUE,
        name TEXT,
        category TEXT,
        price REAL
    );

    CREATE TABLE IF NOT EXISTS dim_date (
        date_key TEXT PRIMARY KEY,
        day INTEGER,
        month INTEGER,
        quarter INTEGER,
        year INTEGER,
        weekday TEXT
    );

    CREATE TABLE IF NOT EXISTS dim_location (
        location_key TEXT PRIMARY KEY,
        city TEXT UNIQUE,
        state TEXT,
        region TEXT
    );

    CREATE TABLE IF NOT EXISTS dim_payment (
        payment_key TEXT PRIMARY KEY,
        method_name TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS fact_sales (
        fact_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id TEXT NOT NULL,
        customer_key INTEGER NOT NULL,
        product_key INTEGER NOT NULL,
        date_key TEXT NOT NULL,
        location_key TEXT NOT NULL,
        payment_key TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        sales_amount REAL NOT NULL,
        profit_margin REAL NOT NULL,
        FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
        FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
        FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
        FOREIGN KEY (location_key) REFERENCES dim_location(location_key),
        FOREIGN KEY (payment_key) REFERENCES dim_payment(payment_key)
    );

    CREATE TABLE IF NOT EXISTS etl_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_timestamp TEXT NOT NULL,
        raw_orders_count INTEGER NOT NULL,
        duplicates_removed INTEGER NOT NULL,
        missing_imputed INTEGER NOT NULL,
        standardized_payments INTEGER NOT NULL,
        invalid_qty_pruned INTEGER NOT NULL,
        facts_loaded INTEGER NOT NULL,
        duration_ms REAL NOT NULL
    );
    """)

    conn.commit()

    # Seed initial catalog and users if empty
    check_products = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if check_products == 0:
        seed_initial_data(conn)
    else:
        conn.close()

def seed_initial_data(conn):
    cursor = conn.cursor()
    print("Seeding Initial Operational Data (Products, Customers, Intentional Dirty Records)...")

    # 1. Products (24 Products across 6 Categories)
    products_data = [
        # Electronics
        ("Noise-Cancelling Wireless Headphones", "Electronics", 4999.0, 45, "🎧", "Active ANC with 35hr playback battery."),
        ("Mechanical RGB Gaming Keyboard", "Electronics", 3499.0, 30, "⌨️", "Tactile blue switches with customizable backlight."),
        ("Smart Fitness Tracker Band 6", "Electronics", 2199.0, 60, "⌚", "SpO2 and continuous 24/7 heart rate monitor."),
        ("4K Ultra HD Streaming Dongle", "Electronics", 3199.0, 25, "📺", "Dual-band Wi-Fi with HDR10+ support."),
        
        # Fashion
        ("Classic Oxford Cotton Slim Shirt", "Fashion", 1299.0, 50, "👔", "100% breathable pure combed cotton fabric."),
        ("Slim-Fit Stretch Denim Jeans", "Fashion", 1899.0, 40, "👖", "Indigo blue wash with 2-way comfortable stretch."),
        ("Breathable Mesh Running Shoes", "Fashion", 2499.0, 35, "👟", "EVA foam sole designed for distance jogging."),
        ("Lightweight Polarized Sunglasses", "Fashion", 899.0, 55, "🕶️", "100% UV400 protective polarized lenses."),

        # Home & Living
        ("Aromatherapy Essential Oil Diffuser", "Home & Living", 1499.0, 30, "🌿", "Ultra-quiet ultrasonic cool mist with 7 LED modes."),
        ("Memory Foam Ergonomic Contour Pillow", "Home & Living", 1199.0, 45, "🛏️", "Orthopedic cervical neck alignment support."),
        ("Ceramic Modern Non-Stick Cookware Set", "Home & Living", 3899.0, 20, "🍳", "Teflon-free durable scratch-resistant ceramic coating."),
        ("Smart LED Desk Lamp with USB Charger", "Home & Living", 1699.0, 40, "💡", "Touch control with adjustable color temperature."),

        # Books & Learning
        ("Data Warehousing in the Age of AI", "Books & Learning", 799.0, 50, "📚", "Modern dimensional star schemas and ML pipelines."),
        ("Hands-On Machine Learning Patterns", "Books & Learning", 999.0, 40, "📖", "Practical classification, clustering and regression."),
        ("Full-Stack Modern SaaS Architecture", "Books & Learning", 849.0, 35, "📕", "Design systems, RESTful microservices and databases."),
        ("Clean Code: Software Engineering Guide", "Books & Learning", 699.0, 50, "📗", "Refactoring and professional software craftsmanship."),

        # Beauty & Care
        ("Vitamin C 10% Brightening Face Serum", "Beauty & Care", 649.0, 60, "✨", "Pure ethyl ascorbic acid with ferulic acid."),
        ("Deep Hydrating Ceramide Moisturizer", "Beauty & Care", 549.0, 65, "🧴", "Triple barrier restoration daily face formula."),
        ("Organic Cold-Pressed Moroccan Argan Oil", "Beauty & Care", 899.0, 40, "💧", "Intense hair smoothing and skin elasticity."),
        ("SPF 50+ Invisible Matte Sunscreen Gel", "Beauty & Care", 499.0, 70, "☀️", "Zero white-cast broad spectrum UVA/UVB protection."),

        # Gourmet Grocery
        ("Single-Origin Arabica Dark Roast Coffee", "Gourmet Grocery", 599.0, 50, "☕", "Artisan whole beans harvested from Coorg estates."),
        ("Raw Organic Himalayan Forest Honey", "Gourmet Grocery", 449.0, 60, "🍯", "Unpasteurized raw wild multi-floral nectar."),
        ("Premium Roasted & Salted California Almonds", "Gourmet Grocery", 699.0, 45, "🌰", "Slow roasted crunchy California nonpareil almonds."),
        ("Artisanal 70% Dark Cocoa Belgian Chocolate", "Gourmet Grocery", 349.0, 80, "🍫", "Single origin cocoa sweetened with raw cane sugar.")
    ]

    for p in products_data:
        cursor.execute("INSERT INTO products (name, category, price, stock, emoji, description) VALUES (?, ?, ?, ?, ?, ?)", p)

    # 2. Locations Master
    cities = [
        ('Mumbai', 'Maharashtra', 'West'),
        ('Pune', 'Maharashtra', 'West'),
        ('Bengaluru', 'Karnataka', 'South'),
        ('Hyderabad', 'Telangana', 'South'),
        ('Delhi', 'Delhi', 'North'),
        ('Chennai', 'Tamil Nadu', 'South'),
        ('Kolkata', 'West Bengal', 'East'),
        ('Ahmedabad', 'Gujarat', 'West')
    ]
    for c in cities:
        cursor.execute("INSERT OR IGNORE INTO dim_location (location_key, city, state, region) VALUES (?, ?, ?, ?)", (c[0], c[0], c[1], c[2]))

    # 3. Canonical Payment Dimensions
    canonical_payments = ['UPI', 'Credit/Debit Card', 'COD', 'NetBanking', 'NEXUS Wallet']
    for cp in canonical_payments:
        cursor.execute("INSERT OR IGNORE INTO dim_payment (payment_key, method_name) VALUES (?, ?)", (cp, cp))

    # 4. Customers (80 Customers)
    first_names = ['Aarav', 'Vivaan', 'Aditya', 'Vihaan', 'Arjun', 'Sai', 'Reyansh', 'Ayaan', 'Krishna', 'Ishaan',
                   'Diya', 'Saanvi', 'Ananya', 'Aadhya', 'Pari', 'Chiara', 'Myra', 'Riya', 'Isha', 'Ahana',
                   'Rohan', 'Pranav', 'Dev', 'Kabir', 'Karan', 'Tara', 'Meera', 'Sara', 'Neha', 'Pooja']
    last_names = ['Sharma', 'Verma', 'Patel', 'Chavan', 'Vichare', 'Dhawade', 'Deshmukh', 'Joshi', 'Kulkarni',
                  'Shah', 'Mehta', 'Nair', 'Iyer', 'Reddy', 'Rao', 'Singh', 'Gupta', 'Kapoor', 'Bose', 'Chatterjee']

    random.seed(42)
    for i in range(1, 81):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        full_name = f"{fn} {ln}"
        email = f"customer{i}@example.in" if i > 1 else "demo@shop.in"
        age = random.randint(19, 65)
        gender = 'Female' if fn in ['Diya', 'Saanvi', 'Ananya', 'Aadhya', 'Pari', 'Chiara', 'Myra', 'Riya', 'Isha', 'Ahana', 'Tara', 'Meera', 'Sara', 'Neha', 'Pooja'] else 'Male'
        loc = random.choice(cities)
        cursor.execute("INSERT INTO customers (name, email, age, gender, city, state) VALUES (?, ?, ?, ?, ?, ?)",
                       (full_name, email, age, gender, loc[0], loc[1]))

    # 5. Default Users: Shopper & Admin
    # Customer user (demo@shop.in / demo123 linked to customer #1)
    cursor.execute("""
        INSERT INTO users (email, password, name, role, customer_id)
        VALUES ('demo@shop.in', 'demo123', 'Demo Shopper', 'customer', 1)
    """)

    # Admin user (admin@shop.in / admin123 with full executive analytics access)
    cursor.execute("""
        INSERT INTO users (email, password, name, role, customer_id)
        VALUES ('admin@shop.in', 'admin123', 'Store Administrator', 'admin', 1)
    """)

    # 6. Historical Orders (900 Orders spanning 24 Months, with Intentional Dirty Records for ETL)
    start_date = datetime(2024, 1, 1)
    all_prod_ids = list(range(1, 25))
    prod_prices = {row[0]: row[1] for row in cursor.execute("SELECT id, price FROM products").fetchall()}

    raw_payments_pool = [
        'UPI', 'upi', 'U.P.I', 'Credit/Debit Card', 'cc', 'credit card', 'COD', 'cash on delivery',
        'NetBanking', 'netbanking', 'NEXUS Wallet', 'wallet'
    ]

    order_records = []
    item_records = []

    for i in range(1, 901):
        order_id = f"ORD-{20240000 + i}"
        cust_id = random.randint(1, 80)
        random_days = random.randint(0, 720)
        odate = (start_date + timedelta(days=random_days)).strftime("%Y-%m-%d")
        
        # Dirty Data Injection #1: 5% missing delivery city (NULL) to test imputation
        if random.random() < 0.05:
            d_city = None
        else:
            d_city = random.choice(cities)[0]

        # Dirty Data Injection #2: non-standard payment string representations
        raw_pay = random.choice(raw_payments_pool)

        # Select items in order (Mix of organic orders and real-world e-commerce affinity bundles)
        affinity_bundles = [
            [17, 18], [17, 20], [18, 20],
            [1, 2], [1, 3],
            [13, 14], [13, 16], [14, 16],
            [21, 22], [21, 24], [23, 24],
            [5, 6], [6, 7],
            [9, 10], [10, 12]
        ]
        if random.random() < 0.42:
            bundle = random.choice(affinity_bundles)
            chosen_pids = list(bundle)
            if random.random() < 0.25:
                other_pids = [p for p in all_prod_ids if p not in chosen_pids]
                chosen_pids.append(random.choice(other_pids))
        else:
            basket_size = random.choices([1, 2, 3], weights=[50, 40, 10])[0]
            chosen_pids = random.sample(all_prod_ids, basket_size)
        
        order_total = 0.0
        for pid in chosen_pids:
            qty = random.randint(1, 3)
            # Dirty Data Injection #3: 0.8% invalid negative quantities
            if random.random() < 0.008:
                qty = -1
            
            uprice = prod_prices[pid]
            line_tot = max(0.0, qty * uprice)
            order_total += line_tot
            item_records.append((order_id, pid, qty, uprice, line_tot))

        order_records.append((order_id, cust_id, odate, d_city, raw_pay, order_total, 'Delivered'))

    # Dirty Data Injection #4: Intentional duplicate orders
    for dup in order_records[:15]:
        order_records.append(dup)

    cursor.executemany("""
        INSERT INTO orders (id, customer_id, order_date, delivery_city, payment_method, total_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, order_records)

    cursor.executemany("""
        INSERT INTO order_items (order_id, product_id, quantity, unit_price, total_price)
        VALUES (?, ?, ?, ?, ?)
    """, item_records)

    # 7. Reviews
    review_comments = [
        "Superb build quality! Exceeded expectations.",
        "Very fast delivery, packaging was robust.",
        "Value for money purchase, definitely buying again.",
        "Decent performance, exactly as described in specifications.",
        "Premium finish and great customer support."
    ]
    reviews_data = []
    for pid in all_prod_ids:
        for _ in range(random.randint(2, 5)):
            cid = random.randint(1, 80)
            author = cursor.execute("SELECT name FROM customers WHERE id = ?", (cid,)).fetchone()[0]
            rating = random.choice([4, 5, 5, 4, 3])
            comm = random.choice(review_comments)
            reviews_data.append((pid, cid, author, rating, comm))

    cursor.executemany("""
        INSERT INTO reviews (product_id, customer_id, author, rating, comment)
        VALUES (?, ?, ?, ?, ?)
    """, reviews_data)

    conn.commit()
    conn.close()
    print("Initial Database Seeding Complete!")

# ==============================================================================
# Helper Functions for Admin Database Inspection & SQL Queries
# ==============================================================================
def get_all_tables():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def get_table_sample(table_name, limit=50):
    conn = get_db()
    cursor = conn.cursor()
    # Validate table name to avoid injection
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        conn.close()
        return {'columns': [], 'rows': []}

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]

    cursor.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,))
    rows = [list(r) for r in cursor.fetchall()]
    conn.close()
    return {'columns': columns, 'rows': rows}

def run_custom_query(sql, limit=100):
    conn = get_db()
    cursor = conn.cursor()
    sql_clean = sql.strip()
    if not sql_clean.lower().startswith('select'):
        conn.close()
        raise ValueError("Only SELECT queries are permitted in the inspector.")

    cursor.execute(sql_clean)
    columns = [d[0] for d in cursor.description] if cursor.description else []
    rows = [list(r) for r in cursor.fetchmany(limit)]
    conn.close()
    return {'columns': columns, 'rows': rows}

def reset_database():
    """
    Drops all operational and analytical tables, then re-runs init_db() to seed the clean benchmark demo dataset.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF")
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    for t in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {t}")
    conn.commit()
    conn.close()

    init_db()
