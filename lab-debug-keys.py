#!/usr/bin/env python3

import json
from vmanage.api.authentication import Authentication
from vmanage.api.device import Device

def main():
    vm_host = "192.168.227.200"
    vm_user = "admin"
    vm_pass = "password"

    auth = Authentication(host=vm_host, user=vm_user, password=vm_pass, validate_certs=False)
    session = auth.login()

    dev_api = Device(session=session, host=vm_host)
    devices = dev_api.get_device_list(category="vedges")

    # Inspect the first 3 items
    print("First 3 device records (raw JSON):\n")
    for idx, d in enumerate(devices[:3], start=1):
        print(f"--- Device #{idx} ---")
        print(json.dumps(d, indent=2))
        print("Keys:", list(d.keys()))
        print()

if __name__ == "__main__":
    main()

