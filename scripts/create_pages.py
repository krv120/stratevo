"""Generate static pages and metadata from the shared shell and editable templates."""
from pathlib import Path
import html
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import seo
ROOT=Path(__file__).resolve().parents[1]/'web'
BOOK='https://app.minup.io/book/stratevo'
LOGO='<svg viewBox="0 0 34 32" aria-hidden="true"><path d="M32 2H13C3 2 0 11 8 16L22 24H5L1 31H21C32 31 35 22 26 16L13 9H28Z"/></svg>'


def page(name,route,content):
    title,description=seo.PAGES.get(route,('Supplier account' if name in ('access','portal','supplier-account') else 'Staff sign-in' if name=='admin' else 'Page not found','Private account access and supplier management.'))
    scripts=['ui','navigation']
    if name in ('supplier','supplier-account','marketplace'):scripts+=['storage','market']
    if name in ('admin','access','portal'):scripts+=['site']
    if name=='admin':scripts+=['manager','video','content']
    if name=='methodology':scripts+=['comparison']
    source='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+' | STRATEVO</title><meta name="description" content="'+html.escape(description,quote=True)+'"><!--SEO-START-->'+seo.metadata(route)+'<!--SEO-END--><link rel="stylesheet" href="/site.css"><link rel="icon" type="image/svg+xml" href="/favicon.svg">'+''.join('<script defer src="/'+file+'.js"></script>' for file in scripts)+'</head><body><a class="skip-link" href="#main-content">Skip to content</a>'
    source+='<header class="mobile-header"><a class="brand" href="/" aria-label="STRATEVO home">'+LOGO+'<span>STRATEVO</span></a><a class="primary header-booking" data-booking href="'+BOOK+'" target="_blank" rel="noopener noreferrer">Book a Call</a><button type="button" id="menu-open" aria-label="Open navigation" aria-controls="navigation-drawer" aria-expanded="false"><span aria-hidden="true">☰</span></button></header>'
    source+='<dialog id="navigation-drawer" aria-labelledby="navigation-title"><div class="drawer-heading"><h2 id="navigation-title">Explore STRATEVO</h2><button type="button" data-menu-close aria-label="Close navigation">×</button></div><nav aria-label="Main navigation"><a href="/methodology">How It Works</a><a href="/marketplace">Marketplace</a><a href="/supplier">For Suppliers</a><a href="/supplier/account">My Supplier Account</a><a data-booking href="'+BOOK+'" target="_blank" rel="noopener noreferrer">Book a Sourcing Call ↗</a></nav></dialog>'
    source+='<noscript><nav class="fallback-nav" aria-label="Site navigation"><a href="/methodology">How It Works</a><a href="/marketplace">Marketplace</a><a href="/supplier">For Suppliers</a><a href="/supplier/account">My Supplier Account</a></nav></noscript><main id="main-content" class="site-main">'+content+'</main>'
    source+='<footer class="site-footer"><div><a class="brand" href="/">'+LOGO+'<span>STRATEVO</span></a><p>Independent B2B sourcing.<br>Personal attention. Practical next steps.</p></div><section aria-labelledby="operator-footer"><h2 id="operator-footer">Legal &amp; Operator Information</h2><p>Vasilis Krevatsoulis</p><a href="mailto:info@stratevo.store">info@stratevo.store</a><a href="tel:+306989472740">+30 6989472740</a><a href="/terms#operator">Operator details</a></section><nav aria-label="Legal navigation"><a href="/privacy">Privacy</a><a href="/cookies">Cookies &amp; storage</a><a href="/terms">Terms</a><a href="mailto:info@stratevo.store?subject=Listing%20or%20IP%20report">Report a Listing / IP Infringement</a></nav></footer>'
    if name not in ('admin','supplier-account','supplier','access','portal'):
        source+='<nav class="mobile-booking" aria-label="Book a consultation"><a class="primary" data-booking href="'+BOOK+'" target="_blank" rel="noopener noreferrer">Book a Sourcing Call ↗</a></nav>'
    if '<form' in content:source+='<noscript><p class="notice">JavaScript is needed to submit these forms securely. Please contact info@stratevo.store if you cannot enable it.</p></noscript>'
    (ROOT/(name+'.html')).write_text(source+'</body></html>')


def build():
    for p in sorted((ROOT/'templates').glob('*.content.html')):
        name=p.name.removesuffix('.content.html');route={'home':'/','supplier-account':'/supplier/account'}.get(name,'/'+name)
        page(name,route,p.read_text())
    page('access','/access','<section class="page-top narrow"><h1>Secure supplier sign-in</h1><p>Use the single-use link from your email. Keep it private.</p><button class="primary" id="consume-link" type="button">Continue Securely</button><p id="consume-status" role="status"></p><a class="secondary" href="mailto:info@stratevo.store">Contact STRATEVO for Access Help</a></section>')
    page('portal','/portal','<section class="page-top narrow"><h1>Supplier account</h1><p id="portal-status" role="status">Checking access…</p><div id="portal-content" hidden></div><a class="secondary" href="/supplier/account">My Supplier Account</a></section>')
    page('404','/404','<section class="page-top"><p class="eyebrow">404</p><h1>We couldn’t find that page.</h1><p>Return home or book a conversation with STRATEVO.</p><a class="secondary" href="/">Return Home</a><a class="primary" href="'+BOOK+'">Book a Sourcing Call</a></section>')

if __name__=='__main__':build()
