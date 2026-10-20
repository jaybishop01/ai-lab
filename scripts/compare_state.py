"""Compare two Snowflake databases object by object: tables/views, columns, rows, semantic views.

Usage: compare_state.py --connection NAME --ref-db REF --test-db TEST [--ignore TABLE ...]
Uses a named connection from ~/.snowflake/connections.toml, so no password is handled here.
Exit 0 = identical, 1 = differences. Time-dependent models (freshness) belong in --ignore for row checks.
"""
import argparse, sys, snowflake.connector

ap = argparse.ArgumentParser()
ap.add_argument("--connection", required=True)
ap.add_argument("--ref-db", required=True)
ap.add_argument("--test-db", required=True)
ap.add_argument("--ignore", nargs="*", default=[], help="table names to skip in the row comparison")
a = ap.parse_args()
con = snowflake.connector.connect(connection_name=a.connection)

def q(sql):
    cur = con.cursor(); cur.execute(sql); return cur.fetchall()

def objects(db):
    return {(r[0], r[1]): r[2] for r in q(
        f"select table_schema, table_name, table_type from {db}.information_schema.tables "
        "where table_schema <> 'INFORMATION_SCHEMA'")}

def columns(db):
    return {(r[0], r[1], r[2]): (r[3], r[4]) for r in q(
        f"select table_schema, table_name, column_name, ordinal_position, data_type "
        f"from {db}.information_schema.columns where table_schema <> 'INFORMATION_SCHEMA'")}

def sem_views(db):
    out = {}
    for r in q(f"show semantic views in database {db}"):
        schema, name = r[3], r[1]   # created_on, name, database_name, schema_name
        ddl = q(f"select get_ddl('semantic_view', '{db}.{schema}.{name}')")[0][0]
        out[(schema, name)] = " ".join(ddl.replace(db, "<DB>").replace(db.lower(), "<DB>").split())
    return out

bad = []
ro, to = objects(a.ref_db), objects(a.test_db)
for k in sorted(set(ro) ^ set(to)):
    bad.append(f"object only in {'ref' if k in ro else 'test'}: {k}")
for k in sorted(set(ro) & set(to)):
    if ro[k] != to[k]: bad.append(f"object type differs {k}: {ro[k]} vs {to[k]}")
rc, tc = columns(a.ref_db), columns(a.test_db)
for k in sorted(set(rc) ^ set(tc)):
    bad.append(f"column only in {'ref' if k in rc else 'test'}: {k}")
for k in sorted(set(rc) & set(tc)):
    if rc[k] != tc[k]: bad.append(f"column differs {k}: {rc[k]} vs {tc[k]}")
checked = 0
for (schema, name), typ in sorted(ro.items()):
    if (schema, name) not in to or name.upper() in {i.upper() for i in a.ignore}: continue
    try:
        ref, test = f'{a.ref_db}."{schema}"."{name}"', f'{a.test_db}."{schema}"."{name}"'
        d1 = q(f"select count(*) from (select * from {ref} minus select * from {test})")[0][0]
        d2 = q(f"select count(*) from (select * from {test} minus select * from {ref})")[0][0]
        n1, n2 = q(f"select count(*) from {ref}")[0][0], q(f"select count(*) from {test}")[0][0]
        checked += 1
        if d1 or d2 or n1 != n2: bad.append(f"rows differ in {schema}.{name}: ref={n1} test={n2} minus={d1}/{d2}")
    except snowflake.connector.Error as e:
        bad.append(f"could not compare {schema}.{name}: {str(e)[:120]}")
rs, ts = sem_views(a.ref_db), sem_views(a.test_db)
for k in sorted(set(rs) ^ set(ts)): bad.append(f"semantic view only in {'ref' if k in rs else 'test'}: {k}")
for k in sorted(set(rs) & set(ts)):
    if rs[k] != ts[k]: bad.append(f"semantic view DDL differs: {k}")
print(f"objects ref={len(ro)} test={len(to)} | row-compared={checked} | semantic views ref={len(rs)} test={len(ts)}")
print("IDENTICAL" if not bad else "DIFFERENCES:\n  " + "\n  ".join(bad))
sys.exit(1 if bad else 0)
