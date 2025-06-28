#!/usr/bin/env python3

import json
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_fec_aggregation(session, host, device_ips, hours=1):
    """
    POST to the FEC aggregation endpoint, grouping only on 'name'.
    """
    url = f"https://{host}:443/dataservice/statistics/approute/fec/aggregation"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                { "field":"entry_time",      "type":"date",   "operator":"last_n_hours", "value":[str(hours)] },
                { "field":"local_system_ip", "type":"string","operator":"in",           "value":device_ips }
            ]
        },
        "aggregation": {
            "field": [
                { "property":"name", "sequence":1 }
            ],
            "metrics": [
                { "property":"loss_percentage", "type":"avg" },
                { "property":"latency",         "type":"avg" },
                { "property":"jitter",          "type":"avg" }
            ]
        }
    }
    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    return resp.json()

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # 1) Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 2) Build list of data-plane IPs
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
        and d.get("personality","").lower() not in ("vmanage","vsmart","vbond")
    ]
    if not ips:
        print("❌ No data-plane routers found!")
        return

    # 3) Fetch raw FEC aggregation
    raw = fetch_fec_aggregation(session, vm_host, ips, hours=1)

    # 4) Show full response so you see exactly what fields returned
    print("=== Full JSON Response ===\n")
    print(json.dumps(raw, indent=2))

    records = raw.get("data", [])
    if not records:
        print("\n❌ No records in data.")
        return

    # 5) Parse each record.name into its components and print a nice table
    print("\n=== Parsed tunnel breakdown ===")
    hdr = f"{'LOCAL-IP':<16} {'L-COLOR':<8} {'REMOTE-IP':<16} {'R-COLOR':<8} {'LOSS%':>6} {'LAT(ms)':>8} {'JIT(ms)':>8}"
    print(hdr)
    print("-" * len(hdr))
    for r in records:
        # name is "localIP:localColor-remoteIP:remoteColor"
        name = r.get("name","")
        try:
            left, right = name.split("-",1)
            lip, lcol   = left.split(":",1)
            rip, rcol   = right.split(":",1)
        except ValueError:
            lip = lcol = rip = rcol = "<parse-error>"

        loss = r.get("loss_percentage", 0.0)
        lat  = r.get("latency",          0.0)
        jit  = r.get("jitter",           0.0)

        print(f"{lip:<16} {lcol:<8} {rip:<16} {rcol:<8} {loss:6.3f} {lat:8.2f} {jit:8.2f}")

if __name__ == "__main__":
    main()

