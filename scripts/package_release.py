"""Package complete allowlisted source and reviewed evidence; exclude private state."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ['README.md','DEPLOYMENT.md','KEY-SETUP.md','RELEASE-TESTING.md',
              'RELEASE-NOTES.md','SECURITY-REVIEW.md','LIVE-COMPARISON.md',
              '.env.example','.gitignore','.vercelignore','requirements.txt',
              'requirements-dev.txt','vercel.json']
DIRECTORIES = ['app','api','web','scripts','tests','migrations','validation']
EXCLUDED = {'__pycache__','node_modules','.venv','.git','private'}
SUFFIXES = {'.py','.js','.cjs','.css','.html','.sql','.json','.jsonl','.woff2',
            '.txt','.svg','.jpg','.png','.md','.log'}


def build(output):
    paths = [ROOT/name for name in ROOT_FILES]
    for directory in DIRECTORIES:
        paths.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and p.suffix in SUFFIXES and not EXCLUDED.intersection(p.relative_to(ROOT).parts))
    files = {}
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Unsafe source path')
        name = path.relative_to(ROOT).as_posix()
        data = path.read_bytes()
        if re.search(rb'AIza[0-9A-Za-z_-]{35}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data):
            raise ValueError('Possible secret in '+name)
        files[name] = data
    try:
        commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty = bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())
    except subprocess.CalledProcessError:
        commit,dirty = 'unavailable',True
    manifest = {'release_version':'2026.10.20-static-rc1','package_date':'2026-10-20',
                'base_commit':commit,'worktree_modified':dirty,
                'note':'Hashes identify exact packaged bytes; manifest excludes itself.',
                'files':{n:hashlib.sha256(d).hexdigest() for n,d in sorted(files.items())}}
    files['MANIFEST.json'] = (json.dumps(manifest,indent=2)+'\n').encode()
    output = Path(output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,20,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644 << 16
            archive.writestr(entry,data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:raise ValueError('Archive CRC mismatch')
        for name,digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=digest:raise ValueError('Archive hash mismatch')
    print(json.dumps({'archive':str(output),'files':len(files),'bytes':output.stat().st_size,
                      'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'private'/'STRATEVO-2026.10.20-static-rc1.zip'))
    build(parser.parse_args().output)
