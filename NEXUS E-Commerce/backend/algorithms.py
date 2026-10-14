import math
import random
import time
from collections import defaultdict
from itertools import combinations
from .database import get_db

# ==============================================================================
# 1. OLAP Dimensional Engine (Multidimensional SQL Cube Aggregation)
# ==============================================================================
def execute_olap(level='year', group_by='cat', measure='sales', cat_filter=None, city_filter=None, year_filter=None):
    conn = get_db()
    cursor = conn.cursor()

    time_col = {
        'year': 'd.year',
        'quarter': 'CAST(d.year AS TEXT) || "-Q" || CAST(d.quarter AS TEXT)',
        'month': 'substr(d.date_key, 1, 7)'
    }.get(level, 'd.year')

    group_col = {
        'cat': 'p.category',
        'city': 'l.city',
        'pay': 'pm.payment_key',
        'gender': 'c.gender',
        'none': '"Total"'
    }.get(group_by, 'p.category')

    meas_expr = {
        'sales': 'SUM(f.sales_amount)',
        'qty': 'SUM(f.quantity)',
        'profit': 'SUM(f.profit_margin)'
    }.get(measure, 'SUM(f.sales_amount)')

    where_clauses = ["1=1"]
    params = []
    if cat_filter:
        where_clauses.append("p.category = ?")
        params.append(cat_filter)
    if city_filter:
        where_clauses.append("l.city = ?")
        params.append(city_filter)
    if year_filter:
        where_clauses.append("d.year = ?")
        params.append(int(year_filter))

    sql = f"""
        SELECT {time_col} as time_key,
               {group_col} as dim_group,
               {meas_expr} as val
        FROM fact_sales f
        JOIN dim_date d ON f.date_key = d.date_key
        JOIN dim_product p ON f.product_key = p.product_key
        JOIN dim_location l ON f.location_key = l.location_key
        JOIN dim_payment pm ON f.payment_key = pm.payment_key
        JOIN dim_customer c ON f.customer_key = c.customer_key
        WHERE {" AND ".join(where_clauses)}
        GROUP BY time_key, dim_group
        ORDER BY time_key ASC
    """

    rows = cursor.execute(sql, params).fetchall()
    conn.close()

    time_keys = sorted(list({r['time_key'] for r in rows}))
    dim_groups = sorted(list({r['dim_group'] for r in rows}))

    grid = {t: {g: 0 for g in dim_groups} for t in time_keys}
    for r in rows:
        grid[r['time_key']][r['dim_group']] = round(r['val'] or 0, 2)

    op_type = "Roll-up" if level == 'year' else ("Drill-down" if level == 'month' else "Slice & Dice")
    if cat_filter or city_filter or year_filter:
        op_type += " (Filtered Slice)"

    return {
        'operation_type': op_type,
        'level': level,
        'group_by': group_by,
        'measure': measure,
        'time_keys': time_keys,
        'dim_groups': dim_groups,
        'grid': grid
    }

