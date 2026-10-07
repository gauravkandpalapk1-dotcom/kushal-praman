import { beforeEach, describe, expect, it, vi } from "vitest";
import { IDBFactory } from "fake-indexeddb";
import { decrypt, encrypt, generateQueueKey, sha256Hex } from "./crypto";

// The sync engine talks to the API only through these two functions.
const uploadWithProgress = vi.fn();
const post = vi.fn();
vi.mock("../api", () => {
  class ApiError extends Error {
    constructor(public status: number, public code: string | null, message: string) {
      super(message);
    }
    get isNetwork() {
      return this.status === 0;
    }
  }
  return { ApiError, uploadWithProgress: (...a: unknown[]) => uploadWithProgress(...a), api: { post: (...a: unknown[]) => post(...a) } };
});

const enc = new TextEncoder();
const OWNER = 7;

async function freshEngine() {
  vi.resetModules();
  globalThis.indexedDB = new IDBFactory(); // isolated database per test
  const store = await import("./store");
  store.__resetDbForTests();
  const { syncEngine } = await import("./sync");
  return { store, syncEngine };
}

beforeEach(() => {
  uploadWithProgress.mockReset();
  post.mockReset().mockResolvedValue({ numbers: [] });
  localStorage.clear();
  localStorage.setItem("kp.user", JSON.stringify({ id: OWNER }));
});

describe("crypto", () => {
  it("computes the SHA-256 test vector for 'abc'", async () => {
    expect(await sha256Hex(enc.encode("abc").buffer as ArrayBuffer)).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
  it("round-trips AES-GCM with a non-extractable key", async () => {
    const key = await generateQueueKey();
    expect(key.extractable).toBe(false);
    const plain = enc.encode("evidence #17").buffer as ArrayBuffer;
    const { iv, ciphertext } = await encrypt(key, plain);
    expect(new Uint8Array(ciphertext)).not.toEqual(new Uint8Array(plain));
    expect(new TextDecoder().decode(await decrypt(key, iv, ciphertext))).toBe("evidence #17");
  });
});

describe("offline capture → sync", () => {
  it("saves encrypted with a reserved evidence number while offline, then syncs when back online", async () => {
    const { store, syncEngine } = await freshEngine();
    syncEngine.setSimulatedOffline(true);
    await store.setReservations(OWNER, [17, 18]);

    const bytes = enc.encode("ten minute practical");
    const item = await syncEngine.capture({
      ownerUserId: OWNER,
      blob: new Blob([bytes], { type: "video/mp4" }),
      filename: "practical.mp4",
      kind: "video",
      qualificationId: 1,
      location: { latitude: 30.3165, longitude: 78.0322, accuracy_m: 10, source: "device" },
    });

    expect(item.reserved_number).toBe(17);
    expect(item.status).toBe("saved");
    expect(item.offline_captured).toBe(true);
    expect(item.encrypted).toBe(true);
    expect(item.client_sha256).toBe(await sha256Hex(bytes.buffer as ArrayBuffer));
    expect(new Uint8Array(item.payload)).not.toEqual(bytes);
    expect(await store.getReservations(OWNER)).toEqual([18]);
    expect(uploadWithProgress).not.toHaveBeenCalled();

    uploadWithProgress.mockImplementation(async (_path: string, form: FormData) => {
      const meta = JSON.parse(String(form.get("meta")));
      const file = form.get("file") as Blob;
      // Server receives the decrypted plaintext with the device hash and reserved number.
      expect(meta.reserved_number).toBe(17);
      expect(meta.offline_captured).toBe(true);
      expect(await sha256Hex(await file.arrayBuffer())).toBe(meta.client_sha256);
      return { id: 5, label: "Evidence #17", integrity_ok: true, synced_at: "2026-10-07T09:00:00Z" };
    });
    syncEngine.setSimulatedOffline(false);
    await vi.waitFor(async () => expect((await store.getItem(item.local_id))?.status).toBe("synced"));

    const synced = (await store.getItem(item.local_id))!;
    expect(synced.server_label).toBe("Evidence #17");
    expect(synced.payload.byteLength).toBe(0); // device copy freed after verified upload
  });

  it("keeps the item queued after a dropped connection and retries later", async () => {
    const { store, syncEngine } = await freshEngine();
    const { ApiError } = await import("../api");
    syncEngine.setSimulatedOffline(true);
    const item = await syncEngine.capture({
      ownerUserId: OWNER,
      blob: new Blob([enc.encode("photo")], { type: "image/jpeg" }),
      filename: "p.jpg",
      kind: "photo",
      qualificationId: 1,
    });

    uploadWithProgress.mockRejectedValueOnce(new ApiError(0, "network", "Connection lost during upload"));
    syncEngine.setSimulatedOffline(false);
    await vi.waitFor(async () => expect((await store.getItem(item.local_id))?.attempts).toBe(1));
    await vi.waitFor(() => expect(syncEngine.isSyncing).toBe(false));
    const after = (await store.getItem(item.local_id))!;
    expect(after.status).toBe("saved");
    expect(after.last_error).toMatch(/Connection lost/);

    uploadWithProgress.mockResolvedValueOnce({ id: 6, label: "Evidence #18", integrity_ok: true, synced_at: null });
    await syncEngine.syncAll();
    expect((await store.getItem(item.local_id))?.status).toBe("synced");
    expect((await store.getItem(item.local_id))?.attempts).toBe(2);
  });

  it("marks a server rejection as failed and reports it", async () => {
    const { store, syncEngine } = await freshEngine();
    const { ApiError } = await import("../api");
    uploadWithProgress.mockRejectedValueOnce(new ApiError(415, "unsupported_type", "File type not allowed"));
    const item = await syncEngine.capture({
      ownerUserId: OWNER,
      blob: new Blob([enc.encode("x")], { type: "application/zip" }),
      filename: "x.zip",
      kind: "document",
      qualificationId: 1,
    });
    await vi.waitFor(async () => expect((await store.getItem(item.local_id))?.status).toBe("failed"));
    expect(post).toHaveBeenCalledWith("/sync/report", expect.objectContaining({ local_id: item.local_id, outcome: "failed" }));
  });
});
