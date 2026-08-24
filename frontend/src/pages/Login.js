import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { loginUser } from "../api";
import "../App.css";

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm]       = useState({ username: "", password: "" });
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  const onChange = (e) => setForm((p) => ({ ...p, [e.target.name]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.username.trim() || !form.password) { setError("Please fill in both fields."); return; }
    setLoading(true);
    try {
      const res = await loginUser(form);
      if (res.data.status === "success") {
        localStorage.setItem("username", res.data.username);
        navigate("/profile");
      } else {
        setError(res.data.message || "Invalid username or password.");
      }
    } catch (err) {
      setError(err.response?.data?.message || "Cannot reach the server. Make sure the backend is running on port 5000.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-outer">
      <div className="page-card">
        <div className="auth-logo">🎓</div>
        <div className="auth-title-row">
          <h1>Welcome back</h1>
          <p className="subtitle">Sign in to get your personalised course recommendations</p>
        </div>
        {error && <div className="alert alert--error" style={{ marginBottom: 20 }}><span>⚠</span> {error}</div>}
        <form className="form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input id="username" name="username" type="text" placeholder="Your username" value={form.username} onChange={onChange} autoFocus autoComplete="username" />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input id="password" name="password" type="password" placeholder="Your password" value={form.password} onChange={onChange} autoComplete="current-password" />
          </div>
          <button type="submit" className="btn btn--primary" disabled={loading} style={{ marginTop: 6 }}>
            {loading ? <span className="spinner" /> : "Sign In →"}
          </button>
        </form>
        <p className="auth-footer">
          No account yet? <Link to="/register" className="link">Create one</Link>
        </p>
        <p className="auth-footer" style={{ marginTop: 8 }}>
          <Link to="/" className="link" style={{ fontSize: '.8rem', color: 'var(--text-3)' }}>← Back to home</Link>
        </p>
      </div>
    </div>
  );
}