# Make your data AI ready with dbt and Snowflake: Snowflake lab bootstrap

One SQL file that recreates, in any Snowflake database, exactly what the workshop's dbt platform
production job built: the `HED_RECORDS` source (750 rows), 13 views, the time spine table, the seed
table, and the `sv_hed_at_risk_students` semantic view. No dbt needed on the Snowflake side.

dbt project it mirrors: https://github.com/dbt-labs/snowflake_sko_hol_2026 (production run #520219493)

## Use it
- **Snowsight worksheet:** open `bootstrap.sql`, change `SET lab_db = ...` to your database, Run All (about 1 minute).
- **Cortex Code:** paste `PROMPT.md`.

Objects land in `<lab_db>.INDUSTRIES_HIGHER_EDUCATION` (source), `<lab_db>.sv_higher_education`
(models and semantic view), and `<lab_db>.WORKSHOP_SEED` (seed, unused by models).

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
| `scripts/run_sql_file.py` | Runs `bootstrap.sql` through a named Snowflake connection |
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
- The catalog reports `NUMBER` without precision or scale. Scale is set from the data (e.g. GPA `NUMBER(38,2)`). Values match; the exact prod declared precision isn't verifiable from the artifacts.
- `dq_hed__freshness` depends on the current time, so its output changes day to day, as it does in prod.
- Needs Snowflake semantic views on the account.
