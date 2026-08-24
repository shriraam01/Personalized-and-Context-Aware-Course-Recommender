"""
Course Recommender - Flask Backend
====================================
All 4 ML improvements:
  1. Feedback system  — thumbs up/down stored, XGBoost trained on real signals
  2. Collaborative filtering — similar users boost shared liked courses
  3. Sentence Transformers — semantic similarity (falls back to TF-IDF)
  4. Profile-to-field mapping — budget/time/cert matched directly to course fields
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import mysql.connector
from mysql.connector import IntegrityError, Error as MySQLError
import joblib, os, hashlib, traceback
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBRegressor

# ── Improvement 3: Sentence Transformers ─────────────────────────────────────
try:
    from sentence_transformers import SentenceTransformer
    _ST = SentenceTransformer("all-MiniLM-L6-v2")
    USE_SEMANTIC = True
    print("[INFO] Sentence Transformers loaded.")
except Exception:
    USE_SEMANTIC = False
    print("[INFO] Using TF-IDF fallback.")

# ── Embedding cache — precomputed at startup, reused across all requests ──────
_EMBED_CACHE = {"corpus": None, "embeddings": None}

def get_course_embeddings(corpus):
    """Return cached embeddings if corpus unchanged, else recompute."""
    global _EMBED_CACHE
    if _EMBED_CACHE["corpus"] == corpus and _EMBED_CACHE["embeddings"] is not None:
        return _EMBED_CACHE["embeddings"]
    print(f"[CACHE] Computing embeddings for {len(corpus)} courses...")
    embeddings = _ST.encode(
        corpus, show_progress_bar=True,
        normalize_embeddings=True, batch_size=128
    )
    _EMBED_CACHE["corpus"]     = corpus
    _EMBED_CACHE["embeddings"] = embeddings
    print("[CACHE] Done — embeddings cached in memory.")
    return embeddings

def precompute_embeddings():
    """Called once at startup — fetches all courses and pre-encodes them."""
    if not USE_SEMANTIC:
        return
    try:
        print("[STARTUP] Pre-computing course embeddings...")
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT course_title, subject, level FROM courses")
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            print("[STARTUP] No courses found — skipping precompute.")
            return
        corpus = [
            f"{r.get('course_title','')} {r.get('course_title','')} {r.get('course_title','')} "
            f"{r.get('subject','')} {r.get('level','')}"
            for r in rows
        ]
        get_course_embeddings(corpus)
        print(f"[STARTUP] {len(corpus)} course embeddings ready. First request will be fast.")
    except Exception as e:
        print(f"[STARTUP] Precompute failed (non-fatal): {e}")

app = Flask(__name__)
app.secret_key = "course-recommender-secret-2024"
CORS(app, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

DB_CONFIG = {
    "host": "localhost", "user": "root",
    "password": "root123", "database": "course_recommender"
}

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def safe(v):
    return "" if v is None else str(v)

def infer_level(exp):
    try:
        exp = float(exp)
    except Exception:
        exp = 0.0
    if exp == 0:  return "Beginner"
    if exp <= 2:  return "Intermediate"
    return "Advanced"

def jaccard_sim(a, b):
    s1, s2 = set(a.lower().split()), set(b.lower().split())
    u = s1 | s2
    return len(s1 & s2) / len(u) if u else 0.0

def get_col(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).values.astype(float)
    return np.zeros(len(df))

def build_url(row):
    import urllib.parse
    # Use stored URL only if it's a real Udemy course URL
    url = str(row.get("url", "")).strip()
    if url.startswith("http") and "udemy.com/course/" in url:
        return url
    # Always fall back to Udemy search — guaranteed to work and show relevant results
    title = str(row.get("title", "")).strip()
    if title:
        query = urllib.parse.quote_plus(title)
        return f"https://www.udemy.com/courses/search/?q={query}&sort=relevance"
    return "https://www.udemy.com"

# ── Keyword expansion ─────────────────────────────────────────────────────────
EXPAND = {
    "data science":           "pandas numpy statistics visualization sql data analysis",
    "machine learning":       "regression classification sklearn supervised unsupervised model",
    "artificial intelligence":"deep learning nlp pytorch tensorflow keras",
    "web development":        "html css javascript react node express frontend backend",
    "mobile development":     "android ios swift kotlin flutter react native",
    "cyber security":         "hacking penetration testing network security cryptography",
    "cloud computing":        "aws azure gcp kubernetes terraform serverless",
    "devops":                 "docker kubernetes jenkins ci cd automation pipeline",
    "blockchain":             "ethereum solidity smart contracts web3 defi",
}
GOAL_EXPAND = {
    "data scientist":            "python sql statistics machine learning data",
    "machine learning engineer": "tensorflow pytorch deployment mlops",
    "software engineer":         "algorithms data structures system design",
    "web developer":             "javascript react html css node api",
    "mobile app developer":      "swift kotlin flutter react native",
    "cyber security specialist": "penetration testing hacking network",
    "cloud engineer":            "aws azure terraform kubernetes",
    "ai researcher":             "deep learning nlp computer vision",
    "devops engineer":           "docker kubernetes jenkins pipeline",
    "blockchain developer":      "solidity ethereum smart contract web3",
}

def expand_keywords(interest, goal, level):
    out = []
    for k, v in EXPAND.items():
        if k in interest.lower():
            out.append(v)
    for k, v in GOAL_EXPAND.items():
        if k in goal.lower():
            out.append(v)
    out.append(level.lower())
    return " ".join(out)

# ── Improvement 4: Profile-to-field mapping ───────────────────────────────────
BUDGET_MAP = {
    "free only":        0.0,
    "under ₹1,000":    1000.0,
    "₹1,000 – ₹5,000": 5000.0,
    "₹5,000+":         99999.0,
    "no limit":        99999.0,
}
TIME_MAP = {
    "1 – 2 hours / week":  2.0,
    "3 – 5 hours / week":  5.0,
    "5 – 10 hours / week": 10.0,
    "10+ hours / week":    20.0,
}

def budget_score(user_budget_str, course_price):
    max_price = BUDGET_MAP.get(user_budget_str.lower(), 99999.0)
    if max_price >= 99999.0 or course_price <= 0:
        return 1.0
    if course_price <= max_price:
        return 1.0
    over = (course_price - max_price) / (max_price + 1e-9)
    return max(0.0, 1.0 - over)

def time_score(user_time_str, course_duration_hours):
    weekly = TIME_MAP.get(user_time_str.lower(), 5.0)
    ideal  = weekly * 4
    if course_duration_hours <= 0:
        return 0.5
    diff = abs(course_duration_hours - ideal)
    return max(0.0, 1.0 - diff / (ideal + 1e-9))

def cert_score(cert_needed_str, is_paid_val):
    if cert_needed_str.lower() == "yes":
        return 1.0 if float(is_paid_val or 0) > 0 else 0.3
    return 1.0

# ── Improvement 1+2: Feedback helpers ────────────────────────────────────────
def get_feedback_boost(username, course_ids):
    if not course_ids:
        return {}
    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        ph   = ",".join(["%s"] * len(course_ids))

        # Direct user feedback
        cur.execute(
            f"SELECT course_id, liked FROM feedback WHERE username=%s AND course_id IN ({ph})",
            [username] + list(course_ids)
        )
        rows  = cur.fetchall()
        # Small nudge only — feedback should not override profile matching
        boost = {r["course_id"]: (0.08 if r["liked"] else -0.06) for r in rows}

        # Collaborative filtering: find courses liked by similar users
        liked_ids = [r["course_id"] for r in rows if r["liked"]]
        if liked_ids:
            ph2 = ",".join(["%s"] * len(liked_ids))
            cur.execute(
                f"""SELECT f2.course_id, COUNT(*) as cnt
                    FROM feedback f1
                    JOIN feedback f2 ON f1.username = f2.username
                    WHERE f1.course_id IN ({ph2})
                      AND f1.username != %s
                      AND f2.liked = 1
                      AND f2.course_id NOT IN ({ph2})
                    GROUP BY f2.course_id
                    ORDER BY cnt DESC
                    LIMIT 20""",
                liked_ids + [username] + liked_ids
            )
            for r in cur.fetchall():
                cid = r["course_id"]
                boost[cid] = boost.get(cid, 0.0) + min(0.04, r["cnt"] * 0.01)

        cur.close(); conn.close()
        return boost
    except Exception as e:
        print(f"[FEEDBACK BOOST] {e}")
        return {}

def get_feedback_for_training(username):
    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("SELECT course_id, liked FROM feedback WHERE username=%s", (username,))
        rows = cur.fetchall()
        cur.close(); conn.close()
        return rows
    except Exception:
        return []

# ── XGBoost ───────────────────────────────────────────────────────────────────
MODEL_PATH = "course_model.pkl"

def train_xgb(X, y):
    print(f"[TRAIN] samples={len(y)} features={X.shape[1]}")
    xgb = XGBRegressor(
        n_estimators=300, max_depth=5, learning_rate=0.1,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, verbosity=0, tree_method="hist"
    )
    xgb.fit(X, y)
    joblib.dump(xgb, MODEL_PATH)
    print("[TRAIN] Done")
    return xgb

def get_model(X, y):
    if os.path.exists(MODEL_PATH):
        try:
            m = joblib.load(MODEL_PATH)
            expected = m.n_features_in_ if hasattr(m, "n_features_in_") else X.shape[1]
            if expected != X.shape[1]:
                print(f"[TRAIN] Feature mismatch ({expected} vs {X.shape[1]}) — retraining.")
                os.remove(MODEL_PATH)
                return train_xgb(X, y)
            m.predict(X[:1])
            return m
        except Exception as e:
            print(f"[TRAIN] Load failed ({e}) — retraining.")
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
    return train_xgb(X, y)

# ── Recommender ───────────────────────────────────────────────────────────────
def recommend_courses(user):
    username = safe(user.get("username", ""))
    print(f"[REC] user={username}")

    conn = get_db()
    cur  = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM courses")
    rows = cur.fetchall()
    cur.close(); conn.close()

    if not rows:
        return [], 0.0, "Unknown"

    df = pd.DataFrame(rows).reset_index(drop=True)
    df.fillna("", inplace=True)
    df.rename(columns={"course_title": "title", "subject": "domain",
                        "level": "difficulty"}, inplace=True)
    n = len(df)
    print(f"[REC] {n} courses")

    # Numeric
    subs     = get_col(df, "num_subscribers")
    reviews  = get_col(df, "num_reviews")
    price    = get_col(df, "price")
    duration = get_col(df, "content_duration")
    is_paid  = get_col(df, "is_paid")

    pop_norm = (np.log1p(subs) * 0.6 + np.log1p(reviews) * 0.4)
    pop_norm = pop_norm / (pop_norm.max() + 1e-9)
    pr_norm  = price    / (price.max()    + 1e-9)
    dur_norm = duration / (duration.max() + 1e-9)

    # User fields
    detected  = infer_level(user.get("experience_years", 0))
    interest  = safe(user.get("interest"))
    goal      = safe(user.get("career_goal"))
    tools     = safe(user.get("known_tools"))
    budget    = safe(user.get("budget"))
    time_pref = safe(user.get("time_commitment"))
    cert      = safe(user.get("certification_needed"))

    # Text corpus
    titles  = df["title"].astype(str).tolist()
    domains = df["domain"].astype(str).tolist()
    diffs   = df["difficulty"].astype(str).tolist()
    corpus  = [f"{t} {t} {t} {d} {lv}" for t, d, lv in zip(titles, domains, diffs)]
    core     = (interest + " " + goal + " " + tools + " ") * 4
    ctx      = " ".join([safe(user.get("learning_style", "")),
                         safe(user.get("motivation", "")),
                         safe(user.get("career_stage", "")),
                         detected, expand_keywords(interest, goal, detected)])
    user_text = core + ctx

    # Similarity
    if USE_SEMANTIC:
        print("[REC] Semantic similarity (cached)...")
        course_emb = get_course_embeddings(corpus)
        user_emb   = _ST.encode([user_text], show_progress_bar=False,
                                normalize_embeddings=True)
        cos        = cosine_similarity(user_emb, course_emb).flatten()
    else:
        print("[REC] TF-IDF similarity...")
        tfidf  = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        matrix = tfidf.fit_transform(corpus)
        cos    = cosine_similarity(tfidf.transform([user_text]), matrix).flatten()

    jac = np.array([jaccard_sim(user_text, c) for c in corpus])

    # Domain boost
    il = interest.lower(); iw = il.split()
    dom_boost = np.array([
        1.0 if il in str(d).lower() or str(d).lower() in il
        else 0.4 if any(w in str(d).lower() for w in iw)
        else 0.0 for d in domains
    ])

    # Difficulty
    lmap  = {"Beginner": 1, "Intermediate": 2, "Advanced": 3, "All": 2}
    u_lvl = lmap.get(detected, 1)
    diff  = np.array([1.0 / (1.0 + abs(u_lvl - lmap.get(
        str(s).split()[0].capitalize(), 2))) for s in diffs])

    # Improvement 4: direct field mapping
    budget_sc = np.array([budget_score(budget, p) for p in price])
    time_sc   = np.array([time_score(time_pref, d) for d in duration])
    cert_sc   = np.array([cert_score(cert, ip) for ip in is_paid])

    # Feature matrix (12 features)
    X_raw = np.column_stack([
        cos, jac, pop_norm, diff, dom_boost,
        reviews / max(reviews.max(), 1),
        subs    / max(subs.max(), 1),
        pr_norm, dur_norm,
        budget_sc, time_sc, cert_sc
    ])
    scaler = MinMaxScaler()
    X      = scaler.fit_transform(X_raw)

    # Proxy target
    y_proxy = (cos * 0.30 + jac * 0.08 + dom_boost * 0.25 + diff * 0.12 +
               pop_norm * 0.10 + budget_sc * 0.08 + time_sc * 0.04 + cert_sc * 0.03)

    # Improvement 1: only blend feedback when we have ENOUGH signals (min 15)
    # With fewer signals, random thumbs corrupt the model more than they help
    fb_rows = get_feedback_for_training(username)
    MIN_FEEDBACK_FOR_TRAINING = 15
    if fb_rows and len(fb_rows) >= MIN_FEEDBACK_FOR_TRAINING and "id" in df.columns:
        print(f"[REC] Blending {len(fb_rows)} feedback signals into training")
        fb_map     = {r["course_id"]: (1.0 if r["liked"] else 0.0) for r in fb_rows}
        cids       = df["id"].values
        y_feedback = np.array([fb_map.get(int(c), -1.0) for c in cids])
        has_fb     = y_feedback >= 0
        y_final    = y_proxy.copy()
        # Blend lightly — profile proxy still dominates 70%
        y_final[has_fb] = y_proxy[has_fb] * 0.70 + y_feedback[has_fb] * 0.30
    else:
        if fb_rows:
            print(f"[REC] Only {len(fb_rows)} feedback signals — need {MIN_FEEDBACK_FOR_TRAINING} to train. Using proxy only.")
        y_final = y_proxy

    model = get_model(X, y_final)
    ml_sc = np.clip(model.predict(X), 0, 1)

    # Profile-driven scoring — cos and dom_boost dominate
    # ml_sc reduced to prevent overfitting to proxy target
    final = (cos       * 0.35 +   # semantic profile match (most important)
             dom_boost * 0.25 +   # exact domain alignment
             diff      * 0.15 +   # difficulty level match
             ml_sc     * 0.10 +   # XGBoost (small weight — avoids overfitting)
             budget_sc * 0.06 +   # budget fit
             jac       * 0.04 +   # jaccard keyword overlap
             time_sc   * 0.03 +   # time commitment match
             pop_norm  * 0.01 +   # popularity (tiny — avoids popularity bias)
             cert_sc   * 0.01)    # certification preference
    df["final_score"] = final
    df["ml_score"]    = np.round(ml_sc * 100, 1)   # XGBoost raw score as %
    df["cos_score"]   = np.round(cos * 100, 1)      # semantic similarity %

    # Print top 5 ML scores to terminal so you can see them
    top5_idx = np.argsort(final)[::-1][:5]
    print("[ML SCORES] Top 5 XGBoost predictions:")
    for i, idx in enumerate(top5_idx):
        print(f"  #{i+1} ml={ml_sc[idx]:.4f} ({ml_sc[idx]*100:.1f}%)  "
              f"cos={cos[idx]:.4f}  final={final[idx]:.4f}  "
              f"title={df.iloc[idx]['title'][:50]}")

    # Improvement 1+2: post-scoring feedback/collaborative boost
    if "id" in df.columns:
        fb_boost = get_feedback_boost(username, df["id"].tolist())
        if fb_boost:
            print(f"[REC] Feedback boost on {len(fb_boost)} courses")
            for idx, row in df.iterrows():
                cid = row.get("id")
                if cid in fb_boost:
                    df.at[idx, "final_score"] = min(
                        1.0, df.at[idx, "final_score"] + fb_boost[cid])

    df = df.sort_values("final_score", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)

    scores     = df["final_score"].values
    top_score  = float(scores[0]) if len(scores) > 0 else 0.0
    gap_thresh = top_score * 0.15
    cutoff     = len(scores)
    for i in range(1, len(scores)):
        if i >= 6 and (scores[i - 1] - scores[i] > gap_thresh or scores[i] < 0.02):
            cutoff = i; break

    n_results = max(6, min(15, cutoff))
    top_n = df.head(n_results).copy()

    # Build URL separately — only keep the fields the frontend needs
    KEEP_COLS = ["id", "title", "domain", "difficulty", "num_subscribers",
                 "num_reviews", "price", "final_score", "rank"]
    display_cols = [c for c in KEEP_COLS if c in top_n.columns]
    result = top_n[display_cols].copy()

    # Add course_url as the only URL field — computed cleanly, never shown as text
    result["course_url"] = top_n.apply(build_url, axis=1)

    top_score = float(result["final_score"].iloc[0]) if len(result) > 0 else 0
    print(f"[REC] Done: n={n_results}, top_score={top_score:.4f}")
    return result.to_dict("records"), detected


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/register", methods=["POST"])
def register():
    try:
        d = request.get_json(force=True)
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        if not u or not p:
            return jsonify({"status": "fail", "message": "Both fields required."}), 400
        if len(u) < 3:
            return jsonify({"status": "fail", "message": "Username min 3 chars."}), 400
        if len(p) < 6:
            return jsonify({"status": "fail", "message": "Password min 6 chars."}), 400
        conn = get_db(); cur = conn.cursor()
        cur.execute("INSERT INTO users(username,password) VALUES(%s,%s)", (u, hash_pw(p)))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"status": "success"})
    except IntegrityError:
        return jsonify({"status": "fail", "message": "Username already exists."}), 409
    except Exception as e:
        print(f"[REGISTER] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    try:
        d = request.get_json(force=True)
        u = (d.get("username") or "").strip()
        p = d.get("password") or ""
        if not u or not p:
            return jsonify({"status": "fail", "message": "Both fields required."}), 400
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s AND password=%s", (u, hash_pw(p)))
        user = cur.fetchone(); cur.close(); conn.close()
        if user:
            return jsonify({"status": "success", "username": u})
        return jsonify({"status": "fail", "message": "Invalid username or password."}), 401
    except Exception as e:
        print(f"[LOGIN] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/profile", methods=["POST"])
def profile():
    try:
        d = request.get_json(force=True)
        u = (d.get("username") or "").strip()
        if not u:
            return jsonify({"status": "fail", "message": "Not identified."}), 400
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id FROM users WHERE username=%s", (u,))
        if not cur.fetchone():
            cur.close(); conn.close()
            return jsonify({"status": "fail", "message": "User not found."}), 404
        cur = conn.cursor()
        cur.execute(
            """UPDATE users SET interest=%s, career_goal=%s, experience_years=%s,
               known_tools=%s, preferred_language=%s, budget=%s, time_commitment=%s,
               learning_style=%s, certification_needed=%s, motivation=%s,
               career_stage=%s WHERE username=%s""",
            (d.get("interest"), d.get("career_goal"), d.get("experience_years"),
             d.get("known_tools"), d.get("preferred_language"), d.get("budget"),
             d.get("time_commitment"), d.get("learning_style"),
             d.get("certification_needed"), d.get("motivation"),
             d.get("career_stage"), u)
        )
        conn.commit(); cur.close(); conn.close()
        # Clear cached model so it retrains with updated profile on next request
        if os.path.exists(MODEL_PATH):
            os.remove(MODEL_PATH)
            print(f"[PROFILE] Model cache cleared for {u} — will retrain")
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"[PROFILE] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/recommend", methods=["POST", "GET"])
def recommend():
    try:
        if request.method == "POST":
            d = request.get_json(force=True) or {}
            u = (d.get("username") or "").strip()
        else:
            u = (request.args.get("username") or "").strip()
        if not u:
            return jsonify({"status": "fail", "message": "Not identified."}), 400

        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (u,))
        user = cur.fetchone(); cur.close(); conn.close()

        if not user:
            return jsonify({"status": "fail", "message": "User not found."}), 404
        if not user.get("interest"):
            return jsonify({"status": "fail", "message": "Please complete your profile first."}), 400

        user["username"] = u
        courses, level = recommend_courses(user)
        return jsonify({"status": "success", "level": level, "courses": courses})
    except Exception as e:
        print(f"[RECOMMEND ERROR]\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": f"Error: {str(e)}"}), 500


@app.route("/api/feedback", methods=["POST"])
def feedback():
    """POST /api/feedback  body: {username, course_id, liked: true/false}"""
    try:
        d         = request.get_json(force=True)
        username  = (d.get("username") or "").strip()
        course_id = d.get("course_id")
        liked     = d.get("liked")
        if not username or course_id is None or liked is None:
            return jsonify({"status": "fail", "message": "Missing fields."}), 400

        liked_int = 1 if liked else 0
        conn = get_db(); cur = conn.cursor()
        cur.execute(
            """INSERT INTO feedback (username, course_id, liked)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE liked=%s, created_at=NOW()""",
            (username, int(course_id), liked_int, liked_int)
        )
        conn.commit(); cur.close(); conn.close()

        # Invalidate model so it retrains with new feedback signal
        if os.path.exists(MODEL_PATH):
            os.remove(MODEL_PATH)
            print(f"[FEEDBACK] Model cache cleared for {username}")

        return jsonify({"status": "success", "liked": liked})
    except Exception as e:
        print(f"[FEEDBACK] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/profile/load", methods=["POST"])
def profile_load():
    """Load saved profile fields for a user so the UI can pre-populate."""
    try:
        d = request.get_json(force=True)
        u = (d.get("username") or "").strip()
        if not u:
            return jsonify({"status": "fail"}), 400
        conn = get_db(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE username=%s", (u,))
        user = cur.fetchone(); cur.close(); conn.close()
        if not user:
            return jsonify({"status": "fail"}), 404
        # Return only profile fields, not password
        profile_fields = [
            "interest","career_goal","experience_years","known_tools",
            "preferred_language","budget","time_commitment","learning_style",
            "certification_needed","motivation","career_stage"
        ]
        profile = {f: user.get(f) for f in profile_fields}
        return jsonify({"status": "success", "profile": profile})
    except Exception as e:
        print(f"[PROFILE LOAD] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    return jsonify({"status": "logged_out"})


@app.route("/api/setup", methods=["POST"])
def setup():
    """One-time DB migration — run once after deploying."""
    conn = get_db(); cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id         INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            username   VARCHAR(80)  NOT NULL,
            course_id  INT UNSIGNED NOT NULL,
            liked      TINYINT(1)   NOT NULL DEFAULT 1,
            created_at TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uq_user_course (username, course_id),
            INDEX idx_username (username),
            INDEX idx_course   (course_id)
        ) ENGINE=InnoDB
    """)
    cols = [
        ("interest","VARCHAR(100)"),("career_goal","VARCHAR(100)"),
        ("experience_years","VARCHAR(10)"),("known_tools","VARCHAR(200)"),
        ("preferred_language","VARCHAR(50)"),("budget","VARCHAR(50)"),
        ("time_commitment","VARCHAR(50)"),("learning_style","VARCHAR(50)"),
        ("certification_needed","VARCHAR(10)"),("motivation","VARCHAR(100)"),
        ("career_stage","VARCHAR(50)"),
    ]
    added = []
    for col, dtype in cols:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {dtype}")
            added.append(col)
        except MySQLError:
            pass
    conn.commit(); cur.close(); conn.close()
    return jsonify({"status": "done", "columns_added": added})


@app.route("/api", methods=["GET","POST","OPTIONS"])
@app.route("/api/", methods=["GET","POST","OPTIONS"])
def api_root():
    """Catch-all for bare /api requests — returns available routes."""
    return jsonify({
        "status": "ok",
        "message": "Course Recommender API",
        "routes": [
            "POST /api/register",
            "POST /api/login",
            "POST /api/logout",
            "POST /api/profile",
            "POST /api/recommend",
            "POST /api/feedback",
            "POST /api/setup",
        ]
    })

if __name__ == "__main__":
    precompute_embeddings()
    app.run(debug=True, port=5000, use_reloader=False)