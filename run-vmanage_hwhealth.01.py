#!/usr/bin/env python3
"""
ingest_vmanage_hwhealth_detail.py
Same as the previous loader but pulls
    /dataservice/device/hardwarehealth/detail
instead of the summary endpoint.
"""

import os, re, getpass, urllib3
from datetime import datetime, timezone
import psycopg2
from psycopg2.extras import execute_batch
from vmanage.api.authentication import Authentication   # ← SDK only for auth

# ───── vManage creds ─────
VM_HOST = "192.168.227.200"
VM_USER = "admin"
VM_PASS = "password"                         # leave blank → prompt / $VM_PASS
# ─────────────────────────

# ───── PostgreSQL ─────
PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="vmanage01",
    user="admin",          # change
    password="admin",  # change
)
TABLE = "vmanage_hwhealth"        # same table schema as before
# ───────────────────────


def fnum(val):
    """return float if val looks numeric; else None"""
    if val in ("", None, "--"):
        return None
    m = re.search(r"\d+(\.\d+)?", str(val))
    return float(m.group()) if m else None


def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ➊  Login via SDK
    pw = VM_PASS or os.getenv("VM_PASS") or getpass.getpass("vManage password: ")
    auth = Authentication(VM_HOST, VM_USER, pw, validate_certs=False)
    session = auth.login()
    print(f"✅  Authenticated to vManage @ {VM_HOST}")

    # ➋  Raw GET to the *detail* endpoint
    url = f"https://{VM_HOST}/dataservice/device/hardwarehealth/detail"
    r = session.get(url, verify=False)
    r.raise_for_status()
    data = r.json().get("data", [])
    print(f"🔎  Retrieved {len(data)} records from /hardwarehealth/detail")

    if not data:
        print("❌  Empty payload — nothing to insert")
        return

    # ➌  Build the rows we need
    ts_now = datetime.now(timezone.utc)
    rows = []
    for d in data:
        rows.append(
            dict(
                ts=ts_now,
                local_system_ip=d.get("local-system-ip") or d.get("system-ip"),
                omp_peers=int(d["ompPeers"]) if str(d.get("ompPeers","")).isdigit() else None,
                vsmart_peers=int(d["number-vsmart-peers"]) if str(d.get("number-vsmart-peers","")).isdigit() else None,
                mem_usage_pct=fnum(d.get("memUsageDisplay")),
                cpu_load_pct=fnum(d.get("cpuLoadDisplay")),
                bfd_sessions=int(d["bfdSessions"]) if str(d.get("bfdSessions","")).isdigit() else None,
                reachability=d.get("reachability"),
                control_connections=int(d["controlConnections"]) if str(d.get("controlConnections","")).isdigit() else None,
            )
        )

    # ➍  Insert into TimescaleDB
    cols = rows[0].keys()
    insert_sql = (
        f"INSERT INTO {TABLE} ({', '.join(cols)}) "
        f"VALUES ({', '.join([f'%({c})s' for c in cols])});"
    )

    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, rows, page_size=100)
        conn.commit()

    print(f"💾  Inserted {len(rows)} rows at {ts_now.isoformat()}")


if __name__ == "__main__":
    main()

