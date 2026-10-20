"""Live Download & Preview Hub for the STRATEVO Sourcing & Advisory Overview 1-Page PDF Brochure."""
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "STRATEVO_Sourcing_and_Advisory_Overview.pdf"
PNG_PATH = ROOT / "STRATEVO_Sourcing_and_Advisory_Overview_Preview.png"
GUIDE_PATH = ROOT / "STRATEVO_One_Sheet_Copy_and_Canva_Guide.md"

HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Download — STRATEVO Sourcing & Advisory Overview (1-Page PDF)</title>
<style>
  :root {
    --bg: #080c13;
    --panel: #111a29;
    --card: #162338;
    --line: #293950;
    --blue: #2569e6;
    --blue-hover: #3477f5;
    --light: #94b9ff;
    --text: #eff4ff;
    --muted: #b2bfd2;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.55;
  }
  .topbar {
    position: sticky;
    top: 0;
    z-index: 20;
    background: rgba(8, 12, 19, 0.94);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--line);
    padding: 14px 24px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 12px;
    font-weight: 800;
    letter-spacing: 0.05em;
    font-size: 18px;
  }
  .brand svg { width: 28px; height: 28px; flex: none; }
  .brand span.sub {
    font-weight: 600;
    font-size: 12px;
    letter-spacing: 0.04em;
    color: var(--light);
    background: var(--card);
    border: 1px solid #35507c;
    padding: 4px 10px;
    border-radius: 5px;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 11px 18px;
    border-radius: 7px;
    font-weight: 700;
    font-size: 14px;
    text-decoration: none;
    cursor: pointer;
    transition: all 0.15s ease;
    border: 1px solid transparent;
  }
  .btn-primary {
    background: var(--blue);
    border-color: #5c95ff;
    color: #fff;
    box-shadow: 0 6px 20px rgba(37, 105, 230, 0.35);
  }
  .btn-primary:hover { background: var(--blue-hover); }
  .btn-secondary {
    background: var(--panel);
    border-color: #3d5578;
    color: #deebff;
  }
  .btn-secondary:hover { border-color: var(--light); }
  .container {
    max-width: 1220px;
    margin: 0 auto;
    padding: 28px 24px 60px;
    display: grid;
    grid-template-columns: 1.35fr 1fr;
    gap: 28px;
    align-items: start;
  }
  @media (max-width: 960px) {
    .container { grid-template-columns: 1fr; }
  }
  .preview-frame {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
  }
  .preview-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
    font-size: 13px;
    color: var(--muted);
  }
  .preview-img {
    width: 100%;
    height: auto;
    display: block;
    border-radius: 6px;
    border: 1px solid #2e4366;
    background: #fff;
  }
  .side-panel {
    display: flex;
    flex-direction: column;
    gap: 18px;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 20px;
  }
  .eyebrow {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: var(--light);
    text-transform: uppercase;
    margin: 0 0 8px;
  }
  .card h2 {
    margin: 0 0 10px;
    font-size: 19px;
    line-height: 1.25;
  }
  .card p {
    margin: 0 0 14px;
    font-size: 14px;
    color: var(--muted);
  }
  .dl-stack {
    display: grid;
    gap: 10px;
  }
  .dl-stack .btn {
    justify-content: center;
    padding: 13px 18px;
    font-size: 14.5px;
  }
  .script-box {
    background: #090e18;
    border: 1px solid #273954;
    border-radius: 6px;
    padding: 12px;
    font-size: 12.8px;
    color: #d6e4fa;
    white-space: pre-wrap;
    margin-bottom: 10px;
  }
  .copy-btn {
    width: 100%;
    justify-content: center;
    font-size: 13px;
    padding: 9px 14px;
  }
  ul.checks {
    margin: 0;
    padding-left: 18px;
    font-size: 13.5px;
    color: var(--muted);
  }
  ul.checks li { margin-bottom: 7px; }
  ul.checks li strong { color: var(--text); }
