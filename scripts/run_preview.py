"""Load a private local JSON environment file and start the development server."""
import json
import os
import runpy
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
path=Path(sys.argv[1]).resolve()
if not path.is_relative_to(root/'private'):
    raise SystemExit('Configuration must be in private/')
os.environ.update(json.loads(path.read_text()))
runpy.run_module('app.server',run_name='__main__')
