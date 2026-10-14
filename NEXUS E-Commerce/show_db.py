#!/usr/bin/env python3
"""
NEXUS E-Commerce — Backend Database Inspector
Use this script if your evaluator or teacher asks to see the raw backend database tables,
order IDs, customers, and analytical fact sales rows directly in the terminal.
"""

import sqlite3
import os
import sys

# Windows UTF-8 console output protection
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend', 'nexus_ecommerce.db')

def print_table(title, rows, headers):
    print("\n" + "=" * 80)
    print(f"[*] {title}")
    print("=" * 80)
    if not rows:
        print("(No records found)")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val if val is not None else 'NULL')))

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(str(val if val is not None else 'NULL').ljust(col_widths[i]) for i, val in enumerate(row)))
    print(f"Total shown: {len(rows)} records\n")

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not yet created at: {DB_PATH}")
        print("Please run `python start_server.py` first to initialize the database.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "#" * 80)
    print("  NEXUS E-COMMERCE -- BACKEND DATABASE INSPECTION CONSOLE")
    print(f"  Physical SQLite Database File: {DB_PATH}")
    print("#" * 80)

    # 1. Orders table
    cursor.execute("""
        SELECT o.id, c.name, o.order_date, o.delivery_city, o.payment_method, o.total_amount, o.status
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        ORDER BY o.id DESC
        LIMIT 10
    """)
    orders = cursor.fetchall()
    print_table("LATEST OPERATIONAL ORDERS (orders table)", orders,
                ["Order ID", "Customer", "Order Date", "City", "Payment", "Total (INR)", "Status"])

    # 2. Fact Sales table
    cursor.execute("""
        SELECT f.order_id, p.name, f.date_key, f.location_key, f.quantity, f.sales_amount, f.profit_margin
        FROM fact_sales f
        JOIN dim_product p ON f.product_key = p.product_key
        ORDER BY f.fact_id DESC
        LIMIT 10
    """)
    facts = cursor.fetchall()
    print_table("ANALYTICAL STAR SCHEMA FACTS (fact_sales table)", facts,
                ["Order ID", "Product", "Date Key", "Location", "Qty", "Sales (INR)", "Margin (INR)"])

    # 3. Tables summary
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [r[0] for r in cursor.fetchall()]
    print("=" * 80)
    print("ALL TABLES PRESENT IN BACKEND DATABASE:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"  - {t.ljust(22)} : {cnt} rows")
    print("=" * 80)
    print("\n[OK] You can also view this live in the Admin Web UI under 'Database Inspector' tab!")
    conn.close()

if __name__ == '__main__':
    main()
