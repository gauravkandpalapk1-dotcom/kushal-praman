// Minimal browser surface for the offline engine under Node: IndexedDB (fake), localStorage, navigator.
import "fake-indexeddb/auto";

class MemoryStorage {
  private m = new Map<string, string>();
  getItem(k: string) {
    return this.m.has(k) ? this.m.get(k)! : null;
  }
  setItem(k: string, v: string) {
    this.m.set(k, String(v));
  }
  removeItem(k: string) {
    this.m.delete(k);
  }
  clear() {
    this.m.clear();
  }
}

Object.assign(globalThis, { localStorage: new MemoryStorage() });
if (!("navigator" in globalThis) || !globalThis.navigator?.userAgent) {
  Object.defineProperty(globalThis, "navigator", { value: { userAgent: "vitest", onLine: true }, configurable: true });
}
