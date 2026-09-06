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

# ── Sentence Transformers ─────────────────────────────────────────────────────
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
        cur.execute("SELECT course_name, course_description, skills FROM courses")
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            print("[STARTUP] No courses found — skipping precompute.")
            return
        corpus = [build_course_text(r) for r in rows]
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
    """Fallback difficulty inference from years of experience, used only
    when the user has not picked an explicit preferred_difficulty."""
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

def get_numeric_col(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).values.astype(float)
    return np.zeros(len(df))

def build_course_text(row):
    """Corpus text per course for embeddings — title weighted x2, plus the
    real description and skills text (the whole reason Coursera was chosen
    over Udemy: there's actual content here, not just a title)."""
    name  = safe(row.get("course_name"))
    desc  = safe(row.get("course_description"))
    skl   = safe(row.get("skills"))
    return f"{name} {name} {desc} {skl}"

def build_url(row):
    """Coursera URLs in this dataset are real, full course links — use
    directly rather than constructing a search URL."""
    url = str(row.get("course_url", "")).strip()
    if url.startswith("http"):
        return url
    name = str(row.get("course_name", "")).strip()
    if name:
        import urllib.parse
        query = urllib.parse.quote_plus(name)
        return f"https://www.coursera.org/search?query={query}"
    return "https://www.coursera.org"

# ── Domain vocabulary mapping ─────────────────────────────────────────────────
# Maps the fixed dropdown labels used in Profile.js to the REAL primary_domain
# / secondary_domain tag vocabulary found in courses.csv (117 unique tags,
# extracted from the dataset's own Skills field — see enrichment pipeline).
# This is a documented bridging table, not a guess: every tag on the right
# was confirmed present in the dataset before being used here.

INTEREST_DOMAIN_MAP = {
    "Data Science":                    ["data-science", "data-analysis"],
    "Machine Learning":                ["machine-learning"],
    "Artificial Intelligence":         ["machine-learning", "computer-science"],
    "Software Development":            ["software-development", "computer-science"],
    "Web & Mobile Development":        ["mobile-and-web-development"],
    "Cyber Security":                  ["computer-security-and-networks"],
    "Cloud Computing":                 ["cloud-computing"],
    "IT & Networking":                 ["information-technology"],
    "Business Strategy":               ["business-strategy", "business-essentials"],
    "Leadership & Management":         ["leadership-and-management"],
    "Data Analysis & Statistics":      ["data-analysis", "probability-and-statistics"],
    "Public Health":                   ["public-health", "patient-care"],
    "Life Sciences":                   ["life-sciences"],
    "Physical Sciences & Engineering": ["physical-science-and-engineering",
                                        "mechanical-engineering", "electrical-engineering"],
    "Arts & Humanities":               ["arts-and-humanities", "music-and-art"],
    "Language Learning":               ["language-learning", "learning-english"],
    "Personal Development":            ["personal-development"],
    "Environmental Science":           ["environmental-science-and-sustainability"],
    "Design & Product":                ["design-and-product"],
    "Social Sciences":                 ["social-sciences", "governance-and-society"],
}

JOBROLE_DOMAIN_MAP = {
    "Data Scientist":              ["data-science", "machine-learning"],
    "Machine Learning Engineer":   ["machine-learning", "software-development"],
    "Software Engineer":           ["software-development", "computer-science"],
    "Web/Mobile Developer":        ["mobile-and-web-development"],
    "Cyber Security Specialist":   ["computer-security-and-networks"],
    "Cloud Engineer":              ["cloud-computing", "information-technology"],
    "Business Analyst":            ["business-essentials", "data-analysis"],
    "Product Manager":             ["design-and-product", "business-strategy"],
    "Healthcare Professional":     ["public-health", "life-sciences", "patient-care"],
    "Researcher / Academic":       ["research-methods", "physical-science-and-engineering"],
    "Manager / Team Lead":         ["leadership-and-management"],
    "Career Switcher / Exploring": [],
}

INDUSTRY_DOMAIN_MAP = {
    "Technology":                    ["information-technology", "software-development", "computer-science"],
    "Finance":                       ["business-essentials", "business-strategy"],
    "Healthcare":                    ["public-health", "life-sciences", "patient-care"],
    "Education":                     ["personal-development", "language-learning"],
    "Government / Public Sector":    ["governance-and-society"],
    "Media, Arts & Entertainment":   ["arts-and-humanities", "music-and-art"],
    "Manufacturing & Engineering":   ["mechanical-engineering", "electrical-engineering",
                                       "physical-science-and-engineering"],
    "Environmental / Sustainability":["environmental-science-and-sustainability"],
    "Other / Not sure":              [],
}

