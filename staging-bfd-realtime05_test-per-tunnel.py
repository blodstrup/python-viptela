#!/usr/bin/env python3
import urllib3
from vmanage.api.authentication import Authentication
from vmanage.api.http_methods import HttpMethods

def fetch_tunnel_health(session, host, device_ip, limit=1, interval=1):
    url    = f"https://{host}:443/dataservice/statistics/tunnelhealth/history"
    params = {
      "deviceId":       device_ip,
      "timescale":      str(interval),  # in seconds
      "limit":          str(limit),
      "entityType":     "vedge"
    }
    resp = session.get(url, params=params, verify=False)
    resp.raise_for_status()
    return resp.json().get("data", [])

def main():
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    vm_host, vm_user, vm_pass = "192.168.227.200","admin","password"

    # login
    auth    = Authentication(vm_host, vm_user, vm_pass, validate_certs=False)
    session = auth.login()

    for ip in ("192.168.107.11","192.168.107.12"):
        print(f"--- TunnelHealth for {ip} (latest) ---")
        data = fetch_tunnel_health(session, vm_host, ip, limit=1, interval=1)
        for entry in data:
            print(
              f"{entry['tloc']:<30} "
              f"loss={entry['loss']}%  "
              f"lat={entry['latency']}ms  "
              f"jit={entry['jitter']}ms"
            )
        print()

if __name__=="__main__":
    main()

