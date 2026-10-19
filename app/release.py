"""Public build identity only; never return environment configuration or secrets."""
import os
import re

RELEASE = '2026.10.19-routing-check-1'


def identity():
    commit = os.environ.get('VERCEL_GIT_COMMIT_SHA', '')
    return {'release': RELEASE,
            'commit': commit if re.fullmatch(r'[0-9a-fA-F]{40}', commit) else None}
