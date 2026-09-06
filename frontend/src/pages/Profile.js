import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitProfile, logoutUser } from "../api";
import API from "../api";
import "../App.css";

// Field shape: { name, label, icon, type: "select" | "text" | "number", options?, placeholder? }
const SECTIONS = [
  {
    heading: "About You",
    icon: "👤",
    fields: [
      { name: "interests", label: "Area of Interest", icon: "🎯", type: "select",
        options: ["Data Science","Computer Science","Business","Arts & Humanities","Health",
                  "Personal Development","Language Learning","Physical Science & Engineering",
                  "Social Sciences","Music & Art"] },
      { name: "career_goal", label: "Career Goal", icon: "🚀", type: "text",
        placeholder: "e.g. Become a Data Scientist" },
      { name: "education_level", label: "Education Level", icon: "🎓", type: "select",
        options: ["High School","Undergraduate","Graduate","Postgraduate","Working Professional"] },
      { name: "degree_field", label: "Degree / Field of Study", icon: "📖", type: "text",
        placeholder: "e.g. Computer Science" },
      { name: "current_year", label: "Current Year", icon: "📅", type: "select",
        options: ["1st Year","2nd Year","3rd Year","4th Year","Final Year","Graduated"] },
      { name: "academic_performance", label: "Academic Performance (CGPA / %)", icon: "📊", type: "number",
        placeholder: "e.g. 8.4" },
    ],
  },
  {
    heading: "Skills & Experience",
    icon: "🛠",
    fields: [
      { name: "existing_skills", label: "Existing Skills", icon: "✅", type: "text",
        placeholder: "e.g. Python, SQL, Excel" },
      { name: "experience_level", label: "Experience Level", icon: "📈", type: "select",
        options: ["Beginner","Intermediate","Advanced"] },
      { name: "experience_years", label: "Years of Experience", icon: "⏳", type: "number",
        placeholder: "e.g. 1" },
      { name: "desired_skills", label: "Desired Skills", icon: "🌱", type: "text",
        placeholder: "e.g. Machine Learning, React" },
      { name: "target_job_role", label: "Target Job Role", icon: "💼", type: "text",
        placeholder: "e.g. Data Analyst" },
      { name: "target_industry", label: "Target Industry", icon: "🏭", type: "text",
        placeholder: "e.g. Fintech" },
    ],
  },
  {
    heading: "Learning Preferences",
    icon: "📚",
    fields: [
      { name: "preferred_difficulty", label: "Preferred Difficulty", icon: "🎚", type: "select",
        options: ["Beginner","Intermediate","Advanced","Mixed"] },
      { name: "preferred_language", label: "Course Language", icon: "🌐", type: "select",
        options: ["English","Hindi","French","Spanish","German"] },
      { name: "learning_objective", label: "Learning Objective", icon: "🎯", type: "select",
        options: ["Career Growth","Job Switch","Skill Improvement","Academic Learning",
                  "Certification","Personal Interest"] },
      { name: "content_preference", label: "Content Preference", icon: "🎬", type: "select",
        options: ["Video Lectures","Reading / Text","Hands-on Projects","Mixed"] },
      { name: "teaching_style", label: "Teaching Style", icon: "🧑‍🏫", type: "select",
        options: ["Structured / Guided","Self-paced / Exploratory","Project-based","Theory-focused"] },
    ],
  },
  {
    heading: "Budget & Context",
    icon: "⚙️",
    fields: [
      { name: "budget", label: "Budget", icon: "💰", type: "select",
        options: ["Free only","Free to audit (pay for certificate)","Paid - any budget"] },
      { name: "available_hours_per_week", label: "Hours Available / Week", icon: "⏱", type: "number",
        placeholder: "e.g. 5" },
      { name: "completion_time", label: "Desired Completion Time", icon: "📆", type: "select",
        options: ["Within 1 month","1 - 3 months","3 - 6 months","6+ months"] },
      { name: "learning_mode", label: "Preferred Learning Mode", icon: "🖥", type: "select",
        options: ["Self-paced","Instructor-led / Scheduled","Hands-on / Lab-based",
                  "Video + Reading","No preference"] },
      { name: "certification_needed", label: "Certificate Required?", icon: "🏆", type: "select",
        options: ["Yes","No"] },
    ],
  },
];

const buildDefaults = () => {
  const d = {};
  SECTIONS.forEach(s => s.fields.forEach(f => {
    d[f.name] = f.type === "select" ? f.options[0] : "";
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
                  {field.type === "select" ? (
                    <select name={field.name} value={profile[field.name]}
                      onChange={onChange} className="profile-select">
                      {field.options.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      className="profile-select"
                      type={field.type === "number" ? "number" : "text"}
                      name={field.name}
                      value={profile[field.name]}
                      placeholder={field.placeholder || ""}
                      onChange={onChange}
                    />
                  )}
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