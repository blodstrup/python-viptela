#!/usr/bin/env python3

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

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
    print(f"✅ Authenticated to vManage @ {vm_host}")

    # 3. Instantiate the Device API
    dev_api = Device(session=session, host=vm_host)

    # 4. Fetch *all* devices (status list gives you host-name & system-ip)
    all_devices = dev_api.get_device_status_list()  # returns a list of dicts :contentReference[oaicite:0]{index=0}

    # 5. Filter out placeholders and print only real vEdges
    print("\nvEdge inventory:")
    for d in all_devices:
        ip = d.get("system-ip") or d.get("systemIp") or ""
        if not ip or ip == "0.0.0.0":
            continue

        hostname = (
            d.get("host-name")
            or d.get("hostName")
            or "<unknown>"
        )
        print(f" • {hostname:20} [{ip}]")

if __name__ == "__main__":
    main()

