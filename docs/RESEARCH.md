# Research & Design Basis

Every design decision traces to one of the ten numbered sources in our SIH deck. The same content is
served by `GET /api/v1/research` from `database/seed/research_references.json` and shown in the app at
`/research` (cards + decision matrix).

> **Use this file to answer "why did you design it this way?"** Each row names the decision and where to
> show it live.

## Research → design-decision matrix

| # | Source | What it supports | Decision in the product | Show it live |
|---|---|---|---|---|
| 1 | NCVET (2023). *Guidelines for RPL* | Video + geotag evidence; PC-wise reporting; candidates lose wages attending | Build **on** existing evidence; capture timestamp/geotag/hash; PC-wise record; capture near the worksite | Capture screen metadata; Assessment Record |
| 2 | ILO (2026). *From Experience to Opportunity*, doi:10.54394/00034676 | Inconsistent standards weaken trust; too few assessors | Measure consistency (blind double-scoring → weighted κ); cut review time by surfacing the segment | Admin → Agreement; Impact metrics |
| 3 | DigiLocker NAD, nad.digilocker.gov.in/skill | Skill certificates already flow digitally | Record → Awarding Body → existing ecosystem. **DigiLocker shown as existing, NOT integrated** | Trace screen output chain |
| 4 | NQR (2025). Q-File: Assistant Electrician, QG-03-IS-03883-2025-V2-IISSSC | Official QP → NOS → PC; assessment mode Offline | Data model = official hierarchy; PC10 stored verbatim; offline-first matches the QP | Mapper chain; Admin → Qualifications |
| 5 | Buçinca, Malaya & Gajos (2021). *To Trust or to Think*. ACM CSCW, doi:10.1145/3449287 | Explanations alone don't stop over-reliance; deciding first (cognitive forcing) helps | **Assessor-first**: interpretive AI locked until the initial score is locked, **server-enforced (409)**; post-reveal change rate monitored | Assess screen; Swagger `ai-support` 409; Impact → over-reliance monitor |
| 6 | Funke et al. (2019). Video-based surgical skill assessment, IJCARS 14(7) | Video skill scoring works in narrow, structured domains | AI only finds/tags/segments/flags; never scores; competency-language guardrail | AI panel disclaimer; Jury → AI role |
| 7 | Wang et al. (2022). Survey of video-based action quality assessment | AQA is action/segment-level and domain-specific | Segment-level anchoring (00:42–01:08) via scene detection | Workspace timeline; Mapper "Video segment" node |
| 8 | Jonsson & Svingby (2007). *The use of scoring rubrics*. Educ. Res. Review 2(2) | Analytic, task-specific rubrics + exemplars + rater training improve reliability | Versioned 0–4 PC rubric shown at scoring time; exemplar slot; `draft` until validated | Assess screen rubric; Admin rubric editor |
| 9 | Bhogale et al. (2023). *Vistaar*, Interspeech, doi:10.21437/Interspeech.2023-2589 | Indian-language ASR benchmarks + open models (IndicWhisper) | Swappable ASR adapter returning timestamped, language-tagged segments | Workspace transcript; Status → AI services |
| 10 | Zheng et al. (2023). *Judging LLM-as-a-Judge*, NeurIPS D&B | LLM judges show position/verbosity/self-enhancement bias | LLM limited to structured neutral description; never a judge; guardrail; human final decision | `ai/llm.py`, `ai/guardrails.py` |

## Honest limitations of how we use these sources

- **[2] ILO (2026)** is cited for the problem framing as summarised in our deck. Before the finale,
  re-check the exact wording of the claims we attribute to it against the report.
- **[5]** shows forcing functions reduce over-reliance *in their experimental tasks*. It doesn't prove
  our specific RPL workflow avoids anchoring. That's why we log the post-reveal change rate and treat it
  as a pilot measurement.
- **[5]** also found forcing functions were rated *less pleasant*. We accept that friction knowingly,
  and it's a fair jury question.
- **[6][7]** are cited to *limit* our CV claims, not to support them.
- **[8]** supports rubric use. Our PC10 rubric descriptors are **team-drafted**, not from the Q-File,
  and must be validated with SSC-certified assessors.
- The 91% confidence in the demo is **seeded DEMO ANALYSIS**, not a model output. Real-mode scores are
  uncalibrated relevance scores, and calibration against assessor confirmations is part of the pilot.

## Validation plan (from slide 6)

Two assessors · same PC10 recordings · same PC-level rubric · blind to each other → weighted Cohen's κ
(quadratic). κ is reported only from **n ≥ 30** double-scored decisions (`KAPPA_MIN_PAIRS`). Until
then the product says **"Pilot measurement underway."** The implementation is unit-tested against
scikit-learn's `cohen_kappa_score`.
