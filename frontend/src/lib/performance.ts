// Local opt-in diagnostics only; fixed names and durations, never user inputs.
const enabled =
  import.meta.env.DEV && new URLSearchParams(location.search).has("profile");
export function measureSource(
  name: string,
  update: () => Promise<unknown>,
): void {
  if (!enabled) {
    void update();
    return;
  }
  const start = performance.now();
  void update().then(() =>
    performance.measure(name, { start, end: performance.now() }),
  );
}
