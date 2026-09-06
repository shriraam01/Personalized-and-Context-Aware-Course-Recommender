import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { submitProfile, logoutUser } from "../api";
import API from "../api";
import "../App.css";

// NOTE: option label strings below are matched byte-for-byte against
// mapping dictionaries in backend/app.py (INTEREST_DOMAIN_MAP,
// JOBROLE_DOMAIN_MAP, INDUSTRY_DOMAIN_MAP, COMPLETION_WEEKS_MAP,
// ACADEMIC_PERFORMANCE_MAP, HOURS_PER_WEEK_MAP). If you change a label
// here, change it in app.py too, or that field silently stops scoring.

const SECTIONS = [
  {
    heading: "About You",
    icon: "👤",
    sub: "Tell us about your academic background",
    fields: [
      { name: "education_level", label: "Education Level", icon: "🎓",
        options: ["High School", "Undergraduate", "Postgraduate", "PhD", "Working Professional"] },
      { name: "degree_field", label: "Field of Study", icon: "📖",
        options: ["Computer Science", "Engineering", "Business", "Science", "Arts & Humanities", "Other"] },
      { name: "current_year", label: "Current Year / Stage", icon: "📅",
        options: ["1st Year", "2nd Year", "3rd Year", "4th Year", "Graduated", "Not Applicable"] },
      { name: "academic_performance", label: "Academic Performance", icon: "📊",
        options: ["Below 60%", "60% - 75%", "75% - 90%", "90%+", "Prefer not to say"] },
      { name: "experience_level", label: "Self-Rated Experience", icon: "🧗",
        options: ["Beginner", "Intermediate", "Advanced", "Expert"] },
      { name: "experience_years", label: "Years of Practical Experience", icon: "🕓",
        options: [{value:"0",label:"0 — Complete beginner"},{value:"1",label:"1 year"},{value:"2",label:"2 years"},{value:"3",label:"3 years"},{value:"5",label:"5+ years"}] },
    ],
  },
  {
    heading: "Goals & Skills",
    icon: "🎯",
    sub: "What are you aiming for, and what do you already know",
    fields: [
      { name: "interests", label: "Area of Interest", icon: "💡",
        options: ["Data Science","Machine Learning","Artificial Intelligence","Software Development",
                  "Web & Mobile Development","Cyber Security","Cloud Computing","IT & Networking",
                  "Business Strategy","Leadership & Management","Data Analysis & Statistics",
                  "Public Health","Life Sciences","Physical Sciences & Engineering",
                  "Arts & Humanities","Language Learning","Personal Development",
                  "Environmental Science","Design & Product","Social Sciences"] },
      { name: "career_goal", label: "Career Goal", icon: "🚀",
        options: ["Data Scientist","Machine Learning Engineer","Software Engineer","Web/Mobile Developer",
                  "Cyber Security Specialist","Cloud Engineer","Business Analyst","Product Manager",
                  "Healthcare Professional","Researcher / Academic","Manager / Team Lead",
                  "Career Switcher / Exploring"] },
      { name: "target_job_role", label: "Target Job Role", icon: "💼",
        options: ["Data Scientist","Machine Learning Engineer","Software Engineer","Web/Mobile Developer",
                  "Cyber Security Specialist","Cloud Engineer","Business Analyst","Product Manager",
                  "Healthcare Professional","Researcher / Academic","Manager / Team Lead",
                  "Career Switcher / Exploring"] },
      { name: "target_industry", label: "Target Industry", icon: "🏢",
        options: ["Technology","Finance","Healthcare","Education","Government / Public Sector",
                  "Media, Arts & Entertainment","Manufacturing & Engineering",
                  "Environmental / Sustainability","Other / Not sure"] },
      { name: "existing_skills", label: "Strongest Existing Skill", icon: "🛠",
        options: ["Python","JavaScript","Java","C++","SQL","Excel / Spreadsheets","Writing / Communication",
                  "Design Tools","Statistics","None yet"] },
      { name: "desired_skills", label: "Skill You Most Want to Learn", icon: "📈",
        options: ["Python","Machine Learning","Cloud Platforms (AWS/Azure/GCP)","Cyber Security Tools",
                  "Data Visualization","Public Speaking","Project Management","UI/UX Design",
                  "Statistics","Writing / Communication"] },
      { name: "learning_objective", label: "Primary Learning Objective", icon: "🏁",
        options: ["Get a certificate","Build practical skills for a project","Prepare for a job interview",
                  "Switch careers","Academic requirement","Personal interest / curiosity"] },
    ],
  },
  {
    heading: "Learning Style",
    icon: "📚",
    sub: "How do you prefer to learn",
    fields: [
      { name: "preferred_difficulty", label: "Preferred Difficulty", icon: "🎚",
        options: ["Beginner", "Intermediate", "Advanced", "Any"] },
      { name: "preferred_language", label: "Preferred Course Language", icon: "🌐",
        options: ["English", "Hindi", "French", "Spanish", "German"] },
      { name: "content_preference", label: "Preferred Content Style", icon: "🎬",
        options: ["Video lectures", "Hands-on Projects", "Reading / Docs", "Interactive Labs", "Mixed"] },
      { name: "teaching_style", label: "Preferred Teaching Style", icon: "🧑‍🏫",
        options: ["Structured / Curriculum-based", "Practical / Project-based",
                  "Theory-heavy / Academic", "Story-driven / Case studies"] },
    ],
  },
  {
    heading: "Your Context",
    icon: "⏱️",
    sub: "Constraints that shape which courses actually fit right now",
    fields: [
      { name: "budget", label: "Budget", icon: "💰",
        options: ["Free courses only", "Willing to pay for certificate", "No preference"] },
      { name: "available_hours_per_week", label: "Hours Available per Week", icon: "⏳",
        options: ["1-2 hrs/week", "3-5 hrs/week", "5-10 hrs/week", "10+ hrs/week"] },
      { name: "completion_time", label: "Target Completion Time", icon: "📆",
        options: ["Within a week", "Within a month", "1-3 months", "No specific deadline"] },
      { name: "learning_mode", label: "Preferred Format", icon: "🖥️",
        options: ["Hands-on projects", "Video lectures & reading", "No preference"] },
      { name: "certification_needed", label: "Certificate Required?", icon: "🏆",
        options: ["Yes", "No"] },
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
                merged[key] = String(saved[key]);
              }
            });
            return merged;
          });
        }
      })
      .catch(() => {})
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
              <p className="profile-section-sub">{currentSection.sub}</p>
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