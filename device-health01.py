#!/usr/bin/env python3
"""
ingest_vmanage_hwhealth.py
Pull /dataservice/device/hardwarehealth and insert snapshots into TimescaleDB
"""

import os
import re
import getpass
import urllib3
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_batch

from vmanage.api.authentication import Authentication   # SDK just for login

# ───── vManage credentials ─────
VM_HOST = "192.168.227.200"
VM_USER = "admin"
VM_PASS = "password"                       # leave blank → prompt / $VM_PASS
# ───────────────────────────────

# ───── Postgres connection ─────
PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="vmanage01",
    user="admin",          # <── change
    password="admin",  # <── change or use .pgpass/env-vars
)
TABLE = "vmanage_hwhealth"
# ───────────────────────────────


def parse_float(s):
    """Return first float in a string, or None."""
    if s in (None, "", "--"):
        return None
    m = re.search(r"\d+(\.\d+)?", str(s))
    return float(m.group()) if m else None


def build_rows(hw_data, ts_now):
    """Extract only the fields we need and normalise types."""
    rows = []
    for d in hw_data:
        rows.append(
            dict(
                ts=ts_now,
                local_system_ip=d.get("local-system-ip") or d.get("system-ip"),
                omp_peers=int(d["ompPeers"])
                if str(d.get("ompPeers", "")).isdigit()
                else None,
                vsmart_peers=int(d["number-vsmart-peers"])
                if str(d.get("number-vsmart-peers", "")).isdigit()
                else None,
                mem_usage_pct=parse_float(d.get("memUsageDisplay")),
                cpu_load_pct=parse_float(d.get("cpuLoadDisplay")),
                bfd_sessions=int(d["bfdSessions"])
                if str(d.get("bfdSessions", "")).isdigit()
                else None,
                reachability=d.get("reachability"),
                control_connections=int(d["controlConnections"])
                if str(d.get("controlConnections", "")).isdigit()
                else None,
            )
        )
    return rows


def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ── 1)  Auth via SDK (cookie + XSRF handled for us) ───────────
    pw = VM_PASS or os.getenv("VM_PASS") or getpass.getpass("vManage password: ")
    auth = Authentication(VM_HOST, VM_USER, pw, validate_certs=False)
    session = auth.login()
    print(f"✅  Authenticated to vManage @ {VM_HOST}")

    # ── 2)  Raw REST call to Hardware Health endpoint ────────────
    url = f"https://{VM_HOST}/dataservice/device/hardwarehealth"
    r = session.get(url, verify=False)
    r.raise_for_status()
    hw_data = r.json().get("data", [])
    print(f"🔎  Retrieved {len(hw_data)} hardware-health records")

    if not hw_data:
        print("❌  Empty payload — nothing to insert")
        return

    # ── 3)  Build rows for DB ─────────────────────────────────────
    ts_now = datetime.now(timezone.utc)
    rows = build_rows(hw_data, ts_now)

    # ── 4)  Bulk insert into TimescaleDB ──────────────────────────
    cols = [c for c in rows[0].keys()]          # ordered list incl. ts
    insert_sql = f"""
        INSERT INTO {TABLE} ({', '.join(cols)})
        VALUES ({', '.join([f'%({c})s' for c in cols])});
    """

    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, rows, page_size=100)
        conn.commit()

    print(f"💾  Inserted {len(rows)} rows at {ts_now.isoformat()}")

if __name__ == "__main__":
    main()
