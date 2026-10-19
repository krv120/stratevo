"""Release regression coverage; uses synthetic data and isolated local HTTP."""
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
import os
import test_marketplace as fixtures
from app import seo, intake
from test_intake import inquiry

class Head(HTMLParser):
    def __init__(self):super().__init__();self.metas=[];self.links=[];self.h1=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='meta':self.metas.append(a)
        if tag=='link':self.links.append(a)
        if tag=='h1':self.h1+=1

class ReleaseQualityTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.MarketplaceTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.MarketplaceTests.tearDownClass.__func__)
    setUp=fixtures.MarketplaceTests.setUp
    http=fixtures.MarketplaceTests.http

    def test_all_public_metadata_unique_and_complete(self):
        descriptions=set()
        for route in seo.PAGES:
            status,body,_=self.http(route);self.assertEqual(status,200)
            h=Head();h.feed(body.decode());self.assertEqual(h.h1,1)
            ds=[m['content'] for m in h.metas if m.get('name')=='description'];self.assertEqual(len(ds),1);self.assertGreater(len(ds[0]),50);self.assertNotIn(ds[0],descriptions);descriptions.add(ds[0])
            self.assertEqual(len([l for l in h.links if l.get('rel')=='canonical']),1)
            for key in ['og:title','og:description','og:image','og:url']:self.assertEqual(len([m for m in h.metas if m.get('property')==key]),1)
            self.assertTrue(any(m.get('name')=='twitter:card' for m in h.metas))
            self.assertTrue(any(l.get('rel')=='icon' for l in h.links))

    def test_new_routes_assets_and_unknown_route_types(self):
        for route in ['/assessment','/methodology','/cookies','/assessment.js','/comparison.js','/stages.js','/quality.css','/favicon.svg','/images/stratevo-social.jpg']:
            self.assertEqual(self.http(route)[0],200,route)
        status,body,headers=self.http('/no-such-page');self.assertEqual(status,404);self.assertIn('text/html',headers['Content-Type']);self.assertIn(b'Return home',body);self.assertIn('noindex',headers['X-Robots-Tag'])
        status,body,headers=self.http('/api/no-such-route');self.assertEqual(status,404);self.assertIn('application/json',headers['Content-Type'])

    def test_structured_data_valid_and_not_fabricated_authority(self):
        for route in seo.PAGES:
            block=seo.metadata(route).split('<script type="application/ld+json">')[1].split('</script>')[0]
            parsed=json.loads(block);self.assertIn(parsed['@type'],('WebSite','WebPage'))
            for key in ['aggregateRating','review','address','price','certification']:self.assertNotIn(key,parsed)
        with patch.dict(seo.PAGES,{'/methodology':('</script><script>alert(1)</script>','test')}):
            self.assertEqual(seo.metadata('/methodology').count('</script>'),1)

    def test_sitemap_gates_new_pages_and_private_exclusions(self):
        self.assertNotIn('<loc>',seo.sitemap())
        with patch.dict(os.environ,{'APP_ENV':'production','SITE_INDEXABLE':'true','SITE_LAUNCH_APPROVED':'true','PUBLIC_ORIGIN_VERIFIED':'true'}):
            for route in ['/assessment','/methodology','/cookies']:self.assertIn(route+'</loc>',seo.sitemap())
            for route in ['/admin','/access','/supplier/account','/inquiry','/ai']:self.assertFalse(seo.indexable(route))

    def test_assessment_source_persisted_with_same_retry_rules(self):
        data=inquiry(source='assessment');first=intake.submit(data);self.assertEqual(first,intake.submit(data))
        self.assertEqual(intake.list_inquiries()['inquiries'][0]['details']['source'],'assessment')

    def test_cookie_inventory_and_no_analytics_transport(self):
        hooks=Path('web/stages.js').read_text()
        for forbidden in ['fetch(','sendBeacon(','localStorage','sessionStorage','document.cookie']:self.assertNotIn(forbidden,hooks)
        inventory=Path('web/cookies.html').read_text()
        for key in ['stratevo_session','stratevo-inquiry-draft','stratevo-assessment-draft']:self.assertIn(key,inventory)
        for page in Path('web').glob('*.html'):
            self.assertNotIn('googletagmanager.com',page.read_text());self.assertNotIn('>Accept all</button>',page.read_text())

    def test_social_graphic_dimensions(self):
        from PIL import Image
        with Image.open('web/images/stratevo-social.jpg') as image:self.assertEqual(image.size,(1200,630))

    def test_public_pages_not_runtime_provider_dependent(self):
        with patch.dict(os.environ,{'AI_API_KEY':'','AI_MODEL':'','SMTP_HOST':''}):
            for route in ['/assessment','/methodology','/cookies','/']:self.assertEqual(self.http(route)[0],200)

    def test_static_compression_and_private_json_exclusion(self):
        import gzip,urllib.request
        for route in ['/quality.css','/assessment.js']:
            with urllib.request.urlopen(urllib.request.Request(self.base+route,headers={'Accept-Encoding':'gzip'})) as response:
                self.assertEqual(response.headers['Content-Encoding'],'gzip')
                self.assertIn('Accept-Encoding',response.headers['Vary'])
                self.assertTrue(gzip.decompress(response.read()))
            with urllib.request.urlopen(urllib.request.Request(self.base+route,headers={'Accept-Encoding':'gzip;q=0'})) as response:self.assertIsNone(response.headers['Content-Encoding'])
        with urllib.request.urlopen(urllib.request.Request(self.base+'/api/health',headers={'Accept-Encoding':'gzip'})) as response:
            self.assertIsNone(response.headers['Content-Encoding']);self.assertEqual(response.headers['Cache-Control'],'no-store')

    def test_webmaster_tokens_are_opt_in_escaped_and_home_only(self):
        self.assertNotIn('google-site-verification',seo.metadata('/'))
        with patch.dict(os.environ,{'GOOGLE_SITE_VERIFICATION':'test-public-token"<>','BING_SITE_VERIFICATION':'test-public-bing'}):
            self.assertIn('test-public-token&quot;&lt;&gt;',seo.metadata('/'))
            self.assertIn('msvalidate.01',seo.metadata('/'))
            self.assertNotIn('google-site-verification',seo.metadata('/methodology'))

    def test_legacy_live_route_compatibility_is_navigation_only(self):
        import urllib.request
        for old,new in [('/rfq','/assessment'),('/supplier-portal','/supplier/account'),('/business-information','/#launch-status')]:
            with urllib.request.urlopen(self.base+old) as response:self.assertEqual(response.url,self.base+new)
        self.assertEqual(self.http('/rfq',{'product':'must not submit'})[0],404)

    def test_native_form_fallback_never_defaults_to_get(self):
        import re
        for page in Path('web').glob('*.html'):
            for tag in re.findall(r'<form\b[^>]*>',page.read_text()):self.assertIn('method="post"',tag,page.name)
