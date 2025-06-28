
#!/usr/bin/env python3

import json
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_realtime_sla_for_device(session, host, device_ip, minutes=1):
    """
    Query real-time App-Aware Routing statistics for a device
    Returns tunnel metrics for the last N minutes (default=1)
    """
    url = f"https://{host}:443/dataservice/statistics/approute/fec"
    payload = {
        "query": {
            "condition": "AND",
            "rules": [
                {
                    "field": "entry_time",
                    "type": "date",
                    "operator": "last_n_minutes",
                    "value": [str(minutes)]
                },
                {
                    "field": "local_system_ip",
                    "type": "string",
                    "operator": "in",
                    "value": [device_ip]
                }
            ]
        },
        "size": 10000  # Ensure we get all recent records
    }

    resp = session.post(url, json=payload, verify=False)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    
    # Aggregate metrics per tunnel (simple average)
    tunnel_metrics = {}
    for record in data:
        tunnel_name = record.get("name", "<unknown>")
        metrics = tunnel_metrics.setdefault(tunnel_name, {
            "loss": [], "latency": [], "jitter": []
        })
        
        if (loss := record.get("loss_percentage")) is not None:
            metrics["loss"].append(loss)
        if (latency := record.get("latency")) is not None:
            metrics["latency"].append(latency)
        if (jitter := record.get("jitter")) is not None:
            metrics["jitter"].append(jitter)
    
    # Calculate averages per tunnel
    result = []
    for name, metrics in tunnel_metrics.items():
        result.append({
            "name": name,
            "loss_percentage": sum(metrics["loss"])/len(metrics["loss"]) if metrics["loss"] else 0,
            "latency": sum(metrics["latency"])/len(metrics["latency"]) if metrics["latency"] else 0,
            "jitter": sum(metrics["jitter"])/len(metrics["jitter"]) if metrics["jitter"] else 0
        })
    
    return result

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 1) vManage connection info
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # 2) Authenticate
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 3) Fetch edge devices (non-control-plane)
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()

    edges = [
        d["system-ip"] for d in all_devs
        if (d.get("system-ip") not in (None, "0.0.0.0")
        and d.get("personality", "").lower() not in ("vmanage", "vsmart", "vbond")
    ]

    if not edges:
        print("❌ No data-plane routers found!")
        return

    # 4) Fetch & print real-time SLA per tunnel
    for ip in edges:
        print(f"--- REAL-TIME SLA for {ip} (last 1 min) ---")
        try:
            sla_list = fetch_realtime_sla_for_device(session, vm_host, ip)
        except Exception as e:
            print(f"⚠️  Failed for {ip}: {e}\n")
            continue

        if not sla_list:
            print("  (no tunnel data)\n")
            continue

        # Print table header
        print(f"{'TUNNEL':<30} {'LOSS%':>8} {'LAT(ms)':>10} {'JIT(ms)':>10}")
        print("-" * 60)
        for t in sla_list:
            print(f"{t['name'][:29]:<30} {t['loss_percentage']:8.2f} "
                  f"{t['latency']:10.2f} {t['jitter']:10.2f}")
        print()

if __name__ == "__main__":
    main()