</style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <rect width="48" height="48" rx="10" fill="#1458d2"/>
        <path transform="translate(7 8)" fill="white" d="M32 2H13C3 2 0 11 8 16L22 24H5L1 31H21C32 31 35 22 26 16L13 9H28Z"/>
      </svg>
      <span>STRATEVO</span>
      <span class="sub">1-PAGE BROCHURE DOWNLOAD HUB</span>
    </div>
    <div class="actions">
      <a class="btn btn-primary" href="/download/STRATEVO_Sourcing_and_Advisory_Overview.pdf" download="STRATEVO Sourcing & Advisory Overview.pdf">
        ⬇ Download PDF Brochure (27 KB)
      </a>
      <a class="btn btn-secondary" href="/view/STRATEVO_Sourcing_and_Advisory_Overview.pdf" target="_blank" rel="noopener">
        Open Raw PDF ↗
      </a>
      <a class="btn btn-secondary" href="/download/STRATEVO_Sourcing_and_Advisory_Overview_Preview.png" download="STRATEVO Sourcing & Advisory Overview.png">
        ⬇ Download High-Res PNG
      </a>
    </div>
  </header>

  <main class="container">
    <section class="preview-frame">
      <div class="preview-header">
        <span><strong>STRATEVO Sourcing &amp; Advisory Overview.pdf</strong> · 1 Page (A4 Portrait)</span>
        <span>All links &amp; QR code embedded</span>
      </div>
      <a href="/download/STRATEVO_Sourcing_and_Advisory_Overview.pdf" download="STRATEVO Sourcing & Advisory Overview.pdf" title="Click to download PDF">
        <img class="preview-img" src="/preview.png" alt="STRATEVO Sourcing & Advisory Overview 1-Page PDF Preview">
      </a>
    </section>

    <aside class="side-panel">
      <div class="card">
        <p class="eyebrow">Ready to Send</p>
        <h2>Download Your 1-Page Client One-Sheet</h2>
        <p>Built with your exact <strong>stratevo.online</strong> brand system, Inter typography, live clickable Minup links (<code>app.minup.io/book/stratevo</code>), and scannable QR code.</p>
        <div class="dl-stack">
          <a class="btn btn-primary" href="/download/STRATEVO_Sourcing_and_Advisory_Overview.pdf" download="STRATEVO Sourcing & Advisory Overview.pdf">
            ⬇ Download PDF ("STRATEVO Sourcing &amp; Advisory Overview.pdf")
          </a>
          <a class="btn btn-secondary" href="/download/STRATEVO_Sourcing_and_Advisory_Overview_Preview.png" download="STRATEVO Sourcing & Advisory Overview.png">
            ⬇ Download 250-DPI PNG (For Inline LinkedIn Chat)
          </a>
        </div>
      </div>

      <div class="card">
        <p class="eyebrow">Psychological Triggers Inside</p>
        <h2>Why This Converts B2B Buyers</h2>
        <ul class="checks">
          <li><strong>The Conflict-of-Interest Hook:</strong> Exposes why paid directory badges and 5–10% factory-commission agents cost buyers more—positioning STRATEVO as strictly buyer-aligned.</li>
          <li><strong>Concrete Quote Anchoring ($7.80 EXW vs. $8.35 FOB):</strong> Shows visually how a "cheaper" unit quote becomes $9.93 landed once mold tooling ($1,450) and port drayage ($680) are added.</li>
          <li><strong>Zero AI Clichés or Em-Dashes:</strong> Written in crisp, direct commercial procurement language with natural sentence cadence.</li>
          <li><strong>Low-Friction Minup CTA:</strong> Direct clickable button + QR code to your 15-minute free consultation on Minup.</li>
        </ul>
      </div>

      <div class="card">
        <p class="eyebrow">LinkedIn DM Companion Script</p>
        <h2>What to Write When Sending This PDF</h2>
        <div class="script-box" id="li-script">Appreciate you asking. In short: I run an independent B2B sourcing consultancy here in Europe (STRATEVO). We help brands and e-commerce founders source from China without getting burned by trading middlemen, hidden EXW/tooling charges, or invalid compliance PDFs.

Unlike traditional agents, we don't take kickbacks from factories. We vet the manufacturers, compare their quotes on equal terms so you see the true landed cost, and introduce you directly to the factory.

I attached our 1-page overview so you can see how our quote check works in 30 seconds. If you're looking at a new product or want a second pair of eyes on a quote, grab a free 15-minute slot on my Minup calendar here: https://app.minup.io/book/stratevo</div>
        <button class="btn btn-secondary copy-btn" type="button" onclick="navigator.clipboard.writeText(document.getElementById('li-script').innerText); this.innerText='✓ Copied LinkedIn Script!'; setTimeout(()=>this.innerText='Copy LinkedIn Message', 2000);">
          Copy LinkedIn Message
        </button>
      </div>
    </aside>
  </main>
</body>
</html>
"""


class BrochureHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_common_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")

    def do_GET(self):
        parsed = urllib.parse.unquote(self.path.split("?")[0])
        if parsed in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(body)
        elif parsed.startswith("/download/") and parsed.endswith(".pdf"):
            data = PDF_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="STRATEVO_Sourcing_and_Advisory_Overview.pdf"',
            )
            self.send_header("Content-Length", str(len(data)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(data)
        elif parsed.startswith("/view/") and parsed.endswith(".pdf"):
            data = PDF_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header(
                "Content-Disposition",
                'inline; filename="STRATEVO_Sourcing_and_Advisory_Overview.pdf"',
            )
            self.send_header("Content-Length", str(len(data)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(data)
        elif parsed in ("/preview.png", "/download/STRATEVO_Sourcing_and_Advisory_Overview_Preview.png"):
            data = PNG_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            if parsed.startswith("/download/"):
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="STRATEVO Sourcing & Advisory Overview.png"',
                )
            self.send_header("Content-Length", str(len(data)))
            self._send_common_headers()
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), BrochureHandler)
    print("Serving STRATEVO Brochure Download Hub on http://0.0.0.0:8080", flush=True)
    server.serve_forever()
