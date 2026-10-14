# NEXUS E-Commerce — Unifying e-commerce transactions with advanced analytics and Decision Support System (DSS)
**A Full-Stack Data Warehouse and Data Mining (DWM) Enterprise Platform**

---

## 1. System Overview & Problem Solved
Traditional e-commerce architectures face a classic architectural conflict:
- **OLTP (Online Transaction Processing):** Needs normalized, high-concurrency ACID transactions for shopping carts, stock decrementing, and checkout latency.
- **OLAP (Online Analytical Processing):** Needs denormalized multidimensional Star Schemas for business intelligence, sales forecasting, customer clustering, and association analysis.

Querying normalized tables for deep analytical intelligence degrades the checkout experience. **NEXUS E-Commerce** bridges this gap with a dual architecture:
1. **Consumer Storefront (OLTP):** A modern e-commerce shopping experience across 6 categories with cart management, wishlist, product details, customer reviews, and order tracking.
2. **Role-Based Access Control (RBAC):** Analytics, profit margins, and internal operational data are restricted exclusively to Store Administrators (`admin@shop.in` / `admin123`). Shoppers only see the customer storefront.
3. **Automated ETL Pipeline:** Cleanses operational noise (duplicates, null delivery city imputation, canonical payment normalization, and invalid negative quantity filtering) and populates the analytical Star Schema.
4. **Executive Decision Support System (DSS):** Translates advanced DWM algorithms (K-Means, Agglomerative, Divisive, Gaussian Naive Bayes, KNN, Linear Regression, Apriori, FP-Growth, Eclat) into visual, accessible business intelligence.

---

## 2. Where Backend Data is Stored?

The entire database is stored locally in an enterprise SQLite relational database:
```
backend/nexus_ecommerce.db
```
*(SQLite is zero-configuration, lightweight, and fully embedded).*

---

## 3. Implemented DWM Topics & Modules

| Topic | Implementation | Technical Component |
|---|---|---|
| **OLTP vs. OLAP** | Normalized transactional tables vs. Star Schema | `orders`, `order_items` vs. `fact_sales` |
| **ETL Preprocessing** | De-duplication, imputation, canonical string mapping | `backend/etl_pipeline.py` & audit log |
| **Dimensional Modeling** | Star Schema (`FACT_SALES` + 5 Dimensions) | `dim_customer`, `dim_product`, `dim_date`, `dim_location`, `dim_payment` |
| **Multidimensional OLAP** | Roll-up, Drill-down, Slice, Dice, Pivot | `backend/algorithms.py` (`execute_olap`) |
| **Customer Clustering** | K-Means (K-Means++), Agglomerative, Divisive | Behavioral scatter plot (Spend vs. Frequency) |
| **Classification** | Gaussian Naive Bayes & K-Nearest Neighbors (KNN) | 70/30 train-test split, 3x3 confusion matrix, sandbox |
| **Sales Forecasting** | Simple Linear Regression ($R^2$ fit & 3-month projection) | Trend velocity slope, intercept, and future projections |
| **Market Basket Analysis** | Apriori vs. FP-Growth vs. Eclat Tri-Comparison | Support, Confidence, Lift, and cross-sell bundles |

---

## 4. How to Run the Application

1. **Install Requirements:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Launch Server:**
   ```bash
   python start_server.py
   ```
3. **Open in Browser:**
   Navigate to `http://localhost:5000`

### Login Accounts
- **Customer Account:** `demo@shop.in` / `demo123` (Accesses Storefront, Cart, Orders)
- **Admin Account:** `admin@shop.in` / `admin123` (Unlocks Executive Analytics, DWM Suite, Database Inspector)

*(Press **`P`** on any page to toggle **16:9 Presentation Fit** for projector/screen presentations).*

---
**NEXUS E-Commerce — Operational Storefront & Analytical Decision Support Platform © 2026**
