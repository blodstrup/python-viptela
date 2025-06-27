#!/usr/bin/env python3

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device
from vmanage.api.monitor_network import MonitorNetwork

def main():
    # 1) connection info
    vm_host, vm_user, vm_pass = "192.168.227.200", "admin", "password"

    # 2) login
    auth    = Authentication(host=vm_host, user=vm_user, password=vm_pass, validate_certs=False)
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}\n")

    # 3) grab the full status list (gives you host-name + real system-ip)
    dev_api     = Device(session=session, host=vm_host)
    all_devices = dev_api.get_device_status_list()

    # 4) drop anything with the placeholder IP “0.0.0.0”
    real_edges = [
        d for d in all_devices
        if (d.get("system-ip") or d.get("systemIp") or "") not in ("", "0.0.0.0")
    ]
    if not real_edges:
        print("❌ No data-plane routers found! (all IPs were 0.0.0.0)")
        return

    # 5) sanity check: list them
    print("Data-plane devices:")
    for d in real_edges:
        name = d.get("host-name") or d.get("hostName") or d.get("serialNumber") or d.get("uuid")
        ip   = d.get("system-ip") or d.get("systemIp")
        print(f" • {name:20} [{ip}]")
    print()

    # 6) build monitor client
    mon = MonitorNetwork(session=session, host=vm_host)

    # 7) pull BFD→TLOC for each one
    for d in real_edges:
        name = d.get("host-name") or d.get("hostName") or d.get("serialNumber") or d.get("uuid")
        ip   = d.get("system-ip") or d.get("systemIp")

        print(f"--- BFD TLOC entries for {name} ({ip}) ---")
        try:
            bfd_list = mon.get_bfd_tloc(system_ip=ip)
        except Exception as e:
            print(f" ⚠️ Skipping {name} ({ip}): {e}\n")
            continue

        if not bfd_list:
            print("  (no BFD→TLOC entries returned)\n")
            continue

        for e in bfd_list:
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


