#!/usr/bin/env python3
"""
1) Parses site-matrix16.txt
2) Prints it as a nice ASCII table (no tabulate/etc)
3) Deletes existing rows and inserts the new rows into PostgreSQL table site_matrix
"""

import psycopg2
import os
import sys

INPUT_FILE = 'site-matrix16.txt'


def parse_file(path):
    rows = []
    with open(path) as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            # split on commas, then on first '='
            parts = [p.split('=', 1) for p in line.split(',')]
            d = {k: v for k, v in parts}
            rows.append({
                'site_type':  d.get('type', ''),
                'remotesite': d.get('remotesite', ''),
                'host_name':  d.get('name', ''),
                'site_ip':    d.get('site_ip', '')
            })
    return rows


def print_table(rows, cols):
    # compute max width for each column
    widths = {}
    for c in cols:
        widths[c] = max(len(c), *(len(r[c]) for r in rows))
    # header
    hdr = " | ".join(c.ljust(widths[c]) for c in cols)
    sep = "-+-".join('-' * widths[c] for c in cols)
    print(hdr)
    print(sep)
    # rows
    for r in rows:
        print(" | ".join(r[c].ljust(widths[c]) for c in cols))
    print()


def insert_into_db(rows, cols):
    # You can also set PGHOST, PGUSER, PGDATABASE, PGPASSWORD in env
    conn = psycopg2.connect(
        host=os.getenv('PGHOST', 'localhost'),
        dbname=os.getenv('PGDATABASE', 'vmanage01'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', '8ds0jq'),
        port=os.getenv('PGPORT', '5432'),
    )
    cur = conn.cursor()

    # Remove all existing rows
    cur.execute("DELETE FROM site_matrix;")

    sql = """
    INSERT INTO site_matrix (site_type, remotesite, host_name, site_ip)
    VALUES (%s, %s, %s, %s)
    """
    for r in rows:
        cur.execute(sql, [r[c] for c in cols])

    conn.commit()
    cur.close()
    conn.close()


def main():
    if not os.path.isfile(INPUT_FILE):
        print(f"Error: cannot find {INPUT_FILE}", file=sys.stderr)
        sys.exit(1)

    rows = parse_file(INPUT_FILE)
    if not rows:
        print("No data found.", file=sys.stderr)
        sys.exit(1)

    cols = ['site_type', 'remotesite', 'host_name', 'site_ip']
    print("\nData to be inserted:\n")
    print_table(rows, cols)

    confirm = input("Proceed to delete existing data and insert new rows into site_matrix? [y/N] ")
    if confirm.lower() != 'y':
        print("Aborted.")
        sys.exit(0)

    insert_into_db(rows, cols)
    print("Done! Inserted", len(rows), "rows (after deleting existing data).")


if __name__ == '__main__':
    main()

