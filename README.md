# Make your data AI ready with dbt and Snowflake: Snowflake lab setup

## Start here (about 2 minutes)
1. Log in to your Snowflake lab account and open **Projects → Worksheets → + → SQL Worksheet**.
2. At the top of the worksheet, use the **context selector** to pick **your lab database**.
3. Open [`bootstrap.sql`](bootstrap.sql), click **Raw**, then select all (**Cmd/Ctrl+A**) and copy (**Cmd/Ctrl+C**).
4. Paste it into the worksheet and click **Run All** (the ▶ dropdown → *Run All*). Wait about a minute.

Using Cortex Code instead? Paste the file into a worksheet as above, or tell Cortex Code:
*"Ask me for my lab database, then run the SQL in this worksheet against it."*

## Check it worked
Run these in the same worksheet:
```sql
select count(*) from INDUSTRIES_HIGHER_EDUCATION.HED_RECORDS;                -- 750
show semantic views in schema sv_higher_education;                           -- SV_HED_AT_RISK_STUDENTS
select count(*) from sv_higher_education.vw_hed_retention_risk_analysis;     -- 257 at-risk students
```

## Fell behind? Catch up
- **Re-running is safe.** Every statement is `CREATE OR REPLACE` / `IF NOT EXISTS`. Paste and Run All again.
- **First result shows `NULL`:** no database is selected. Pick one in the context selector and run again.
- **"Insufficient privileges":** your role can't create schemas in that database. Ask a facilitator.
- **Semantic view step fails:** semantic views aren't enabled on the account. Ask a facilitator.

## What this creates
| Schema | Objects |
|---|---|
| `INDUSTRIES_HIGHER_EDUCATION` | `HED_RECORDS`: the 750-row source table |
| `sv_higher_education` | 13 views, `metricflow_time_spine` table, `sv_hed_at_risk_students` semantic view |
| `WORKSHOP_SEED` | `hed_records` seed table (not used by any view) |

This is exactly what the workshop's dbt platform production job builds (run #520219493 of
[snowflake_sko_hol_2026](https://github.com/dbt-labs/snowflake_sko_hol_2026)), as plain SQL.

## Naming
Two schemas are renamed from prod; everything else keeps prod's names:

| Prod schema | Lab schema | Why |
|---|---|---|
| `LUIS_LEON_HIGHER_EDUCATION` | `INDUSTRIES_HIGHER_EDUCATION` | Personal name; this is the project's own default in `_hed__sources.yml` |
| `prod_workshop_Jb_2d9662` | `WORKSHOP_SEED` | Per-attendee target schema from the prod run |

The dbt platform Catalog still shows the prod source schema, since that lives in the Training Snowflake.

## How it's made
| File | Purpose |
|---|---|
| `bootstrap.sql` | Generated. Do not hand-edit. |
| `scripts/generate_bootstrap.py` | Builds `bootstrap.sql` from the prod run's `manifest.json` (compiled SQL) and `catalog.json` (types, comments), plus `data/hed_records_prod.json` |
| `data/hed_records_prod.json` | The 750 prod source rows, exported from the production Snowflake through a read-only dbt platform run |
| `scripts/verify_bootstrap.py` | Checks a bootstrapped database against the prod catalog: types, columns, comments, row counts, views run, semantic view exists |
| `scripts/run_sql_file.py` | Runs `bootstrap.sql` through a named Snowflake connection (`--database` = the worksheet's database) |
| `scripts/compare_to_prod.py`, `compare_state.py` | Earlier dbt-build comparison tools |

References are two-part (`schema.object`), so the `USE DATABASE` line decides where everything goes.

## Regenerate
```
python3 scripts/generate_bootstrap.py --artifacts <run artifacts dir> --rows data/hed_records_prod.json \
  --seed-csv hed_records.csv --out bootstrap.sql \
  --rename LUIS_LEON_HIGHER_EDUCATION=INDUSTRIES_HIGHER_EDUCATION prod_workshop_Jb_2d9662=WORKSHOP_SEED
```
Pass the same `--rename` to `scripts/verify_bootstrap.py`.

## Known limits
- **Dates are shifted.** The sample data is from 2025, which made every student look a year inactive and Critical. After loading, every date column moves by the same number of days so the newest login is 2026-10-18 (3 days before the 10/21/2026 event). Gaps between dates are unchanged. Change it with `--latest-login` when regenerating. This is the only data difference from prod.
- The catalog reports `NUMBER` without precision or scale. Scale is set from the data (e.g. GPA `NUMBER(38,2)`). Values match; the exact prod declared precision isn't verifiable from the artifacts.
- `dq_hed__freshness` depends on the current time, so its output changes day to day, as it does in prod.
- Needs Snowflake semantic views on the account.
