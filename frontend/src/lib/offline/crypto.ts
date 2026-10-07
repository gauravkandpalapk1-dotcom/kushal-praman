// At-rest protection for the offline evidence queue.
//
// The AES-GCM key is generated on the device as a NON-EXTRACTABLE CryptoKey and stored
// in IndexedDB. Script code can use it but can't read the raw key bytes. This protects
// queued evidence from casual inspection of browser storage. It does NOT protect against
// a fully compromised device or malicious script running in this origin (see docs/OFFLINE.md).

export function cryptoAvailable(): boolean {
  return typeof crypto !== "undefined" && !!crypto.subtle && (typeof isSecureContext === "undefined" || isSecureContext);
}

export async function sha256Hex(data: ArrayBuffer): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export async function generateQueueKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
}

export async function encrypt(key: CryptoKey, data: ArrayBuffer): Promise<{ iv: Uint8Array<ArrayBuffer>; ciphertext: ArrayBuffer }> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, data);
  return { iv, ciphertext };
}

export async function decrypt(key: CryptoKey, iv: Uint8Array<ArrayBuffer>, ciphertext: ArrayBuffer): Promise<ArrayBuffer> {
  return crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ciphertext);
}
