import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { registerUser } from "../api";
import "../App.css";

export default function Register() {
  const navigate = useNavigate();
  const [form, setForm]       = useState({ username: "", password: "", confirm: "" });
  const [error, setError]     = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const onChange = (e) => setForm((p) => ({ ...p, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess("");
    if (!form.username.trim() || !form.password || !form.confirm) { setError("Please fill in all fields."); return; }
    if (form.username.trim().length < 3) { setError("Username must be at least 3 characters."); return; }
    if (form.password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (form.password !== form.confirm) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      const res = await registerUser({ username: form.username.trim(), password: form.password });
      if (res.data.status === "success") {
        setSuccess("Account created! Redirecting to login…");
        setTimeout(() => navigate("/login"), 1400);
      } else {
        setError(res.data.message || "Registration failed.");
      }
    } catch (err) {
      if (err.response?.status === 409) {
        setError("That username is already taken. Try a different one.");
      } else {
        setError(err.response?.data?.message || "Cannot reach the server. Make sure the backend is running.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-outer">
      <div className="page-card">
        <div className="auth-logo">✦</div>
        <div className="auth-title-row">
          <h1>Create account</h1>
          <p className="subtitle">Get AI-powered course recommendations tailored just for you</p>
        </div>
        {error   && <div className="alert alert--error"   style={{ marginBottom: 20 }}><span>⚠</span> {error}</div>}
        {success && <div className="alert alert--success" style={{ marginBottom: 20 }}><span>✓</span> {success}</div>}
        <form className="form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="reg-username">Username</label>
            <input id="reg-username" name="username" type="text" placeholder="At least 3 characters" value={form.username} onChange={onChange} autoFocus />
          </div>
          <div className="field">
            <label htmlFor="reg-password">Password</label>
            <input id="reg-password" name="password" type="password" placeholder="At least 6 characters" value={form.password} onChange={onChange} />
          </div>
          <div className="field">
            <label htmlFor="reg-confirm">Confirm password</label>
            <input id="reg-confirm" name="confirm" type="password" placeholder="Repeat your password" value={form.confirm} onChange={onChange} />
          </div>
          <button type="submit" className="btn btn--primary" disabled={loading} style={{ marginTop: 6 }}>
            {loading ? <span className="spinner" /> : "Create Account →"}
          </button>
        </form>
        <p className="auth-footer">Already have an account? <Link to="/login" className="link">Sign in</Link></p>
        <p className="auth-footer" style={{ marginTop: 8 }}>
          <Link to="/" className="link" style={{ fontSize: '.8rem', color: 'var(--text-3)' }}>← Back to home</Link>
        </p>
      </div>
    </div>
  );
}