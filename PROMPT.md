# One-shot prompt for Cortex Code (CoCo)

Paste this into CoCo. The same file also works by hand: open `bootstrap.sql` in a Snowsight worksheet,
change the `SET lab_db` line, and Run All.

---
Set up the "Make your data AI ready with dbt and Snowflake" lab objects in this Snowflake account.

1. Open `bootstrap.sql` from https://github.com/dbt-labs/ai-ready-workshop-bootstrap (or this folder).
2. Change the line `SET lab_db = 'SNOWFLAKE_SUMMIT_2026_HOL_DB';` to use my lab database: <YOUR_DATABASE>.
3. Run every statement in the file, in order. Stop and show me the error if one fails.
4. Then run these checks and show the results:
   - `select count(*) from INDUSTRIES_HIGHER_EDUCATION.HED_RECORDS;`  (expect 750)
   - `show semantic views in schema sv_higher_education;`  (expect SV_HED_AT_RISK_STUDENTS)
   - `select count(*) from sv_higher_education.vw_hed_retention_risk_analysis;`

Do not create any functions or agents. Do not touch any database other than <YOUR_DATABASE>.
