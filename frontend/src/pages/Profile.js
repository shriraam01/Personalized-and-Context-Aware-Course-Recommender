import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitProfile, logoutUser } from "../api";
import API from "../api";
import "../App.css";

const SECTIONS = [
  {
    heading: "About You",
    icon: "👤",
    fields: [
      { name: "interest",          label: "Area of Interest",        icon: "🎯", options: ["Data Science","Machine Learning","Artificial Intelligence","Web Development","Mobile Development","Cyber Security","Cloud Computing","DevOps","Blockchain"] },
      { name: "career_goal",       label: "Career Goal",             icon: "🚀", options: ["Data Scientist","Machine Learning Engineer","Software Engineer","Web Developer","Mobile App Developer","Cyber Security Specialist","Cloud Engineer","AI Researcher","DevOps Engineer","Blockchain Developer"] },
      { name: "experience_years",  label: "Years of Experience",     icon: "📅", options: [{value:"0",label:"0 — Complete beginner"},{value:"1",label:"1 year"},{value:"2",label:"2 years"},{value:"3",label:"3 years"},{value:"5",label:"5+ years"}] },
      { name: "known_tools",       label: "Primary Tool / Language", icon: "🛠", options: ["Python","JavaScript","Java","C++","SQL","TensorFlow","PyTorch","Docker","Kubernetes","React","Node.js"] },
      { name: "preferred_language",label: "Course Language",         icon: "🌐", options: ["English","Hindi","French","Spanish","German"] },
      { name: "career_stage",      label: "Career Stage",            icon: "🧭", options: ["Student","Entry Level","Mid Level","Senior Professional","Career Switcher"] },
    ],
  },
  {
    heading: "Your Preferences",
    icon: "⚙️",
    fields: [
      { name: "budget",               label: "Budget",                icon: "💰", options: ["Free Only","Under ₹1,000","₹1,000 – ₹5,000","₹5,000+","No limit"] },
      { name: "time_commitment",      label: "Weekly Time Available", icon: "⏱", options: ["1 – 2 hours / week","3 – 5 hours / week","5 – 10 hours / week","10+ hours / week"] },
      { name: "learning_style",       label: "Learning Style",        icon: "📚", options: ["Video lectures","Hands-on Projects","Reading / Docs","Interactive Labs","Mixed"] },
      { name: "certification_needed", label: "Certificate Required?", icon: "🏆", options: ["Yes","No"] },
      { name: "motivation",           label: "Primary Motivation",    icon: "💡", options: ["Career Growth","Job Switch","Skill Improvement","Academic Learning","Freelancing","Personal Interest"] },
    ],
  },
];

const buildDefaults = () => {
  const d = {};
  SECTIONS.forEach(s => s.fields.forEach(f => {
    const first = f.options[0];
    d[f.name] = typeof first === "string" ? first : first.value;
  }));
  return d;
};

