#!/usr/bin/env python3
import json
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_sla_for_device(session, host, device_ip, hours=1):
    """
    Query the Application Aware Routing Aggregation API for a single device,
    returning a list of tunnels with avg loss, latency, jitter.
    """
    url = f"https://{host}:443/dataservice/statistics/approute/fec/aggregation"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                {
                    "field":    "entry_time",
                    "type":     "date",
                    "operator": "last_n_hours",
                    "value":    [str(hours)]
                },
                {
                    "field":    "local_system_ip",
                    "type":     "string",
                    "operator": "in",
                    "value":    [device_ip]
                }
            ]
        },
        "aggregation": {
            "field": [
                { "property": "name", "sequence": 1 }
            ],
            "metrics": [
                { "property": "loss_percentage", "type": "avg" },
                { "property": "latency",         "type": "avg" },
                { "property": "jitter",          "type": "avg" }
            ]
        }
    }

    resp = session.post(
        url,
        json=payload,
        verify=False  # because we used validate_certs=False
    )
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 1) vManage creds & host
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # 2) Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 3) Build list of data-plane routers
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    edges = [
        d.get("system-ip") or d.get("systemIp")
        for d in all_devs
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
    ]
    if not edges:
        print("❌ No data-plane routers found!")
        return

    # 4) For each edge, fetch & print SLA per tunnel
    for ip in edges:
        print(f"--- SLA metrics for device {ip} (last 1h) ---")
        try:
            sla_list = fetch_sla_for_device(session, vm_host, ip, hours=1)
        except Exception as e:
            print(f" ⚠️  Failed for {ip}: {e}\n")
            continue

        if not sla_list:
            print("  (no tunnel data returned)\n")
            continue

        # header
        print(f"{'TUNNEL NAME':<30} {'LOSS%':>8} {'LAT(ms)':>10} {'JIT(ms)':>10}")
        print("-" * 60)
        for t in sla_list:
            name    = t.get("name",              "<unknown>")
            loss    = t.get("loss_percentage",   0.0)
            latency = t.get("latency",           0.0)
            jitter  = t.get("jitter",            0.0)
            print(f"{name:<30} {loss:8.2f} {latency:10.2f} {jitter:10.2f}")
        print()

if __name__ == "__main__":
    main()
