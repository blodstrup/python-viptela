#!/usr/bin/env python3
"""
ingest_vmanage_inventory.py
Fetch device inventory from Cisco vManage and push into a TimescaleDB table
"""

import json
import re
from datetime import datetime, timezone

import urllib3
import psycopg2
from psycopg2.extras import execute_batch

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device


# ───────────────────────────────
#  CONFIG  ▸  edit to suit
# ───────────────────────────────
VM_HOST = "192.168.227.200"
VM_USER = "admin"
VM_PASS = "password"

PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="vmanage01",
    user="postgres",
    password="8ds0jq",
)

TABLE = "vmanage_device_inventory"     # keep in sync with SQL above


# ───────────────────────────────
#  HELPER  ▸  flatten/rename keys
# ───────────────────────────────
def normalise(d: dict) -> dict:
    """
    Convert vManage field names → snake_case expected by SQL.
    Missing keys safely map to None.
    """
    mapping = {
        "deviceId": "device_id",
        "system-ip": "system_ip",
        "host-name": "host_name",
        "reachability": "reachability",
        "status": "status",
        "personality": "personality",
        "device-type": "device_type",
        "device-groups": "device_groups",
        "lastupdated": "lastupdated",
        "domain-id": "domain_id",
        "board-serial": "board_serial",
        "certificate-validity": "certificate_validity",
        "max-controllers": "max_controllers",
        "uuid": "uuid",
        "controlConnections": "control_connections",
        "device-model": "device_model",
        "version": "version",
        "connectedVManages": "connected_vmanages",
        "site-id": "site_id",
        "ompPeers": "omp_peers",
        "latitude": "latitude",
        "longitude": "longitude",
        "isDeviceGeoData": "isdevicegeodata",
        "platform": "platform",
        "uptime-date": "uptime_date",
        "statusOrder": "status_order",
        "device-os": "device_os",
        "validity": "validity",
        "state": "state",
        "state_description": "state_description",
        "model_sku": "model_sku",
        "local-system-ip": "local_system_ip",
        "total_cpu_count": "total_cpu_count",
        "linux_cpu_count": "linux_cpu_count",
        "testbed_mode": "testbed_mode",
        "layoutLevel": "layout_level",
        "site-name": "site_name",
    }

    out = {v: d.get(k) for k, v in mapping.items()}

    # Convert strings that should be int / bool where obvious
    for k in ("control_connections", "omp_peers", "total_cpu_count",
              "linux_cpu_count", "status_order", "layout_level",
              "max_controllers", "site_id", "domain_id"):
        if out[k] in (None, "--", ""):
            out[k] = None
        else:
            try:
                out[k] = int(out[k])
            except ValueError:
                out[k] = None

    for k in ("latitude", "longitude"):
        try:
            out[k] = float(out[k]) if out[k] is not None else None
        except ValueError:
            out[k] = None

    # arrays come as Python list already – fine for psycopg2
    return out


# ───────────────────────────────
#  MAIN
# ───────────────────────────────
def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # ➊  vManage auth
    auth = Authentication(host=VM_HOST, user=VM_USER,
                          password=VM_PASS, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {VM_HOST}")

    # ➋  Fetch devices
    dev_api = Device(session=session, host=VM_HOST)
    devices = dev_api.get_device_status_list()
    if not devices:
        print("❌ No devices returned!")
        return
    print(f"🔎  Retrieved {len(devices)} devices")

    # ➌  Prepare rows
    ts_now = datetime.now(tz=timezone.utc)
    rows = []
    for d in devices:
        norm = normalise(d)
        cols = ",".join(norm.keys())
        placeholders = ",".join([f"%({c})s" for c in norm.keys()])
        norm["ts"] = ts_now
        rows.append(norm)

    # ➍  Insert
    insert_sql = f"""
        INSERT INTO {TABLE} (
            ts, {", ".join(rows[0].keys() - {"ts"})}
        ) VALUES (
            %(ts)s, {", ".join([f"%({c})s" for c in rows[0].keys() if c != "ts"])}
        );
    """

    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, rows, page_size=100)
        conn.commit()

    print(f"💾 Inserted {len(rows)} rows into {TABLE} at {ts_now.isoformat()}")


if __name__ == "__main__":
    main()

