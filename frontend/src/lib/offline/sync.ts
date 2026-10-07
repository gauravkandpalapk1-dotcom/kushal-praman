// Offline-first capture → encrypted local queue → automatic sync.
//
//   capture()  hashes the plaintext (SHA-256), encrypts it (AES-GCM) and stores it in IndexedDB
//              with a reserved evidence number, so "Evidence #17 · saved locally" is real offline.
//   syncAll()  runs on: app start, the browser `online` event, every 15 s, the field-simulation
//              switch going back online, and the manual "Sync now" button.
//              Uploads are idempotent on local_id, so a retry after a dropped connection is safe.

import { api, ApiError, uploadWithProgress } from "../api";
import type { Evidence, EvidenceKind } from "../types";
import { cryptoAvailable, decrypt, encrypt, generateQueueKey, sha256Hex } from "./crypto";
import * as store from "./store";
import type { QueueItem } from "./store";

const SIM_KEY = "kp.fieldOffline";
const KEY_NAME = "queue-key-v1";
const RESERVE_BLOCK = 5;

export interface CaptureInput {
  ownerUserId: number;
  blob: Blob;
  filename: string;
  kind: EvidenceKind;
  qualificationId: number | null;
  pcHintId?: number | null;
  language?: string | null;
  location?: { latitude: number; longitude: number; accuracy_m: number | null; source: "device" | "demo" } | null;
  capturedAt?: Date;
}

type Listener = () => void;

class SyncEngine {
  private listeners = new Set<Listener>();
  private browserOnline = true;
  private simulatedOffline = false;
  private syncing = false;
  private timer: ReturnType<typeof setInterval> | null = null;
  private started = false;
  version = 0;
  lastSyncAt: string | null = null;
  lastError: string | null = null;

  start() {
    if (this.started || typeof window === "undefined") return;
    this.started = true;
    this.browserOnline = navigator.onLine;
    try {
      this.simulatedOffline = localStorage.getItem(SIM_KEY) === "1";
    } catch {
      this.simulatedOffline = false;
    }
    window.addEventListener("online", () => {
      this.browserOnline = true;
      this.emit();
      void this.syncAll();
    });
    window.addEventListener("offline", () => {
      this.browserOnline = false;
      this.emit();
    });
    this.timer = setInterval(() => void this.syncAll(), 15000);
    void this.syncAll();
  }

  subscribe = (fn: Listener) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  private emit() {
    this.version++;
    this.listeners.forEach((l) => l());
  }

  get online() {
    return this.browserOnline && !this.simulatedOffline;
  }
  get isSimulatedOffline() {
    return this.simulatedOffline;
  }
  get isBrowserOnline() {
    return this.browserOnline;
  }
  get isSyncing() {
    return this.syncing;
  }

  setSimulatedOffline(on: boolean) {
    this.simulatedOffline = on;
    try {
      localStorage.setItem(SIM_KEY, on ? "1" : "0");
    } catch {
      /* ignore */
    }
    this.emit();
    if (!on) void this.syncAll();
  }

  private async key(): Promise<CryptoKey | null> {
    if (!cryptoAvailable()) return null;
    let k = await store.getKey(KEY_NAME);
    if (!k) {
      k = await generateQueueKey();
      await store.putKey(KEY_NAME, k);
    }
    return k;
  }

  /** Reserve a block of evidence numbers while online so offline captures get real numbers. */
  async ensureReservations(ownerUserId: number) {
    if (!this.online) return;
    const have = await store.getReservations(ownerUserId);
    if (have.length >= 2) return;
    try {
      const out = await api.post<{ numbers: number[] }>("/sync/reserve", { count: RESERVE_BLOCK });
      const merged = Array.from(new Set([...have, ...out.numbers])).sort((a, b) => a - b);
      await store.setReservations(ownerUserId, merged);
    } catch {
      /* best effort; server assigns a number on upload anyway */
    }
  }

