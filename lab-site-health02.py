#!/usr/bin/env python3
"""
fetch_site_health_common.py

1) Authenticate to vManage
2) Pull /dataservice/statistics/sitehealth/common
3) Print rows in a simple ASCII table
4) Insert each row into PostgreSQL table site_health_common in DB vmanage01
"""

import sys
import json
import requests
import psycopg2
from urllib3.exceptions import InsecureRequestWarning

# suppress self-signed cert warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# vManage connection info
VMANAGE_HOST = "https://192.168.227.200"
VMANAGE_USER = "admin"
VMANAGE_PASS = "password"

# Database connection info
DB_HOST     = "192.168.227.252"
DB_NAME     = "vmanage01"
DB_USER     = "admin"
DB_PASS     = "admin"


def authenticate_session():
    sess = requests.Session()
    sess.verify = False
    login_url = f"{VMANAGE_HOST}/j_security_check"
    creds = {"j_username": VMANAGE_USER, "j_password": VMANAGE_PASS}
    r = sess.post(login_url, data=creds)
    if r.status_code != 200:
        print("Login failed", file=sys.stderr)
        sys.exit(1)
    token = sess.get(f"{VMANAGE_HOST}/dataservice/client/token").text
    sess.headers.update({
        "X-XSRF-TOKEN": token,
        "Content-Type": "application/json"
    })
    return sess


def fetch_site_health(sess):
    url = f"{VMANAGE_HOST}/dataservice/statistics/sitehealth/common"
    params = {
        "isHeatMap":     "false",
        "interval":      "30",
        "includeDetails":"false",
        "includeRegion": "false"
    }
    r = sess.get(url, params=params)
    r.raise_for_status()
    return r.json().get("data", [])


def print_table(rows):
    if not rows:
        print("No data to display.")
        return
    # Extract headers and compute column widths
    headers = list(rows[0].keys())
    widths = {}
    for h in headers:
        max_cell = max(len(str(r.get(h, ''))) for r in rows)
        widths[h] = max(len(h), max_cell)

    # Build header line
    header_line = ' | '.join(h.ljust(widths[h]) for h in headers)
    sep_line    = '-+-'.join('-' * widths[h] for h in headers)
    print(header_line)
    print(sep_line)

    # Print each row
    for r in rows:
        row_line = ' | '.join(str(r.get(h, '')).ljust(widths[h]) for h in headers)
        print(row_line)


def save_to_db(rows):
    conn = psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME,
        user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()
    insert_sql = """
    INSERT INTO site_health_common (
      site_id, site_name, latitude, longitude,
      site_health, devices_health, tunnels_health, apps_health,
      devices_health_score, tunnels_health_score, apps_health_score,
      apps_usage, prev_apps_usage
    ) VALUES (
      %(site_id)s, %(site_name)s, %(latitude)s, %(longitude)s,
      %(site_health)s, %(devices_health)s, %(tunnels_health)s, %(apps_health)s,
      %(devices_health_score)s, %(tunnels_health_score)s, %(apps_health_score)s,
      %(apps_usage)s, %(prev_apps_usage)s
    )
    """
    for row in rows:
        cur.execute(insert_sql, row)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Inserted {len(rows)} rows into site_health_common.")


def main():
    sess = authenticate_session()
    rows = fetch_site_health(sess)
    print_table(rows)
    if rows:
        save_to_db(rows)
    else:
        print("No data returned; skipping DB write.")


if __name__ == "__main__":
    main()


