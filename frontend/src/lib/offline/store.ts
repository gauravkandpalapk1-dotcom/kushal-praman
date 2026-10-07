// IndexedDB persistence for the offline evidence queue.
import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { EvidenceKind } from "../types";

export type QueueStatus = "saved" | "uploading" | "synced" | "failed";

export interface QueueItem {
  local_id: string;
  owner_user_id: number;
  reserved_number: number | null;
  kind: EvidenceKind;
  filename: string;
  mime_type: string;
  size_bytes: number;
  client_sha256: string;
  captured_at: string;
  queued_at: string;
  latitude: number | null;
  longitude: number | null;
  accuracy_m: number | null;
  location_source: "device" | "demo" | null;
  device: string;
  language: string | null;
  qualification_id: number | null;
  pc_hint_id: number | null;
  offline_captured: boolean;
  encrypted: boolean;
  iv: Uint8Array<ArrayBuffer> | null;
  payload: ArrayBuffer; // ciphertext when encrypted, else plaintext
  status: QueueStatus;
  attempts: number;
  progress: number;
  last_error: string | null;
  server_evidence_id: number | null;
  server_label: string | null;
  synced_at: string | null;
}

interface KPDB extends DBSchema {
  queue: { key: string; value: QueueItem; indexes: { by_owner: number } };
  keys: { key: string; value: CryptoKey };
  reservations: { key: number; value: { owner_user_id: number; numbers: number[] } };
}

let dbPromise: Promise<IDBPDatabase<KPDB>> | null = null;

export function db() {
  if (!dbPromise) {
    dbPromise = openDB<KPDB>("kaushal-pramaan", 1, {
      upgrade(d) {
        const q = d.createObjectStore("queue", { keyPath: "local_id" });
        q.createIndex("by_owner", "owner_user_id");
        d.createObjectStore("keys");
        d.createObjectStore("reservations");
      },
    });
  }
  return dbPromise;
}

export async function putItem(item: QueueItem) {
  await (await db()).put("queue", item);
}
export async function getItem(localId: string) {
  return (await db()).get("queue", localId);
}
export async function listItems(ownerId: number) {
  const items = await (await db()).getAllFromIndex("queue", "by_owner", ownerId);
  return items.sort((a, b) => b.queued_at.localeCompare(a.queued_at));
}
export async function deleteItem(localId: string) {
  await (await db()).delete("queue", localId);
}

export async function getKey(name: string) {
  return (await db()).get("keys", name);
}
export async function putKey(name: string, key: CryptoKey) {
  await (await db()).put("keys", key, name);
}

export async function getReservations(ownerId: number): Promise<number[]> {
  return (await (await db()).get("reservations", ownerId))?.numbers ?? [];
}
export async function setReservations(ownerId: number, numbers: number[]) {
  await (await db()).put("reservations", { owner_user_id: ownerId, numbers }, ownerId);
}

/** Test hook: lets unit tests reset the singleton between fake-indexeddb instances. */
export function __resetDbForTests() {
  dbPromise = null;
}
