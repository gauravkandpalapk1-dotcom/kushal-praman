# AI Architecture

> **AI finds the evidence. The assessor decides what it means.**
> AI retrieves, tags and maps evidence. It never makes the competency decision.

## What the AI may and may not output

| Allowed (evidential) | Forbidden (verdict) |
|---|---|
| "Potential evidence supporting PC10 found at 00:42–01:08." | "Candidate is competent." |
| Tags: *insulated wire stripper, crimping tool, ring lug* | "Score 3/4", "should pass", "qualified", "certified" |
| Neutral segment description bound to the PC text | Any judgement of the candidate |
| `signal ∈ {supports, partial, not_found}` about the **evidence** | A score or grade of the **person** |

`ai/guardrails.py` enforces the right-hand column on every AI-written string: descriptions, summaries,
tags, rationales and statements. It covers English and Hindi verdict terms (e.g. *competent, pass, fail,
qualified, certified, N/4, सक्षम, पास, फेल*). Candidate speech transcripts are **evidence** and are never
rewritten; a transcript line that trips the guardrail is only flagged. AI schemas have no score field at
all.

## Pipeline (`backend/app/services/pipeline.py`, background thread, per-step persistence)

| # | Step | Implementation | Mode |
|---|---|---|---|
| 1 | Integrity | Recompute SHA-256 of the stored file, compare with the device hash | **REAL** always |
| 2 | Probe | `ffprobe`: duration, codec, resolution, audio | **REAL** always |
| 3 | Segmentation | `ffmpeg select='gt(scene,0.15)'` → contiguous segments; 30 s windows as fallback | **REAL** always |
| 4 | Speech-to-text | `ai/speech.py`: faster-whisper / IndicWhisper adapter → timestamped, language-tagged lines | REAL if installed · DEMO for the demo video · otherwise *skipped (unavailable)* |
| 5 | Vision tags | `ai/vision.py`: LLM vision on keyframes per segment | REAL with an API key · DEMO · *skipped* |
| 6 | OCR | `ai/ocr.py`: Tesseract for photos/documents | REAL if installed · *not applicable to video* |
| 7 | LLM description | `ai/llm.py`: Claude (`claude-sonnet-5-5`) or Gemini, JSON-only neutral descriptions + summary | REAL with an API key · DEMO · *skipped* |
| 8 | Evidence Mapper | `ai/mapper.py`: ranks (segment × PC) | REAL lexical baseline · DEMO for the demo video |

Each step stores `status`, `mode (real|demo|unavailable)`, `provider`, `model` and `detail` in
`ai_analyses`, and the UI badges each one. **Unavailable services are skipped, never simulated.**

## Evidence Mapper

```
for each segment s, for each PC p in the evidence's qualification:
    text(s)  = transcript lines in s (+ English translation) + vision tags + LLM description
    score    = lexical relevance(text(s), PC text + curated PC keywords incl. Hindi/Hinglish terms)
rank → top segment(s) per PC above a threshold → EvidenceMapping(status=pending)
statement = "Potential evidence supporting {PC} found at {mm:ss}–{mm:ss}."
```

- The score is an **uncalibrated relevance score in [0, 1], not a probability** and not a judgement of
  the candidate. The UI says so wherever it's shown.
- The baseline is deliberately simple and explainable (term overlap with the official PC wording). The
  planned upgrade is multilingual embeddings in pgvector, plus LLM re-ranking constrained to the PC
  text.
- Every mapping is a **proposal**. The assessor confirms, edits (PC or time range) or rejects it, and the
  original is preserved in the audit log.

## Two tiers of output (assessor-first, Buçinca et al. [5])

| Tier | Fields | Visible |
|---|---|---|
| 1 · Retrieval | segment, PC, statement | Before scoring (this is the time saving) |
| 2 · Interpretation | confidence, signal, rationale, tags | Only after **this assessor's** initial score for that PC is locked; enforced by the API |

The *post-reveal change rate* (final ≠ initial after AI reveal) is tracked as an over-reliance monitor.

## Demo mode vs real mode

- `KP_MODE=demo`: steps 1–3 are real. Steps 4, 5, 7 and 8 use `ai/fixtures/practical_demo.json`
  **only** when the evidence's SHA-256 equals the demo video's hash (computed at startup). All such
  output is labelled **DEMO ANALYSIS**. No external network calls are made, so the demo survives a dead
  network or an unavailable API.
- `KP_MODE=real`: only installed or configured adapters run.
- The demo's **91% confidence is seeded**, not produced by a model. Say so if asked.

## Why the AI is this narrow

- Video skill scoring has strong results in **narrow, structured** domains (Funke et al. 2019 [6]), and
  action quality assessment is segment-level and domain-specific (Wang et al. 2022 [7]). That doesn't
  generalise to judging competency across trades.
- LLM judges show systematic biases (Zheng et al. 2023 [10]). We use LLMs as describers, never judges.
- Explanations alone don't prevent over-reliance (Buçinca et al. 2021 [5]), hence assessor-first.

## Known limitations / failure modes

| Failure mode | Effect | Mitigation |
|---|---|---|
| Noisy site audio, code-switching | ASR errors → missed keyword matches | Transcript shown as evidence, not truth; assessor watches the clip; IndicWhisper benchmarked on Vistaar [9] |
| Camera angle hides hands/tools | No tags → no mapping | "No segment proposed" is explicit; the assessor reviews the full recording |
| Lexical mapper misses paraphrase | False negatives | Embedding upgrade; assessor can add/edit mappings |
| Over-trust in the relevance score | Anchoring | Tier-2 lock; uncalibrated label; change-rate monitor |
| LLM verdict leakage | Competency language in descriptions | Guardrail + JSON-only prompts; unit-tested |
| Synthetic demo media | Not real evidence | Watermarked; replace before the finale (`DEMO.md`) |

## Evaluation plan (pilot)

1. **Retrieval:** segment-level recall/precision of surfaced segments vs assessor-marked segments per PC.
2. **Calibration:** reliability diagram of relevance scores vs assessor confirm/reject decisions.
3. **Human-AI:** post-reveal change rate, and agreement (weighted κ) with vs without AI support.
4. **Efficiency:** assessor minutes per candidate vs full-replay baseline.
5. **ASR:** WER on a held-out set of site recordings per language.

None of these numbers exist yet. The product reports *pilot measurement underway* until they do.
