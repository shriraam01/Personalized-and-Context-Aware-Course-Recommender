import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../App.css";

const FEATURES = [
  { icon: "🎯", title: "Truly Personalised",  desc: "Courses matched to your exact interests, goals and experience level" },
  { icon: "⚡", title: "Instant Results",      desc: "Get your top 6 course picks in seconds, ranked by relevance" },
  { icon: "🏆", title: "Top Rated Only",       desc: "Only highly reviewed and popular courses make the list" },
  { icon: "🧭", title: "Context Aware",        desc: "We consider your budget, time, learning style and career stage" },
];

const STEPS = [
  { n: "01", title: "Create your profile",     desc: "Tell us your interests, career goal, experience level and learning preferences." },
  { n: "02", title: "We analyse your profile", desc: "Our system scores thousands of courses against your unique profile." },
  { n: "03", title: "Get your top matches",    desc: "Receive your personalised top 6 course picks with direct links." },
];



export default function Home() {
  const navigate  = useNavigate();
  const username  = localStorage.getItem("username");


  return (
    <div className="home-root">

      {/* Navbar */}
      <nav className="home-nav">
        <div className="home-nav-logo">
          <span className="home-nav-icon">🎓</span>
          <span className="home-nav-brand">Course Recommender</span>
        </div>
        <div className="home-nav-actions">
          {username ? (
            <button className="btn-nav-primary" onClick={() => navigate("/profile")}>My Profile</button>
          ) : (
            <>
              <button className="btn-nav-ghost" onClick={() => navigate("/login")}>Sign In</button>
              <button className="btn-nav-primary" onClick={() => navigate("/register")}>Get Started</button>
            </>
          )}
        </div>
      </nav>

      {/* Hero — full bleed two-column layout */}
      <section className="home-hero">
        <div className="home-hero-blob blob-1" />
        <div className="home-hero-blob blob-2" />

        {/* Left — text */}
        <div className="home-hero-content">
          <div className="home-hero-badge">✦ Smart Course Discovery</div>
          <h1 className="home-hero-title">
            Find Your <span className="home-hero-highlight">Perfect Course</span><br />
            in Seconds
          </h1>
          <p className="home-hero-sub">
            Tell us your goals, experience and learning style.
            We analyse thousands of courses and handpick the ones
            that are truly right for you.
          </p>
          <div className="home-hero-cta">
            <button className="btn-hero-primary" onClick={() => navigate(username ? "/profile" : "/register")}>
              {username ? "Get Recommendations →" : "Start for Free →"}
            </button>
            {!username && (
              <button className="btn-hero-ghost" onClick={() => navigate("/login")}>
                Already have an account?
              </button>
            )}
          </div>
          <div className="home-stats">
            <div className="home-stat">
              <span className="home-stat-num">3,000+</span>
              <span className="home-stat-label">Courses analysed</span>
            </div>
            <div className="home-stat-div" />
            <div className="home-stat">
              <span className="home-stat-num">9</span>
              <span className="home-stat-label">Tech domains</span>
            </div>
            <div className="home-stat-div" />
            <div className="home-stat">
              <span className="home-stat-num">100%</span>
              <span className="home-stat-label">Personalised</span>
            </div>
          </div>
        </div>

        {/* Right — custom SVG illustration, part of the design */}
        <div className="home-hero-illus">
          <svg viewBox="0 0 480 500" fill="none" xmlns="http://www.w3.org/2000/svg" className="hero-svg">

            {/* Background circle — blends with indigo palette */}
            <circle cx="280" cy="240" r="200" fill="#eef2ff" />
            <circle cx="280" cy="240" r="160" fill="#e0e7ff" />

            {/* Floating card 1 — course card */}
            <g filter="url(#shadow1)">
              <rect x="30" y="80" width="200" height="110" rx="16" fill="white" />
              <rect x="30" y="80" width="200" height="6" rx="3" fill="#6366f1" />
              <rect x="50" y="106" width="120" height="10" rx="5" fill="#c7d2fe" />
              <rect x="50" y="124" width="80" height="8" rx="4" fill="#e0e7ff" />
              <rect x="50" y="148" width="56" height="22" rx="11" fill="#6366f1" />
              <text x="78" y="163" fontFamily="Inter,sans-serif" fontSize="9" fill="white" textAnchor="middle" fontWeight="700">Enroll</text>
              <rect x="116" y="148" width="48" height="22" rx="11" fill="#f3f4f6" />
              <text x="140" y="163" fontFamily="Inter,sans-serif" fontSize="8" fill="#6b7280" textAnchor="middle">Preview</text>
              {/* Star rating */}
              <text x="50" y="140" fontFamily="Inter,sans-serif" fontSize="9" fill="#f59e0b">★★★★★</text>
              <text x="100" y="140" fontFamily="Inter,sans-serif" fontSize="8" fill="#9ca3af">4.9 (12k)</text>
            </g>

            {/* Floating card 2 — match score */}
            <g filter="url(#shadow2)">
              <rect x="260" y="50" width="160" height="80" rx="14" fill="white" />
              <circle cx="296" cy="90" r="22" fill="#eef2ff" stroke="#c7d2fe" strokeWidth="2" />
              <text x="296" y="87" fontFamily="Inter,sans-serif" fontSize="11" fill="#6366f1" textAnchor="middle" fontWeight="800">97</text>
              <text x="296" y="98" fontFamily="Inter,sans-serif" fontSize="7" fill="#6366f1" textAnchor="middle">%</text>
              <text x="328" y="82" fontFamily="Inter,sans-serif" fontSize="10" fill="#111827" fontWeight="700">Best Match</text>
              <text x="328" y="96" fontFamily="Inter,sans-serif" fontSize="8" fill="#6b7280">For your profile</text>
            </g>

            {/* Central illustration — person at laptop */}
            {/* Desk */}
            <rect x="120" y="330" width="280" height="12" rx="6" fill="#c7d2fe" />
            <rect x="150" y="342" width="10" height="60" rx="4" fill="#a5b4fc" />
            <rect x="360" y="342" width="10" height="60" rx="4" fill="#a5b4fc" />

            {/* Laptop base */}
            <rect x="155" y="260" width="210" height="130" rx="10" fill="#1e1b4b" />
            <rect x="165" y="268" width="190" height="112" rx="6" fill="#312e81" />
            {/* Screen content */}
            <rect x="175" y="276" width="170" height="8" rx="3" fill="#4f46e5" />
            <rect x="175" y="290" width="100" height="6" rx="3" fill="#6366f1" opacity="0.7" />
            <rect x="175" y="302" width="130" height="6" rx="3" fill="#6366f1" opacity="0.5" />
            <rect x="175" y="314" width="80" height="6" rx="3" fill="#6366f1" opacity="0.4" />
            {/* Progress bar on screen */}
            <rect x="175" y="328" width="170" height="8" rx="4" fill="#1e1b4b" />
            <rect x="175" y="328" width="110" height="8" rx="4" fill="#818cf8" />
            {/* Laptop hinge */}
            <rect x="140" y="390" width="240" height="14" rx="7" fill="#312e81" />

            {/* Person — simple friendly figure */}
            {/* Body */}
            <ellipse cx="260" cy="230" rx="38" ry="42" fill="#6366f1" />
            {/* Head */}
            <circle cx="260" cy="178" r="30" fill="#fbbf24" />
            {/* Hair */}
            <ellipse cx="260" cy="155" rx="30" ry="14" fill="#1f2937" />
            {/* Eyes */}
            <circle cx="250" cy="176" r="4" fill="#1f2937" />
            <circle cx="270" cy="176" r="4" fill="#1f2937" />
            <circle cx="251" cy="175" r="1.5" fill="white" />
            <circle cx="271" cy="175" r="1.5" fill="white" />
            {/* Smile */}
            <path d="M250 188 Q260 196 270 188" stroke="#1f2937" strokeWidth="2" strokeLinecap="round" fill="none" />
            {/* Arms */}
            <rect x="222" y="228" width="16" height="50" rx="8" fill="#6366f1" />
            <rect x="282" y="228" width="16" height="50" rx="8" fill="#6366f1" />
            {/* Hands on keyboard */}
            <ellipse cx="230" cy="282" rx="12" ry="8" fill="#fbbf24" />
            <ellipse cx="290" cy="282" rx="12" ry="8" fill="#fbbf24" />

            {/* Floating badge — domain tags */}
            <g filter="url(#shadow2)">
              <rect x="20" y="230" width="110" height="34" rx="17" fill="#6366f1" />
              <text x="75" y="251" fontFamily="Inter,sans-serif" fontSize="10" fill="white" textAnchor="middle" fontWeight="700">📊 Data Science</text>
            </g>
            <g filter="url(#shadow2)">
              <rect x="350" y="200" width="100" height="34" rx="17" fill="#8b5cf6" />
              <text x="400" y="221" fontFamily="Inter,sans-serif" fontSize="10" fill="white" textAnchor="middle" fontWeight="700">🧠 ML / AI</text>
            </g>
            <g filter="url(#shadow2)">
              <rect x="360" y="290" width="96" height="34" rx="17" fill="#06b6d4" />
              <text x="408" y="311" fontFamily="Inter,sans-serif" fontSize="10" fill="white" textAnchor="middle" fontWeight="700">🌐 Web Dev</text>
            </g>

            {/* Sparkles */}
            <circle cx="80" cy="160" r="5" fill="#fbbf24" opacity="0.8" />
            <circle cx="440" cy="150" r="4" fill="#f472b6" opacity="0.7" />
            <circle cx="420" cy="380" r="6" fill="#34d399" opacity="0.6" />
            <circle cx="60" cy="340" r="4" fill="#818cf8" opacity="0.8" />
            <text x="76" y="164" fontSize="10" textAnchor="middle">✦</text>
            <text x="436" y="154" fontSize="8" textAnchor="middle">✦</text>

            <defs>
              <filter id="shadow1" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="4" stdDeviation="8" floodColor="#6366f1" floodOpacity="0.12" />
              </filter>
              <filter id="shadow2" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="4" stdDeviation="6" floodColor="#000" floodOpacity="0.08" />
              </filter>
            </defs>
          </svg>
        </div>
      </section>

      {/* Domains strip */}
      <section className="home-domains">
        <p className="home-section-label">Covering all major tech domains</p>
      </section>

      {/* Features */}
      <section className="home-features">
        <div className="home-section-head">
          <h2 className="home-section-title">Why Course Recommender?</h2>
          <p className="home-section-sub">Personalised and context-aware recommendations for your learning journey</p>
        </div>
        <div className="home-features-grid">
          {FEATURES.map((f, i) => (
            <div className="home-feature-card" key={i}>
              <div className="home-feature-icon">{f.icon}</div>
              <h3 className="home-feature-title">{f.title}</h3>
              <p className="home-feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="home-how">
        <div className="home-section-head">
          <h2 className="home-section-title">How it works</h2>
          <p className="home-section-sub">Three simple steps to your perfect course</p>
        </div>
        <div className="home-steps">
          {STEPS.map((s, i) => (
            <div className="home-step" key={i}>
              <div className="home-step-num">{s.n}</div>
              <h3 className="home-step-title">{s.title}</h3>
              <p className="home-step-desc">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="home-cta-banner">
        <div className="home-cta-blob" />
        <h2 className="home-cta-title">Ready to find your next course?</h2>
        <p className="home-cta-sub">Join learners who are getting smarter course recommendations.</p>
        <button className="btn-hero-primary" onClick={() => navigate(username ? "/profile" : "/register")}>
          {username ? "Go to my profile →" : "Get Started — It's Free →"}
        </button>
      </section>

      <footer className="home-footer">
        <span className="home-nav-icon">🎓</span>
        <span>Course Recommender — Personalised & Context-Aware Course Recommendations</span>
      </footer>
    </div>
  );
}