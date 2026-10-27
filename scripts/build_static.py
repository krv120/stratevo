"""Build a public-only Vercel output; Python is reserved for APIs, not page routing."""
from pathlib import Path
import runpy
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import seo


def build():
    for script in ('build_content.py', 'create_pages.py'):
        runpy.run_path(str(ROOT / 'scripts' / script), run_name='__main__')
    output = ROOT / 'public-site'
    output.mkdir(exist_ok=True)
    names = ['home', 'supplier', 'supplier-account', 'marketplace', 'methodology',
             'assessment', 'inquiry', 'privacy', 'cookies', 'terms', 'admin',
             'access', 'portal', '404']
    allowed = set()
    for name in names:
        destination = 'index.html' if name == 'home' else name + '.html'
        source = (ROOT / 'web' / (name + '.html')).read_text()
        source = source.replace('<head>', '<head><meta name="stratevo-api" content="/api/index.py">', 1)
        (output / destination).write_text(source)
        allowed.add(destination)
    for name in ['site.css', 'favicon.svg'] + [n + '.js' for n in
                 ['ui', 'navigation', 'site', 'market', 'manager', 'operations', 'storage', 'comparison', 'video']] + [
                 'fonts/inter-latin.woff2', 'fonts/inter-greek.woff2', 'images/stratevo-social.jpg']:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / 'web' / name, target)
        allowed.add(name)
    for name, text in [('robots.txt', seo.robots()), ('sitemap.xml', seo.sitemap())]:
        (output / name).write_text(text)
        allowed.add(name)
    # Remove stale build outputs, never source or private state.
    for path in output.rglob('*'):
        if path.is_file() and path.relative_to(output).as_posix() not in allowed:
            path.unlink()
    print('Built', len(allowed), 'public files in public-site/')


if __name__ == '__main__':
    build()
