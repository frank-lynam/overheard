// A tiny publish/subscribe store: state, set(patch), subscribe(fn).
export function createStore(initial) {
  let state = { ...initial };
  const subscribers = new Set();
  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...patch };
      subscribers.forEach((fn) => fn(state));
    },
    subscribe(fn) {
      subscribers.add(fn);
      fn(state);
      return () => subscribers.delete(fn);
    },
  };
}
