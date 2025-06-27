#!/usr/bin/env python3

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device
from vmanage.api.monitor_network import MonitorNetwork

def main():
    # 1. Connection details
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # 2. Authenticate
    auth = Authentication(
        host=vm_host,
        user=vm_user,
        password=vm_pass,
        validate_certs=False
    )
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 3. Get all vEdge system-IPs
    dev_api = Device(session=session, host=vm_host)
    all_devices = dev_api.get_device_status_list()      # full device list
    vedges = [d for d in all_devices if d.get("deviceType","").lower()=="vedge"]

    # 4. Instantiate MonitorNetwork for BFD calls
    mon = MonitorNetwork(session=session, host=vm_host)

    # 5. Loop and collect BFD-TLOC data
    for d in vedges:
        sysip = d.get("system-ip") or d.get("systemIp")
        if not sysip or sysip == "0.0.0.0":
            continue

        # pull the BFD→TLOC table for this device
        bfd = mon.get_bfd_tloc(system_ip=sysip)           # :contentReference[oaicite:0]{index=0}

        print(f"--- BFD TLOC for {sysip} ---")
        for entry in bfd.get("data", []):
            tloc        = entry.get("tloc", "<none>")
            state       = entry.get("state", "<unknown>")
            loss        = entry.get("loss", entry.get("loss-rate","—"))
            jitter      = entry.get("jitter", entry.get("jitter-rate","—"))
            latency     = entry.get("latency", "—")
            print(f" • TLOC {tloc:25}  State: {state:8}  Loss%: {loss:5}  Jitter: {jitter:5}  Latency: {latency}")
        print()

if __name__ == "__main__":
    main()

