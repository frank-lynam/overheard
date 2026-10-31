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
  queue: (mode = 0) => call("GET", `/queue?mode=${mode}`),
  message: (id, mode = 0) => call("GET", `/messages/${id}?mode=${mode}`),
  lookup: (q) => call("GET", `/lookup?q=${encodeURIComponent(q)}`),
  entries: () => call("GET", "/entries"),
  saveEntry: (id, entry) => call("PUT", `/entries/${id}`, entry),
  simulation: (mode) => call("GET", `/simulation?mode=${mode}`),
  assumptions: () => call("GET", "/assumptions"),
  saveAssumptions: (a) => call("PUT", "/assumptions", a),
  corrections: (voicemail) =>
    voicemail ? call("GET", `/corrections?voicemail=${encodeURIComponent(voicemail)}`) : call("GET", "/corrections"),
  postCorrection: (c) => call("POST", "/corrections", c),
  accuracy: () => call("GET", "/accuracy"),
  // mode 2: the day's spike incidents, a message's resolution (and its human state), the mode-2 scoreboard
  incidents: () => call("GET", "/incidents"),
  resolution: (id) => call("GET", `/resolutions/${id}`),
  setResolution: (id, state, reply) => call("POST", `/resolutions/${id}`, { state, reply }),
  scoreboard2: () => call("GET", "/scoreboard2"),
  // mode 3: the archive analytics
  rootCauses: () => call("GET", "/archive/root-causes"),
  eventImpact: () => call("GET", "/archive/event-impact"),
  journeys: () => call("GET", "/archive/journeys"),
  promises: () => call("GET", "/archive/promises"),
  equity: () => call("GET", "/archive/equity"),
  letterLab: (text) => call("POST", "/archive/letter-lab", { text }),
  askArchive: (question) => call("POST", "/archive/ask", { question }),
  knowledgeGaps: () => call("GET", "/knowledge-gaps"),
  weakSignals: () => call("GET", "/weak-signals"),
  staffingForecast: () => call("GET", "/staffing-forecast"),
};