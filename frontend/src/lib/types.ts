// Types mirror docs/API.md — the backend contract.

export type Role = "candidate" | "assessor" | "admin";
export type Mode = "real" | "demo";

export interface Agency { id: number; name: string; code: string }

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  candidate: {
    id: number;
    candidate_code: string;
    qualification_id: number | null;
    preferred_language: string | null;
    district: string | null;
  } | null;
  assessor: { id: number; assessor_code: string; agency: Agency | null } | null;
}

export interface TokenOut { access_token: string; token_type: string; expires_in: number; user: User }

export interface RubricLevel { score: number; descriptor: string; exemplar: string | null }
export interface Rubric {
  id: number;
  version: number;
  status: "draft" | "validated";
  author_note?: string | null;
  levels: RubricLevel[];
}

export interface PC {
  id: number;
  code: string;
  text: string;
  is_verbatim: boolean;
  source_note: string | null;
  max_marks: number;
  rubric: Rubric | null;
}

export interface NOS {
  id: number;
  code: string;
  title: string;
  version?: string | null;
  is_mandatory?: boolean;
  pcs?: PC[];
}

export interface Qualification {
  id: number;
  title: string;
  nqr_code: string;
  nsqf_level: number;
  sector_skill_council?: string | null;
  version?: string | null;
  assessment_mode?: string | null;
  source_ref?: number | null;
  nos_count?: number;
  pc_count?: number;
}

export interface QualificationTree { qualification: Qualification; nos: (NOS & { pcs: PC[] })[] }

export type EvidenceKind = "video" | "photo" | "audio" | "document";
export type EvidenceStatus = "received" | "processing" | "ready" | "failed";

export interface EvidenceMeta {
  latitude: number | null;
  longitude: number | null;
  accuracy_m: number | null;
  device: string | null;
  duration_s: number | null;
  width: number | null;
  height: number | null;
  language: string | null;
}

export interface Evidence {
  id: number;
  display_number: number;
  label: string;
  kind: EvidenceKind;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  client_sha256: string | null;
  integrity_ok: boolean | null;
  status: EvidenceStatus;
  is_demo: boolean;
  offline_captured: boolean;
  encrypted_at_rest: boolean;
  captured_at: string | null;
  synced_at: string | null;
  qualification_id: number | null;
  candidate: { id: number; full_name: string; candidate_code: string };
  metadata: EvidenceMeta | null;
  media_url: string;
}

export type StepStatus = "pending" | "running" | "done" | "skipped" | "failed";
export interface ProcessingStep {
  key: string;
  label: string;
  status: StepStatus;
  mode: "real" | "demo" | "unavailable" | null;
  detail: string | null;
  started_at: string | null;
  finished_at: string | null;
}
export interface Processing {
  evidence_id: number;
  status: "queued" | "running" | "done" | "failed" | "not_started";
  mode: Mode;
  started_at: string | null;
  finished_at: string | null;
  steps: ProcessingStep[];
}

export interface Segment { id: number; start_s: number; end_s: number; label: string | null; source: string | null }
export interface TranscriptLine {
  start_s: number;
  end_s: number;
  text: string;
  language?: string | null;
  translation_en?: string | null;
  mode?: string;
}
export interface Surfaced {
  mapping_id: number;
  segment_id: number;
  start_s: number;
  end_s: number;
  pc_id: number;
  pc_code: string;
  nos_code: string;
  statement: string;
  mode: Mode;
}
export interface Workspace { evidence: Evidence; segments: Segment[]; transcript: TranscriptLine[]; surfaced: Surfaced[] }

export type MappingStatus = "pending" | "confirmed" | "edited" | "rejected";
export interface Mapping {
  id: number;
  evidence_id: number;
  segment: { id: number; start_s: number; end_s: number } | null;
  pc: { id: number; code: string; text: string; nos: { id: number; code: string; title: string } };
  qualification?: { id: number; title: string; nqr_code: string } | null;
  statement: string;
  status: MappingStatus;
  mode: Mode;
  decided_by: string | null;
  decided_at: string | null;
  locked: boolean;
  lock_reason: string | null;
  confidence: number | null;
  rationale: string | null;
  tags: string[] | null;
}

export type AssessmentStatus = "opened" | "initial_locked" | "ai_revealed" | "finalized";
export interface Assessment {
  id: number;
  status: AssessmentStatus;
  max_score: number;
  blind: boolean;
  is_second_assessor: boolean;
  evidence: Evidence;
  candidate: { id: number; full_name: string; candidate_code: string };
  qualification: Qualification;
  nos: NOS;
  pc: PC;
  assessor: { id: number; assessor_code: string; full_name: string };
  opened_at: string;
  initial_score: number | null;
  initial_note: string | null;
  initial_locked_at: string | null;
  ai_revealed_at: string | null;
  final_score: number | null;
  final_rationale: string | null;
  finalized_at: string | null;
  score_changed: boolean | null;
  mapping: { id: number; status: MappingStatus } | null;
}

export interface AISupport {
  assessment_id: number;
  mode: Mode;
  pc: PC;
  nos: NOS;
  findings: {
    mapping_id: number;
    start_s: number;
    end_s: number;
    statement: string;
    signal: "supports" | "partial" | "not_found";
    confidence: number | null;
    rationale: string | null;
    tags: string[];
    transcript: TranscriptLine[];
  }[];
  summary: string | null;
  services: { service: string; provider: string; model: string | null; mode: string }[];
  disclaimer: string;
}

export interface AuditEntry {
  id: number;
  ts: string;
  actor: { id: number | null; name: string | null; role: string | null; code: string | null } | null;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  summary: string;
  details: Record<string, unknown> | null;
  prev_hash: string | null;
  hash: string;
}
export interface AuditVerify { ok: boolean; entries: number; head_hash: string | null; broken_at: number | null }

export interface Agreement {
  threshold: number;
  n_pairs: number;
  weighting: string;
  status: "insufficient" | "reported";
  kappa: number | null;
  kappa_linear: number | null;
  exact_agreement: number | null;
  adjacent_agreement: number | null;
  message: string;
  data_source: "demo" | "pilot" | "mixed" | "none";
  pairs: {
    evidence_label: string;
    pc_code: string;
    candidate: string;
    assessor_a: string;
    score_a: number;
    assessor_b: string;
    score_b: number;
    is_demo: boolean;
  }[];
}

export interface MetricSide { value: number | null; n: number; status?: string; min_n?: number }
export interface Metric {
  key: string;
  label: string;
  unit: string;
  definition?: string;
  pilot: MetricSide;
  demo: MetricSide;
  note?: string | null;
}
export interface Impact {
  metrics: Metric[];
  ai_influence: { post_reveal_change_rate: number | null; n: number; note: string };
  counts: Record<string, number>;
}

export interface ResearchRef {
  number: number;
  short: string;
  citation: string;
  url: string | null;
  doi?: string | null;
  category: "policy" | "research";
  what_it_says: string;
  design_decision: string;
  where_in_product: string[];
}

export interface Health {
  status: string;
  mode: Mode;
  version: string;
  time: string;
  db: { ok: boolean; engine?: string };
  storage: { ok: boolean; [k: string]: unknown };
  ffmpeg: { available: boolean; version?: string | null };
  audit_chain: { ok: boolean; entries: number };
  services: { key: string; name: string; provider: string; available: boolean; mode: string; detail?: string | null }[];
}
