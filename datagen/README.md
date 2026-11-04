# Synthetic Data Generator (`datagen/`)

Seeded, deterministic, multi-tenant synthetic data generator for the **Institute Intelligence Platform (DataMoat)**. Produces realistic Indian JEE/NEET coaching data across Tier-2/3 institutes, including clean Parquet tables, latent ground-truth tables, messy Excel/CSV exports with golden parse outputs, and rendered A4 OMR scan images with camera/WhatsApp augmentations.

## CLI Usage

Run from the repo root:

```bash
# Fast smoke / CI preset (1 institute, 300 students, ~2.2 s)
python -m datagen --seed 42 --preset tiny --out data/

# Full multi-institute preset (4 institutes, 3,450 students across 2024-2026 cohorts, ~30 s)
python -m datagen --seed 42 --preset full --out data/

# Run with a curveball scenario override
python -m datagen --seed 42 --preset tiny --out data_scen/ --scenario dropout_x2
```

### Supported Curveball Scenarios (`datagen/scenarios/*.yaml`)

| Scenario | Description |
|---|---|
| `dropout_x2` | Doubles annual dropout rate (`0.18 -> 0.36`) to stress-test retention recall/precision under severe attrition. |
| `marks_only` | Institutes upload only test and subject totals (`marks_only_share: 1.0`, zero item-level responses). |
| `no_attendance` | Suppresses 95% of daily attendance logs (`missing_rate: 0.95`) to test graceful degradation without attendance. |
| `sudden_heavy` | Shifts 65% of dropouts to sudden/unannounced (`sudden_share: 0.65`) with no pre-dropout attendance fade. |
| `small_batches` | Caps batch size at `[20, 30]` (`batch_size_range: [20, 30]`) to test cold-start and small-N shrinkage. |
| `neet_sectioned_200` | Switches NEET mocks to legacy 200-question Section A (35) + Section B (10 of 15) format (`sectioned_200`). |

## Determinism & Seed Policy

- Every randomness source derives from `numpy.random.SeedSequence(seed)` spawned into 8 isolated sub-streams (`institutes`, `traits`, `dropout`, `items`, `responses`, `attendance`, `fees`, `engagement`, `outcomes`, `messy_omr`).
- All entity UUIDs (`institutes`, `batches`, `students`, `guardians`, `consents`, `questions`, `tests`, `answer_keys`, `fees`) are generated via deterministic `uuid.uuid5(DATAMOAT_NAMESPACE, key)`.
- All Parquet outputs are sorted by the exact `sort_by` keys declared in `contracts/datasets.yaml` and written with `zstd` compression and explicit PyArrow schemas.
- Two runs with `--seed 42` on the same platform produce **byte-identical** SHA-256 hashes across every generated Parquet, CSV, JSON, and PNG/JPG file.

## Configuration & Provenance (`datagen/config/generator_config.yaml`)

Every parameter in `datagen/config/generator_config.yaml` carries an inline `# source:` and `confidence: {high | medium | low | assumption}` comment tracing back to `docs/FEASIBILITY_CHECK.md`:
- **Institutes:** 4 coaching institutes across Patna (`patna_jee`, Tier-2, 600 students), Lucknow (`lucknow_neet`, Tier-2, 450 students), Gaya (`gaya_both`, Tier-3, 200 students), and Kota (`kota_large`, Tier-2, 2,200 students).
- **Compliance & Age Floor:** Every student in `data/clean/students.parquet` is strictly $\ge 16.0$ years old at `join_date` (MoE 2024 Guidelines cl. 6(i)), and $\ge 55\%$ of students are minors ($< 18$ years old at `as_of = 2026-10-01`) requiring DPDP s.9 verifiable parental consent and non-tracking routing. An under-16 row is injected **only** in `data/dirty/01_patna_students_row3_merged.xlsx` to test ingestion rejection.
- **Privacy Guarantee:** Zero real PII is used. All student, guardian, and counsellor names are drawn exclusively from `datagen/generator/synthetic_names.py` (`SYNTHETIC_NAME_LIST_V1`) and all phone numbers reside in the reserved `999990xxxx` synthetic range.

## Output Layout (`data/`)

- `data/clean/*.parquet` — 16 multi-tenant clean tables conforming to `contracts/datasets.yaml` and `contracts/schema.sql`.
- `data/truth/*.parquet` — 4 ground-truth evaluation tables (`true_theta_topic`, `true_item_params`, `dropout_events`, `true_final_outcomes`) plus `calibration_samples.json`.
- `data/dirty/*` — 12 messy CSV/XLSX exports across all 4 institutes with golden parse outputs in `data/dirty/expected/<file>.json` and reference parser `datagen/messy/reference_parse.py`.
- `data/omr/synthetic/*` — 210 rendered A4 OMR sheets (`full`) / 24 (`tiny`) across `jee_75`, `neet_200`, and `generic_mcq_100` layouts under 6 imaging conditions (`clean_scan`, `skew_Perspective`, `low_light_shadow`, `crease_shadow`, `whatsapp_recompressed`, `faint_pencil_and_erased`) with ground truth in `data/omr/synthetic/truth.json`.

## Known Limitations

- Synthetic data validates internal model consistency, IRT parameter recovery, and rule-vs-ML routing mechanics under controlled causal assumptions, but **cannot** substitute for real field pilot validation on live coaching institute cohorts.
