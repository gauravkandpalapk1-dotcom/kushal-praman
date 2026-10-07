"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { listItems, type QueueItem } from "./store";
import { syncEngine } from "./sync";

/** Re-renders on any sync-engine change (network state, queue progress). */
export function useSyncState() {
  useEffect(() => syncEngine.start(), []);
  const version = useSyncExternalStore(
    syncEngine.subscribe,
    () => syncEngine.version,
    () => 0,
  );
  return {
    version,
    online: syncEngine.online,
    simulatedOffline: syncEngine.isSimulatedOffline,
    browserOnline: syncEngine.isBrowserOnline,
    syncing: syncEngine.isSyncing,
    lastSyncAt: syncEngine.lastSyncAt,
    engine: syncEngine,
  };
}

export function useQueue(ownerId: number | null | undefined) {
  const state = useSyncState();
  const [items, setItems] = useState<QueueItem[]>([]);
  useEffect(() => {
    if (ownerId == null) return;
    let alive = true;
    listItems(ownerId)
      .then((xs) => alive && setItems(xs))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, [ownerId, state.version]);
  return { ...state, items };
}
