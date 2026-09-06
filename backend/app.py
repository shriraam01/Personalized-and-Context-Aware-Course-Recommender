"""
Course Recommender - Flask Backend
====================================
Rebuilt for the Coursera dataset / new personalization+context schema.
All 4 ML improvements preserved:
  1. Feedback system  — thumbs up/down stored, XGBoost trained on real signals
  2. Collaborative filtering — similar users boost shared liked courses
  3. Sentence Transformers — semantic similarity (falls back to TF-IDF)
  4. Profile-to-field mapping — budget/time/certification matched directly to course fields
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

def build_corpus(df):
    """
    Build the semantic-embedding corpus from the new Coursera fields.
    Used both at startup (precompute) and per-request (recommend) — the
    two MUST produce identical text for a given row so the embedding
    cache actually hits.
    """
    names = df["course_name"].astype(str).tolist()
    descs = df["course_description"].astype(str).tolist()
    skills = df["skills"].astype(str).tolist()
    pdom  = df["primary_domain"].astype(str).tolist()
    sdom  = df["secondary_domain"].astype(str).tolist()
    diffs = df["difficulty_level"].astype(str).tolist()
    corpus = []
    for n, d, sk, pd_, sd, dl in zip(names, descs, skills, pdom, sdom, diffs):
        corpus.append(f"{n} {n} {d[:400]} {sk} {pd_} {sd} {dl}")
    return corpus

def precompute_embeddings():
    """Called once at startup — fetches all courses and pre-encodes them."""
    if not USE_SEMANTIC:
        return
    try:
        print("[STARTUP] Pre-computing course embeddings...")
        conn = get_db()
        cur  = conn.cursor(dictionary=True)
        cur.execute("""SELECT course_name, course_description, skills,
                              primary_domain, secondary_domain, difficulty_level
                       FROM courses""")
        rows = cur.fetchall()
        cur.close(); conn.close()
        if not rows:
            print("[STARTUP] No courses found — skipping precompute.")
            return
        df = pd.DataFrame(rows).fillna("")
        corpus = build_corpus(df)
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

def to_float(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def jaccard_sim(a, b):
    s1, s2 = set(a.lower().split()), set(b.lower().split())
    u = s1 | s2
    return len(s1 & s2) / len(u) if u else 0.0

def get_col(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).values.astype(float)
    return np.zeros(len(df))

def normalize_domain_text(s):
    return str(s).replace("-", " ").replace("_", " ").lower()

# ── Keyword expansion ─────────────────────────────────────────────────────────
# Keyed to the "interests" dropdown values used in the Profile form.
EXPAND = {
    "data science":                     "pandas numpy statistics visualization sql data analysis",
    "computer science":                 "algorithms data structures programming software",
    "business":                         "strategy management finance marketing entrepreneurship",
    "arts & humanities":                "history philosophy literature writing culture",
    "health":                           "medicine nutrition anatomy public health wellness",
    "personal development":             "productivity leadership communication mindfulness",
    "language learning":                "vocabulary grammar speaking fluency conversation",
    "physical science & engineering":   "physics mechanics electronics engineering design",
    "social sciences":                  "psychology sociology economics research behavior",
    "music & art":                      "design creativity drawing composition visual art",
}
# Free-text career_goal / target_job_role substring expansion.
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
    "business analyst":          "excel sql reporting stakeholder analysis",
    "product manager":           "roadmap stakeholder agile user research",
}

def expand_keywords(interests, goal, difficulty):
    out = []
    il = interests.lower()
    for k, v in EXPAND.items():
        if k in il:
            out.append(v)
    gl = goal.lower()
    for k, v in GOAL_EXPAND.items():
        if k in gl:
            out.append(v)
    out.append(difficulty.lower())
    return " ".join(out)

# ── Improvement 4: Profile-to-field mapping ───────────────────────────────────
def budget_score(user_budget, is_free_to_audit, budget_tier):
    ub = (user_budget or "").lower()
    free_audit = bool(is_free_to_audit)
    if "free only" in ub:
        return 1.0 if free_audit else 0.15
    if "free to audit" in ub:
        return 1.0 if free_audit else 0.5
    return 1.0  # "Paid - any budget" → no constraint

def time_score(available_hours_per_week, estimated_duration_hours):
    weekly = to_float(available_hours_per_week, 5.0) or 5.0
    if weekly <= 0:
        weekly = 5.0
    ideal = weekly * 4.0  # rough 1-month horizon
    dur = to_float(estimated_duration_hours, 0.0) or 0.0
    if dur <= 0:
        return 0.5
    diff = abs(dur - ideal)
    return max(0.0, 1.0 - diff / (ideal + 1e-9))

def cert_score(certification_needed, certification_offered):
    needed = str(certification_needed).lower() in ("yes", "true", "1")
    if needed:
        return 1.0 if bool(certification_offered) else 0.3
    return 1.0

def mode_score(user_mode, course_learning_mode, course_format):
    um = (user_mode or "").lower().strip()
    if not um or "no preference" in um:
        return 0.7
    text = f"{course_learning_mode} {course_format}".lower()
    if "self-paced" in um and "self-paced" in text:
        return 1.0
    if "instructor" in um and ("instructor" in text or "scheduled" in text or "cohort" in text):
        return 1.0
    if "hands-on" in um and ("hands-on" in text or "lab" in text or "guided project" in text):
        return 1.0
    if "video" in um and "video" in text:
        return 1.0
    words = [w for w in um.replace("/", " ").split() if len(w) > 3]
    return 0.6 if any(w in text for w in words) else 0.3

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
        return [], "Beginner"

    df = pd.DataFrame(rows).reset_index(drop=True)
    df.fillna("", inplace=True)
    n = len(df)
    print(f"[REC] {n} courses")

    # Numeric course fields (new schema)
    rating   = get_col(df, "course_rating")
    duration = get_col(df, "estimated_duration_hours")
    rating_norm = np.clip(rating / 5.0, 0, 1)
    dur_norm    = duration / (duration.max() + 1e-9)

    is_free_to_audit       = df["is_free_to_audit"].tolist()
    certification_offered  = df["certification_offered"].tolist()
    budget_tier            = df["budget_tier"].astype(str).tolist()
    time_commitment_tier   = df["time_commitment_tier"].astype(str).tolist()
    learning_mode_course   = df["learning_mode"].astype(str).tolist()
    course_format          = df["course_format"].astype(str).tolist()
    primary_domain         = df["primary_domain"].astype(str).tolist()
    secondary_domain       = df["secondary_domain"].astype(str).tolist()
    difficulty_level       = df["difficulty_level"].astype(str).tolist()

    # User fields (new schema)
    interests           = safe(user.get("interests"))
    career_goal         = safe(user.get("career_goal"))
    existing_skills      = safe(user.get("existing_skills"))
    desired_skills       = safe(user.get("desired_skills"))
    target_job_role      = safe(user.get("target_job_role"))
    target_industry      = safe(user.get("target_industry"))
    preferred_difficulty = safe(user.get("preferred_difficulty")) or "Intermediate"
    learning_objective   = safe(user.get("learning_objective"))
    content_preference   = safe(user.get("content_preference"))
    teaching_style       = safe(user.get("teaching_style"))
    user_budget          = safe(user.get("budget"))
    available_hours      = user.get("available_hours_per_week")
    user_learning_mode   = safe(user.get("learning_mode"))
    certification_needed = safe(user.get("certification_needed"))

    # Text corpus (courses) — shared builder so the embedding cache can hit
    corpus = build_corpus(df)

    core = (interests + " " + career_goal + " " + desired_skills + " " +
            existing_skills + " " + target_job_role + " " + target_industry + " ") * 3
    ctx  = " ".join([
        learning_objective, content_preference, teaching_style,
        preferred_difficulty,
        expand_keywords(interests, career_goal + " " + target_job_role, preferred_difficulty)
    ])
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

    # Domain boost — word-overlap between interests/target_industry and the
    # course's primary/secondary domain (domain slugs are hyphenated, so
    # normalize before comparing).
    interest_words = set(
        w for w in (interests + " " + target_industry).lower().replace("&", " ").split()
        if len(w) > 2
    )
    dom_text = [
        normalize_domain_text(pd_) + " " + normalize_domain_text(sd)
        for pd_, sd in zip(primary_domain, secondary_domain)
    ]
    dom_boost = np.array([
        1.0 if interest_words and all(w in dt for w in interest_words)
        else 0.5 if any(w in dt for w in interest_words)
        else 0.0
        for dt in dom_text
    ])

    # Difficulty match
    lmap  = {"beginner": 1, "intermediate": 2, "advanced": 3, "mixed": 2}
    u_lvl = lmap.get(preferred_difficulty.lower(), 2)
    diff  = np.array([
        1.0 / (1.0 + abs(u_lvl - lmap.get(str(s).split()[0].lower(), 2)))
        if str(s).strip() else 0.5
        for s in difficulty_level
    ])

    # Improvement 4: direct field mapping (Coursera fields)
    budget_sc = np.array([
        budget_score(user_budget, fa, bt)
        for fa, bt in zip(is_free_to_audit, budget_tier)
    ])
    time_sc = np.array([time_score(available_hours, d) for d in duration])
    cert_sc = np.array([
        cert_score(certification_needed, co) for co in certification_offered
    ])
    mode_sc = np.array([
        mode_score(user_learning_mode, lm, cf)
        for lm, cf in zip(learning_mode_course, course_format)
    ])

    # Feature matrix (10 features)
    X_raw = np.column_stack([
        cos, jac, rating_norm, diff, dom_boost,
        dur_norm, budget_sc, time_sc, cert_sc, mode_sc
    ])
    scaler = MinMaxScaler()
    X      = scaler.fit_transform(X_raw)

    # Proxy target
    y_proxy = (cos * 0.30 + jac * 0.05 + dom_boost * 0.25 + diff * 0.15 +
               rating_norm * 0.08 + budget_sc * 0.08 + time_sc * 0.05 +
               cert_sc * 0.02 + mode_sc * 0.02)

    # Improvement 1: only blend feedback when we have ENOUGH signals (min 15)
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

    # Profile-driven scoring — cos and dom_boost dominate
    final = (cos       * 0.35 +
             dom_boost * 0.25 +
             diff      * 0.15 +
             ml_sc     * 0.10 +
             budget_sc * 0.05 +
             jac       * 0.03 +
             time_sc   * 0.03 +
             rating_norm * 0.02 +
             cert_sc   * 0.01 +
             mode_sc   * 0.01)
    df["final_score"] = final
    df["ml_score"]    = np.round(ml_sc * 100, 1)
    df["cos_score"]   = np.round(cos * 100, 1)

    top5_idx = np.argsort(final)[::-1][:5]
    print("[ML SCORES] Top 5 XGBoost predictions:")
    for i, idx in enumerate(top5_idx):
        print(f"  #{i+1} ml={ml_sc[idx]:.4f} ({ml_sc[idx]*100:.1f}%)  "
              f"cos={cos[idx]:.4f}  final={final[idx]:.4f}  "
              f"title={str(df.iloc[idx]['course_name'])[:50]}")

    # Improvement 1+2: post-scoring feedback/collaborative boost
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

    KEEP_COLS = [
        "course_id", "course_name", "university", "difficulty_level", "course_rating",
        "skills", "course_format", "budget_tier", "is_free_to_audit",
        "certification_offered", "estimated_duration_hours", "time_commitment_tier",
        "learning_mode", "primary_domain", "secondary_domain", "course_url",
        "final_score", "rank"
    ]
    display_cols = [c for c in KEEP_COLS if c in top_n.columns]
    result = top_n[display_cols].copy()

    top_score = float(result["final_score"].iloc[0]) if len(result) > 0 else 0
    print(f"[REC] Done: n={n_results}, top_score={top_score:.4f}")
    return result.to_dict("records"), preferred_difficulty


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


# Personalization + context fields, exactly matching Schema.sql `users` table.
PROFILE_FIELDS = [
    "interests", "career_goal",
    "education_level", "degree_field", "current_year", "academic_performance",
    "existing_skills", "experience_level", "experience_years",
    "desired_skills", "target_job_role", "target_industry",
    "preferred_difficulty", "preferred_language",
    "learning_objective", "content_preference", "teaching_style",
    "budget", "available_hours_per_week", "completion_time",
    "learning_mode", "certification_needed",
]

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

        cert_val = 1 if str(d.get("certification_needed", "")).strip().lower() == "yes" else 0

        values = {
            "interests":                d.get("interests"),
            "career_goal":              d.get("career_goal"),
            "education_level":          d.get("education_level"),
            "degree_field":             d.get("degree_field"),
            "current_year":             d.get("current_year"),
            "academic_performance":     to_float(d.get("academic_performance")),
            "existing_skills":          d.get("existing_skills"),
            "experience_level":         d.get("experience_level"),
            "experience_years":         to_float(d.get("experience_years")),
            "desired_skills":           d.get("desired_skills"),
            "target_job_role":          d.get("target_job_role"),
            "target_industry":          d.get("target_industry"),
            "preferred_difficulty":     d.get("preferred_difficulty"),
            "preferred_language":       d.get("preferred_language"),
            "learning_objective":       d.get("learning_objective"),
            "content_preference":       d.get("content_preference"),
            "teaching_style":           d.get("teaching_style"),
            "budget":                   d.get("budget"),
            "available_hours_per_week": to_float(d.get("available_hours_per_week")),
            "completion_time":          d.get("completion_time"),
            "learning_mode":            d.get("learning_mode"),
            "certification_needed":     cert_val,
        }

        cur = conn.cursor()
        set_clause = ", ".join(f"{col}=%s" for col in values.keys())
        cur.execute(
            f"UPDATE users SET {set_clause} WHERE username=%s",
            list(values.values()) + [u]
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

        profile_out = {}
        for f in PROFILE_FIELDS:
            v = user.get(f)
            if f == "certification_needed":
                v = "Yes" if v else "No"
            profile_out[f] = v
        return jsonify({"status": "success", "profile": profile_out})
    except Exception as e:
        print(f"[PROFILE LOAD] {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/logout", methods=["POST"])
def logout():
    return jsonify({"status": "logged_out"})


@app.route("/api/setup", methods=["POST"])
def setup():
    """
    One-time DB migration — run once after deploying.
    users/courses are already fully defined by Schema.sql; this route only
    ensures the feedback table exists (it references courses.course_id).
    """
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
            INDEX idx_course   (course_id),
            CONSTRAINT fk_feedback_course FOREIGN KEY (course_id)
                REFERENCES courses(course_id) ON DELETE CASCADE
        ) ENGINE=InnoDB
    """)
    conn.commit(); cur.close(); conn.close()
    return jsonify({"status": "done"})


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
            "POST /api/profile/load",
            "POST /api/recommend",
            "POST /api/feedback",
            "POST /api/setup",
        ]
    })

if __name__ == "__main__":
    precompute_embeddings()
    app.run(debug=True, port=5000, use_reloader=False)