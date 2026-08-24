import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:5000/api",
  withCredentials: false,
  headers: { "Content-Type": "application/json" },
});

export const registerUser  = (data) =>
  API.post("/register", data);

export const loginUser = (data) =>
  API.post("/login", data);

export const logoutUser = () => {
  localStorage.removeItem("username");
  return API.post("/logout");
};

export const submitProfile = (profileData) => {
  const username = localStorage.getItem("username");
  return API.post("/profile", { ...profileData, username });
};

export const getRecommendations = () => {
  const username = localStorage.getItem("username");
  return API.post("/recommend", { username });
};

export const submitFeedback = (courseId, liked) => {
  const username = localStorage.getItem("username");
  return API.post("/feedback", { username, course_id: courseId, liked });
};

export default API;