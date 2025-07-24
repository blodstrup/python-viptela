#!/usr/bin/env python3
"""
device-collector-04.py  –  "latest-only" inventory ingestor

• Polls Cisco vManage for the current device list.
• Keeps exactly ONE row per device_id in the table  `device_inventory`.
• Inserts new devices; updates existing rows only when vManage's
  `lastupdated` field changes (so we don’t thrash the disk).

This version merges the **working field-mapping and type-cleanups** from the
old device-collector-03.py with the up-sert/ON CONFLICT logic, ensures every
row dictionary has a uniform set of columns, and aligns with the current
table schema (drops unsupported columns).
"""

from __future__ import annotations

import os
import getpass
import urllib3
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

# ─────────────────────────── vManage connection ────────────────────────────
VM_HOST = "192.168.227.200"
VM_USER = "admin"
VM_PASS = "password"                     # leave blank → prompt/env var

# ────────────────────── PostgreSQL connection ──────────────────────────────
PG_CONN: dict[str, str | int] = {
    "host": "localhost",
    "port": 5432,
    "dbname": "vmanage01",
    "user": "postgres",
    "password": "8ds0jq",
}

TABLE = "device_inventory"   # one-row-per-device table
# ────────────────────────────────────────────────────────────────────────────


def normalise(d: dict) -> dict:
    """Map vManage JSON → snake_case + basic type coercion."""
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

    # only copy keys that exist in the JSON
    out: dict[str, object] = {v: d.get(k) for k, v in mapping.items() if k in d}

    # type coercion for ints
    for k in (
        "control_connections", "omp_peers", "total_cpu_count",
        "linux_cpu_count", "layout_level",
        "max_controllers", "site_id"
    ):
        if k not in out:
            continue
        try:
            out[k] = int(out[k]) if out[k] not in (None, "--", "") else None
        except (ValueError, TypeError):
            out[k] = None

    # type coercion for floats
    for k in ("latitude", "longitude"):
        if k not in out:
            continue
        try:
            out[k] = float(out[k]) if out[k] not in (None, "--", "") else None
        except (ValueError, TypeError):
            out[k] = None

    return out


def main() -> None:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    pw = (
        VM_PASS
        or os.getenv("VM_PASS")
        or getpass.getpass(f"vManage password for {VM_USER}@{VM_HOST}: ")
    )

    # login to vManage
    auth = Authentication(VM_HOST, VM_USER, pw, validate_certs=False)
    session = auth.login()
    print("✅  logged in to vManage @", VM_HOST)

    devices = Device(session=session, host=VM_HOST).get_device_status_list()
    print(f"🔎  pulled {len(devices)} devices from vManage")

    # build rows
    ts_poll = datetime.now(timezone.utc)
    rows: list[dict] = []
    for d in devices:
        rec = normalise(d)
        rec["ts"] = ts_poll
        rows.append(rec)

    if not rows:
        print("⚠️  no device data returned")
        return

    # ensure uniform keys across all rows
    all_cols = sorted({ key for rec in rows for key in rec.keys() })
    for rec in rows:
        for key in all_cols:
            rec.setdefault(key, None)
    cols = all_cols

    # build SQL template
    template = "(" + ",".join([f"%({c})s" for c in cols]) + ")"
    set_clause = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "device_id"
    )
    conflict_where = (
        "WHERE device_inventory.lastupdated IS DISTINCT FROM EXCLUDED.lastupdated"
    )

    insert_sql = f"""
        INSERT INTO {TABLE} ({', '.join(cols)}) VALUES %s
        ON CONFLICT (device_id) DO UPDATE
        SET {set_clause}
        {conflict_where};
    """

    # execute batch upsert
    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, rows, template=template, page_size=200)
        conn.commit()

    print(f"💾  up-serted {len(rows)} device rows @ {ts_poll.isoformat()}")


if __name__ == "__main__":
    main()