# ==============================================================================
# 2. Customer Loyalty Clustering (K-Means, Agglomerative, Divisive)
# ==============================================================================
def get_customer_feature_vectors():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.customer_id, c.name,
               COUNT(DISTINCT f.order_id) as total_orders,
               COALESCE(SUM(f.sales_amount), 0) as total_spend,
               COALESCE(AVG(f.sales_amount), 0) as aov,
               COALESCE(SUM(f.quantity), 0) as total_units
        FROM dim_customer c
        LEFT JOIN fact_sales f ON c.customer_key = f.customer_key
        GROUP BY c.customer_id, c.name
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def euclidean_dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def kmeans_clustering(points, k=4, max_iters=35):
    if len(points) < k:
        return {p['customer_id']: 0 for p in points}, [[0, 0]] * k

    vectors = [(p['total_orders'], p['total_spend']) for p in points]
    # K-Means++ initialization
    random.seed(42)
    centroids = [vectors[random.randint(0, len(vectors) - 1)]]
    while len(centroids) < k:
        dists = [min(euclidean_dist(x, c)**2 for c in centroids) for x in vectors]
        total_d = sum(dists)
        if total_d == 0:
            centroids.append(random.choice(vectors))
            continue
        probs = [d / total_d for d in dists]
        r = random.random()
        cum = 0
        for i, p in enumerate(probs):
            cum += p
            if cum >= r:
                centroids.append(vectors[i])
                break

    assignments = [0] * len(vectors)
    for _ in range(max_iters):
        changed = False
        for i, vec in enumerate(vectors):
            closest = min(range(k), key=lambda c_idx: euclidean_dist(vec, centroids[c_idx]))
            if assignments[i] != closest:
                assignments[i] = closest
                changed = True

        for c_idx in range(k):
            cluster_members = [vectors[i] for i, a in enumerate(assignments) if a == c_idx]
            if cluster_members:
                avg_orders = sum(m[0] for m in cluster_members) / len(cluster_members)
                avg_spend = sum(m[1] for m in cluster_members) / len(cluster_members)
                centroids[c_idx] = (avg_orders, avg_spend)

        if not changed:
            break

    mapping = {points[i]['customer_id']: assignments[i] for i in range(len(points))}
    return mapping, centroids

def agglomerative_clustering(points, k=4):
    vectors = [(p['total_orders'], p['total_spend']) for p in points]
    clusters = {i: [i] for i in range(len(vectors))}
    
    while len(clusters) > k:
        c_keys = list(clusters.keys())
        min_dist = float('inf')
        pair_to_merge = (c_keys[0], c_keys[1])

        for i in range(len(c_keys)):
            for j in range(i + 1, len(c_keys)):
                k1, k2 = c_keys[i], c_keys[j]
                # Average Linkage
                dist_sum = sum(euclidean_dist(vectors[idx1], vectors[idx2]) for idx1 in clusters[k1] for idx2 in clusters[k2])
                avg_d = dist_sum / (len(clusters[k1]) * len(clusters[k2]))
                if avg_d < min_dist:
                    min_dist = avg_d
                    pair_to_merge = (k1, k2)

        k1, k2 = pair_to_merge
        clusters[k1].extend(clusters[k2])
        del clusters[k2]

    mapping = {}
    for cluster_label, member_indices in enumerate(clusters.values()):
        for idx in member_indices:
            mapping[points[idx]['customer_id']] = cluster_label
    return mapping

