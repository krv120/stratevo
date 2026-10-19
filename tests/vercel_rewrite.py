"""Local rewrite simulation, not a claim of testing Vercel infrastructure."""
import json
import re
from pathlib import Path
from urllib.parse import quote, urlsplit
from api.index import handler


def destination(path):
    rule = json.loads((Path(__file__).resolve().parents[1] / 'vercel.json').read_text())['rewrites'][0]
    request = urlsplit(path)
    match = re.fullmatch(rule['source'], request.path)
    if not match:
        raise ValueError('Request did not match configured rewrite')
    target = rule['destination']
    for index, value in enumerate(match.groups(), 1):
        target = target.replace('$'+str(index), quote(value, safe='/'))
    return target + (('&' if '?' in target else '?') + request.query if request.query else '')


class RewrittenHandler(handler):
    def do_GET(self):
        self.path = destination(self.path)
        super().do_GET()

    def do_POST(self):
        self.path = destination(self.path)
        super().do_POST()
