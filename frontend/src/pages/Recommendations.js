import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getRecommendations, submitFeedback } from "../api";
import "../App.css";

// ── Pure helpers (no hooks) ───────────────────────────────────────────────────
function levelClass(d) {
  if (!d) return "beginner";
  const k = d.toLowerCase().split(" ")[0];
  if (k === "intermediate") return "intermediate";
  if (k === "advanced")     return "advanced";
  if (k === "all")          return "alllevels";
  return "beginner";
}

function levelPillClass(l) {
  if (l === "Intermediate") return "level-pill--intermediate";
  if (l === "Advanced")     return "level-pill--advanced";
  return "level-pill--beginner";
}

function levelLabel(d) {
  if (!d) return "Beginner";
  const k = d.toLowerCase().split(" ")[0];
  if (k === "intermediate") return "Intermediate";
  if (k === "advanced")     return "Advanced";
  if (k === "all")          return "All Levels";
  return "Beginner";
}

function fmt(n) {
  const num = Number(n);
  if (!num || isNaN(num)) return null;
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + "M";
  if (num >= 1_000)     return Math.round(num / 1_000) + "k";
  return String(num);
}

const RANK_GRADIENTS = [
  "linear-gradient(135deg,#f59e0b,#ef4444)",
  "linear-gradient(135deg,#6366f1,#8b5cf6)",
  "linear-gradient(135deg,#06b6d4,#6366f1)",
  "linear-gradient(135deg,#10b981,#06b6d4)",
  "linear-gradient(135deg,#8b5cf6,#ec4899)",
  "linear-gradient(135deg,#f97316,#f59e0b)",
];

// ── Score ring ────────────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const [animated, setAnimated] = useState(false);
  const pct    = Math.min(Math.round((score || 0) * 100), 100);
  const r      = 26;
  const circ   = 2 * Math.PI * r;
  const offset = animated ? circ - (pct / 100) * circ : circ;

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 200);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="score-ring-wrap">
      <svg width="68" height="68" viewBox="0 0 68 68">
        <circle cx="34" cy="34" r={r} fill="none" stroke="var(--border)" strokeWidth="5" />
        <circle
          cx="34" cy="34" r={r} fill="none" stroke="var(--indigo)" strokeWidth="5"
          strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={offset}
          transform="rotate(-90 34 34)"
          style={{ transition: "stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)" }}
        />
      </svg>
      <div className="score-ring-label">
        <span className="score-ring-num">{pct}</span>
        <span className="score-ring-pct">%</span>
      </div>
    </div>
  );
}

