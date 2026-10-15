"""Environment-controlled indexability; preview pages are noindex by default."""
import html
import json
import os
from urllib.parse import urlsplit

PAGES={
 '/assessment':('China sourcing assessment — build a clear product brief','Define your product, quantity, specifications, budget and destination. Review your sourcing brief before choosing to send a private inquiry.'),
 '/methodology':('How to evaluate manufacturers and compare sourcing quotes','See how STRATEVO structures supplier evaluation: comparable specifications, MOQ, quote scope, evidence, samples and delivery. Includes an illustrative comparison.'),
 '/cookies':('Cookies and browser storage','See the essential sessions and requested temporary drafts used by this STRATEVO build. No optional analytics or advertising trackers are installed.'),
 '/':('China sourcing assistance for small businesses','STRATEVO helps e-commerce sellers, resellers and small businesses define China sourcing requirements and assess their next steps.'),
 '/inquiry':('Send a China sourcing inquiry','Share your product specifications, quantity and destination privately with STRATEVO. No order, payment or commitment is created.'),
 '/supplier':('Supplier registration','Register your business privately and submit product information to STRATEVO. Email confirmation is not business verification.'),
 '/marketplace':('Supplier-submitted product Marketplace','Explore supplier-submitted product details, advertised prices and minimum quantities. Inquiries go through STRATEVO.'),
 '/ai':('STRATEVO sourcing assistant','Get sourcing guidance and prepare a clear inquiry. No customer account required. AI answers and supplier claims require checking.'),
 '/privacy':('Privacy and data-use notice','How this STRATEVO preview handles inquiries, supplier registrations, AI messages and essential sessions; remaining launch disclosures.'),
 '/terms':('Service scope and website terms','Understand STRATEVO sourcing assistance, unverified product information and the separate proposal required for paid services.')}


def canonical():
    from app.settings import canonical as configured_canonical
    return configured_canonical()

def indexable(route):
    from app.settings import environment
    try:production=environment()=='production'
    except ValueError:return False
    return production and os.environ.get('SITE_LAUNCH_APPROVED')=='true' and os.environ.get('PUBLIC_ORIGIN_VERIFIED')=='true' and os.environ.get('SITE_INDEXABLE','false').lower()=='true' and route in PAGES and route not in ('/ai','/inquiry')


def metadata(route):
    title,description=PAGES.get(route,('Page not found','This STRATEVO page could not be found. Return home or start a sourcing inquiry.') if route=='/404' else ('Private workspace','STRATEVO private account and operational workspace.'))
    url=html.escape(canonical()+route,quote=True)
    title=html.escape(title+' | STRATEVO',quote=True);description=html.escape(description,quote=True)
    robots='index,follow' if indexable(route) else 'noindex,nofollow'
    image=html.escape(canonical()+'/images/stratevo-social.jpg',quote=True)
    graph={'@context':'https://schema.org','@type':'WebPage','name':PAGES.get(route,('Private workspace',))[0],'url':canonical()+route}
    if route=='/':graph.update({'@type':'WebSite','name':'STRATEVO','description':PAGES['/'][1]})
    structured=('<script type="application/ld+json">'+json.dumps(graph,ensure_ascii=False).replace('<',r'\u003c')+'</script>') if route in PAGES else ''
    verification=''
    if route=='/':
        for setting,name in [('GOOGLE_SITE_VERIFICATION','google-site-verification'),('BING_SITE_VERIFICATION','msvalidate.01')]:
            value=os.environ.get(setting,'').strip()
            if len(value)>256:raise ValueError('Invalid site verification token')
            if value:verification+='<meta name="'+name+'" content="'+html.escape(value,quote=True)+'">'
    return verification+f'<meta name="robots" content="{robots}"><link rel="canonical" href="{url}"><meta property="og:type" content="website"><meta property="og:site_name" content="STRATEVO"><meta property="og:title" content="{title}"><meta property="og:description" content="{description}"><meta property="og:url" content="{url}"><meta property="og:image" content="{image}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630"><meta property="og:image:alt" content="STRATEVO — China sourcing. Clearer decisions."><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{title}"><meta name="twitter:description" content="{description}"><meta name="twitter:image" content="{image}"><meta name="twitter:image:alt" content="STRATEVO — China sourcing. Clearer decisions.">'+structured



def robots():
    if not indexable('/'):return 'User-agent: *\nDisallow: /\n'
    return 'User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin\nDisallow: /access\nDisallow: /portal\nDisallow: /supplier/account\nSitemap: '+canonical()+'/sitemap.xml\n'


def sitemap():
    urls=''.join('<url><loc>'+html.escape(canonical()+route)+'</loc></url>' for route in PAGES if indexable(route))
    return '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+urls+'</urlset>'
