#!/usr/bin/env python3

import json
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_aggregated_sla(session, host, device_ips, hours=1):
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
                {"property":"jitter","type":"avg"}
            ]
        }
    }
    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # 1) auth
    auth    = Authentication(host=vm_host, user=vm_user, password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 2) get data-plane IPs
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    data_plane_ips = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("","0.0.0.0")
        and d.get("personality","").lower() not in ("vmanage","vsmart","vbond")
    ]
    if not data_plane_ips:
        print("❌ No data-plane routers found!"); return

    # 3) fetch SLA
    sla = fetch_aggregated_sla(session, vm_host, data_plane_ips, hours=1)
    if not sla:
        print("❌ No SLA data returned."); return

    # DEBUG: print the first record to inspect keys
    print("DEBUG first record:", json.dumps(sla[0], indent=2), "\n")

    # 4) print table with correct key lookups
    print(f"{'SRC-IP':<16} {'DST-IP':<16} {'LOSS%_AVG':>10} {'LAT(ms)_AVG':>12} {'JIT(ms)_AVG':>12}")
    print("-"*70)
    for rec in sla:
        # adjust these lookups to match the keys you saw in DEBUG
        src = rec.get("sourceSystemIp") or rec.get("source_system_ip") or "<unk>"
        dst = rec.get("destSystemIp")   or rec.get("dest_system_ip")   or "<unk>"
        loss = rec.get("loss_percentage_avg") or rec.get("lossPercentageAvg") or rec.get("loss_percent_avg") or 0
        lat  = rec.get("latency_avg")         or rec.get("latencyAvg")        or 0
        jit  = rec.get("jitter_avg")          or rec.get("jitterAvg")         or 0

        print(f"{src:<16} {dst:<16} {float(loss):10.2f} {float(lat):12.2f} {float(jit):12.2f}")

if __name__ == "__main__":
    main()
