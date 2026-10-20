# One-shot prompt for Cortex Code (CoCO)

Paste this into CoCO, or run: `cortex exec -c <connection> --file PROMPT.md`

---
Set up the "Make your data AI ready with dbt and Snowflake" workshop environment in this Snowflake account.

1. In this repo, run `sql/01_source_data.sql` against the current connection. It creates the
   HED_RECORDS source table with 50 sample students. (Use `sql/00_account_setup.sql` first only if
   this is a brand new account and you have ACCOUNTADMIN.)
2. Clone https://github.com/dbt-labs/snowflake_sko_hol_2026 next to this repo.
3. Create a dbt profile named `industries_snowflake` for the same connection. Use the same database
   as step 1 for models, and a role that can create schemas.
4. In the cloned project run `dbt deps`, `dbt source freshness`, then `dbt build`, in that order. These are the production job's steps.
5. Report each model, test, and the semantic view `sv_hed_at_risk_students` as pass or fail.
   Then run `select count(*) from sv_higher_education.vw_hed_student_success_kpi`.

Do not touch any database other than the one named in step 1. Stop and ask if something fails twice.
