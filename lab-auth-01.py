#!/usr/bin/env python3

from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def main():
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    # 1. Authenticate
    auth = Authentication(
        host=vm_host,
        user=vm_user,
        password=vm_pass,
        validate_certs=False
    )
    session = auth.login()
    print(f"✅ Authenticated to vManage @ {vm_host}")

    # 2. Instantiate Device API
    dev_api = Device(session=session, host=vm_host)

    # 3. Fetch vEdges — returns a list of dicts
    vedges = dev_api.get_device_list(category="vedges")

    # 4. Print inventory
    print("vEdge inventory:")
    for d in vedges:
        hostname = d.get("host-name") or d.get("hostname")
        sysip    = d.get("system-ip") or d.get("systemIp")
        print(f" • {hostname}  [{sysip}]")

if __name__ == "__main__":
    main()
