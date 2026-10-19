# Make your data AI ready with dbt and Snowflake: environment bootstrap

Recreates the workshop demo environment in a fresh Snowflake account.
dbt project: https://github.com/dbt-labs/snowflake_sko_hol_2026 (`dbt_industries_views`, Higher Education models)

## What's here
| File | Purpose |
|---|---|
| `sql/00_account_setup.sql` | Warehouse, role, database grants (ACCOUNTADMIN, one time) |
| `sql/01_source_data.sql` | Creates `SNOWFLAKE_SUMMIT_2026_HOL_DB.LUIS_LEON_HIGHER_EDUCATION.HED_RECORDS` and loads 50 sample students |
| `hed_records.csv` | Same data as a CSV (identical to the project's seed) |

## Steps
1. Run `sql/00_account_setup.sql`, then `sql/01_source_data.sql` in a Snowflake worksheet.
2. Clone the dbt project and point a profile at the account with role `WORKSHOP_TRANSFORMER`.
3. `dbt deps && dbt build`. This produces what the prod job produces: staging, intermediate, 5 marts views, 4 data-quality models, the time spine, and the `sv_hed_at_risk_students` semantic view, all in schema `sv_higher_education`.
4. To use different source names, run the SQL with `SET src_db=...; SET src_schema=...;` first, and build with `--vars '{hed_source_database: X, hed_source_schema: Y}'`.

## Notes
- The semantic view needs the `Snowflake-Labs/dbt_semantic_view` package (in `packages.yml`) and Snowflake semantic views enabled on the account.
- The project sets `static_analysis: strict`, so it needs the dbt engine (Fusion) in the target environment.
- No credentials live in this repo.
