const DEFAULT_API_BASE_URL = "http://localhost:8000";

// VITE_API_BASE_URL controls which FastAPI backend the frontend calls.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(
  /\/+$/,
  "",
);

if (import.meta.env.DEV) {
  console.log("API_BASE_URL:", API_BASE_URL);
}

export { API_BASE_URL };
