// src/config.js

const PROD_API_BASE = "https://agentc-patient-sim.onrender.com"; // <- replace this

const LOCAL_API_BASE = "http://localhost:8000";

const isLocalhost =
  window.location.hostname === "localhost" ||
  window.location.hostname === "127.0.0.1";

export const API_BASE =
  import.meta.env.VITE_API_BASE || (isLocalhost ? LOCAL_API_BASE : PROD_API_BASE);
