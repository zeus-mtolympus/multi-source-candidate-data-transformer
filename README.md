# Multi-Source Candidate Data Transformer

A two-stage ETL pipeline that ingests candidate data from multiple sources (CSV, plain-text resumes, GitHub JSON), resolves duplicates, merges fields with conflict tracking and provenance, scores confidence, and projects the canonical profile to any runtime-configured output shape.

Built for the Eightfold Engineering Intern (Jul–Dec 2026) assignment.

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Stage 1: build canonical profiles from all sources
python orchestrator.py --stage stage1

# 3. Stage 2: project to a specific output config
python orchestrator.py --stage stage2 --config configs/default_full.json

# 4. Both stages in one command
python orchestrator.py --stage all --config configs/default_full.json
```

Run Stage 2 for all included configs:

```bash
python orchestrator.py --stage stage2 --config configs/default_full.json
python orchestrator.py --stage stage2 --config configs/minimal_ats.json
python orchestrator.py --stage stage2 --config configs/display_export.json
python orchestrator.py --stage stage2 --config configs/strict_required_linkedin.json
python orchestrator.py --stage stage2 --config configs/optional_strict_on_missing_error.json
```

---

## Pipeline Overview

```
recruiter_data.csv
resume/*.txt            --> source_loader   (load files, track failures)
github/*.json                    |
                                 v
                             parser          (parse GitHub JSON)
                                 |
                                 v
                         field_extractor     (extract tagged values from each source)
                                 |
                                 v
                          normalizer         (E.164, ISO-3166, canonical skills, https://)
                                 |
                                 v
                        entity_resolver      (exact-email deduplication)
                                 |
                                 v
                         merge_engine        (source-priority merge, provenance, conflict tracking)
                                 |
                                 v
                  confidence_calculator      (per-field + overall confidence + match_confidence)
                                 |
                                 v
                   canonical_profiles.json  <-- Stage 1 output (38 profiles)
                                 |
                                 v
                      projection_engine      (config-driven field reshape)
                                 |
                                 v
                       schema_validator      (type and required-field validation)
                                 |
                                 v
                      output/*_output.json  <-- Stage 2 output
```

---

## Outputs

| File | Description |
|------|-------------|
| `canonical_profiles.json` | Stage 1: 38 canonical profiles (from 42 CSV rows after 4 duplicate collapses) |
| `output/default_full_output.json` | All fields + per-field confidence + provenance |
| `output/minimal_ats_output.json` | 5-field ATS format, missing fields omitted |
| `output/display_export_output.json` | Human-readable display format |
| `output/strict_required_linkedin_output.json` | Only candidates with a LinkedIn URL (35/38) |
| `output/optional_strict_on_missing_error_output.json` | Requires portfolio URL, errors on missing (11/38) |

---

## Stage 2 Configs

| Config | Fields | `on_missing` | Confidence | Provenance | Pass / Total |
|--------|--------|-------------|-----------|-----------|-------------|
| `default_full.json` | 21 (all fields) | null | yes | yes | 38 / 38 |
| `minimal_ats.json` | 5 | omit | no | no | 38 / 38 |
| `display_export.json` | 5 (display-formatted) | null | no | no | 38 / 38 |
| `strict_required_linkedin.json` | 3, linkedin required | null | no | no | 35 / 38 |
| `optional_strict_on_missing_error.json` | 3, portfolio on_missing=error | error | no | no | 11 / 38 |
| `broken_type_mismatch.json` | intentionally invalid | — | — | — | rejected at config validation |

The broken config uses a wildcard `from` expression (`skills[].name`) with a scalar type (`string`). `validate_config()` raises `ValueError` before any candidate is processed.

---

## Canonical Profile Schema

| Field | Type | Notes |
|-------|------|-------|
| `candidate_id` | `string` | `cand_` + SHA-256(primary email)[:12]. Deterministic — same inputs produce the same ID. |
| `full_name` | `string \| null` | Source priority: CSV > Resume > GitHub |
| `emails` | `string[]` | Lowercased, deduped across all sources |
| `phones` | `string[]` | E.164 format (e.g. `+919876543210`) |
| `location` | `{city, region, country}` | `country` is ISO-3166 alpha-2 (e.g. `"IN"`) |
| `links` | `{linkedin, github, portfolio, other[]}` | All normalised to `https://` |
| `headline` | `string \| null` | Derived from `experience[0]` as `"Title at Company"` when not in CSV |
| `years_experience` | `number \| null` | Derived from earliest resume start date when not in CSV |
| `skills` | `[{name, confidence, sources[]}]` | Canonical names, sorted by confidence descending |
| `experience` | `[{company, title, start, end, summary}]` | Dates as `YYYY-MM`, sorted most-recent-first (`end: null` = current role) |
| `education` | `[{institution, degree, field, end_year}]` | |
| `certifications` | `[{name, year}]` | Extracted from resume Certifications section; `year` is null if not stated |
| `provenance` | `[{field, source, method, value, role}]` | Every populated field is traceable. `role` is `primary` or `conflicting_alternate`. |
| `overall_confidence` | `number` | 0.0–1.0 weighted sum across all key fields. Missing fields score 0.0, so enriched profiles always outrank sparse stubs. |
| `match_confidence` | `number \| null` | `1.0` if at least one enrichment source loaded successfully. `0.5` if enrichment was attempted but all files failed. `null` if no enrichment was referenced in the CSV. |
| `_meta` | object | `sources_used[]`, `sources_failed[]`, `data_quality[]`, `generated_at` |

---

## Confidence Scoring

### Field weights (must sum to 1.0)

| Field | Weight | Rationale |
|-------|--------|-----------|
| `full_name` | 0.20 | High-trust identity signal |
| `emails` | 0.20 | High-trust identity signal |
| `phones` | 0.08 | Lower weight — often shared or work numbers |
| `location` | 0.07 | Useful but not critical for matching |
| `headline` | 0.07 | Often recycled / generic |
| `years_experience` | 0.08 | Key matching signal |
| `skills` | 0.10 | Core matching signal |
| `experience` | 0.12 | Most discriminating matching signal |
| `education` | 0.08 | Important for level matching |

**All fields always appear in the denominator.** Before this design, a CSV-only stub with only name+email scored 0.90 (higher than a fully enriched profile at 0.88), because missing fields were excluded from the weighted average. Now:

- Fully enriched (skills, experience, education): 0.86–0.89
- CSV-only stub (name, email, maybe location): 0.54–0.81

### Base scores per (source, method)

| Source | Method | Score | Meaning |
|--------|--------|-------|---------|
| CSV | `direct` | 0.90 | Recruiter-entered, validated at source |
| GitHub | `direct` | 0.70 | API data, fairly reliable |
| Resume | `regex_extracted` | 0.65 | Regex on structured text (emails, phones, links) |
| Resume | `section_heuristic` | 0.55 | Section parsing (experience, education, certifications) |
| GitHub | `language_inferred` | 0.50 | Repo language ≠ proficiency, lowest trust |

### Corroboration bonus

When the same skill appears in more than one source: `confidence += 0.10` per additional agreeing source, capped at 1.0.

Example: Python in resume (0.65) + GitHub repos (0.50) → `max(0.65, 0.50) + 0.10 = 0.75`.

---

## Source Priority

For scalar fields (name, headline, years_experience, location, etc.) when multiple sources have different values:

**CSV beats Resume beats GitHub**

The losing value is recorded in `provenance` with `role: "conflicting_alternate"`. Nothing is silently dropped.

---

## Entity Resolution

- **Match key:** email from the CSV `email` column, lowercased, exact match.
- **Duplicate rows (same email):** collapsed into one profile. The earlier row's fields are stored in provenance as `conflicting_alternate`. `match_confidence` is reduced by 0.10 to reflect the identity uncertainty.
- **Similar names, different emails:** kept as separate profiles. Name similarity is never used for merging — it produces false positives on common names.
- **No email in CSV:** the candidate goes into a no-email bucket and participates in no deduplication. Any resume or GitHub email they have is used for their profile but not for identity resolution.

---

## Data Quality Signals

`_meta.data_quality` contains per-profile warnings:

| Warning | Condition |
|---------|-----------|
| `"no_skills"` | `skills` array is empty |
| `"no_experience"` | `experience` array is empty |
| `"no_enrichment"` | `sources_used == ["csv"]` — no resume or GitHub was loaded |

A fully enriched profile has `data_quality: []`.

---

## Edge Cases (case by case from the sample data)

### 1. Duplicate CSV rows — Priya Singh
Two rows in `recruiter_data.csv` share email `priya.singh@innovate.co.in` with different `years_experience` values (7 and 5).

**Handled:** Entity resolver collapses to one profile. The earlier row's `years_experience: 5` is stored in provenance as `conflicting_alternate`. `match_confidence` reduced from 1.0 to 0.9.

The same pattern applies to **Shruti Kapoor / Shruti R. Kapoor** and **Nikhil Verma / Nikhil R. Verma** — both pairs share an email and produce a single output profile.

### 2. Same-name, different-person pair — Vivek Singh & Vivek S. Singh
`vivek.singh@techwave.in` and `vivekssingh@techwave.in` are two distinct candidates with near-identical names.

**Handled:** Both survive as separate profiles (`cand_8fb2b5feb274` and `cand_b53a79d6c3ec`). Identity is never inferred from name similarity. This is an intentional design decision — fuzzy name matching would incorrectly merge common Indian names like Rahul Nair and Rahul K. Nair. Both candidates have `match_confidence: null` (no enrichment).

### 3. Another same-name pair — Rahul Nair & Rahul K. Nair
Two different people at different companies. Different emails.

**Handled:** Kept separate. Both are CSV-only with `data_quality: ["no_skills", "no_experience", "no_enrichment"]`.

### 4. GitHub source failure — Vikram Patel, Suresh Menon
GitHub URL present in CSV but the `github/*.json` file is missing from disk.

**Handled:** `sources_failed: ["github"]`, `match_confidence: 0.5`. Profile built from CSV only. No crash.

### 5. Resume source failure — Neha Gupta, Ravi Shankar, Lakshmi Venkatesh
Resume filename referenced in CSV but file is missing.

**Handled:** `sources_failed: ["resume"]`. Ravi Shankar falls back to CSV-only (`match_confidence: 0.5`). Neha Gupta and Lakshmi Venkatesh enrich via GitHub; Neha's `match_confidence: 1.0` because her GitHub loaded despite the resume failure.

### 6. Partial enrichment — Preeta Subramaniam
GitHub URL present but file missing; resume loads successfully.

**Handled:** `sources_failed: ["github"]`, `sources_used: ["csv", "resume"]`, `match_confidence: 1.0`. At least one enrichment source succeeded, so the candidate is considered fully resolvable.

### 7. GitHub location as free-text string — multiple candidates
GitHub API returns `"location": "Bangalore, India"` as a single string.

**Handled:** Split on the last comma → `city: "Bangalore"`, `country: "India"`. Country then normalised to ISO-3166 alpha-2 via pycountry → `"IN"`. Without this fix, the full string would be stored in `city` and `country` would always be null for GitHub-sourced locations.

### 8. Skill corroboration — Arjun Mehta, Ananya Sharma, Karan Iyer
JavaScript and Python appear in both resume text (`regex_extracted`, 0.65) and GitHub repo languages (`language_inferred`, 0.50).

**Handled:** Skills from all sources merge in `_skill_map`. Corroboration bonus applied: `max(0.65, 0.50) + 0.10 = 0.75`. These skills surface with `"sources": ["resume", "github"]` and higher confidence than single-source skills.

### 9. Reference section contacts — Deepak Malhotra
Resume contains a `References` section with a third-party recruiter's email and phone.

**Handled:** `_extract_contacts()` skips any line containing "refer" (case-insensitive). The recruiter's email `priya.hr@oldfirm.com` and phone are excluded from the candidate's profile.

### 10. Certifications in resume — 6 candidates
Arjun Mehta, Aditya Bose, Deepak Malhotra, Karan Iyer, Naveen Reddy, and Rohan Kapoor each have a `Certifications` section.

```
• AWS Certified Solutions Architect – Associate (2023)
• Certified Kubernetes Administrator (CKA)
```

**Handled:** `_parse_certifications()` strips the bullet, extracts the name, and checks if the last parenthesised group is a 4-digit year. Abbreviations like `(CKA)` are kept in the name, not parsed as a year. Result: `[{"name": "AWS Certified Solutions Architect – Associate", "year": 2023}, {"name": "Certified Kubernetes Administrator (CKA)", "year": null}]`.

### 11. URL normalisation — resume-extracted links
Resume text may contain LinkedIn or GitHub URLs without the `https://` scheme: `linkedin.com/in/arjunmehta`.

**Handled:** `normalize_url()` prepends `https://` if no scheme is present, making all links valid absolute URLs regardless of source.

### 12. Email case normalisation
The same email may appear in different cases across sources.

**Handled:** All emails are lowercased before deduplication and storage. Entity resolution also uses the lowercased value, so case differences never create duplicate profiles.

### 13. Headline and years_experience derivation
Some candidates have no `headline` or `years_experience` in the CSV.

**Handled:**
- `headline` is derived as `"Title at Company"` from `experience[0]` when absent from all sources. Recorded in provenance with `method: "derived"`.
- `years_experience` is computed from the earliest start date in parsed experience entries when the CSV value is missing. Also recorded as derived.
- Neither derivation overwrites a value that came from CSV.

### 14. CSV-only candidates — 14 profiles
14 candidates have no `resume_file` and no `github_url` in the CSV.

**Handled:** Schema-valid output with `skills: []`, `experience: []`, `education: []`, `certifications: []`. `overall_confidence` correctly reflects the sparse data (0.54–0.81) because missing fields contribute 0.0 to the weighted sum. `data_quality: ["no_skills", "no_experience", "no_enrichment"]` signals this to downstream consumers.

---

## Running Tests

Stage 1 integration tests load `canonical_profiles.json`; Stage 2 integration tests load `output/*.json`. Generate them first:

```bash
# Generate outputs (Stage 1 + all Stage 2 configs)
python orchestrator.py --stage stage1
python orchestrator.py --stage stage2 --config configs/default_full.json
python orchestrator.py --stage stage2 --config configs/minimal_ats.json
python orchestrator.py --stage stage2 --config configs/display_export.json
python orchestrator.py --stage stage2 --config configs/strict_required_linkedin.json
python orchestrator.py --stage stage2 --config configs/optional_strict_on_missing_error.json

# Run all 143 tests
python -m pytest tests/ -v
```

Test breakdown: 10 test files, 143 tests — unit tests for each module plus integration tests covering the full pipeline end-to-end on the sample data.

---

## Project Structure

```
candidate_data/
├── pipeline/
│   ├── config.py                     field weights, base confidence scores, file-name constants
│   ├── stage1/
│   │   ├── source_loader.py          load CSV rows; attach resume and GitHub raw content
│   │   ├── parser.py                 parse GitHub JSON
│   │   ├── field_extractor.py        extract tagged values from CSV, resume text, GitHub
│   │   ├── normalizer.py             E.164, ISO-3166, canonical skills, URL normalisation
│   │   ├── entity_resolver.py        exact-email deduplication
│   │   ├── merge_engine.py           source-priority merge, provenance, conflict tracking
│   │   ├── confidence_calculator.py  per-field + overall confidence + match_confidence
│   │   └── stage1.py                 orchestrates Stage 1; writes canonical_profiles.json
│   └── stage2/
│       ├── projection_engine.py      config-driven field projection (path, from, normalize, limit)
│       ├── schema_validator.py       config validation + per-field type checking
│       └── stage2.py                 orchestrates Stage 2; writes output/*_output.json
├── tests/
│   ├── test_normalizer.py
│   ├── test_field_extractor.py
│   ├── test_merge_engine.py
│   ├── test_confidence_calculator.py
│   ├── test_entity_resolver.py
│   ├── test_parser.py
│   ├── test_projection_engine.py
│   ├── test_schema_validator.py
│   ├── test_source_loader.py
│   ├── test_stage1_integration.py    requires canonical_profiles.json
│   └── test_stage2_integration.py    requires output/*.json
├── configs/
│   ├── default_full.json
│   ├── minimal_ats.json
│   ├── display_export.json
│   ├── strict_required_linkedin.json
│   ├── optional_strict_on_missing_error.json
│   └── broken_type_mismatch.json
├── resume/                           candidate resume files (*.txt, UTF-8)
├── github/                           candidate GitHub API snapshots (*.json)
├── output/                           Stage 2 outputs (generated)
├── recruiter_data.csv
├── canonical_profiles.json           Stage 1 output (generated)
├── orchestrator.py
├── requirements.txt
└── README.md
```

---

## Assumptions

1. Resume files are named `{csv_name}_resume.txt` where `csv_name` matches the CSV `name` column exactly (case-sensitive). A mismatch silently marks the resume as a failed source.
2. GitHub JSON files follow the same convention: `{csv_name}_github.json`.
3. Email is the sole entity-resolution key. No phone-based or name-based matching is performed.
4. Source priority for scalar field conflicts: **CSV > Resume > GitHub**.
5. Phone numbers without a country code are assumed to be Indian (+91). Configurable in `pipeline/config.py` via `PHONE_DEFAULT_REGION`.
6. All input files are UTF-8 encoded.
7. Resumes are plain-text (`.txt`), one page, with standard section headers (`Experience`, `Education`, `Skills`, `Certifications`, etc.).
8. The CSV `name` column is always populated (nameless rows are not handled).
9. One batch run processes all candidates in the CSV together — no incremental or delta processing.
10. The GitHub `blog` field is treated as the candidate's portfolio URL.

---

## Deliberately Descoped

Per the Eightfold assignment: *"note assumptions and anything descoped."*

| Item | Reason |
|------|--------|
| PDF / DOCX resume parsing | Requires `python-docx` / `pdfminer`; only `.txt` resumes are handled |
| LinkedIn profile URL | Requires authentication; no public REST API available |
| ATS JSON blob (alternative structured source) | CSV satisfies the structured-source requirement |
| Recruiter notes (`.txt` free text) | Optional unstructured source; not selected |
| Fuzzy / probabilistic entity resolution | Name similarity causes false positives on common Indian names; email-exact is safer |
| Incremental / delta reprocessing | Full re-run each time; no diff against a previous run's output |
| LLM / ML extraction | All extraction is deterministic (regex + section heuristics) |
| Retroactive un-merging | Once two rows merge, the merge is permanent in this run |
| Portfolio URL extraction from resume body | Free-form URL patterns produce too many false positives (documentation links, company pages) |
| Gender / demographic inference | Eightfold's platform is explicitly skills-first and removes demographic signals from hiring decisions; no demographic data exists in any source |
| Seniority level inference | Derivable from `years_experience` by the consumer; including an unverified `senior` / `mid` label here would be misleading |

---

## Demo Video

*2-minute screen recording — to be added before submission.*

Planned content:
1. Run `python orchestrator.py --stage all --config configs/default_full.json` — show Stage 1 summary output (enrichment coverage, skills coverage, cert count)
2. Show `canonical_profiles.json` — compare Arjun Mehta (fully enriched, `overall_confidence: 0.876`) vs Farhan Ali (CSV-only stub, `overall_confidence: 0.540`)
3. Run `python orchestrator.py --stage stage2 --config configs/minimal_ats.json` — show the different output shape
4. Explain the **Vivek Singh / Vivek S. Singh** identity edge case and why they are correctly kept as two separate profiles
5. Explain one design decision: why `overall_confidence` always includes missing fields in the denominator, so enriched profiles rank higher than sparse stubs
