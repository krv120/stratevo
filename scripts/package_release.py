"""Build a reproducible source allowlist package without private data or credentials."""
import hashlib
import json
import re
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ['PUBLIC-MARKETPLACE-UPDATE.md','REFERENCE-RESTORATION.md','START-HERE.md','README.md','AUDIT-REPORT.md','AI-KNOWLEDGE-GUIDE.md',
              'AI-EVALUATION.md','KEY-SETUP.md','DEPLOYMENT.md','SOURCING-AI-NOTES.md',
              'LIVE-SITE-AUDIT.md','.env.example','.gitignore','.vercelignore',
              'requirements.txt','vercel.json']
DIRECTORIES = ['app','api','web','scripts','tests','migrations']
SUFFIXES = {'.py','.js','.cjs','.css','.html','.sql','.json','.jsonl','.woff2','.txt'}
LOGS = ['unit-tests.log','postgres-tests.log','browser-tests.log','bandit-after.json']


def build():
    files = {}
    paths = [ROOT/name for name in ROOT_FILES]
    for folder in DIRECTORIES:
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in SUFFIXES and '__pycache__' not in p.parts and 'node_modules' not in p.parts]
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
            raise ValueError('Symlink or outside source path rejected')
        name = path.relative_to(ROOT).as_posix()
        if name.startswith('private/') or ('/.env' in name) or (name.startswith('.env') and name != '.env.example'):
            raise ValueError('Private configuration rejected')
        data = path.read_bytes()
        if re.search(rb'AIza[0-9A-Za-z_-]{35}|sk-(?:proj-)?[A-Za-z0-9_-]{32,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', data):
            raise ValueError('Possible hard-coded secret; inspect source before packaging')
        files[name] = data
    # Only explicitly reviewed synthetic-test logs, never arbitrary private files.
    for name in LOGS:
        path = ROOT/'private'/'audit'/name
        if path.exists() and not path.is_symlink():
            files['validation/'+name] = path.read_bytes()
    manifest = {'format_version':1,'note':'Source and synthetic validation only; hashes exclude this manifest itself.',
                'files':{name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}}
    files['MANIFEST.json'] = json.dumps(manifest,indent=2).encode()
    output=ROOT/'private'/'stratevo-reviewed-source.zip'
    output.parent.mkdir(mode=0o700,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            entry=zipfile.ZipInfo(name,date_time=(2026,10,9,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            entry.external_attr=0o100644 << 16
            archive.writestr(entry,data)
    output.chmod(0o600)
    # Reopen and verify all packaged bytes, not only the pre-write manifest.
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC validation failed')
        for name,digest in manifest['files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                raise ValueError('Archive checksum mismatch')
        if any(name.startswith('private/') for name in archive.namelist()):
            raise ValueError('Private file in archive')
    print(f'{output}\n{len(files)} files; {output.stat().st_size} bytes\nSHA256 {hashlib.sha256(output.read_bytes()).hexdigest()}')
    return output

if __name__=='__main__':build()
