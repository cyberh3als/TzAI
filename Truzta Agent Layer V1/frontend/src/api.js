const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

function formatError(detail) {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const field = Array.isArray(item.loc) ? item.loc.filter((part) => part !== "body").join(".") : "";
      return field ? `${field}: ${item.msg}` : item.msg;
    }).join("; ");
  }
  return "Request failed";
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(formatError(payload.detail));
  return payload;
}

export const api = {
  frameworks: () => request("/frameworks"),
  clients: () => request("/clients"),
  client: (clientId) => request(`/clients/${clientId}`),
  controls: (clientId) => request(`/clients/${clientId}/controls`),
  gapQuestions: (clientId) => request(`/clients/${clientId}/gap-questions`),
  gapFindings: (clientId) => request(`/clients/${clientId}/gap-findings`),
  gapInterview: (clientId) => request(`/clients/${clientId}/gap-interview`),
  gapAnswer: (clientId, text) => request(`/clients/${clientId}/gap-interview/answer`, { method: "POST", body: JSON.stringify({ text }) }),
  gapSkip: (clientId) => request(`/clients/${clientId}/gap-interview/skip`, { method: "POST" }),
  gapEvaluate: (clientId) => request(`/clients/${clientId}/gap-interview/evaluate`, { method: "POST" }),
  createClient: (submission) => request("/clients", { method: "POST", body: JSON.stringify(submission) }),
};