// ── Course row ────────────────────────────────────────────────────────────────
function CourseRow({ course, rank, onFeedback }) {
  const [feedback, setFeedback] = useState(null);  // null | true | false
  const [sending,  setSending]  = useState(false);
  const isMounted = useRef(true);

  useEffect(() => {
    isMounted.current = true;
    return () => { isMounted.current = false; };
  }, []);

  // Use course.id if available, else course_id, else index
  const courseId = course.id ?? course.course_id ?? null;

  const handleFeedback = (liked) => {
    // Guard: don't fire if already sending or no valid course id
    if (sending || courseId === null || courseId === undefined) return;

    // If clicking the same button again → toggle off (reset feedback)
    const isToggleOff = feedback === liked;
    const valueToSend = isToggleOff ? !liked : liked; // send opposite to "reset"

    setSending(true);
    onFeedback(courseId, valueToSend)
      .then(() => {
        if (isMounted.current) {
          setFeedback(isToggleOff ? null : liked);
        }
      })
      .catch((e) => {
        console.warn("Feedback failed (non-critical):", e.message);
      })
      .finally(() => {
        if (isMounted.current) setSending(false);
      });
  };

  const lvl  = levelClass(course.difficulty);
  const subs = fmt(course.num_subscribers);
  const revs = fmt(course.num_reviews);
  const grad = RANK_GRADIENTS[(rank - 1) % RANK_GRADIENTS.length];
  const url  = course.course_url || "https://www.udemy.com";

  return (
    <div className="course-row">
      <div className="course-row-rank" style={{ background: grad }}>{rank}</div>

      <div className="course-row-body">
        <div className="course-row-top">
          <h3 className="course-row-title">{course.title}</h3>
          <ScoreRing score={course.final_score || 0} />
        </div>
        <div className="course-row-meta">
          <span className="tag tag--domain">{course.domain || "General"}</span>
          <span className={`tag tag--${lvl}`}>{levelLabel(course.difficulty)}</span>
          {subs && <span className="course-row-stat">👥 {subs} students</span>}
          {revs && <span className="course-row-stat">⭐ {revs} reviews</span>}
          {Number(course.price) === 0
            ? <span className="free-badge">Free</span>
            : course.price
              ? <span className="course-row-stat">₹{course.price}</span>
              : null
          }
        </div>

      </div>

      <div className="course-row-actions">
        {/* Only show feedback buttons if we have a valid course ID */}
        {courseId !== null && courseId !== undefined && (
          <div className="feedback-btns">
            <button
              type="button"
              className={`feedback-btn${feedback === true ? " active-like" : ""}`}
              onClick={() => handleFeedback(true)}
              disabled={sending}
              title="Relevant to my needs"
            >👍</button>
            <button
              type="button"
              className={`feedback-btn${feedback === false ? " active-dislike" : ""}`}
              onClick={() => handleFeedback(false)}
              disabled={sending}
              title="Not relevant"
            >👎</button>
          </div>
        )}
        <button
          type="button"
          className="course-row-btn"
          onClick={() => window.open(url, "_blank", "noopener,noreferrer")}
        >
          View on Udemy
        </button>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function Recommendations() {
  const navigate  = useNavigate();
  const username  = localStorage.getItem("username");
  const [data,    setData]    = useState(null);
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!username) { navigate("/login"); return; }

    let cancelled = false;
    getRecommendations()
      .then((res) => {
        if (cancelled) return;
        if (res.data.status === "success" || res.data.courses) {
          setData(res.data);
        } else {
          setError(res.data.message || "Could not load recommendations.");
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err.response?.data?.message ||
          "Failed to reach the server. Is the backend running on port 5000?"
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [username, navigate]);

  // Stable feedback handler — does NOT cause re-renders on its own
  const handleFeedback = useCallback((courseId, liked) => {
    return submitFeedback(courseId, liked).catch((e) => {
      // Swallow silently — feedback failure is non-critical
      console.warn("Feedback API error:", e.message);
    });
  }, []);

  if (loading) return (
    <div className="page-outer">
      <div className="page-card">
        <div className="loading-wrap">
          <div className="loading-icon" />
          <p>Finding your best courses…</p>
        </div>
      </div>
    </div>
  );

  if (error) return (
    <div className="page-outer">
      <div className="page-card">
        <div className="alert alert--error" style={{ marginBottom: 24 }}>
          <span>⚠</span> {error}
        </div>
        <button className="btn btn--ghost" onClick={() => navigate("/profile")}>
          ← Back to Profile
        </button>
      </div>
    </div>
  );

  const courses = data?.courses || [];
  const level   = data?.level   || "Beginner";
  const rated   = courses.filter(c => c.final_score > 0).length;

  return (
    <div className="page-outer" style={{ alignItems: "flex-start", paddingTop: 36 }}>
      <div className="page-card page-card--full">

        <div className="rec-header">
          <div className="rec-header-top">
            <button className="back-btn" onClick={() => navigate("/profile")}>
              ← Edit Profile
            </button>
          </div>
          <h1>Your Recommended Courses</h1>
          <p className="subtitle">
            Ranked by relevance to your profile — use 👍 / 👎 to improve future recommendations
          </p>
        </div>

        <div className="stats-strip">
          <div className="stat-cell">
            <span className="stat-label">Your level</span>
            <span className={`level-pill ${levelPillClass(level)}`}>{level}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">Courses found</span>
            <span className="stat-value">{courses.length}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">Ranked by</span>
            <span className="stat-value" style={{ fontSize: ".9rem" }}>Relevance</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">Rate to improve</span>
            <span className="stat-value" style={{ fontSize: ".9rem" }}>👍 / 👎</span>
          </div>
        </div>

        {courses.length > 0 ? (
          <>
            <p className="feedback-hint">
              Rate each course to personalise your future recommendations
            </p>
            <div className="courses-list">
              {courses.map((course, i) => (
                <CourseRow
                  key={course.id ?? course.course_id ?? i}
                  course={course}
                  rank={i + 1}
                  onFeedback={handleFeedback}
                />
              ))}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <p>No courses matched your profile. Try updating your interests.</p>
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => navigate("/profile")}
              style={{ maxWidth: 240, margin: "0 auto" }}
            >
              Update Profile
            </button>
          </div>
        )}
      </div>
    </div>
  );
}