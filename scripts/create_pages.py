"""Generate static site pages from a shared shell; no private data embedded."""
from pathlib import Path
import sys, re, html as escape_html
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.seo import PAGES
ROOT = Path(__file__).resolve().parents[1] / 'web'

LOGO = '<svg viewBox="0 0 34 32" aria-hidden="true"><path d="M32 2H13C3 2 0 11 8 16L22 24H5L1 31H21C32 31 35 22 26 16L13 9H28Z"/></svg>'

def page(name, title, content):
    home = name == 'home.html'
    route={'home.html':'/','index.html':'/ai','supplier-account.html':'/supplier/account'}.get(name,'/'+name.removesuffix('.html'))
    if route in PAGES:title=PAGES[route][0]
    description=PAGES.get(route,('', 'Private STRATEVO account and operational workspace.'))[1]
    scripts=''
    for file,pages in [('leads.js',('home.html','index.html','assessment.html','marketplace.html','supplier-account.html','supplier.html','admin.html')),('manager.js',('admin.html',)),('storage.js',('supplier.html','supplier-account.html','marketplace.html','inquiry.html','assessment.html','admin.html','portal.html')),('site.js',('admin.html','access.html','portal.html')),('market.js',('supplier.html','supplier-account.html','marketplace.html','admin.html')),('stages.js',('assessment.html','inquiry.html')),('assessment.js',('assessment.html',)),('comparison.js',('methodology.html',)),('intake.js',('inquiry.html','admin.html'))]:
        if name in pages:scripts+='<script defer src="/'+file+'"></script>'
    body_class = 'reference-home' if home else 'reference-inner'
    html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="description" content="'+escape_html.escape(description,quote=True)+'"><!--SEO--><title>'+title+' | STRATEVO</title><link rel="stylesheet" href="/site.css"><link rel="stylesheet" href="/reference.css"><link rel="stylesheet" href="/quality.css"><link rel="icon" type="image/svg+xml" href="/favicon.svg"><script defer src="/visual.js"></script><link rel="stylesheet" href="/market.css"><script defer src="/dialogs.js"></script>'+scripts+'</head><body class="'+body_class+'">'
    html += '<a class="skip-link" href="#main-content">Skip to content</a><canvas id="constellation" aria-hidden="true"></canvas><div class="site-chrome"><div class="preview-strip"><strong>NON-CONTRACTING PREVIEW</strong><span>Products publish after Confirm and Publish. Email confirmation is separate. No orders or payments are accepted. Operator disclosure is pending.</span><a href="/#launch-status">Launch status</a><a href="/admin">Manager access</a></div><header class="reference-header"><a class="brand" href="/" aria-label="STRATEVO home">'+LOGO+'<span>STRATEVO</span></a><button class="menu-toggle" aria-expanded="false" aria-controls="main-nav" type="button">Menu <span aria-hidden="true">+</span></button><nav id="main-nav" aria-label="Main navigation"><a href="/ai">STRATEVO AI</a><a href="/marketplace">Marketplace</a><a href="/methodology">The process</a><a href="/#network">Network</a><a class="mobile-nav-link" href="/inquiry">Send a sourcing inquiry</a><a class="mobile-nav-link" href="/supplier">Are you a supplier?</a><a class="mobile-nav-link" href="/supplier#sign-in">Supplier access</a><a class="mobile-nav-link" data-booking href="https://app.minup.io/book/stratevo" target="_blank" rel="noopener noreferrer">Book a sourcing review ↗</a></nav><div class="header-actions"><a class="supplier-link" href="/supplier">Are you a supplier?</a><a class="rfq-link" href="/assessment">Start assessment</a><a class="booking" data-booking href="https://app.minup.io/book/stratevo" target="_blank" rel="noopener noreferrer">Book a sourcing review <span aria-hidden="true">↗</span></a></div></header></div><main class="site-main" id="main-content">'
    html += content
    html += '<footer class="footer-nav"><a class="brand" href="/">'+LOGO+'<span>STRATEVO</span></a><span>Independent B2B sourcing.<br>Research. Evidence. Human judgment.</span><span><a data-public-contact href="/inquiry">Contact through a sourcing inquiry</a><br><a href="/inquiry">Sourcing inquiry</a> · <a href="/methodology">Our method</a> · <a href="/assessment">Assessment</a> · <a href="/privacy">Privacy</a> · <a href="/cookies">Cookies &amp; storage</a> · <a href="/terms">Terms &amp; scope</a> · <a href="/admin">Manager access</a></span></footer></main>'
    if home:
        html += '<a class="floating-ai" href="/ai"><i aria-hidden="true"></i><span aria-hidden="true">✧</span> Ask STRATEVO</a>'
    if name == 'index.html':
        html += '<script defer src="/app.js"></script>'
    if '<form' in html:
        # If a script fails or JavaScript is disabled, never put passwords/contact fields into URLs.
        html=re.sub(r'<form(?![^>]*\bmethod=)', '<form method="post"',html)
        html+='<noscript><p class="notice">JavaScript is required to submit these forms securely. Explanatory content and navigation remain available; no form has been submitted.</p></noscript>'
    html += '</body></html>'
    (ROOT/name).write_text(html)

