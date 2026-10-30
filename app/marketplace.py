"""Private supplier accounts and staff-reviewed product submissions.

Private account/documents are deliberately stored separately from public payloads.
"""
import base64
import io
import json
import math
import os
import re
import secrets
import uuid
import warnings
from decimal import Decimal, InvalidOperation
from app import suppliers as s, controls
from app.privacy import buyer_safe, normalized

CATEGORIES = ('industrial', 'packaging', 'consumer', 'food')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS market_accounts (
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, private_profile TEXT NOT NULL,
 created_at BIGINT NOT NULL, verified_at BIGINT
);
CREATE TABLE IF NOT EXISTS market_products (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id),
 public_payload TEXT NOT NULL, image TEXT NOT NULL DEFAULT '',
 visibility TEXT NOT NULL CHECK(visibility IN ('published','withdrawn','hidden')),
 created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS market_tokens (
 digest TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES market_accounts(id),
 expires_at BIGINT NOT NULL, used_at BIGINT
);

CREATE TABLE IF NOT EXISTS market_publications (
 account_id TEXT PRIMARY KEY REFERENCES market_accounts(id) ON DELETE CASCADE,
 submission_digest TEXT NOT NULL UNIQUE, payload_digest TEXT NOT NULL, created_at BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS market_product_owner ON market_products(owner_id);
CREATE INDEX IF NOT EXISTS market_token_expiry ON market_tokens(expires_at);
'''
NOTICE = 'Supplier-provided information. Publication is not proof of email ownership, business identity, product quality, pricing or certifications.'


def clean_text(value, profile):
    value = buyer_safe(normalized(value))
    for field in ('company','contact','email','whatsapp','wechat','license_number'):
        secret = profile.get(field,'')
        if isinstance(secret,str) and len(secret.strip()) >= 3:
            value = re.sub(re.escape(normalized(secret.strip())), '[private detail removed]', value, flags=re.IGNORECASE)
    # Common phone-number formats. This may conservatively redact long numeric specifications.
    value = re.sub(r'(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)', '[private detail removed]', value)
    return value


def image_data(encoded):
    if not encoded:return ''
    with controls.image_slot():return decode_image(encoded)


def decode_image(encoded):
    if not isinstance(encoded,str) or len(encoded)>700000:raise s.WorkflowError('Product photo must be JPEG, PNG or WebP, up to 500 KB.')
    try:
        from PIL import Image, ImageOps
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>500000:raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.format not in ('JPEG','PNG','WEBP') or getattr(source,'n_frames',1)!=1 or source.width*source.height>12000000:raise ValueError()
                source.load()
                picture=ImageOps.exif_transpose(source).convert('RGB')
                picture.thumbnail((1200,1200))
                # A new raster removes original metadata, filename and active content.
                clean=Image.new('RGB',picture.size);clean.paste(picture)
                buffer=io.BytesIO();clean.save(buffer,format='JPEG',quality=82,optimize=True)
                output=buffer.getvalue()
                if len(output)>500000:raise ValueError()
                return base64.b64encode(output).decode()
    except ImportError:
        raise s.WorkflowError('Image processing is not installed on this deployment. Try without a photo or contact the operator.',503) from None
    except Exception:
        raise s.WorkflowError('Invalid or oversized photo. Use a single JPEG, PNG or WebP image, up to 500 KB and 12 megapixels.') from None


def product_data(data, profile):
    if not isinstance(data,dict):raise s.WorkflowError('Add product details.')
    title=clean_text(s.field(data,'title',minimum=3,maximum=140),profile)
    description=clean_text(s.field(data,'description',minimum=20,maximum=1500),profile)
    category=s.field(data,'category',maximum=30)
    if category not in CATEGORIES:raise s.WorkflowError('Choose a product category.')
    location=clean_text(s.field(data,'location',minimum=0,maximum=100),profile)
    unit=s.field(data,'unit',maximum=30)
    if unit not in ('pieces','sets','kilograms','litres','metres'):raise s.WorkflowError('Choose a selling unit.')
    from app.normalization import quantity as normalize_quantity
    quantity=normalize_quantity(data.get('moq'))
    if quantity is not None and (isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity) or not 0<quantity<=1e9):raise s.WorkflowError('MOQ must be a positive number.')
    price=data.get('price','')
    currency=data.get('currency','')
    if price not in ('',None):
        if not isinstance(price,(str,int,float)) or isinstance(price,bool):raise s.WorkflowError('Check the advertised price.')
        if len(str(price))>32:raise s.WorkflowError('Check the advertised price.')
        try:
            amount=Decimal(str(price))
            if not amount.is_finite() or not 0<amount<=Decimal('1000000000') or amount.as_tuple().exponent < -4:raise InvalidOperation()
        except (InvalidOperation,ValueError):raise s.WorkflowError('Price must be positive, with up to four decimal places.') from None
        if currency not in ('EUR','USD','GBP','CNY'):raise s.WorkflowError('Choose a price currency.')
        price=format(amount,'f')
    else:price=None;currency=None
    if data.get('rights_consent') is not True:raise s.WorkflowError('Confirm that you have the rights to publish these descriptions and images.',field='rights_consent')
    if data.get('content_consent') is not True:raise s.WorkflowError('Confirm that the product text and image contain no supplier identity, contacts, source links or unauthorized content.')
    payload={'title':title,'description':description,'category':category,'location':location or None,'moq':quantity,'unit':unit,'price':price,'currency':currency,'notice':NOTICE}
    return payload,image_data(data.get('image',''))


def private_profile(data):
    data=dict(data)
    for key in ('phone','employees','founded_year','lead_time'):
        value=data.get(key)
        if type(value) in (int,float) and math.isfinite(value):data[key]=str(int(value)) if float(value).is_integer() else str(value)
    profile={key:s.field(data,key,maximum=maximum) for key,maximum in [('company',200),('contact',200),('country',100),('city',100)]}
    profile['email']=s.email_address(data)
    profile['whatsapp']=s.field(data,'whatsapp',minimum=0,maximum=60)
    profile['wechat']=s.field(data,'wechat',minimum=0,maximum=100)
    profile['license_number']=s.field(data,'license_number',minimum=0,maximum=150)
    if data.get('consent') is not True:raise s.WorkflowError('Confirm the private-data and publication notice.')
    if data.get('license_pdf'):
        raise s.WorkflowError('Document uploads are disabled until malware scanning and quarantine are implemented. Submit without a document.',503)
    profile['license_pdf']=''
    from app import normalization
    profile['website']=normalization.website(data.get('website',''))
    for key,maximum in [('phone',80),('capabilities',3000),('lead_time',150),('employees',100),('founded_year',4)]:
        profile[key]=s.field(data,key,minimum=0,maximum=maximum)
    if profile['founded_year']:
        import datetime
        if not profile['founded_year'].isdigit() or not 1000<=int(profile['founded_year'])<=datetime.date.today().year:raise s.WorkflowError('Enter a valid founding year.',field='founded_year')
    for key in ('categories','certifications','materials','regions'):profile[key]=normalization.sequence(data.get(key,[]),key)
    return profile


def issue(db, account):
    token=secrets.token_urlsafe(32)
    db.execute('UPDATE market_tokens SET used_at=? WHERE owner_id=? AND used_at IS NULL',(s.now(),account['id']))
    db.execute('INSERT INTO market_tokens VALUES (?,?,?,NULL)',(s.digest(token),account['id'],s.now()+86400))
    link=s.public_base()+'/access#market_token='+token
    listing=db.execute('SELECT id,public_payload FROM market_products WHERE owner_id=? ORDER BY created_at DESC LIMIT 1',(account['id'],)).fetchone()
    from urllib.parse import quote
    listing_note=('\n\nListing reference: P-'+listing['id'][:12]+'\nMarketplace: '+s.public_base()+'/marketplace?q='+quote(json.loads(listing['public_payload'])['title'][:100])) if listing else ''
    message_id=s.queue(db,account['email'],'STRATEVO — confirm your supplier email',
                   'Confirm your email to access your supplier account. Your supplier directory listing is separate from email verification. Confirmation does not certify your business.\n\n'+link+listing_note+'\n\nThis link expires in 24 hours and can be used once. If you did not request this, ignore it.')

    from app.mail_policy import audit_auth_mail
    audit_auth_mail(db,message_id,account['email'],account['id'])
    return message_id


def register(data, *, immediate=False):
    """Create a supplier account; public form requests an immediate management session, not publication."""
    if immediate:return publish_registration(data)
    s.rate_limit('market-register',20,3600)
    s.public_base()
    profile=private_profile(data)
    payload,image=product_data(data.get('product'),profile)
    message_id=None
    with s.database() as db:
        controls.capacity(db,'account',len(image))
        owner=str(uuid.uuid4())
        inserted=db.execute('INSERT INTO market_accounts VALUES (?,?,?,?,NULL) ON CONFLICT(email) DO NOTHING RETURNING id',(owner,profile['email'],json.dumps(profile),s.now())).fetchone()
        if inserted:
            from app.listings import create_pending
            create_pending(db,owner,payload,image)
            message_id=issue(db,{'id':owner,'email':profile['email']})
            from app.intake import enqueue
            enqueue(db,'supplier',owner,'Product category: '+payload['category']+'; business country: '+profile['country'])
    return {'message':'If this email is eligible, a confirmation email is queued. Products appear only after email confirmation, without manager approval. If you already registered, request a fresh access link.'},message_id


def publish_registration(data):
    from app import settings
    s.rate_limit('market-register',20,3600)
    profile=private_profile(data)
    payload,image=product_data(data.get('product'),profile)
    key=data.get('submission_key') or secrets.token_urlsafe(32)
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,100}',key):raise s.WorkflowError('Invalid submission key.')
    fingerprint=s.digest(json.dumps({'profile':profile,'product':payload,'image':image},sort_keys=True))
    message_id=None
    with s.database() as db:
        controls.capacity(db,'lock')
        existing=db.execute('SELECT * FROM market_publications WHERE submission_digest=?',(s.digest(key),)).fetchone()
        if existing:
            if existing['payload_digest']!=fingerprint:raise s.WorkflowError('This submission key was used for different details. Review a new submission.',409)
            if existing['created_at']<s.now()-86400:raise s.WorkflowError('Registration recovery expired. Use your account or request an email access link.',410)
            owner=existing['account_id']
            if controls.suspended(db,owner):raise s.WorkflowError('This supplier account is suspended.',403)
        else:
            # Email alone never grants access or replaces an existing supplier's details.
            if db.execute('SELECT id FROM market_accounts WHERE email=?',(profile['email'],)).fetchone():
                return {'submitted':False,'published':False,'message':'This registration cannot create a new account. If you registered before, use your existing session or request a secure access link.','storage':settings.storage_status()},None
            controls.capacity(db,'account',len(image))
            owner=str(uuid.uuid4())
            db.execute('INSERT INTO market_accounts VALUES (?,?,?,?,NULL)',(owner,profile['email'],json.dumps(profile),s.now()))
            db.execute('INSERT INTO market_publications VALUES (?,?,?,?)',(owner,s.digest(key),fingerprint,s.now()))
            from app.listings import create_pending
            create_pending(db,owner,payload,image)
            from app.operations import upsert_supplier
            upsert_supplier(db,owner,{**profile,'product':payload})
            # Missing email/origin configuration never rolls back an otherwise valid publication.
            try:
                s.public_base()
                message_id=issue(db,{'id':owner,'email':profile['email']})
            except s.WorkflowError as error:
                if error.status!=503:raise
            from app.intake import enqueue
            enqueue(db,'supplier',owner,'Product category: '+payload['category']+'; business country: '+profile['country'])
        session=s.session(db,'publisher',owner)
    storage=settings.storage_status()
    return {'supplier_id':owner,'supplier':{**payload,'reference':owner},'new_submission':not bool(existing),'management':{'method':'http_only_cookie','expires_in_seconds':28800},'submitted':True,'published':False,'review_status':'pending','email_confirmed':False,'redirect':'/supplier/account','_session':session,
            'storage':storage,'message':'Submitted for review. Your account is ready in this browser. Your product is not public until approved. '+storage['warning']},message_id


def request_access(data):
    s.rate_limit('market-access',15,3600)
    s.public_base();email=s.email_address(data);message_id=None
    with s.database() as db:
        account=db.execute('SELECT id,email FROM market_accounts WHERE email=?',(email,)).fetchone()
        if account and not controls.suspended(db,account['id']):message_id=issue(db,account)
    return {'message':'If this email has an eligible supplier account, a secure confirmation/sign-in link is queued.'},message_id


def consume(data):
    s.rate_limit('market-consume',100,3600)
    raw=s.field(data,'token',minimum=40,maximum=100)
    with s.database() as db:
        token=db.execute('UPDATE market_tokens SET used_at=? WHERE digest=? AND used_at IS NULL AND expires_at>? RETURNING owner_id',(s.now(),s.digest(raw),s.now())).fetchone()
        if not token:raise s.WorkflowError('This link expired or was already used. Request a new link.',410)
        if controls.suspended(db,token['owner_id']):raise s.WorkflowError('This supplier account is suspended.',403)
        db.execute('UPDATE market_accounts SET verified_at=COALESCE(verified_at,?) WHERE id=?',(s.now(),token['owner_id']))
        session=s.session(db,'publisher',token['owner_id'])
    return {'status':'active','redirect':'/supplier/account','message':'Email confirmed. You can manage your submissions. You can now securely manage your supplier profile.'},session


def identity(raw):
    identity=s.authenticate(raw,'publisher')
    with s.database() as db:
        row=db.execute('SELECT id,email,private_profile,verified_at FROM market_accounts WHERE id=? AND (verified_at IS NOT NULL OR EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=market_accounts.id))',(identity['application_id'],)).fetchone()
    if not row:raise s.WorkflowError('Confirm your email to access your supplier account.',403)
    return dict(row)


def public_product(row):
    payload=json.loads(row['public_payload'])
    # Explicit projection; never return account data or arbitrary JSON keys.
    return {**{key:payload.get(key) for key in ('title','description','category','location','moq','unit','price','currency')},
            'id':row['id'],'reference':'P-'+row['id'][:12], 'image_url':'/api/marketplace/image/'+row['id'] if row['image'] else None,'notice':NOTICE}


def listings(query='',category='',offset=0):
    if not isinstance(query,str) or len(query)>100 or category not in ('',*CATEGORIES):raise s.WorkflowError('Check the product filters.')
    try:offset=int(offset)
    except (ValueError,TypeError):raise s.WorkflowError('Invalid page.') from None
    if not 0<=offset<=100000:raise s.WorkflowError('Invalid page.')
    with s.database() as db:
        title="(p.public_payload::jsonb->>'title')" if db.postgres else "json_extract(p.public_payload,'$.title')"
        description="(p.public_payload::jsonb->>'description')" if db.postgres else "json_extract(p.public_payload,'$.description')"
        category_field="(p.public_payload::jsonb->>'category')" if db.postgres else "json_extract(p.public_payload,'$.category')"
        clauses=["(a.verified_at IS NOT NULL OR EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=a.id))","p.visibility='published'","NOT EXISTS (SELECT 1 FROM account_controls c WHERE c.account_id=a.id AND c.suspended=1)"]
        values=[]
        if category:clauses.append(category_field+'=?');values.append(category)
        for word in query.lower().split()[:12]:
            clauses.append("LOWER("+title+" || ' ' || "+description+") LIKE ? ESCAPE '!'")
            values.append('%'+word.replace('!','!!').replace('%','!%').replace('_','!_')+'%')
        where=' AND '.join(clauses)
        total=db.execute('SELECT COUNT(*) AS n FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE '+where,tuple(values)).fetchone()['n']
        rows=db.execute("SELECT p.id,p.public_payload,CASE WHEN p.image='' THEN '' ELSE 'yes' END AS image FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE "+where+' ORDER BY COALESCE((SELECT featured FROM suppliers sm WHERE sm.id=a.id),0) DESC,p.created_at DESC,p.id LIMIT 24 OFFSET ?',tuple(values+[offset])).fetchall()
    return {'products':[public_product(row) for row in rows],'total':total,'has_more':total>offset+24,'offset':offset,'notice':NOTICE,'scan_limit':None}


def photo(product_id):
    with s.database() as db:
        row=db.execute("SELECT p.image FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE p.id=? AND (a.verified_at IS NOT NULL OR EXISTS (SELECT 1 FROM market_publications mp WHERE mp.account_id=a.id)) AND p.visibility='published' AND NOT EXISTS (SELECT 1 FROM account_controls c WHERE c.account_id=a.id AND c.suspended=1)",(product_id,)).fetchone()
    if not row or not row['image']:raise s.WorkflowError('Photo not found.',404)
    return base64.b64decode(row['image'])


def mine(raw):
    account=identity(raw)
    profile=json.loads(account['private_profile'])
    with s.database() as db:rows=db.execute("SELECT p.*,COALESCE(r.revision,0) AS revision,COALESCE(r.status,'legacy') AS review_status,COALESCE(r.review_note,'') AS review_note FROM market_products p LEFT JOIN listing_reviews r ON r.product_id=p.id WHERE p.owner_id=? ORDER BY p.created_at DESC",(account['id'],)).fetchall()
    from app.settings import storage_status
    return {'email_confirmed':account['verified_at'] is not None,'storage':storage_status(),'profile':{k:v for k,v in profile.items() if k!='license_pdf'},'products':[{**public_product(r),'image_url':'/api/marketplace/own-image/'+r['id'] if r['image'] else None,'visibility':r['visibility'],'revision':r['revision'],'review_status':r['review_status'],'review_note':r['review_note']} for r in rows]}


def withdraw(raw,data):
    account=identity(raw);product_id=s.field(data,'id',maximum=40)
    with s.database() as db:
        controls.capacity(db,'lock')
        changed=db.execute("UPDATE market_products SET visibility='withdrawn' WHERE id=? AND owner_id=?",(product_id,account['id']))
        if changed.rowcount!=1:raise s.WorkflowError('Product not found.',404)
        db.execute("UPDATE listing_reviews SET status='withdrawn',revision=revision+1,updated_at=? WHERE product_id=?",(s.now(),product_id))
    return {'message':'Product withdrawn from the Marketplace.'}


def moderate(data):
    product_id=s.field(data,'id',maximum=40)
    with s.database() as db:
        changed=db.execute("UPDATE market_products SET visibility='hidden' WHERE id=?",(product_id,))
        if changed.rowcount!=1:raise s.WorkflowError('Product not found.',404)
    return {'message':'Product hidden from the Marketplace.'}


def admin_accounts(offset=0):
    """Manager-only private registry; never return license bytes in a list response."""
    try:offset=int(offset)
    except (ValueError,TypeError):raise s.WorkflowError('Invalid page.') from None
    if not 0<=offset<=100000:raise s.WorkflowError('Invalid page.')
    with s.database() as db:
        rows=db.execute('SELECT id,email,private_profile,verified_at FROM market_accounts ORDER BY created_at DESC,id LIMIT 26 OFFSET ?',(offset,)).fetchall()
        records=[]
        for row in rows[:25]:
            profile=json.loads(row['private_profile'])
            products=db.execute("SELECT id,public_payload,CASE WHEN image='' THEN '' ELSE 'yes' END AS image,visibility FROM market_products WHERE owner_id=? ORDER BY created_at DESC",(row['id'],)).fetchall()
            records.append({'id':row['id'],'suspended':controls.suspended(db,row['id']),'email_confirmed':row['verified_at'] is not None,'publication_enabled':bool(row['verified_at'] is not None or db.execute('SELECT 1 FROM market_publications WHERE account_id=?',(row['id'],)).fetchone()),
                'created_at':db.execute('SELECT created_at FROM market_accounts WHERE id=?',(row['id'],)).fetchone()['created_at'],
                'review_status':(dict(db.execute('SELECT status FROM supplier_reviews WHERE account_id=?',(row['id'],)).fetchone() or {}).get('status','new')),
                'has_license':bool(profile.get('license_pdf')),
                'profile':{key:profile.get(key,'') for key in ('company','contact','country','city','email','whatsapp','wechat','license_number')},
                'products':[{**public_product(p),'visibility':p['visibility']} for p in products]})
    return {'accounts':records,'limit':25,'offset':offset,'has_more':len(rows)>25,'notice':'Private supplier registry. New registrations publish immediately; email confirmation is a separate ownership check. No approval action exists.'}


def license_document(account_id):
    with s.database() as db:row=db.execute('SELECT private_profile FROM market_accounts WHERE id=?',(account_id,)).fetchone()
    if not row:raise s.WorkflowError('Supplier account not found.',404)
    encoded=json.loads(row['private_profile']).get('license_pdf','')
    if not encoded:raise s.WorkflowError('No license was uploaded.',404)
    return base64.b64decode(encoded)