def user_domain_tags(user):
    tags = set()
    tags.update(INTEREST_DOMAIN_MAP.get(safe(user.get("interests")), []))
    tags.update(JOBROLE_DOMAIN_MAP.get(safe(user.get("target_job_role")), []))
    tags.update(INDUSTRY_DOMAIN_MAP.get(safe(user.get("target_industry")), []))
    return tags

# ── Profile-to-field mapping (context-aware scoring) ──────────────────────────
COMPLETION_WEEKS_MAP = {
    "Within a week":        1.0,
    "Within a month":       4.0,
    "1-3 months":          10.0,
    "No specific deadline":26.0,
}

def budget_score(user_budget, is_free_to_audit):
    """budget_tier on the course side collapses to a binary is_free_to_audit
    flag; only 'Free courses only' users are actually constrained by it."""
    if user_budget == "Free courses only":
        return 1.0 if is_free_to_audit else 0.15
    return 1.0

def time_score(hours_per_week, completion_time, duration_hours):
    weeks = COMPLETION_WEEKS_MAP.get(completion_time, 8.0)
    total_available = max(float(hours_per_week or 0), 0.0) * weeks
    if total_available <= 0 or duration_hours <= 0:
        return 0.5
    diff = abs(duration_hours - total_available)
    return max(0.0, 1.0 - diff / (total_available + 1e-9))

def mode_score(user_mode, course_mode):
    if user_mode in (None, "", "No preference"):
        return 1.0
    key = "Hands-on" if "Hands-on" in user_mode else "Video"
    return 1.0 if key.lower() in str(course_mode).lower() else 0.3

def cert_score(cert_needed, cert_offered):
    """certification_offered is constant True across this dataset, so this
    will rarely discriminate between courses — kept for schema completeness,
    weighted minimally in the final score."""
    if cert_needed:
        return 1.0 if cert_offered else 0.3
    return 1.0

def difficulty_score(user_level_label, course_level_label):
    lmap = {"Beginner": 1, "Intermediate": 2, "Conversant": 2,
            "Advanced": 3, "Not Calibrated": 2}
    u = lmap.get(user_level_label, 2)
    c = lmap.get(str(course_level_label).strip(), 2)
    return 1.0 / (1.0 + abs(u - c))

