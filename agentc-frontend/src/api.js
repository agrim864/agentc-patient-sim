const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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
  const res = await fetch(`${API_BASE_URL}/api/specialties`);
  return handleResponse(res);
}

export async function getLevels(specialty) {
  const res = await fetch(
    `${API_BASE_URL}/api/levels?specialty=${encodeURIComponent(specialty)}`
  );
  return handleResponse(res);
}

export async function startSession({ specialty, level }) {
  const res = await fetch(`${API_BASE_URL}/api/start-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ specialty, level }),
  });
  return handleResponse(res);
}

export async function sendChat({ sessionId, message }) {
  const res = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  return handleResponse(res);
}

export async function requestHint({ sessionId }) {
  const res = await fetch(`${API_BASE_URL}/api/hint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return handleResponse(res);
}

export async function getSummary(sessionId) {
  const res = await fetch(`${API_BASE_URL}/api/summary/${sessionId}`);
  return handleResponse(res);
}
