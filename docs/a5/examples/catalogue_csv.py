"""Use case 1: reporting/export. Supply the real production origin."""
import csv
import json
import sys
from urllib.request import urlopen
with urlopen(sys.argv[1].rstrip('/')+'/api/public/plan-types/', timeout=20) as response:
    rows = json.load(response)
writer = csv.DictWriter(sys.stdout,fieldnames=['plan_type','plan_count'])
writer.writeheader()
writer.writerows(rows)
