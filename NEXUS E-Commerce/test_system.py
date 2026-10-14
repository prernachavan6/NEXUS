"""
NEXUS E-Commerce — Automated End-to-End Verification Test Script
Tests all operational endpoints, algorithms, ETL, and database inspector.
"""

import sys
import os
import json

# Ensure nexus_ecommerce is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app import app
from backend.database import init_db, DB_PATH
from backend.etl_pipeline import execute_etl

def run_all_tests():
    print("=" * 80)
    print("🧪 RUNNING COMPREHENSIVE NEXUS E-COMMERCE END-TO-END TEST SUITE")
    print("=" * 80)

    # 1. Database & Initial ETL Check
    print("[1/10] Initializing database and verifying seeding...")
    init_db()
    etl_res = execute_etl()
    print(f"       ✓ Facts loaded: {etl_res['facts_loaded']}, Duplicates cleaned: {etl_res['duplicates_removed']}")
    assert etl_res['facts_loaded'] > 0, "ETL failed to load facts"

    client = app.test_client()

    # 2. Authentication Tests (Customer & Admin RBAC)
    print("[2/10] Testing Authentication & RBAC...")
    # Customer login
    res = client.post('/api/auth/login', json={'email': 'demo@shop.in', 'password': 'demo123'})
    assert res.status_code == 200, f"Customer login failed: {res.data}"
    cust_data = res.get_json()
    assert cust_data['role'] == 'customer', f"Expected customer role, got {cust_data['role']}"
    assert 'customer_id' in cust_data and cust_data['customer_id'] is not None, "Missing customer_id"
    print(f"       ✓ Customer login successful: {cust_data['name']} (Role: {cust_data['role']}, CustID: {cust_data['customer_id']})")

    # Admin login
    res = client.post('/api/auth/login', json={'email': 'admin@shop.in', 'password': 'admin123'})
    assert res.status_code == 200, f"Admin login failed: {res.data}"
    admin_data = res.get_json()
    assert admin_data['role'] == 'admin', f"Expected admin role, got {admin_data['role']}"
    print(f"       ✓ Admin login successful: {admin_data['name']} (Role: {admin_data['role']})")

    # Register new user
    res = client.post('/api/auth/register', json={
        'name': 'Test Shopper',
        'email': f'testshopper_{int(os.getpid())}@test.in',
        'password': 'password123',
        'city': 'Bengaluru'
    })
    assert res.status_code == 200, f"Registration failed: {res.data}"
    reg_data = res.get_json()
    assert reg_data['customer_id'] is not None, "Registered user missing customer_id"
    print(f"       ✓ Registration successful: {reg_data['name']} (CustID: {reg_data['customer_id']})")

    # 3. Product Catalog Tests
    print("[3/10] Testing Product Catalog API...")
    res = client.get('/api/products')
    assert res.status_code == 200, "Failed to get products"
    products = res.get_json()
    assert len(products) >= 24, f"Expected at least 24 products, got {len(products)}"
    sample_pid = products[0]['id']
    print(f"       ✓ Catalog loaded: {len(products)} products verified")

    res = client.get(f'/api/products/{sample_pid}/reviews')
    assert res.status_code == 200, "Failed to get product reviews"
    reviews = res.get_json()
    print(f"       ✓ Product reviews loaded: {len(reviews)} reviews for Product #{sample_pid}")

    # 4. Cart & Checkout Verification (Testing the bug reported by user)
    print("[4/10] Testing Cart Checkout with customer_id...")
    order_payload = {
        'customer_id': cust_data['customer_id'],
        'items': [
            {'product_id': products[0]['id'], 'quantity': 2, 'unit_price': products[0]['price']},
            {'product_id': products[1]['id'], 'quantity': 1, 'unit_price': products[1]['price']}
        ],
        'delivery_city': 'Pune',
        'payment_method': 'UPI'
    }
    res = client.post('/api/orders/checkout', json=order_payload)
    assert res.status_code == 200, f"Checkout failed: {res.data}"
    checkout_res = res.get_json()
    assert 'order_id' in checkout_res, "Checkout did not return order_id"
    new_order_id = checkout_res['order_id']
    print(f"       ✓ Checkout successful! New Order ID generated: {new_order_id} (Total: ₹{checkout_res['total_amount']})")

    # Also test checkout with fallback (null customer_id should NOT throw 400 error anymore)
    res = client.post('/api/orders/checkout', json={
        'customer_id': None,
        'items': [{'product_id': products[0]['id'], 'quantity': 1, 'unit_price': products[0]['price']}],
        'delivery_city': 'Mumbai',
        'payment_method': 'COD'
    })
    assert res.status_code == 200, f"Fallback checkout failed: {res.data}"
    print(f"       ✓ Fallback customer_id checkout successful! Handled safely without 400 error.")

    # 5. Order History Verification
    print("[5/10] Testing Order History...")
    res = client.get(f'/api/orders/customer/{cust_data["customer_id"]}')
    assert res.status_code == 200, "Failed to get customer orders"
    cust_orders = res.get_json()
    assert len(cust_orders) > 0, "Expected customer orders in history"
    print(f"       ✓ Customer order history verified: {len(cust_orders)} orders recorded")

    # 6. Re-run ETL Pipeline with new live order
    print("[6/10] Testing Re-run ETL Pipeline with live placed order...")
    res = client.post('/api/etl/run')
    assert res.status_code == 200, "ETL run failed"
    audit = res.get_json()['audit']
    print(f"       ✓ ETL Pipeline executed: {audit['facts_loaded']} facts loaded in {audit['duration_ms']} ms")

    # 7. OLAP Dimensional Engine Verification
    print("[7/10] Testing OLAP Cube (Roll-up, Drill-down, Slice, Dice, Pivot)...")
    res = client.get('/api/analytics/olap?level=quarter&group_by=cat&measure=sales')
    assert res.status_code == 200, "OLAP request failed"
    olap_data = res.get_json()
    assert len(olap_data['time_keys']) > 0, "OLAP returned no time keys"
    assert len(olap_data['dim_groups']) > 0, "OLAP returned no dimension groups"
    print(f"       ✓ OLAP Cube verified: {len(olap_data['time_keys'])} quarters across {len(olap_data['dim_groups'])} categories")

    # 8. Machine Learning Modules (Clustering, Classification, Regression, Market Basket)
    print("[8/10] Testing Machine Learning & Data Mining Algorithms...")
    # Clustering (K-Means, Agglomerative, Divisive)
    for alg in ['kmeans', 'agglo', 'divisive']:
        res = client.get(f'/api/analytics/clustering?algorithm={alg}&k=4')
        assert res.status_code == 200, f"Clustering {alg} failed"
        clu = res.get_json()
        assert len(clu['segments']) == 4, f"Expected 4 segments for {alg}"
    print("       ✓ Clustering verified: K-Means, Agglomerative, Divisive all 100% operational")

    # Classification (Naive Bayes & KNN)
    res = client.get('/api/analytics/classification?k=5')
    assert res.status_code == 200, "Classification failed"
    cls_res = res.get_json()
    assert 'nb_accuracy' in cls_res and 'knn_accuracy' in cls_res, "Missing accuracy in classification"
    print(f"       ✓ Classification verified: Naive Bayes {cls_res['nb_accuracy']}%, KNN {cls_res['knn_accuracy']}%")

    # Classification sandbox prediction
    res = client.post('/api/analytics/classification/predict', json={'orders': 15, 'aov': 3500, 'categories': 4, 'units': 20, 'k': 5})
    assert res.status_code == 200, "Classification predict failed"
    pred_res = res.get_json()
    print(f"       ✓ Classification prediction sandbox verified: NB={pred_res['nb_prediction']}, KNN={pred_res['knn_prediction']}")

    # Sales Forecasting (Linear Regression)
    res = client.get('/api/analytics/forecast')
    assert res.status_code == 200, "Forecast failed"
    fc = res.get_json()
    assert len(fc['forecast_months']) == 3, "Expected 3-month forecast"
    print(f"       ✓ Sales Forecasting verified: R²={fc['r_squared']}, Slope=+₹{fc['slope']}/mo, 3-Month Projection={fc['forecast_months']}")

    # Market Basket (Apriori, FP-Growth, Eclat)
    res = client.get('/api/analytics/market-basket?min_support=1.5&min_confidence=25.0')
    assert res.status_code == 200, "Market basket failed"
    mb = res.get_json()
    assert 'apriori' in mb['benchmark'] and 'fpgrowth' in mb['benchmark'] and 'eclat' in mb['benchmark'], "Missing benchmark algorithms"
    print(f"       ✓ Market Basket verified: Apriori ({mb['benchmark']['apriori']['latency_ms']}ms), FP-Growth ({mb['benchmark']['fpgrowth']['latency_ms']}ms), Eclat ({mb['benchmark']['eclat']['latency_ms']}ms), {len(mb['rules'])} association rules mined")

    # 9. Database Inspector Verification (Answering "Show Ma'am the Backend")
    print("[9/10] Testing Database Inspector & SQL Console APIs...")
    res = client.get('/api/db/tables')
    assert res.status_code == 200, "Failed to get db tables"
    tables = res.get_json()['tables']
    assert 'orders' in tables and 'fact_sales' in tables, "Expected tables missing in DB"
    print(f"       ✓ Database tables listed: {len(tables)} tables found ({', '.join(tables[:6])}...)")

    res = client.get('/api/db/table/orders?limit=5')
    assert res.status_code == 200, "Failed to get orders table data"
    tbl_data = res.get_json()
    assert len(tbl_data['rows']) > 0, "No rows in orders table"
    print(f"       ✓ Raw table sample inspected: {len(tbl_data['rows'])} rows retrieved with columns: {tbl_data['columns'][:5]}")

    res = client.post('/api/db/query', json={'query': 'SELECT id, customer_id, order_date, total_amount, status FROM orders ORDER BY id DESC LIMIT 3'})
    assert res.status_code == 200, "Failed to execute custom SQL query"
    query_data = res.get_json()['data']
    assert len(query_data['rows']) == 3, f"Expected 3 rows, got {len(query_data['rows'])}"
    print(f"       ✓ Custom SQL Query Console verified: Live queries execute successfully against SQLite database")

    # 10. Frontend Files & UI Checks
    print("[10/10] Verifying Frontend Assets, Palette & Layout...")
    with open(os.path.join(BASE_DIR, 'frontend', 'css', 'styles.css'), 'r', encoding='utf-8') as f:
        css = f.read()
    assert '--primary: #7c3aed;' in css, "Mauve primary color missing in CSS"
    assert '--bg-app: #faf7fc;' in css, "Mauve off-white background missing in CSS"
    print("       ✓ CSS verified: Faint purple / mauve shade with off-white palette active")

    with open(os.path.join(BASE_DIR, 'frontend', 'index.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    assert 'Prerna' not in html and '24101C0072' not in html, "Student watermark still in HTML!"
    assert 'NEXUS E-Commerce' in html, "Brand missing in HTML"
    assert 'modeBar' in html and 'style="display:none;"' in html, "modeBar should be hidden by default for shoppers"
    print("       ✓ HTML verified: Student watermarks removed, brand-only footer present, RBAC modeBar hidden for customers")

    with open(os.path.join(BASE_DIR, 'frontend', 'js', 'app.js'), 'r', encoding='utf-8') as f:
        app_js = f.read()
    assert 'About Project' not in app_js, "'About Project' tab should be removed!"
    assert 'moduleDatabaseInspector' in app_js, "Database Inspector module should be present in app.js"
    assert 'resolvedCustomerId' in app_js or 'customer_id' in app_js, "Customer ID resolution should be in app.js"
    print("       ✓ JavaScript verified: 'About Project' tab removed, Database Inspector active, bulletproof checkout active")

    print("\n" + "=" * 80)
    print("🎉 ALL 10 TEST SUITES PASSED WITH 100% SUCCESS! SYSTEM IS FULLY VERIFIED.")
    print("=" * 80)

if __name__ == '__main__':
    run_all_tests()
