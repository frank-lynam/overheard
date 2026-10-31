// The server's REST API. The browser only ever talks to it (never to an LLM).
async function call(method, path, body) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body ? { "content-type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status}`);
  return res.json();
}
export const api = {
  day: () => call("GET", "/day"),
  queue: () => call("GET", "/queue"),
  message: (id) => call("GET", `/messages/${id}`),
  lookup: (q) => call("GET", `/lookup?q=${encodeURIComponent(q)}`),
  entries: () => call("GET", "/entries"),
  saveEntry: (id, entry) => call("PUT", `/entries/${id}`, entry),
  simulation: (mode) => call("GET", `/simulation?mode=${mode}`),
  assumptions: () => call("GET", "/assumptions"),
};