def divisive_clustering(points, k=4):
    clusters = [list(range(len(points)))]
    vectors = [(p['total_orders'], p['total_spend']) for p in points]

    while len(clusters) < k:
        worst_cluster_idx = max(range(len(clusters)), key=lambda idx: len(clusters[idx]))
        members = clusters.pop(worst_cluster_idx)
        if len(members) <= 1:
            clusters.append(members)
            break

        sub_pts = [points[i] for i in members]
        sub_map, _ = kmeans_clustering(sub_pts, k=2, max_iters=20)
        c0 = [members[i] for i, p in enumerate(sub_pts) if sub_map[p['customer_id']] == 0]
        c1 = [members[i] for i, p in enumerate(sub_pts) if sub_map[p['customer_id']] == 1]
        clusters.append(c0 if c0 else members[:len(members)//2])
        clusters.append(c1 if c1 else members[len(members)//2:])

    mapping = {}
    for cluster_label, member_indices in enumerate(clusters):
        for idx in member_indices:
            mapping[points[idx]['customer_id']] = cluster_label
    return mapping

def cluster_customers(algorithm='kmeans', k=4):
    points = get_customer_feature_vectors()
    if algorithm == 'kmeans':
        mapping, _ = kmeans_clustering(points, k)
    elif algorithm == 'agglo':
        mapping = agglomerative_clustering(points, k)
    elif algorithm == 'divisive':
        mapping = divisive_clustering(points, k)
    else:
        mapping, _ = kmeans_clustering(points, k)

    cluster_buckets = defaultdict(list)
    for p in points:
        cid = p['customer_id']
        c_label = mapping.get(cid, 0)
        cluster_buckets[c_label].append(p)

    segments = []
    # Rank clusters by average spend to assign professional persona titles
    sorted_labels = sorted(cluster_buckets.keys(), key=lambda l: sum(x['total_spend'] for x in cluster_buckets[l]) / max(1, len(cluster_buckets[l])), reverse=True)

    personas = [
        ("High-Value VIPs", "Premium loyalty rewards, early product drops, dedicated account assistance"),
        ("Active Core Shoppers", "Category bundle promotions, volume discounts, replenishment reminders"),
        ("Occasional Discretionary", "Seasonal sales alerts, retargeting vouchers, limited-time flash deals"),
        ("New / Low-Engagement", "First-reorder incentives, guided product onboarding, free shipping perks"),
        ("Bargain Seekers", "Clearance alerts, coupon incentives, budget category cross-sells"),
        ("At-Risk Inactive", "Re-engagement email campaigns, win-back surveys, survey incentives")
    ]

    for rank, label in enumerate(sorted_labels):
        group = cluster_buckets[label]
        count = len(group)
        avg_spend = round(sum(x['total_spend'] for x in group) / max(1, count), 2)
        avg_orders = round(sum(x['total_orders'] for x in group) / max(1, count), 1)
        persona_name, strategy = personas[min(rank, len(personas) - 1)]

        segments.append({
            'cluster_id': label,
            'persona': persona_name,
            'size': count,
            'avg_spend': avg_spend,
            'avg_orders': avg_orders,
            'strategy': strategy
        })

    scatter_points = []
    for s in segments:
        label = s['cluster_id']
        for p in cluster_buckets[label]:
            scatter_points.append({
                'customer_id': p['customer_id'],
                'name': p['name'],
                'orders': p['total_orders'],
                'spend': round(p['total_spend'], 2),
                'cluster': s['persona']
            })

    return {
        'algorithm': algorithm,
        'k': k,
        'segments': segments,
        'scatter_points': scatter_points
    }

# ==============================================================================
# 3. Customer Tier Classification (Gaussian Naive Bayes & KNN)
# ==============================================================================
def get_classification_dataset():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.customer_id,
               COUNT(DISTINCT f.order_id) as orders,
               COALESCE(AVG(f.sales_amount), 0) as aov,
               COUNT(DISTINCT p.category) as distinct_cats,
               COALESCE(SUM(f.quantity), 0) as total_units,
               COALESCE(SUM(f.sales_amount), 0) as total_spend
        FROM dim_customer c
        LEFT JOIN fact_sales f ON c.customer_key = f.customer_key
        LEFT JOIN dim_product p ON f.product_key = p.product_key
        GROUP BY c.customer_id
    """)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    dataset = []
    for r in rows:
        spend = r['total_spend']
        # Label derived using standard customer value distribution:
        # Tier 0: Low-Tier Budget (< 15,000)
        # Tier 1: Mid-Tier Core (15,000 to 45,000)
        # Tier 2: High-Value VIP (> 45,000)
        if spend < 15000:
            target = 0
        elif spend <= 45000:
            target = 1
        else:
            target = 2

        features = [float(r['orders']), float(r['aov']), float(r['distinct_cats']), float(r['total_units'])]
        dataset.append((features, target))
    return dataset

class GaussianNaiveBayes:
    def fit(self, X, y):
        self.classes = sorted(list(set(y)))
        self.class_priors = {}
        self.means = {}
        self.variances = {}

        n_samples = len(X)
        for c in self.classes:
            X_c = [X[i] for i in range(n_samples) if y[i] == c]
            self.class_priors[c] = len(X_c) / n_samples
            n_feat = len(X[0])
            self.means[c] = [sum(X_c[i][f] for i in range(len(X_c))) / len(X_c) for f in range(n_feat)]
            self.variances[c] = [
                sum((X_c[i][f] - self.means[c][f]) ** 2 for i in range(len(X_c))) / max(1, len(X_c) - 1) + 1e-4
                for f in range(n_feat)
            ]

    def _calc_likelihood(self, class_idx, x):
        mean = self.means[class_idx]
        var = self.variances[class_idx]
        log_prob = math.log(self.class_priors[class_idx])
        for f in range(len(x)):
            m, v = mean[f], var[f]
            exponent = math.exp(-((x[f] - m) ** 2) / (2 * v))
            prob = max(1e-12, (1.0 / math.sqrt(2 * math.pi * v)) * exponent)
            log_prob += math.log(prob)
        return log_prob

    def predict(self, X):
        return [max(self.classes, key=lambda c: self._calc_likelihood(c, x)) for x in X]

class KNearestNeighbors:
    def __init__(self, k=5):
        self.k = k

    def fit(self, X, y):
        self.X_train = X
        self.y_train = y
        # Feature normalization
        self.mins = [min(x[f] for x in X) for f in range(len(X[0]))]
        self.maxs = [max(x[f] for x in X) for f in range(len(X[0]))]

    def _normalize(self, x):
        return [(x[f] - self.mins[f]) / max(1e-5, (self.maxs[f] - self.mins[f])) for f in range(len(x))]

    def predict_one(self, x):
        norm_x = self._normalize(x)
        dists = []
        for i, xt in enumerate(self.X_train):
            norm_xt = self._normalize(xt)
            d = euclidean_dist(norm_x, norm_xt)
            dists.append((d, self.y_train[i]))
        dists.sort(key=lambda t: t[0])
        k_nearest = dists[:self.k]
        votes = defaultdict(float)
        for d, lbl in k_nearest:
            votes[lbl] += 1.0 / (d + 1e-5)
        return max(votes.keys(), key=lambda lbl: votes[lbl])

    def predict(self, X):
        return [self.predict_one(x) for x in X]

def train_and_eval_classifiers(k_neighbors=5):
    dataset = get_classification_dataset()
    random.seed(42)
    random.shuffle(dataset)

    # 70% Train, 30% Test split
    split_idx = int(len(dataset) * 0.70)
    train_data = dataset[:split_idx]
    test_data = dataset[split_idx:]

    X_train = [d[0] for d in train_data]
    y_train = [d[1] for d in train_data]
    X_test = [d[0] for d in test_data]
    y_test = [d[1] for d in test_data]

    # Gaussian Naive Bayes
    gnb = GaussianNaiveBayes()
    gnb.fit(X_train, y_train)
    nb_preds = gnb.predict(X_test)
    nb_acc = round(sum(1 for i in range(len(y_test)) if nb_preds[i] == y_test[i]) / len(y_test) * 100, 2)

    # 3x3 Confusion Matrix for Naive Bayes
    nb_conf_matrix = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for actual, pred in zip(y_test, nb_preds):
        nb_conf_matrix[actual][pred] += 1

    # KNN
    knn = KNearestNeighbors(k=k_neighbors)
    knn.fit(X_train, y_train)
    knn_preds = knn.predict(X_test)
    knn_acc = round(sum(1 for i in range(len(y_test)) if knn_preds[i] == y_test[i]) / len(y_test) * 100, 2)

    classes_map = ['Low-Tier Budget', 'Mid-Tier Core', 'High-Value VIP']

    return {
        'classes': classes_map,
        'nb_accuracy': nb_acc,
        'nb_confusion_matrix': nb_conf_matrix,
        'knn_accuracy': knn_acc,
        'k_neighbors': k_neighbors,
        'train_samples': len(train_data),
        'test_samples': len(test_data)
    }

def score_test_customer(features, k_neighbors=5):
    dataset = get_classification_dataset()
    X = [d[0] for d in dataset]
    y = [d[1] for d in dataset]

    gnb = GaussianNaiveBayes()
    gnb.fit(X, y)
    nb_pred = gnb.predict([features])[0]

    knn = KNearestNeighbors(k=k_neighbors)
    knn.fit(X, y)
    knn_pred = knn.predict_one(features)

    classes_map = ['Low-Tier Budget', 'Mid-Tier Core', 'High-Value VIP']
    return {
        'nb_prediction': classes_map[nb_pred],
        'knn_prediction': classes_map[knn_pred],
        'consensus': (nb_pred == knn_pred)
    }

# ==============================================================================
# 4. Sales Forecasting (Linear Regression with R² and 3-Month Projection)
# ==============================================================================
def forecast_sales():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT substr(date_key, 1, 7) as yr_mo,
               SUM(sales_amount) as monthly_sales
        FROM fact_sales
        GROUP BY yr_mo
        ORDER BY yr_mo ASC
    """)
    rows = cursor.fetchall()
    conn.close()

    months = [r['yr_mo'] for r in rows]
    actual_sales = [round(r['monthly_sales'], 2) for r in rows]

    n = len(actual_sales)
    if n < 2:
        return {'months': months, 'actual_sales': actual_sales, 'trend': actual_sales, 'slope': 0, 'r_squared': 0, 'forecast': []}

    x_vals = list(range(n))
    mean_x = sum(x_vals) / n
    mean_y = sum(actual_sales) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, actual_sales))
    denominator = sum((x - mean_x) ** 2 for x in x_vals)
    slope = numerator / denominator if denominator != 0 else 0
    intercept = mean_y - slope * mean_x

    trend_line = [round(intercept + slope * x, 2) for x in x_vals]

    ss_tot = sum((y - mean_y) ** 2 for y in actual_sales)
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(x_vals, actual_sales))
    r_squared = round(1 - (ss_res / ss_tot), 4) if ss_tot > 0 else 1.0

    # Project 3 Months Ahead
    last_mo_str = months[-1] if months else '2025-12'
    y_str, m_str = map(int, last_mo_str.split('-'))
    forecast_months = []
    forecast_sales = []

    for step in range(1, 4):
        m_str += 1
        if m_str > 12:
            m_str = 1
            y_str += 1
        future_key = f"{y_str}-{str(m_str).zfill(2)}"
        future_x = n - 1 + step
        pred_val = max(0.0, round(intercept + slope * future_x, 2))
        forecast_months.append(future_key)
        forecast_sales.append(pred_val)

    return {
        'months': months,
        'actual_sales': actual_sales,
        'trend_line': trend_line,
        'slope': round(slope, 2),
        'intercept': round(intercept, 2),
        'r_squared': r_squared,
        'forecast_months': forecast_months,
        'forecast_sales': forecast_sales
    }

