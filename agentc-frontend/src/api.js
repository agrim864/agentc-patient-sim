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

// Send `sessionId` (camelCase), backend normalizes it
export async function sendChat({ sessionId, message }) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, message }),
  });
  return handleResponse(res);
}

// Textual hint (affects efficiency, not stars directly)
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

// Reveal one hidden objective at the cost of 1 star
// NOTE: backend expects `session_id` and `objective_id`
export async function revealObjective({ sessionId, objectiveId }) {
  const payload = {
    sessionId, // normalized to `session_id` on the backend
  };
  if (objectiveId) {
    payload.objective_id = objectiveId;
  }

  const res = await fetch(`${API_BASE}/api/reveal-objective`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse(res);
}

// Optional helpers if you want to centralize progress calls here
export async function getProgress() {
  const res = await fetch(`${API_BASE}/api/progress`);
  return handleResponse(res);
}

export async function resetProgress() {
  const res = await fetch(`${API_BASE}/api/reset`, {
    method: "POST",
  });
  return handleResponse(res);
}
