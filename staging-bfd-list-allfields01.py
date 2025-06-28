#!/usr/bin/env python3

import json
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_aggregation_raw(session, host, device_ips, hours=1):
    """
    Fetch raw aggregation payload from the App-Route FEC aggregation endpoint
    for the given list of device IPs over the last `hours` hours.
    """
    url = f"https://{host}:443/dataservice/statistics/approute/fec/aggregation"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                {"field":"entry_time",      "type":"date",   "operator":"last_n_hours", "value":[str(hours)]},
                {"field":"local_system_ip", "type":"string", "operator":"in",           "value":device_ips}
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
    return resp.json()  # full JSON, including top-level "data"

def main():
    # suppress warnings for self-signed certs
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # vManage connection info
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # 1) Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 2) Gather data-plane IPs (skip control-plane)
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    data_plane_ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
        and d.get("personality", "").lower() not in ("vmanage","vsmart","vbond")
    ]
    if not data_plane_ips:
        print("❌ No data-plane routers found!")
        return

    # 3) Fetch raw aggregation JSON
    raw = fetch_aggregation_raw(session, vm_host, data_plane_ips, hours=1)

    # 4) Pretty-print the full JSON
    print("=== Full JSON Response ===\n")
    print(json.dumps(raw, indent=2))

    # 5) Compute and display all unique field names under "data"
    data = raw.get("data", [])
    fields = set()
    for rec in data:
        fields.update(rec.keys())

    print("\n=== Fields returned in each record ===")
    for f in sorted(fields):
        print(f"- {f}")

if __name__ == "__main__":
    main()