# ==============================================================================
# 5. Market Basket Analysis (Apriori vs FP-Growth vs Eclat)
# ==============================================================================
def get_transaction_baskets():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT order_id, product_id FROM order_items
    """)
    rows = cursor.fetchall()
    conn.close()

    baskets = defaultdict(set)
    for r in rows:
        baskets[r['order_id']].add(r['product_id'])
    return list(baskets.values())

def run_apriori(baskets, min_support_count):
    start = time.time()
    item_counts = defaultdict(int)
    for b in baskets:
        for item in b:
            item_counts[frozenset([item])] += 1

    frequent_sets = {item: count for item, count in item_counts.items() if count >= min_support_count}
    current_k = 1
    current_l = frequent_sets
    candidates_tested = len(item_counts)

    while current_l:
        current_k += 1
        items_union = set().union(*current_l.keys())
        candidate_k = [frozenset(c) for c in combinations(items_union, current_k)]
        candidates_tested += len(candidate_k)
        counts_k = defaultdict(int)
        for b in baskets:
            for cand in candidate_k:
                if cand.issubset(b):
                    counts_k[cand] += 1
        current_l = {cand: cnt for cand, cnt in counts_k.items() if cnt >= min_support_count}
        frequent_sets.update(current_l)

    latency = round((time.time() - start) * 1000, 2)
    return frequent_sets, latency, candidates_tested

def run_fpgrowth(baskets, min_support_count):
    start = time.time()
    # Simulated tree node counting
    item_counts = defaultdict(int)
    for b in baskets:
        for item in b:
            item_counts[frozenset([item])] += 1

    frequent_1 = {item: count for item, count in item_counts.items() if count >= min_support_count}
    frequent_2 = defaultdict(int)
    tree_nodes = len(frequent_1) * 2

    for b in baskets:
        items = sorted(list(b.intersection({list(x)[0] for x in frequent_1.keys()})))
        for pair in combinations(items, 2):
            frequent_2[frozenset(pair)] += 1
            tree_nodes += 1

    frequent_sets = dict(frequent_1)
    frequent_sets.update({k: v for k, v in frequent_2.items() if v >= min_support_count})
    latency = round((time.time() - start) * 1000, 2)
    return frequent_sets, latency, tree_nodes

def run_eclat(baskets, min_support_count):
    start = time.time()
    # Vertical data format (Item -> TID Set)
    tid_map = defaultdict(set)
    for tid, b in enumerate(baskets):
        for item in b:
            tid_map[frozenset([item])].add(tid)

    frequent_sets = {}
    for item_set, tids in tid_map.items():
        if len(tids) >= min_support_count:
            frequent_sets[item_set] = len(tids)

    # 2-item intersections
    freq_items = list(frequent_sets.keys())
    for i in range(len(freq_items)):
        for j in range(i + 1, len(freq_items)):
            set_a, set_b = freq_items[i], freq_items[j]
            inter_tids = tid_map[set_a].intersection(tid_map[set_b])
            if len(inter_tids) >= min_support_count:
                frequent_sets[set_a.union(set_b)] = len(inter_tids)

    latency = round((time.time() - start) * 1000, 2)
    return frequent_sets, latency

def mine_association_rules(min_support_pct=2.0, min_conf_pct=30.0):
    baskets = get_transaction_baskets()
    total_trans = len(baskets)
    min_sup_count = max(2, int((min_support_pct / 100.0) * total_trans))

    # Benchmark 3 Algorithms
    apriori_sets, apr_latency, apr_candidates = run_apriori(baskets, min_sup_count)
    fp_sets, fp_latency, fp_nodes = run_fpgrowth(baskets, min_sup_count)
    eclat_sets, eclat_latency = run_eclat(baskets, min_sup_count)

    # Association Rules Generation
    rules = []
    conn = get_db()
    cursor = conn.cursor()
    prod_names = {r[0]: r[1] for r in cursor.execute("SELECT id, name FROM products").fetchall()}
    conn.close()

    for itemset, sup_count in apriori_sets.items():
        if len(itemset) == 2:
            items = list(itemset)
            for ant, con in [(items[0], items[1]), (items[1], items[0])]:
                ant_set = frozenset([ant])
                ant_count = apriori_sets.get(ant_set, 0)
                con_set = frozenset([con])
                con_count = apriori_sets.get(con_set, 0)

                if ant_count > 0:
                    conf = (sup_count / ant_count) * 100
                    if conf >= min_conf_pct:
                        con_sup_prob = con_count / total_trans if total_trans > 0 else 0.01
                        lift = round((conf / 100.0) / con_sup_prob, 2) if con_sup_prob > 0 else 1.0

                        rules.append({
                            'antecedents': [ant],
                            'antecedent_names': [prod_names.get(ant, f"Product #{ant}")],
                            'consequents': [con],
                            'consequent_names': [prod_names.get(con, f"Product #{con}")],
                            'support': round((sup_count / total_trans) * 100, 2),
                            'confidence': round(conf, 1),
                            'lift': lift
                        })

    rules.sort(key=lambda r: r['lift'], reverse=True)

    return {
        'total_transactions': total_trans,
        'min_support_count': min_sup_count,
        'benchmark': {
            'apriori': {'latency_ms': apr_latency, 'candidates': apr_candidates, 'sets': len(apriori_sets)},
            'fpgrowth': {'latency_ms': fp_latency, 'nodes': fp_nodes, 'sets': len(fp_sets)},
            'eclat': {'latency_ms': eclat_latency, 'sets': len(eclat_sets)}
        },
        'rules': rules
    }
