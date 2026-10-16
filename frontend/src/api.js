const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  getAccounts: () => request("/accounts"),
  getTransactions: () => request("/transactions"),
  getMeshState: () => request("/mesh/state"),
  sendPayment: (body) => request("/demo/send", { method: "POST", body: JSON.stringify(body) }),
  runGossip: () => request("/mesh/gossip", { method: "POST" }),
  flushBridges: () => request("/mesh/flush", { method: "POST" }),
  reset: () => request("/mesh/reset", { method: "POST" }),
};
