"""Use case 3: automated catalogue health check. No patient data involved.
Exit 0: nonempty counts; exit 1: empty catalogue; network failures propagate.
"""
import json
import sys
from urllib.request import urlopen
url = sys.argv[1].rstrip('/')+'/api/public/plan-types/'
with urlopen(url, timeout=20) as response:
    rows = json.load(response)
total = sum(row['plan_count'] for row in rows)
print(f'Source: {url}\nCatalogue: {total} plans across {len(rows)} types')
print('PASS' if total else 'FAIL: empty catalogue')
sys.exit(0 if total else 1)
