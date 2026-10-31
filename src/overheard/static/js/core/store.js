// A tiny publish/subscribe store: state, set(patch), subscribe(fn, keys), and one-off events (emit/on).
export function createStore(initial) {
  let state = { ...initial };
  const subscribers = new Set();
  const handlers = {};
  return {
    get: () => state,
    set(patch) {
      const changed = Object.keys(patch).filter((k) => state[k] !== patch[k]);
      state = { ...state, ...patch };
      if (changed.length) subscribers.forEach(({ fn, keys }) => (!keys || keys.some((k) => changed.includes(k))) && fn(state));
    },
    subscribe(fn, keys) {
      const sub = { fn, keys };
      subscribers.add(sub);
      fn(state);
      return () => subscribers.delete(sub);
    },
    emit: (name, detail) => (handlers[name] || []).forEach((h) => h(detail)),
    on: (name, h) => (handlers[name] ||= []).push(h),
  };
}
