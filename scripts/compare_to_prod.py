"""Compare a test build of snowflake_sko_hol_2026 to the artifacts of a dbt platform production run.

Offline checks (no Snowflake): node set, compiled SQL, and test results, from the two manifests and run_results.
Live check (optional, --connection): objects and columns in the test database vs the prod catalog.json.

Usage: compare_to_prod.py --prod-dir DIR --test-target DIR [--connection NAME --test-db DB]
  DIR holds manifest.json, run_results.json, catalog.json (prod) / the test project's target/ (manifest, run_results).
Database names are normalised, and the seed's per-attendee target schema is treated as one schema.
Exit 0 = match, 1 = differences.
"""
import argparse, json, re, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--prod-dir", required=True); ap.add_argument("--test-target", required=True)
ap.add_argument("--subset", action="store_true", help="test build is a --select subset: compare only nodes the test built")
ap.add_argument("--connection"); ap.add_argument("--test-db")
a = ap.parse_args()
P, T = Path(a.prod_dir), Path(a.test_target)
load = lambda d, f: json.loads((d / f).read_text())
pm, tm = load(P, "manifest.json"), load(T, "manifest.json")
bad = []

def norm(sql, *dbs):
    for d in dbs:
        if d: sql = re.sub(re.escape(d), "<DB>", sql or "", flags=re.I)
    return " ".join((sql or "").split())

pdb = next(iter(pm["sources"].values()))["database"]
tdb = next(iter(tm["sources"].values()))["database"]
keep = ("model", "seed", "snapshot")
pn = {k: v for k, v in pm["nodes"].items() if v["resource_type"] in keep}
tn = {k: v for k, v in tm["nodes"].items() if v["resource_type"] in keep}
if a.subset: pn = {k: v for k, v in pn.items() if k in tn}
for k in sorted(set(pn) ^ set(tn)): bad.append(f"node only in {'prod' if k in pn else 'test'}: {k}")
same_sql = 0
for k in sorted(set(pn) & set(tn)):
    if pn[k]["config"].get("materialized") != tn[k]["config"].get("materialized"):
        bad.append(f"materialization differs: {k}")
    if pn[k].get("schema") != tn[k].get("schema") and pn[k]["resource_type"] == "model":
        bad.append(f"schema differs: {k}: {pn[k]['schema']} vs {tn[k]['schema']}")
    if norm(pn[k].get("compiled_code"), pdb, tdb) == norm(tn[k].get("compiled_code"), pdb, tdb): same_sql += 1
    else: bad.append(f"compiled SQL differs: {k}")
count = lambda m: len([k for k, v in m["nodes"].items() if v["resource_type"] == "test"])
if not a.subset and count(pm) != count(tm): bad.append(f"test count differs: prod={count(pm)} test={count(tm)}")
status = lambda d: {r["unique_id"]: r["status"] for r in load(d, "run_results.json")["results"]}
ps, ts = status(P), status(T)
if a.subset: ps = {k: v for k, v in ps.items() if k in ts}
for k in sorted(set(ps) ^ set(ts)): bad.append(f"result only in {'prod' if k in ps else 'test'}: {k}")
for k in sorted(set(ps) & set(ts)):
    if ps[k] != ts[k]: bad.append(f"status differs {k}: prod={ps[k]} test={ts[k]}")
print(f"nodes prod={len(pn)} test={len(tn)} | compiled SQL identical={same_sql} | results prod={len(ps)} test={len(ts)}")

if a.connection:
    import snowflake.connector
    con = snowflake.connector.connect(connection_name=a.connection, **({'password': pw} if (pw := __import__('os').environ.get(f'SNOWFLAKE_CONNECTIONS_{a.connection.upper()}_PASSWORD')) else {}))
    cur = con.cursor()
    cur.execute(f"select table_schema, table_name, column_name, data_type from {a.test_db}.information_schema.columns "
                "where table_schema <> 'INFORMATION_SCHEMA'")
    live = {}
    for s, t, c, d in cur.fetchall(): live.setdefault((t.upper()), {})[c.upper()] = d.upper()
    cat = load(P, "catalog.json")["nodes"]
    checked = 0
    for k, n in cat.items():
        if a.subset and k not in tm["nodes"]: continue
        name = n["metadata"]["name"].upper(); cols = {c.upper(): v["type"].upper() for c, v in n["columns"].items()}
        if name not in live: bad.append(f"object missing in test db: {name}"); continue
        checked += 1
        if live[name] != cols: bad.append(f"columns differ in {name}: {sorted(set(cols.items()) ^ set(live[name].items()))[:4]}")
    print(f"live: catalog relations checked={checked}")
print("MATCH" if not bad else "DIFFERENCES:\n  " + "\n  ".join(bad))
sys.exit(1 if bad else 0)
