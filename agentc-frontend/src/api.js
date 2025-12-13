// frontend/src/api.js
import { API_BASE } from "./config";

async function handleResponse(res) {
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch (e) {
    throw new Error("Invalid JSON from backend: " + text);
  }

  if (!res.ok) {
    const msg = data.error || res.statusText || "Request failed";
    throw new Error(msg);
  }
  return data;
}

export async function getSpecialties() {
  const res = await fetch(`${API_BASE}/api/specialties`);
  return handleResponse(res);
}

export async function getLevels(specialty) {
  const res = await fetch(
    `${API_BASE}/api/levels?specialty=${encodeURIComponent(specialty)}`
  );
  return handleResponse(res);
}

export async function startSession({ specialty, level }) {
  const res = await fetch(`${API_BASE}/api/start-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ specialty, level }),
  });
  return handleResponse(res);
}

// IMPORTANT CHANGE: send `sessionId` (camelCase), not `session_id`
export async function sendChat({ sessionId, message }) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, message }),
  });
  return handleResponse(res);
}

// IMPORTANT CHANGE: send `sessionId` here as well
export async function requestHint({ sessionId }) {
  const res = await fetch(`${API_BASE}/api/hint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId }),
  });
  return handleResponse(res);
}

export async function getSummary(sessionId) {
  const res = await fetch(`${API_BASE}/api/summary/${sessionId}`);
  return handleResponse(res);
}
