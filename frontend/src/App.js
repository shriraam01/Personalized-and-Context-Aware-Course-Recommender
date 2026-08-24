import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Home            from "./pages/Home";
import Login           from "./pages/Login";
import Register        from "./pages/Register";
import Profile         from "./pages/Profile";
import Recommendations from "./pages/Recommendations";

function PrivateRoute({ children }) {
  return localStorage.getItem("username")
    ? children
    : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"                element={<Home />} />
        <Route path="/login"           element={<Login />} />
        <Route path="/register"        element={<Register />} />
        <Route path="/profile"         element={<PrivateRoute><Profile /></PrivateRoute>} />
        <Route path="/recommendations" element={<PrivateRoute><Recommendations /></PrivateRoute>} />
        <Route path="*"                element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;