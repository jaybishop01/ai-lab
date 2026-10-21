"""Run a .sql file through a named Snowflake connection, statement by statement. Stops on the first error.
Usage: run_sql_file.py --connection NAME FILE [--set var=value ...]
--set overrides a `SET var = '...';` line in the file (e.g. --set lab_db=JB_AI_READY_TEST).
"""
import argparse, io, re, sys, snowflake.connector
from snowflake.connector.util_text import split_statements

ap = argparse.ArgumentParser()
ap.add_argument("--connection", required=True); ap.add_argument("file"); ap.add_argument("--set", nargs="*", default=[])
a = ap.parse_args()
sql = open(a.file).read()
for kv in a.set:
    k, v = kv.split("=", 1)
    sql, n = re.subn(rf"^SET {k} = '[^']*';", f"SET {k} = '{v}';", sql, flags=re.M | re.I)
    if not n: sys.exit(f"no SET {k} line in {a.file}")
con = snowflake.connector.connect(connection_name=a.connection, **({'password': pw} if (pw := __import__('os').environ.get(f'SNOWFLAKE_CONNECTIONS_{a.connection.upper()}_PASSWORD')) else {}))
ok = 0
for stmt, _ in split_statements(io.StringIO(sql), remove_comments=False):
    if not stmt.strip() or not re.sub(r"--[^\n]*", "", stmt).strip(): continue
    try:
        con.cursor().execute(stmt); ok += 1
    except snowflake.connector.Error as e:
        sys.exit(f"FAILED after {ok} statements:\n{stmt[:300]}\n-> {e}")
print(f"OK: {ok} statements")
