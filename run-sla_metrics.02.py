#!/usr/bin/env python3

import re
import urllib3
import psycopg2
from psycopg2 import OperationalError
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

# ——————————————————————————————————————————————
# 1) Database connection parameters
DB_PARAMS = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "vmanage01",
    "user":     "postgres",
    "password": "8ds0jq"
}

# 2) Fetch SLA helper (unchanged)
def fetch_aggregated_sla(session, host, device_ips, hours=1):
    """
    Fetch aggregated SLA metrics including Tx/Rx octets
    """
    url = f"https://{host}:443/dataservice/statistics/approute/fec/aggregation"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                {"field":"entry_time","type":"date","operator":"last_n_hours","value":[str(hours)]},
                {"field":"local_system_ip","type":"string","operator":"in","value":device_ips}
            ]
        },
        "aggregation": {
            "field":[{"property":"name","sequence":1}],
            "metrics":[
                {"property":"loss_percentage","type":"avg"},
                {"property":"latency","type":"avg"},
                {"property":"jitter","type":"avg"},
                {"property":"tx_octets","type":"avg"},
                {"property":"rx_octets","type":"avg"}
            ]
        }
    }

    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    return resp.json().get("data", [])

# 3) Insert helper (unchanged)
def insert_sla(cur, rec):
    """
    Parse one SLA record and insert into sla_metrics table.
    """
    left, right = re.split(r'-(?=\d+\.\d+\.\d+\.\d+)', rec["name"], maxsplit=1)
    lip, lcol   = left.split(':', 1)
    rip, rcol   = right.split(':', 1)

    loss    = rec.get("loss_percentage", 0.0)
    latency = rec.get("latency",          0.0)
    jitter  = rec.get("jitter",           0.0)
    tx      = int(rec.get("tx_octets",    0.0))
    rx      = int(rec.get("rx_octets",    0.0))

    cur.execute("""
        INSERT INTO sla_metrics (
            local_system_ip, local_color,
            remote_system_ip, remote_color,
            loss_percentage, latency, jitter,
            tx_octets, rx_octets
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
    """, (lip, lcol, rip, rcol, loss, latency, jitter, tx, rx))

# Utility: print a list of dicts as a table
def print_table(records, headers):
    # compute column widths
    cols = headers
    widths = {h: len(h) for h in cols}
    for rec in records:
        for h in cols:
            val = str(rec.get(h, ""))
            widths[h] = max(widths[h], len(val))

    # header row
    header_line = " | ".join(h.ljust(widths[h]) for h in cols)
    sep_line = "-+-".join('-' * widths[h] for h in cols)
    print(header_line)
    print(sep_line)
    # data rows
    for rec in records:
        row = " | ".join(str(rec.get(h, "")).ljust(widths[h]) for h in cols)
        print(row)

# 4) Main flow with manual table printing
def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # Discover data-plane devices
    dev_api   = Device(session=session, host=vm_host)
    all_devs  = dev_api.get_device_status_list()
    data_plane_ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
        and d.get("personality", "").lower() not in ("vmanage","vsmart","vbond")
    ]
    if not data_plane_ips:
        print("❌ No data-plane routers found!")
        return

    # Fetch SLA data
    sla_data = fetch_aggregated_sla(session, vm_host, data_plane_ips, hours=1)
    if not sla_data:
        print("❌ No SLA data returned.")
        return

    # Build records for printing
    headers = [
        "Local IP", "Local Color", "Remote IP", "Remote Color",
        "Loss %", "Latency", "Jitter", "Tx Octets", "Rx Octets"
    ]
    records = []
    for rec in sla_data:
        left, right = re.split(r'-(?=\d+\.\d+\.\d+\.\d+)', rec["name"], maxsplit=1)
        lip, lcol = left.split(':', 1)
        rip, rcol = right.split(':', 1)
        records.append({
            "Local IP": lip,
            "Local Color": lcol,
            "Remote IP": rip,
            "Remote Color": rcol,
            "Loss %": rec.get("loss_percentage", 0.0),
            "Latency": rec.get("latency", 0.0),
            "Jitter": rec.get("jitter", 0.0),
            "Tx Octets": int(rec.get("tx_octets", 0.0)),
            "Rx Octets": int(rec.get("rx_octets", 0.0)),
        })

    # Print table
    print("🔍 SLA Data:")
    print_table(records, headers)

    # Connect to DB and insert
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
    except OperationalError as e:
        print(f"❌ Database connection failed: {e}")
        return

    for rec in sla_data:
        insert_sla(cur, rec)

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Inserted {len(sla_data)} rows into sla_metrics")

if __name__ == "__main__":
    main()

