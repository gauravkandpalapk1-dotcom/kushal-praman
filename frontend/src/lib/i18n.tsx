"use client";

import { useCallback, useSyncExternalStore } from "react";

// Candidate-facing labels in simple language. Assessor/admin screens stay in English
// (technical vocabulary of the QP/NOS/PC standards).
const STRINGS = {
  en: {
    namaste: "Namaste",
    myQualification: "My qualification",
    capture: "Capture evidence",
    captureSub: "Record your work as you normally do it. We link it to the right criterion.",
    video: "Video",
    photo: "Photo",
    voice: "Voice",
    document: "Document",
    record: "Record",
    choose: "Choose file",
    stop: "Stop & save",
    queue: "On this device",
    queueSub: "Saved evidence waits here until there is signal.",
    savedLocally: "Saved locally (encrypted)",
    waiting: "Waiting for connection",
    uploading: "Uploading",
    synced: "Synced",
    hashOk: "Hash verified by server",
    processing: "Processing",
    ready: "Ready for assessment",
    queuedForAssessor: "With the assessor",
    failed: "Not accepted",
    syncNow: "Sync now",
    retry: "Retry",
    noSignal: "No signal: evidence is safe on this phone",
    online: "Online",
    offline: "Offline",
    fieldSim: "Field simulation: no signal",
    location: "Location",
    time: "Time",
    hash: "Fingerprint (SHA-256)",
    noItems: "Nothing waiting. Captured evidence appears here.",
    submitted: "Submitted evidence",
    criteria: "What the assessor looks for",
    saveDevice: "Save to device",
    capturedAuto: "Captured automatically",
    saveNote: "Saved encrypted on this device first. It uploads automatically when there is signal.",
  },
  hi: {
    namaste: "नमस्ते",
    myQualification: "मेरी योग्यता",
    capture: "साक्ष्य दर्ज करें",
    captureSub: "अपना काम वैसे ही रिकॉर्ड करें जैसे आप करते हैं। हम इसे सही मानदंड से जोड़ेंगे।",
    video: "वीडियो",
    photo: "फ़ोटो",
    voice: "आवाज़",
    document: "दस्तावेज़",
    record: "रिकॉर्ड करें",
    choose: "फ़ाइल चुनें",
    stop: "रोकें और सहेजें",
    queue: "इस फ़ोन पर",
    queueSub: "सिग्नल आने तक साक्ष्य यहीं सुरक्षित रहता है।",
    savedLocally: "फ़ोन पर सुरक्षित (एन्क्रिप्टेड)",
    waiting: "कनेक्शन का इंतज़ार",
    uploading: "अपलोड हो रहा है",
    synced: "भेज दिया गया",
    hashOk: "सर्वर ने हैश जाँचा",
    processing: "जाँच जारी",
    ready: "मूल्यांकन के लिए तैयार",
    queuedForAssessor: "मूल्यांकनकर्ता के पास",
    failed: "स्वीकार नहीं हुआ",
    syncNow: "अभी भेजें",
    retry: "फिर कोशिश करें",
    noSignal: "सिग्नल नहीं है: साक्ष्य फ़ोन पर सुरक्षित है",
    online: "ऑनलाइन",
    offline: "ऑफ़लाइन",
    fieldSim: "फ़ील्ड सिमुलेशन: सिग्नल नहीं",
    location: "स्थान",
    time: "समय",
    hash: "फ़िंगरप्रिंट (SHA-256)",
    noItems: "कुछ भी बाकी नहीं। दर्ज साक्ष्य यहाँ दिखेगा।",
    submitted: "भेजे गए साक्ष्य",
    criteria: "मूल्यांकनकर्ता क्या देखेंगे",
    saveDevice: "फ़ोन में सहेजें",
    capturedAuto: "अपने-आप दर्ज जानकारी",
    saveNote: "पहले इसी फ़ोन पर एन्क्रिप्ट करके सहेजा जाता है। सिग्नल आते ही अपने-आप अपलोड होगा।",
  },
} as const;

export type Lang = keyof typeof STRINGS;
export type StrKey = keyof (typeof STRINGS)["en"];
const KEY = "kp.lang";

const listeners = new Set<() => void>();
function readStored(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export function useI18n(defaultLang?: string | null) {
  // Server render has no storage → null; the client then reads the stored choice without a mismatch.
  const stored = useSyncExternalStore(subscribe, readStored, () => null);
  const pick = stored ?? defaultLang;
  const lang: Lang = pick === "hi" || pick === "en" ? pick : "en";
  const setLang = useCallback((l: Lang) => {
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
    listeners.forEach((f) => f());
  }, []);
  /** Primary label, plus the English label as a subtitle when the UI is in Hindi. */
  const t = useCallback((k: StrKey) => STRINGS[lang][k], [lang]);
  const tEn = useCallback((k: StrKey) => STRINGS.en[k], []);
  return { lang, setLang, t, tEn };
}

export function LangToggle({ lang, setLang }: { lang: Lang; setLang: (l: Lang) => void }) {
  return (
    <div className="inline-flex rounded-lg bg-cream-200 p-0.5 text-sm font-semibold" role="group" aria-label="Language">
      {(["hi", "en"] as const).map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={`h-8 rounded-md px-3 ${lang === l ? "bg-white text-navy-900 shadow-sm" : "text-navy-600"}`}
        >
          {l === "hi" ? "हिं" : "EN"}
        </button>
      ))}
    </div>
  );
}
