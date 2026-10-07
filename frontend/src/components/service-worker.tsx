"use client";

import { useEffect } from "react";

/** Registers the app-shell service worker in production builds only (dev server HMR breaks with SW caching). */
export function ServiceWorker() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production" || !("serviceWorker" in navigator)) return;
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* offline capture still works from IndexedDB; only reload-while-offline needs the SW */
    });
  }, []);
  return null;
}
