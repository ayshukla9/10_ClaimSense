"""Generate a submission .txt spec from the actual production origin.
Usage: python docs/a5/build_vega_spec.py https://YOUR.pythonanywhere.com
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

def make_spec(origin):
    url = urlsplit(origin)
    if url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.pythonanywhere.com') or url.path not in ('','/') or url.query or url.fragment or url.username or url.port:
        raise ValueError('Supply the actual HTTPS PythonAnywhere origin, without a path or credentials')
    return {
        '$schema': 'https://vega.github.io/schema/vega-lite/v5.json',
        'title': 'ClaimSense insurance plan catalogue by type',
        'description': 'Live database catalogue counts; no patient data.',
        'data': {'url': origin.rstrip('/')+'/api/public/plan-types/', 'format': {'type':'json'}},
        'mark': 'bar',
        'encoding': {
            'x': {'field':'plan_type', 'type':'nominal', 'title':'Plan type'},
            'y': {'field':'plan_count', 'type':'quantitative', 'title':'Plans', 'axis':{'tickMinStep':1}},
            'tooltip':[{'field':'plan_type'},{'field':'plan_count','type':'quantitative'}],
        },
    }

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    path = Path(__file__).with_name('production_plan_types.txt')
    path.write_text(json.dumps(make_spec(sys.argv[1]),indent=2)+'\n')
    print(path)
