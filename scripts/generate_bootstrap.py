"""Generate bootstrap.sql: the warehouse end state of the production dbt run, as plain Snowflake SQL.

Inputs come from a dbt platform run's artifacts (manifest.json for compiled SQL, catalog.json for
column types and comments) plus the source rows (a JSON file of {"columns": [...], "rows": [[...]]}).

Object references are rewritten to two-part names (schema.object), so one `USE DATABASE` line at the
top of bootstrap.sql decides where everything lands. Schema and object names match prod.

Usage: generate_bootstrap.py --artifacts DIR --rows rows.json --seed-csv hed_records.csv --out bootstrap.sql
"""
import argparse, json, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--artifacts", required=True)
ap.add_argument("--rows", required=True)
ap.add_argument("--seed-csv", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--rename", nargs="*", default=[], help="OLD=NEW schema renames, e.g. LUIS_LEON_HIGHER_EDUCATION=INDUSTRIES_HIGHER_EDUCATION")
a = ap.parse_args()
d = Path(a.artifacts)
manifest = json.loads((d / "manifest.json").read_text())
catalog = json.loads((d / "catalog.json").read_text())
data = json.loads(Path(a.rows).read_text())

src = next(iter(manifest["sources"].values()))
PROD_DB = src["database"]
RENAMES = [kv.split("=", 1) for kv in a.rename]
def rn(text):
    """Apply schema renames (case-insensitive, whole identifier only)."""
    for old, new in RENAMES:
        text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, text, flags=re.I)
    return text
strip_db = lambda sql: rn(re.sub(re.escape(PROD_DB) + r"\.", "", sql, flags=re.I))
q = lambda s: "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"

def scale_of(values):
    """Largest number of decimal places seen; the catalog reports NUMBER without precision/scale."""
    return max((len(str(v).split(".")[1]) for v in values if v is not None and "." in str(v)), default=0)

def col_type(typ, values):
    return f"NUMBER(38,{scale_of(values)})" if typ == "NUMBER" else typ

def lit(v, typ):
    if v is None: return "NULL"
    if typ in ("NUMBER", "FLOAT") and not isinstance(v, bool): return str(v)
    if typ == "BOOLEAN": return "TRUE" if v in (True, "true", "True", 1) else "FALSE"
    return q(v)

out = [
    "-- Make your data AI ready with dbt and Snowflake: Snowflake lab bootstrap",
    f"-- Generated from dbt platform production run artifacts. Recreates what that run built, as plain SQL.",
    "--",
    "-- HOW TO RUN: in a Snowsight worksheet, pick YOUR lab database in the context selector",
    "-- (top of the worksheet), paste this whole file, then Run All. Takes about a minute.",
    "-- Everything is created inside the worksheet's current database. Safe to re-run.",
    "",
    "SELECT CURRENT_DATABASE() AS building_lab_in;  -- if this is NULL, pick a database first",
    "",
]

# Source table: prod column order and types from the catalog.
csrc = catalog["sources"][src["unique_id"]]
cols = sorted(csrc["columns"].values(), key=lambda c: c["index"])
by_name = {c.upper(): i for i, c in enumerate(data["columns"])}
missing = [c["name"] for c in cols if c["name"].upper() not in by_name]
assert not missing, f"rows file is missing columns: {missing}"
colvals = lambda c: [r[by_name[c["name"].upper()]] for r in data["rows"]]
src = {**src, "schema": rn(src["schema"])}
out += [f"CREATE SCHEMA IF NOT EXISTS {src['schema']};",
        f"CREATE OR REPLACE TABLE {src['schema']}.{src['identifier']} (",
        ",\n".join(f"  {c['name']} {col_type(c['type'], colvals(c))}" for c in cols), ");"]
values = [
    "(" + ", ".join(lit(row[by_name[c["name"].upper()]], c["type"]) for c in cols) + ")"
    for row in data["rows"]
]
out += [f"INSERT INTO {src['schema']}.{src['identifier']} ({', '.join(c['name'] for c in cols)}) VALUES",
        ",\n".join(values) + ";", ""]

# Models and seed in dependency order.
nodes = {k: v for k, v in manifest["nodes"].items() if v["resource_type"] in ("model", "seed")}
done, order = set(), []
def visit(k):
    if k in done or k not in nodes: return
    for dep in nodes[k]["depends_on"]["nodes"]: visit(dep)
    done.add(k); order.append(k)
for k in sorted(nodes): visit(k)

for k in order: nodes[k] = {**nodes[k], "schema": rn(nodes[k]["schema"])}
schemas = sorted({nodes[k]["schema"] for k in order})
out += [f"CREATE SCHEMA IF NOT EXISTS {s};" for s in schemas] + [""]
for k in order:
    n = nodes[k]
    name = f"{n['schema']}.{n['alias']}"
    mat = n["config"].get("materialized")
    cat = catalog["nodes"].get(k, {})
    if n["resource_type"] == "seed":
        import csv
        ccols = sorted(cat["columns"].values(), key=lambda c: c["index"])
        seed_rows = list(csv.DictReader(open(a.seed_csv)))
        sv = lambda c: [r[c["name"].lower()] or None for r in seed_rows]
        out += [f"-- seed: {n['name']} (from the repo's seeds/{n['name']}.csv; not used by any model)",
                f"CREATE OR REPLACE TABLE {name} (" + ", ".join(f"{c['name']} {col_type(c['type'], sv(c))}" for c in ccols) + ");",
                f"INSERT INTO {name} ({', '.join(c['name'] for c in ccols)}) VALUES",
                ",\n".join("(" + ", ".join(lit(r[c["name"].lower()] or None, c["type"]) for c in ccols) + ")" for r in seed_rows) + ";", ""]
        continue
    body = strip_db(n["compiled_code"]).strip().rstrip(";").rstrip()
    if mat == "view":
        out.append(f"CREATE OR REPLACE VIEW {name} AS\n{body};")
    elif mat == "table":
        out.append(f"CREATE OR REPLACE TABLE {name} AS\n{body};")
    elif mat == "semantic_view":
        out.append(f"CREATE OR REPLACE SEMANTIC VIEW {name}\n{body};")
    else:
        raise SystemExit(f"unhandled materialization {mat} for {k}")
    # persist_docs: prod carries relation and column comments; copy them from the catalog.
    kind = {"view": "VIEW", "table": "TABLE"}.get(mat)
    if kind and cat:
        if cat["metadata"].get("comment"):
            out.append(f"COMMENT ON {kind} {name} IS {q(cat['metadata']['comment'])};")
        for c in sorted(cat["columns"].values(), key=lambda c: c["index"]):
            if c.get("comment"):
                # Views reject COMMENT ON COLUMN; they take ALTER VIEW ... MODIFY COLUMN.
                if kind == "VIEW":
                    out.append(f"ALTER VIEW {name} MODIFY COLUMN {c['name']} COMMENT {q(c['comment'])};")
                else:
                    out.append(f"COMMENT ON COLUMN {name}.{c['name']} IS {q(c['comment'])};")
    out.append("")

Path(a.out).write_text("\n".join(out) + "\n")
print(f"wrote {a.out}: source rows={len(values)}, objects={len(order)} ({', '.join(nodes[k]['name'] for k in order)})")
