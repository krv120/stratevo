"""Environment-controlled indexability; preview pages are noindex by default."""
import html
import json
import os
from urllib.parse import urlsplit

PAGES={
 '/':('China sourcing for e-commerce and private-label businesses','Work with STRATEVO to define your China sourcing brief, compare manufacturers and identify the evidence needed before choosing a supplier. Book a sourcing call.'),
 '/supplier':('Register your supplier profile','Introduce your company, focus and manufacturing capabilities in the STRATEVO Marketplace. Publish your supplier profile while keeping contact details private.'),
 '/marketplace':('Supplier Marketplace — manufacturing capabilities','Explore supplier names, focus areas and capabilities. Discuss specifications, pricing and next steps with STRATEVO through a sourcing call.'),
 '/methodology':('How STRATEVO evaluates sourcing options','Learn how specifications, minimum order quantities, quote scope, samples and certification evidence shape a structured manufacturer comparison.'),
 '/assessment':('Prepare for your sourcing consultation','Bring your product idea, quantity, budget, destination and timeline to a STRATEVO sourcing call. Uncertain requirements are welcome.'),
 '/inquiry':('Contact STRATEVO about your sourcing project','Book a direct sourcing conversation with STRATEVO or contact us by email to discuss manufacturing requirements and a clearly defined engagement.'),
 '/privacy':('Privacy and personal information','Read how STRATEVO handles supplier profiles, private contact details, account sessions, notifications, booking and data-rights requests.'),
 '/cookies':('Cookies and essential browser storage','Understand STRATEVO’s essential sign-in cookie, public supplier backup and external Minup booking links. No advertising trackers are included.'),
 '/terms':('Terms, operator information and listing reports','Review STRATEVO’s independent sourcing role, supplier listing responsibilities, operator contact information and notice-and-review procedure.')}


def canonical():
    from app.settings import canonical as configured_canonical
    return configured_canonical()

def indexable(route):
    from app.settings import environment
    try:production=environment()=='production'
    except ValueError:return False
    return production and os.environ.get('SITE_LAUNCH_APPROVED')=='true' and os.environ.get('PUBLIC_ORIGIN_VERIFIED')=='true' and os.environ.get('SITE_INDEXABLE','false').lower()=='true' and route in PAGES and route != '/inquiry'


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
