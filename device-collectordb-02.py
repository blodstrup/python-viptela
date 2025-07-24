#!/usr/bin/env python3
"""
ingest_vmanage_inventory.py – fixed version
"""

import os
import getpass
import urllib3
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_batch

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device


# ─────────────────────── configuration ─────────────────────
VM_HOST = "192.168.227.200"
VM_USER = "admin"
VM_PASS = "password"                       # leave blank → prompt / env-var

PG_CONN = dict(
    host="localhost",
    port=5432,
    dbname="vmanage01",
    user="postgres",
    password="8ds0jq",
)

TABLE = "vmanage_device_inventory"
# ────────────────────────────────────────────────────────────


def normalise(d: dict) -> dict:
    """Rename vManage keys → snake_case"""
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

    # type coercion helpers
    for k in (
        "control_connections", "omp_peers", "total_cpu_count",
        "linux_cpu_count", "status_order", "layout_level",
        "max_controllers", "site_id", "domain_id"
    ):
        if out[k] in (None, "", "--"):
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

    return out


def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # login – prompt if password not set
    pw = VM_PASS or os.getenv("VM_PASS") or getpass.getpass("vManage password: ")
    auth = Authentication(VM_HOST, VM_USER, pw, validate_certs=False)
    session = auth.login()
    print(f"✅  Authenticated to vManage @ {VM_HOST}")

    dev_api = Device(session=session, host=VM_HOST)
    devices = dev_api.get_device_status_list()
    print(f"🔎  Retrieved {len(devices)} devices")

    ts_now = datetime.now(timezone.utc)
    rows = []
    for d in devices:
        rec = normalise(d)
        rec["ts"] = ts_now    # same timestamp for this snapshot
        rows.append(rec)

    # -------- SQL (fixed ordering) --------
    cols = [c for c in rows[0].keys() if c != "ts"]
    insert_sql = f"""
        INSERT INTO {TABLE} (
            ts, {', '.join(cols)}
        ) VALUES (
            %(ts)s, {', '.join([f'%({c})s' for c in cols])}
        );
    """

    with psycopg2.connect(**PG_CONN) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, insert_sql, rows, page_size=100)
        conn.commit()

    print(f"💾  Inserted {len(rows)} rows at {ts_now.isoformat()}")


if __name__ == "__main__":
    main()
