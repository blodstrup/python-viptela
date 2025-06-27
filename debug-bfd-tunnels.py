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

    # 3. Grab every device’s status record
    dev_api = Device(session=session, host=vm_host)
    devices = dev_api.get_device_status_list()

    # 4. Filter only the Cisco 8000v routers (CEdges)
    cedges = [
        d for d in devices
        if d.get("deviceModel", "").lower().startswith("C8000")
        and d.get("managementSystemIP", "") not in ("", "0.0.0.0")
    ]
    if not cedges:
        print("❌ No Cisco‐8000 series devices found!")
        return

    # 5. Sanity check: list them
    print("Cisco‐8000 series routers:")
    for d in cedges:
        name = (d.get("host-name") or d.get("hostName") or
                d.get("serialNumber")  or d.get("uuid")     or
                "<unknown>")
        ip   = d["managementSystemIP"]
        print(f" • {name:20} [{ip}]")
    print()

    # 6. Prepare the MonitorNetwork client
    mon = MonitorNetwork(session=session, host=vm_host)

    # 7. Fetch and print BFD→TLOC for each cEdge
    for d in cedges:
        name = (d.get("host-name") or d.get("hostName") or
                d.get("serialNumber")  or d.get("uuid")     or
                "<unknown>")
        ip   = d["managementSystemIP"]

        print(f"--- BFD TLOC entries for {name} ({ip}) ---")
        try:
            entries = mon.get_bfd_tloc(system_ip=ip)
        except Exception as e:
            print(f" ⚠️  Skipping {name} ({ip}): {e}\n")
            continue

        if not entries:
            print("  (no BFD TLOC entries returned)\n")
            continue

        for e in entries:
            tloc    = e.get("tloc",       "<none>")
            state   = e.get("state",      "<unknown>")
            loss    = e.get("loss",       e.get("loss-rate","—"))
            jitter  = e.get("jitter",     e.get("jitter-rate","—"))
            latency = e.get("latency",    "—")
            print(
                f" • TLOC {tloc:30}   "
                f"State: {state:8}   "
                f"Loss%: {loss:5}   "
                f"Jitter: {jitter:5}   "
                f"Latency: {latency}"
            )
        print()

if __name__ == "__main__":
    main()