  async capture(input: CaptureInput): Promise<QueueItem> {
    const plain = await input.blob.arrayBuffer();
    const hash = cryptoAvailable() ? await sha256Hex(plain) : "";
    const key = await this.key();
    let payload = plain;
    let iv: Uint8Array<ArrayBuffer> | null = null;
    if (key) {
      const enc = await encrypt(key, plain);
      payload = enc.ciphertext;
      iv = enc.iv;
    }
    const reserved = await store.getReservations(input.ownerUserId);
    const number = reserved.shift() ?? null;
    await store.setReservations(input.ownerUserId, reserved);

    const now = new Date();
    const item: QueueItem = {
      local_id: crypto.randomUUID(),
      owner_user_id: input.ownerUserId,
      reserved_number: number,
      kind: input.kind,
      filename: input.filename,
      mime_type: input.blob.type || "application/octet-stream",
      size_bytes: input.blob.size,
      client_sha256: hash,
      captured_at: (input.capturedAt ?? now).toISOString(),
      queued_at: now.toISOString(),
      latitude: input.location?.latitude ?? null,
      longitude: input.location?.longitude ?? null,
      accuracy_m: input.location?.accuracy_m ?? null,
      location_source: input.location?.source ?? null,
      device: navigator.userAgent.slice(0, 180),
      language: input.language ?? null,
      qualification_id: input.qualificationId,
      pc_hint_id: input.pcHintId ?? null,
      offline_captured: !this.online,
      encrypted: !!key,
      iv,
      payload,
      status: "saved",
      attempts: 0,
      progress: 0,
      last_error: null,
      server_evidence_id: null,
      server_label: null,
      synced_at: null,
    };
    await store.putItem(item);
    this.emit();
    if (this.online) void this.syncAll();
    else void this.ensureReservationsLater(input.ownerUserId);
    return item;
  }

  private async ensureReservationsLater(ownerUserId: number) {
    // Top up the reservation block when the device is next online.
    const off = this.subscribe(() => {
      if (this.online) {
        off();
        void this.ensureReservations(ownerUserId);
      }
    });
  }

  async syncAll() {
    if (this.syncing || !this.online) return;
    // Only candidates own an evidence queue; assessors and admins never sync or reserve numbers.
    let ownerId: number | null = null;
    try {
      const raw = localStorage.getItem("kp.user");
      const u = raw ? JSON.parse(raw) : null;
      ownerId = u && (u.role === undefined || u.role === "candidate") ? u.id : null;
    } catch {
      ownerId = null;
    }
    if (ownerId == null) return;
    this.syncing = true;
    this.emit();
    try {
      const items = (await store.listItems(ownerId)).filter((i) => i.status === "saved" || i.status === "uploading");
      for (const item of items.reverse()) {
        if (!this.online) break;
        await this.uploadOne(item);
      }
      this.lastSyncAt = new Date().toISOString();
      await this.ensureReservations(ownerId);
    } finally {
      this.syncing = false;
      this.emit();
    }
  }

  private async uploadOne(item: QueueItem) {
    item.status = "uploading";
    item.attempts += 1;
    item.progress = 0;
    await store.putItem(item);
    this.emit();
    try {
      let plain = item.payload;
      if (item.encrypted && item.iv) {
        const key = await this.key();
        if (!key) throw new Error("Encryption key unavailable on this device");
        plain = await decrypt(key, item.iv, item.payload);
      }
      const form = new FormData();
      form.append("file", new Blob([plain], { type: item.mime_type }), item.filename);
      form.append(
        "meta",
        JSON.stringify({
          local_id: item.local_id,
          kind: item.kind,
          qualification_id: item.qualification_id,
          pc_hint_id: item.pc_hint_id,
          client_sha256: item.client_sha256 || null,
          captured_at: item.captured_at,
          latitude: item.latitude,
          longitude: item.longitude,
          accuracy_m: item.accuracy_m,
          device: item.device,
          language: item.language,
          reserved_number: item.reserved_number,
          encrypted_at_rest: item.encrypted,
          offline_captured: item.offline_captured,
          queued_at: item.queued_at,
          sync_attempts: item.attempts,
          notes: item.location_source === "demo" ? "Location: configured demo site (device location unavailable)" : null,
        }),
      );
      const ev = await uploadWithProgress<Evidence>("/evidence", form, (p) => {
        item.progress = p;
        this.emit();
      });
      item.status = "synced";
      item.progress = 100;
      item.server_evidence_id = ev.id;
      item.server_label = ev.label;
      item.synced_at = ev.synced_at ?? new Date().toISOString();
      item.last_error = ev.integrity_ok === false ? "Server hash did not match the device hash" : null;
      item.payload = new ArrayBuffer(0); // free device storage once the server holds a verified copy
      await store.putItem(item);
      this.lastError = null;
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(0, null, String(e));
      if (err.isNetwork || err.status >= 500) {
        item.status = "saved"; // stays queued; retried automatically
        item.last_error = err.message;
      } else {
        item.status = "failed";
        item.last_error = err.message;
        api.post("/sync/report", { local_id: item.local_id, outcome: "failed", attempts: item.attempts, error: err.message }).catch(() => {});
      }
      this.lastError = err.message;
      await store.putItem(item);
    }
    this.emit();
  }

  async retry(localId: string) {
    const item = await store.getItem(localId);
    if (!item) return;
    item.status = "saved";
    item.last_error = null;
    await store.putItem(item);
    this.emit();
    void this.syncAll();
  }

  async remove(localId: string) {
    await store.deleteItem(localId);
    this.emit();
  }
}

export const syncEngine = new SyncEngine();
