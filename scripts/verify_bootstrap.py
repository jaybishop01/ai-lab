"""Check a bootstrapped database against a dbt platform production run's catalog.json.

Compares, for every relation prod built (and the source): object type, column names/order/types,
relation and column comments, and row counts where prod recorded them. Also queries every view so a
view that exists but cannot run is caught, and checks the semantic view exists.
Usage: verify_bootstrap.py --connection NAME --db DB --artifacts DIR
"""
import argparse, json, os, sys
from pathlib import Path
import snowflake.connector

ap = argparse.ArgumentParser()
ap.add_argument("--connection", required=True); ap.add_argument("--db", required=True); ap.add_argument("--artifacts", required=True)
ap.add_argument("--rename", nargs="*", default=[], help="OLD=NEW schema renames used when generating")
a = ap.parse_args()
pw = os.environ.get(f"SNOWFLAKE_CONNECTIONS_{a.connection.upper()}_PASSWORD")
con = snowflake.connector.connect(connection_name=a.connection, **({"password": pw} if pw else {}))
q = lambda sql: con.cursor().execute(sql).fetchall()
cat = json.loads((Path(a.artifacts) / "catalog.json").read_text())
man = json.loads((Path(a.artifacts) / "manifest.json").read_text())

live_t = {(s, t): (typ, cmt or "", rows) for s, t, typ, cmt, rows in q(
    f"select table_schema, table_name, table_type, comment, row_count from {a.db}.information_schema.tables "
    "where table_schema <> 'INFORMATION_SCHEMA'")}
live_c = {}
for s, t, c, i, typ, cmt in q(f"select table_schema, table_name, column_name, ordinal_position, data_type, comment "
                               f"from {a.db}.information_schema.columns where table_schema <> 'INFORMATION_SCHEMA'"):
    live_c.setdefault((s, t), {})[c] = (i, typ, cmt or "")

renames = {o.upper(): nw.upper() for o, nw in (kv.split("=", 1) for kv in a.rename)}
bad, checked = [], 0
for uid, n in list(cat["nodes"].items()) + list(cat["sources"].items()):
    md = n["metadata"]; key = (renames.get(md["schema"].upper(), md["schema"].upper()), md["name"].upper())
    if key not in live_t: bad.append(f"missing: {key}"); continue
    typ, cmt, rows = live_t[key]; checked += 1
    if typ != md["type"]: bad.append(f"type {key}: prod={md['type']} test={typ}")
    if (md.get("comment") or "") != cmt: bad.append(f"relation comment differs: {key}")
    prod_rows = n.get("stats", {}).get("row_count", {}).get("value")
    if prod_rows is not None and prod_rows != rows: bad.append(f"row_count {key}: prod={prod_rows} test={rows}")
    pc = {c["name"]: (c["index"], c["type"], c.get("comment") or "") for c in n["columns"].values()}
    lc = live_c.get(key, {})
    for c in sorted(set(pc) | set(lc)):
        if pc.get(c) != lc.get(c): bad.append(f"column {key}.{c}: prod={pc.get(c)} test={lc.get(c)}")
    if typ == "VIEW":
        try: q(f'select count(*) from {a.db}."{key[0]}"."{key[1]}"')
        except snowflake.connector.Error as e: bad.append(f"view does not run {key}: {str(e)[:100]}")

sv = [n for n in man["nodes"].values() if n["config"].get("materialized") == "semantic_view"]
for n in sv:
    found = q(f"show semantic views like '{n['alias'].upper()}' in schema {a.db}.{n['schema']}")
    if not found: bad.append(f"semantic view missing: {n['schema']}.{n['alias']}")
    else: q(f"describe semantic view {a.db}.{n['schema']}.{n['alias']}"); checked += 1
print(f"relations checked={checked} (catalog nodes {len(cat['nodes'])} + sources {len(cat['sources'])} + semantic views {len(sv)})")
print("MATCH" if not bad else f"DIFFERENCES ({len(bad)}):\n  " + "\n  ".join(bad[:60]))
sys.exit(1 if bad else 0)
