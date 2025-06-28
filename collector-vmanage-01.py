

#!/usr/bin/env python3

import json
import re
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

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
                {"property":"tx_octets","type":"avg"},  # NEW: Tx octets
                {"property":"rx_octets","type":"avg"}   # NEW: Rx octets
            ]
        }
    }

    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    return resp.json().get("data", [])

def format_bytes(num_bytes):
    """Convert bytes to human-readable format (KB/MB/GB)"""
    for unit in ['', 'K', 'M', 'G']:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:6.1f}{unit}B"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f}TB"

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # vManage connection details
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # 1) Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 2) Fetch all devices and filter out control-plane nodes
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    data_plane_ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
        and d.get("personality", "").lower() not in ("vmanage", "vsmart", "vbond")
    ]

    if not data_plane_ips:
        print("❌ No data-plane routers found!")
        return

    # 3) Fetch aggregated SLA for all data-plane routers in one call
    sla_data = fetch_aggregated_sla(session, vm_host, data_plane_ips, hours=1)

    if not sla_data:
        print("❌ No SLA data returned for the given devices.")
        return

    # 4) Print the results with parsed name components
    header = (
        f"{'local-systemip':<18} {'local-color':<20} {'remote-systemip':<18} "
        f"{'remote-color':<20} {'LOSS%':>8} {'LAT(ms)':>8} {'JIT(ms)':>8} "
        f"{'Tx':>10} {'Rx':>10}"
    )
    print(header)
    print("-" * len(header))

    for rec in sla_data:
        name    = rec.get("name", "")
        # split on the hyphen that precedes the remote IP (digit)
        left, right = re.split(r'-(?=\d+\.\d+\.\d+\.\d+)', name, maxsplit=1)
        lip, lcol   = left.split(":",1)
        rip, rcol   = right.split(":",1)

        loss    = rec.get("loss_percentage", 0.0)
        latency = rec.get("latency",          0.0)
        jitter  = rec.get("jitter",           0.0)
        tx      = rec.get("tx_octets",        0.0)  # New metric
        rx      = rec.get("rx_octets",        0.0)  # New metric

        print(
            f"{lip:<18} {lcol:<20} {rip:<18} {rcol:<20} "
            f"{loss:8.2f} {latency:8.2f} {jitter:8.2f} "
            f"{format_bytes(tx):>10} {format_bytes(rx):>10}"
        )

if __name__ == "__main__":
    main()

