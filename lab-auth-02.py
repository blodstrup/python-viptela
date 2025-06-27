#!/usr/bin/env python3

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def main():
    # ───► 1. Connection details ◄───
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # ───► 2. Authenticate ◄───
    auth = Authentication(
        host=vm_host,
        user=vm_user,
        password=vm_pass,
        validate_certs=False
    )
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}")

    # ───► 3. Instantiate the Device API ◄───
    dev_api = Device(session=session, host=vm_host)

    # ───► 4. Fetch vEdges (or all devices) — returns a list of dicts
    devices = dev_api.get_device_list(category="vedges")

    # ───► 5. Print inventory with fallback key names ◄───
    print("\nvEdge inventory:")
    for d in devices:
        # try several possible key names for hostname
        hostname = (
            d.get("host-name")
            or d.get("hostName")
            or d.get("hostname")
            or "<unknown>"
        )
        # try several possible key names for system IP
        sysip = (
            d.get("system-ip")
            or d.get("systemIp")
            or d.get("systemIpAddress")
            or "<unknown>"
        )
        print(f" • {hostname:20} [{sysip}]")

if __name__ == "__main__":
    main()