export default function Profile() {
  const navigate  = useNavigate();
  const username  = localStorage.getItem("username");
  const [profile,     setProfile]     = useState(buildDefaults());
  const [status,      setStatus]      = useState({ type: "", msg: "" });
  const [loading,     setLoading]     = useState(false);
  const [step,        setStep]        = useState(0);
  const [profileLoaded, setProfileLoaded] = useState(false);

  useEffect(() => { if (!username) navigate("/login"); }, [username, navigate]);

  // ── Load saved profile from DB on mount ──────────────────────────────────────
  useEffect(() => {
    if (!username) return;
    API.post("/profile/load", { username })
      .then(res => {
        if (res.data.status === "success" && res.data.profile) {
          const saved = res.data.profile;
          // Only override fields that are actually saved (not null/empty)
          setProfile(prev => {
            const merged = { ...prev };
            Object.keys(saved).forEach(key => {
              if (saved[key] !== null && saved[key] !== "" && saved[key] !== undefined) {
                merged[key] = saved[key];
              }
            });
            return merged;
          });
        }
      })
      .catch(() => {}) // silently ignore if endpoint doesn't exist yet
      .finally(() => setProfileLoaded(true));
  }, [username]);

  const onChange = (e) => setProfile(p => ({ ...p, [e.target.name]: e.target.value }));

  const handleNext = (e) => {
    e.preventDefault(); e.stopPropagation();
    setStatus({ type: "", msg: "" });
    setStep(s => s + 1);
  };

  const handleBack = (e) => {
    e.preventDefault(); e.stopPropagation();
    setStatus({ type: "", msg: "" });
    setStep(s => s - 1);
  };

  const handleGetRecommendations = async (e) => {
    e.preventDefault(); e.stopPropagation();
    setStatus({ type: "", msg: "" });
    setLoading(true);
    try {
      const res = await submitProfile(profile);
      if (res.data.status === "success") {
        setStatus({ type: "success", msg: "Profile saved! Generating your recommendations…" });
        setTimeout(() => navigate("/recommendations"), 1400);
      } else {
        setStatus({ type: "error", msg: res.data.message || "Failed to save profile." });
      }
    } catch (err) {
      setStatus({ type: "error", msg: err.response?.data?.message || "Cannot reach the server." });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => { await logoutUser(); navigate("/"); };

  const handleSidebarStep = (e, i) => {
    e.preventDefault(); e.stopPropagation();
    if (i <= step) setStep(i);
  };

  const currentSection = SECTIONS[step];
  const isLast = step === SECTIONS.length - 1;
  const progressPct = (step / SECTIONS.length) * 100;

  return (
    <div className="profile-page-root">
      <div className="profile-sidebar">
        <div className="profile-sidebar-logo" onClick={() => navigate("/")}>
          <span>🎓</span>
          <span className="profile-sidebar-brand">Course Recommender</span>
        </div>
        <div className="profile-sidebar-welcome">
          <div className="profile-sidebar-avatar">{username?.[0]?.toUpperCase()}</div>
          <div className="profile-sidebar-name">{username}</div>
          <div className="profile-sidebar-sub">
            {profileLoaded ? "Your saved profile loaded" : "Loading your profile…"}
          </div>
        </div>
        <div className="profile-sidebar-steps">
          {SECTIONS.map((s, i) => (
            <button key={i} type="button"
              className={`profile-sidebar-step ${i === step ? "active" : i < step ? "done" : ""}`}
              onClick={(e) => handleSidebarStep(e, i)}>
              <span className="profile-sidebar-step-icon">{i < step ? "✓" : s.icon}</span>
              <span className="profile-sidebar-step-label">{s.heading}</span>
            </button>
          ))}
          <div className="profile-sidebar-step" style={{ cursor:"default", opacity:.5 }}>
            <span className="profile-sidebar-step-icon">🎯</span>
            <span className="profile-sidebar-step-label">Get Results</span>
          </div>
        </div>
        <button type="button" className="profile-sidebar-logout" onClick={handleLogout}>
          Sign out
        </button>
      </div>

      <div className="profile-main">
        <div className="profile-progress-bar">
          <div className="profile-progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
        <div className="profile-main-inner">
          <div className="profile-section-header">
            <div className="profile-section-icon-big">{currentSection.icon}</div>
            <div>
              <h2 className="profile-section-title">{currentSection.heading}</h2>
              <p className="profile-section-sub">
                {step === 0
                  ? "Tell us about your background and what you want to achieve"
                  : "Help us understand your learning context and constraints"}
              </p>
            </div>
          </div>

          {status.msg && (
            <div className={`alert alert--${status.type === "error" ? "error" : "success"}`}
              style={{ marginBottom: 24 }}>
              <span>{status.type === "error" ? "⚠" : "✓"}</span> {status.msg}
            </div>
          )}

          <form onSubmit={(e) => e.preventDefault()} noValidate>
            <div className="profile-fields-grid">
              {currentSection.fields.map(field => (
                <div className="profile-field-card" key={field.name}>
                  <label className="profile-field-label">
                    <span className="profile-field-icon">{field.icon}</span>
                    {field.label}
                  </label>
                  <select name={field.name} value={profile[field.name]}
                    onChange={onChange} className="profile-select">
                    {field.options.map(opt =>
                      typeof opt === "string"
                        ? <option key={opt} value={opt}>{opt}</option>
                        : <option key={opt.value} value={opt.value}>{opt.label}</option>
                    )}
                  </select>
                </div>
              ))}
            </div>

            <div className="profile-nav-row">
              {step > 0 && (
                <button type="button" className="btn-profile-back" onClick={handleBack}>
                  ← Back
                </button>
              )}
              {!isLast ? (
                <button type="button" className="btn-profile-next" onClick={handleNext}>
                  Next → {SECTIONS[step + 1]?.heading}
                </button>
              ) : (
                <button type="button" className="btn-profile-submit"
                  disabled={loading} onClick={handleGetRecommendations}>
                  {loading ? <><span className="spinner" /> Saving…</> : "✨  Get My Recommendations →"}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}