# ── Feedback helpers (collaborative filtering + XGBoost training signal) ─────
def get_feedback_boost(username, course_ids):
    if not course_ids:
        return {}
    try:
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        ph   = ",".join(["%s"] * len(course_ids))

        cur.execute(
            f"SELECT course_id, liked FROM feedback WHERE username=%s AND course_id IN ({ph})",
            [username] + list(course_ids)
        )
        rows  = cur.fetchall()
        boost = {r["course_id"]: (0.08 if r["liked"] else -0.06) for r in rows}

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
        return [], "Beginner"

    df = pd.DataFrame(rows).reset_index(drop=True)
    df.fillna("", inplace=True)
    n = len(df)
    print(f"[REC] {n} courses")

    # Numeric course-side signals
    rating   = get_numeric_col(df, "course_rating")
    duration = get_numeric_col(df, "estimated_duration_hours")
    is_free  = df["is_free_to_audit"].astype(str).str.lower().isin(["1", "true"]).values
    cert_off = df["certification_offered"].astype(str).str.lower().isin(["1", "true"]).values

    rating_norm   = np.clip(rating / 5.0, 0, 1)
    duration_norm = duration / (duration.max() + 1e-9)

    # User fields
    preferred_difficulty = safe(user.get("preferred_difficulty"))
    if preferred_difficulty in ("", "Any"):
        preferred_difficulty = infer_level(user.get("experience_years", 0))

    interests      = safe(user.get("interests"))
    desired_skills = safe(user.get("desired_skills"))
    existing_skills= safe(user.get("existing_skills"))
    job_role       = safe(user.get("target_job_role"))
    industry       = safe(user.get("target_industry"))
    objective      = safe(user.get("learning_objective"))
    budget         = safe(user.get("budget"))
    hours_per_week = user.get("available_hours_per_week") or 0
    completion_time= safe(user.get("completion_time"))
    learning_mode  = safe(user.get("learning_mode"))
    cert_needed    = str(user.get("certification_needed")).lower() in ("1", "true", "yes")

    # Text corpus for embeddings
    course_corpus = [build_course_text(r) for r in rows]
    user_text = " ".join([
        (interests + " ") * 3,
        (desired_skills + " ") * 2,
        (job_role + " ") * 2,
        industry, objective, existing_skills, preferred_difficulty,
    ])

    # Similarity
    if USE_SEMANTIC:
        print("[REC] Semantic similarity (cached)...")
        course_emb = get_course_embeddings(course_corpus)
        user_emb   = _ST.encode([user_text], show_progress_bar=False,
                                normalize_embeddings=True)
        cos = cosine_similarity(user_emb, course_emb).flatten()
    else:
        print("[REC] TF-IDF similarity...")
        tfidf  = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        matrix = tfidf.fit_transform(course_corpus)
        cos    = cosine_similarity(tfidf.transform([user_text]), matrix).flatten()

    jac = np.array([jaccard_sim(user_text, c) for c in course_corpus])

    # Domain boost — matched against real primary/secondary_domain tags
    tags = user_domain_tags(user)
    primary_domains   = df["primary_domain"].astype(str).tolist()
    secondary_domains = df["secondary_domain"].astype(str).tolist()
    dom_boost = np.array([
        1.0 if pd_ in tags else 0.6 if sd_ in tags else 0.0
        for pd_, sd_ in zip(primary_domains, secondary_domains)
    ])

    # Difficulty
    diff = np.array([
        difficulty_score(preferred_difficulty, lvl)
        for lvl in df["difficulty_level"].astype(str).tolist()
    ])

    # Context-aware field scores
    budget_sc = np.array([budget_score(budget, f) for f in is_free])
    time_sc   = np.array([time_score(hours_per_week, completion_time, d) for d in duration])
    mode_sc   = np.array([mode_score(learning_mode, m) for m in df["learning_mode"].tolist()])
    cert_sc   = np.array([cert_score(cert_needed, c) for c in cert_off])

    # Feature matrix for XGBoost (10 features)
    X_raw = np.column_stack([
        cos, jac, dom_boost, diff,
        budget_sc, time_sc, mode_sc, cert_sc,
        rating_norm, duration_norm
    ])
    scaler = MinMaxScaler()
    X = scaler.fit_transform(X_raw)

    # Proxy target
    y_proxy = (cos * 0.30 + dom_boost * 0.25 + diff * 0.15 + budget_sc * 0.10 +
               time_sc * 0.08 + mode_sc * 0.05 + rating_norm * 0.05 + cert_sc * 0.02)

    # Feedback blending — only once enough real signals exist
    fb_rows = get_feedback_for_training(username)
    MIN_FEEDBACK_FOR_TRAINING = 15
    if fb_rows and len(fb_rows) >= MIN_FEEDBACK_FOR_TRAINING:
        print(f"[REC] Blending {len(fb_rows)} feedback signals into training")
        fb_map     = {r["course_id"]: (1.0 if r["liked"] else 0.0) for r in fb_rows}
        cids       = df["course_id"].values
        y_feedback = np.array([fb_map.get(int(c), -1.0) for c in cids])
        has_fb     = y_feedback >= 0
        y_final    = y_proxy.copy()
        y_final[has_fb] = y_proxy[has_fb] * 0.70 + y_feedback[has_fb] * 0.30
    else:
        if fb_rows:
            print(f"[REC] Only {len(fb_rows)} feedback signals — need {MIN_FEEDBACK_FOR_TRAINING} to train. Using proxy only.")
        y_final = y_proxy

    model = get_model(X, y_final)
    ml_sc = np.clip(model.predict(X), 0, 1)

    # Final weighted score (sums to 1.0)
    final = (cos       * 0.32 +
             dom_boost * 0.25 +
             diff      * 0.15 +
             ml_sc     * 0.10 +
             budget_sc * 0.06 +
             time_sc   * 0.05 +
             mode_sc   * 0.03 +
             rating_norm * 0.02 +
             cert_sc   * 0.01 +
             jac       * 0.01)
    df["final_score"] = final

    top5_idx = np.argsort(final)[::-1][:5]
    print("[ML SCORES] Top 5 predictions:")
    for i, idx in enumerate(top5_idx):
        print(f"  #{i+1} ml={ml_sc[idx]:.4f}  cos={cos[idx]:.4f}  "
              f"final={final[idx]:.4f}  name={df.iloc[idx]['course_name'][:50]}")

    # Post-scoring feedback / collaborative-filtering boost
    fb_boost = get_feedback_boost(username, df["course_id"].tolist())
    if fb_boost:
        print(f"[REC] Feedback boost on {len(fb_boost)} courses")
        for idx, row in df.iterrows():
            cid = row.get("course_id")
            if cid in fb_boost:
                df.at[idx, "final_score"] = min(1.0, df.at[idx, "final_score"] + fb_boost[cid])

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

    KEEP_COLS = ["course_id", "course_name", "university", "difficulty_level",
                 "course_rating", "primary_domain", "secondary_domain",
                 "budget_tier", "is_free_to_audit", "estimated_duration_hours",
                 "time_commitment_tier", "learning_mode", "final_score", "rank"]
    display_cols = [c for c in KEEP_COLS if c in top_n.columns]
    result = top_n[display_cols].copy()
    result["course_url"] = top_n.apply(build_url, axis=1)

    top_score = float(result["final_score"].iloc[0]) if len(result) > 0 else 0
    print(f"[REC] Done: n={n_results}, top_score={top_score:.4f}")
    return result.to_dict("records"), preferred_difficulty


