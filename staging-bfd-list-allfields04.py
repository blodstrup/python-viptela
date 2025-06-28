#!/usr/bin/env python3

import json
import re
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_fec_aggregation(session, host, device_ips, hours=1):
    url = f"https://{host}:443/dataservice/statistics/approute/fec/aggregation"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                { "field":"entry_time",      "type":"date",   "operator":"last_n_hours", "value":[str(hours)] },
                { "field":"local_system_ip", "type":"string", "operator":"in",           "value":device_ips }
            ]
        },
        "aggregation": {
            "field":[{"property":"name","sequence":1}],
            "metrics":[
                {"property":"loss_percentage","type":"avg"},
                {"property":"latency",        "type":"avg"},
                {"property":"jitter",         "type":"avg"}
            ]
        }
    }
    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    return resp.json()

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()

    # Collect data-plane IPs
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("","0.0.0.0")
        and d.get("personality","").lower() not in ("vmanage","vsmart","vbond")
    ]

    raw = fetch_fec_aggregation(session, vm_host, ips, hours=1)
    records = raw.get("data", [])

    print("\n=== Parsed tunnel breakdown ===")
    hdr = f"{'LOCAL-IP':<16} {'L-COLOR':<20} {'REMOTE-IP':<16} {'R-COLOR':<20} {'LOSS%':>6} {'LAT(ms)':>8} {'JIT(ms)':>8}"
    print(hdr)
    print("-" * len(hdr))

    for r in records:
        name = r.get("name","")
        # split on the hyphen that precedes the remote IP (digit)
        left, right = re.split(r'-(?=\d+\.\d+\.\d+\.\d+)', name, maxsplit=1)
        lip, lcol   = left.split(":",1)
        rip, rcol   = right.split(":",1)

        loss = r.get("loss_percentage", 0.0)
        lat  = r.get("latency",          0.0)
        jit  = r.get("jitter",           0.0)

        print(f"{lip:<16} {lcol:<20} {rip:<16} {rcol:<20} {loss:6.3f} {lat:8.2f} {jit:8.2f}")

if __name__ == "__main__":
    main()