page('home.html','China sourcing assistance', (ROOT/'templates'/'home.content.html').read_text())
page('supplier.html','Supplier registration', (ROOT/'templates'/'supplier.content.html').read_text())
page('admin.html','Application manager', (ROOT/'templates'/'admin.content.html').read_text())
page('access.html','Secure email access', '''
<section class="narrow"><div class="eyebrow">SINGLE-USE / EMAIL ACCESS</div><h1>One secure link.<br><span>Your next step.</span></h1><div class="form-panel"><h2>Continue with your email link</h2><p class="sub">Confirm below to verify your supplier email or sign in to your account. Links expire and can only be used once.</p><button id="consume-link">Continue securely</button><p id="consume-status" class="form-status" role="status"></p><a id="portal-link" class="primary" href="/portal" hidden>Open supplier account ↗</a><p class="sub"><a href="/supplier#sign-in">Request a new link</a></p></div></section>
''')
page('portal.html','Supplier account', '''
<div class="page-top"><div class="eyebrow">APPROVED SUPPLIER / ACCOUNT</div><h1>Welcome to<br><span>your supplier account.</span></h1><p class="intro">Your application has been approved for platform access. Commercial activity remains subject to a separate agreement.</p></div><p id="portal-status" class="form-status" role="status"></p><div id="portal-content" hidden><div class="portal-grid"><section class="form-panel"><div class="panel-title"><h2>Business profile</h2><span class="badge approved">Approved access</span></div><dl id="profile" class="details"></dl></section><section class="form-panel"><h2>Next steps</h2><p class="intro">Discuss your capabilities and relevant sourcing requirements with the STRATEVO team.</p><a class="primary" data-booking href="https://app.minup.io/book/stratevo" target="_blank" rel="noopener noreferrer">Arrange a conversation ↗</a><p class="notice">No orders, payments, certification badges or public supplier introductions are created by approval.</p></section></div><div class="actions"><button id="supplier-logout" class="quiet">Sign out</button></div></div>
''')

page('index.html','Sourcing intelligence', (ROOT/'templates'/'ai.content.html').read_text())

page('marketplace.html','Product Marketplace',(ROOT/'templates'/'marketplace.content.html').read_text())
page('supplier-account.html','Supplier product account',(ROOT/'templates'/'supplier-account.content.html').read_text())

for name,title in [('inquiry','Send a sourcing inquiry'),('privacy','Privacy and data use'),('terms','Terms and service scope')]:
    page(name+'.html',title,(ROOT/'templates'/(name+'.content.html')).read_text())

for name,title in [('assessment','Sourcing assessment'),('methodology','Sourcing methodology'),('cookies','Cookies and storage')]:
    page(name+'.html',title,(ROOT/'templates'/(name+'.content.html')).read_text())

page('404.html','Page not found','<section class="page-top"><div class="eyebrow">404 / PAGE NOT FOUND</div><h1>This route is missing.</h1><p>The page may have moved. No inquiry or action was created.</p><div class="actions"><a class="blue-button" href="/">Return home</a><a class="secondary" href="/assessment">Start a sourcing assessment</a><a class="secondary" href="/inquiry">Send an inquiry</a></div></section>')