# ── Value conversion maps (frontend select labels -> DB storage types) ───────
ACADEMIC_PERFORMANCE_MAP = {
    "Below 60%": 55.0, "60% - 75%": 67.5, "75% - 90%": 82.5,
    "90%+": 95.0, "Prefer not to say": None,
}
HOURS_PER_WEEK_MAP = {
    "1-2 hrs/week": 2.0, "3-5 hrs/week": 5.0,
    "5-10 hrs/week": 10.0, "10+ hrs/week": 20.0,
}

def to_bool_int(v):
    return 1 if str(v).strip().lower() in ("1", "true", "yes") else 0

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

        academic_performance = ACADEMIC_PERFORMANCE_MAP.get(
            d.get("academic_performance"), None)
        hours_per_week = HOURS_PER_WEEK_MAP.get(
            d.get("available_hours_per_week"), 5.0)
        cert_needed = to_bool_int(d.get("certification_needed"))

        cur = conn.cursor()
        cur.execute(
            """UPDATE users SET
                 interests=%s, career_goal=%s,
                 education_level=%s, degree_field=%s, current_year=%s,
                 academic_performance=%s,
                 existing_skills=%s, experience_level=%s, experience_years=%s,
                 desired_skills=%s, target_job_role=%s, target_industry=%s,
                 preferred_difficulty=%s, preferred_language=%s,
                 learning_objective=%s, content_preference=%s, teaching_style=%s,
                 budget=%s, available_hours_per_week=%s, completion_time=%s,
                 learning_mode=%s, certification_needed=%s
               WHERE username=%s""",
            (d.get("interests"), d.get("career_goal"),
             d.get("education_level"), d.get("degree_field"), d.get("current_year"),
             academic_performance,
             d.get("existing_skills"), d.get("experience_level"), d.get("experience_years"),
             d.get("desired_skills"), d.get("target_job_role"), d.get("target_industry"),
             d.get("preferred_difficulty"), d.get("preferred_language"),
             d.get("learning_objective"), d.get("content_preference"), d.get("teaching_style"),
             d.get("budget"), hours_per_week, d.get("completion_time"),
             d.get("learning_mode"), cert_needed,
             u)
        )
        conn.commit(); cur.close(); conn.close()

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
        if not user.get("interests"):
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
        profile_fields = [
            "interests", "career_goal",
            "education_level", "degree_field", "current_year", "academic_performance",
            "existing_skills", "experience_level", "experience_years",
            "desired_skills", "target_job_role", "target_industry",
            "preferred_difficulty", "preferred_language",
            "learning_objective", "content_preference", "teaching_style",
            "budget", "available_hours_per_week", "completion_time",
            "learning_mode", "certification_needed",
        ]
        profile = {f: user.get(f) for f in profile_fields}
        return jsonify({"status": "success", "profile": profile})
    except Exception as e:
        print(f"[PROFILE LOAD] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    return jsonify({"status": "logged_out"})


@app.route("/api", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/", methods=["GET", "POST", "OPTIONS"])
def api_root():
    return jsonify({
        "status": "ok",
        "message": "Course Recommender API",
        "routes": [
            "POST /api/register", "POST /api/login", "POST /api/logout",
            "POST /api/profile", "POST /api/profile/load",
            "POST /api/recommend", "POST /api/feedback",
        ]
    })

if __name__ == "__main__":
    precompute_embeddings()
    app.run(debug=True, port=5000, use_reloader=False)