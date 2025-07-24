#!/usr/bin/env python3
"""
device-collector-04.py – inventory ingestor + CSV dump + pretty table

• Polls Cisco vManage for the current device list.
• Prints a CSV of every device record (header + rows) to stdout so it can be piped into a table.
• Also prints a fixed-width table summary of key fields.
• Keeps exactly ONE row per device_id in the table `device_inventory` via upsert.
"""

from __future__ import annotations
import os
import sys
import csv
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
VM_PASS = "password"  # leave blank → prompt/env var
# ────────────────────── PostgreSQL connection ──────────────────────────────
PG_CONN: dict[str, str | int] = {
    "host": "localhost",
    "port": 5432,
    "dbname": "vmanage01",
    "user": "postgres",
    "password": "8ds0jq",
}
TABLE = "device_inventory"
# ────────────────────────────────────────────────────────────────────────────

def print_table(headers: list[str], rows: list[list]):
    """Print a fixed-width table from headers and rows."""
    # compute column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    # format string
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    # header
    print(fmt.format(*headers))
    print("-" * (sum(widths) + 2 * (len(widths)-1)))
    # rows
    for row in rows:
        print(fmt.format(*[str(cell) for cell in row]))


def normalise(d: dict) -> dict:
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
    out: dict[str, object] = {v: d.get(k) for k, v in mapping.items() if k in d}
    # int coercion
    for k in (
        "control_connections", "omp_peers", "total_cpu_count",
        "linux_cpu_count", "layout_level", "max_controllers", "site_id"
    ):
        if k in out:
            try:
                out[k] = int(out[k]) if out[k] not in (None, "--", "") else None
            except (ValueError, TypeError):
                out[k] = None
    # float coercion
    for k in ("latitude", "longitude"):
        if k in out:
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
    # login
    auth = Authentication(VM_HOST, VM_USER, pw, validate_certs=False)
    session = auth.login()
    print(f"✅  Logged in to vManage @ {VM_HOST}")

    devices = Device(session=session, host=VM_HOST).get_device_status_list()
    print(f"🔎  Pulled {len(devices)} devices from vManage")

    ts_poll = datetime.now(timezone.utc)
    rows: list[dict] = [{**normalise(d), "ts": ts_poll} for d in devices]
    if not rows:
        print("⚠️  No device data returned")
        return

    # uniform columns
    all_cols = sorted({key for rec in rows for key in rec.keys()})
    for rec in rows:
        for c in all_cols:
            rec.setdefault(c, None)

    # CSV output
    writer = csv.writer(sys.stdout)
    writer.writerow(all_cols)
    for rec in rows:
        writer.writerow([rec[c] for c in all_cols])

    # Pretty table for key fields
    headers = ["device_id", "host_name", "system_ip", "device_type", "version", "reachability", "site_id"]
    table_rows = [[rec[h] for h in headers] for rec in rows]
    print("\nDevice Inventory Summary:")
    print_table(headers, table_rows)

    # upsert
    template = "(" + ",".join(f"%({c})s" for c in all_cols) + ")"
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in all_cols if c != "device_id")
    conflict_where = "WHERE device_inventory.lastupdated IS DISTINCT FROM EXCLUDED.lastupdated"
    insert_sql = f"""
        INSERT INTO {TABLE} ({', '.join(all_cols)}) VALUES %s
        ON CONFLICT (device_id) DO UPDATE
          SET {set_clause}
        {conflict_where};
    """
    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, rows, template=template, page_size=200)
        conn.commit()

    print(f"💾  Upserted {len(rows)} rows into {TABLE} at {ts_poll.isoformat()}")


if __name__ == "__main__":
    main()

