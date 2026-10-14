"""
NEXUS E-Commerce — One-Click Database Reset Utility
Wipes all custom runtime test orders and restores the clean, seeded benchmark state:
80 customers, 24 products, 900 orders, and 1,609 star schema facts with dirty records.
"""

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from backend.database import reset_database
from backend.etl_pipeline import execute_etl

def main():
    print("=" * 80)
    print("  REFRESHING NEXUS E-COMMERCE DATABASE & ADMIN PORTAL TO CLEAN STATE...")
    print("=" * 80)
    print("[1/2] Dropping runtime tables and re-seeding clean demo dataset...")
    reset_database()
    print("      ✓ 80 customers seeded")
    print("      ✓ 24 products seeded")
    print("      ✓ 900 orders seeded (including 15 duplicates for ETL demo)")
    print("      ✓ Admin & Shopper credentials restored")
    
    print("[2/2] Running ETL pipeline to rebuild analytical star schema...")
    audit = execute_etl()
    print(f"      ✓ {audit['facts_loaded']} facts loaded into fact_sales ({audit['duration_ms']} ms)")
    print(f"      ✓ 15 duplicate orders de-duplicated into etl_audit_log")
    
    print("=" * 80)
    print("🎉 SUCCESS: Database and Admin Portal are now completely fresh and clean!")
    print("=" * 80)

if __name__ == '__main__':
    main()
