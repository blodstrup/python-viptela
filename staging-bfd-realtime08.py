#!/usr/bin/env python3

import re
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def fetch_tunnel_health_latest(session, host, device_id):
    """
    GET the very latest 1-second Tunnel-Health sample for numeric deviceId.
    """
    url = f"https://{host}:443/dataservice/statistics/tunnelhealth/history"
    params = {
        "deviceId":  device_id,
        "timescale": "1",
        "limit":     "1"
    }
    r = session.get(url, params=params, verify=False)
    r.raise_for_status()
    return r.json().get("data", [])

def normalize_tloc(tloc):
    """
    Split "A:colA-B:colB" → (A,colA,B,colB).
    """
    left, right = re.split(r'-(?=\d+\.\d+\.\d+\.\d+)', tloc, maxsplit=1)
    a, ca = left.split(":",1)
    b, cb = right.split(":",1)
    return a, ca, b, cb

def main():
    # suppress self-signed cert warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    vm_host, vm_user, vm_pass = "192.168.227.200","admin","password"
    auth    = Authentication(host=vm_host, user=vm_user,
                             password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 1) Use the library to fetch exactly the cEdge list (singular!)
    dev_api = Device(session=session, host=vm_host)
    cedges = dev_api.get_device_list("cedge")   # <-- notice singular

    # Build ip → numeric-ID map directly
    ip_to_id = {
        d["system-ip"]: d["deviceId"]
        for d in cedges
        if d.get("system-ip") and d.get("deviceId") is not None
    }

    # 2) Use the status list to pick only data-plane roles
    status = dev_api.get_device_status_list()
    edges = [
        d["system-ip"]
        for d in status
        if d.get("system-ip") not in (None,"0.0.0.0")
        and d.get("personality","").lower() not in ("vmanage","vsmart","vbond")
    ]
    if not edges:
        print("❌ No data-plane routers found!")
        return

    # 3) Print header
    hdr = (
      f"{'local-systemip':<16} {'local-color':<20} "
      f"{'remote-systemip':<16} {'remote-color':<20} "
      f"{'LOSS%':>6} {'LAT(ms)':>8} {'JIT(ms)':>8} "
      f"{'RX-Octets':>10} {'TX-Octets':>10}"
    )
    print(hdr)
    print("-"*len(hdr))

    # 4) For each cEdge IP, pull its numeric ID and fetch the latest sample
    for ip in edges:
        did = ip_to_id.get(ip)
        if not did:
            print(f"{ip:<16} (no deviceId)")
            continue

        try:
            samples = fetch_tunnel_health_latest(session, vm_host, did)
        except Exception as e:
            print(f"{ip:<16} ⚠️  error: {e}")
            continue

        if not samples:
            print(f"{ip:<16} (no tunnel data)")
            continue

        s = samples[0]
        lip, lcol, rip, rcol = normalize_tloc(s.get("tloc",""))
        print(
            f"{lip:<16} {lcol:<20} "
            f"{rip:<16} {rcol:<20} "
            f"{s.get('loss',0):6.2f} {s.get('latency',0):8.2f} {s.get('jitter',0):8.2f} "
            f"{s.get('rxOctets',0):10} {s.get('txOctets',0):10}"
        )

    print()

if __name__ == "__main__":
    main()
