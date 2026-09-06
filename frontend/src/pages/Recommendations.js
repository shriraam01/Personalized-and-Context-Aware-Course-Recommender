import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { getRecommendations, submitFeedback } from "../api";
import "../App.css";

// ── Pure helpers (no hooks) ───────────────────────────────────────────────────
function levelClass(d) {
  if (!d) return "beginner";
  const k = d.toLowerCase();
  if (k === "intermediate" || k === "conversant") return "intermediate";
  if (k === "advanced")     return "advanced";
  return "beginner";
}

function levelPillClass(l) {
  if (!l) return "level-pill--beginner";
  const k = l.toLowerCase();
  if (k === "intermediate" || k === "conversant") return "level-pill--intermediate";
  if (k === "advanced")     return "level-pill--advanced";
  return "level-pill--beginner";
}

function fmtHours(h) {
  const num = Number(h);
  if (!num || isNaN(num)) return null;
  return num % 1 === 0 ? `${num}h` : `${num.toFixed(1)}h`;
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

  const courseId = course.course_id ?? null;

  const handleFeedback = (liked) => {
    if (sending || courseId === null || courseId === undefined) return;

    const isToggleOff = feedback === liked;
    const valueToSend = isToggleOff ? !liked : liked;

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

  const lvl      = levelClass(course.difficulty_level);
  const grad     = RANK_GRADIENTS[(rank - 1) % RANK_GRADIENTS.length];
  const url      = course.course_url || "https://www.coursera.org";
  const duration = fmtHours(course.estimated_duration_hours);
  const isFree   = String(course.is_free_to_audit).toLowerCase() === "true" ||
                    course.is_free_to_audit === 1 || course.is_free_to_audit === true;

  return (
    <div className="course-row">
      <div className="course-row-rank" style={{ background: grad }}>{rank}</div>

      <div className="course-row-body">
        <div className="course-row-top">
          <h3 className="course-row-title">{course.course_name}</h3>
          <ScoreRing score={course.final_score || 0} />
        </div>
        <div className="course-row-meta">
          <span className="tag tag--domain">{course.primary_domain || "General"}</span>
          <span className={`tag tag--${lvl}`}>{course.difficulty_level || "Beginner"}</span>
          {course.university && <span className="course-row-stat">🏫 {course.university}</span>}
          {course.course_rating ? <span className="course-row-stat">⭐ {course.course_rating}</span> : null}
          {duration && <span className="course-row-stat">⏱ {duration}</span>}
          {isFree
            ? <span className="free-badge">Free to audit</span>
            : <span className="course-row-stat">💳 Paid</span>
          }
        </div>
      </div>

      <div className="course-row-actions">
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
          View on Coursera
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

  const handleFeedback = useCallback((courseId, liked) => {
    return submitFeedback(courseId, liked).catch((e) => {
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
                  key={course.course_id ?? i}
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