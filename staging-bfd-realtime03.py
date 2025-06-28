#!/usr/bin/env python3

import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_realtime_tunnel_metrics(session, host, device_ip):
    """
    Fetch real-time tunnel health statistics for a device.
    """
    url = f"https://{host}:443/dataservice/device/app-route/statistics"
    resp = session.get(
        url,
        params={"deviceId": device_ip},
        verify=False
    )
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # vManage connection info
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # Authenticate
    auth = Authentication(
        host=vm_host,
        user=vm_user,
        password=vm_pass,
        validate_certs=False
    )
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # Fetch edge devices (non-control-plane)
    dev_api  = Device(session=session, host=vm_host)
    all_devs = dev_api.get_device_status_list()
    edges = [
        d["system-ip"] for d in all_devs
        if d.get("system-ip") not in (None, "0.0.0.0")
        and d.get("personality", "").lower() not in ("vmanage", "vsmart", "vbond")
    ]

    if not edges:
        print("❌ No data-plane routers found!")
        return

    # Fetch & print real-time tunnel metrics per device (latest only)
    for ip in edges:
        print(f"--- REAL-TIME TUNNEL METRICS for {ip} ---")
        try:
            tunnel_data = fetch_realtime_tunnel_metrics(session, vm_host, ip)
        except Exception as e:
            print(f"⚠️  Failed for {ip}: {e}\n")
            continue

        if not tunnel_data:
            print("  (no tunnel data)\n")
            continue

        # build a dict to keep only the latest sample per tunnel
        latest = {}
        for t in tunnel_data:
            key = (t.get("src-ip"), t.get("dst-ip"))
            latest[key] = t

        # Print table header
        print(f"{'SRC-IP':<15} {'DST-IP':<15} {'LAT(ms)':>8} {'JIT(ms)':>8} {'LOSS%':>8} {'LAST-UPDATED':>15}")
        print("-" * 80)
        for (src, dst), t in latest.items():
            lat     = t.get("mean-latency", t.get("latency", 0))
            jit     = t.get("mean-jitter",  t.get("jitter",  0))
            loss    = t.get("loss",          t.get("lossPercentage", 0))
            updated = t.get("lastupdated", "")
            print(f"{src:<15} {dst:<15} {lat:8} {jit:8} {loss:8} {updated:>15}")
        print()

if __name__ == "__main__":
    main()

