"""Self-service listings: email verification publishes, never manager approval.

Private account/documents are deliberately stored separately from public payloads.
"""
import base64
import io
import json
import math
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
CREATE INDEX IF NOT EXISTS market_product_owner ON market_products(owner_id);
CREATE INDEX IF NOT EXISTS market_token_expiry ON market_tokens(expires_at);
'''
NOTICE = 'Supplier-provided information. Email ownership is confirmed; business identity, product quality, pricing and certifications are not independently verified.'


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
    quantity=data.get('moq')
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
    if data.get('content_consent') is not True:raise s.WorkflowError('Confirm that the product text and image contain no supplier identity, contacts, source links or unauthorized content.')
    payload={'title':title,'description':description,'category':category,'location':location or None,'moq':quantity,'unit':unit,'price':price,'currency':currency,'notice':NOTICE}
    return payload,image_data(data.get('image',''))


def private_profile(data):
    profile={key:s.field(data,key,maximum=maximum) for key,maximum in [('company',200),('contact',200),('country',100),('city',100)]}
    profile['email']=s.email_address(data)
    profile['whatsapp']=s.field(data,'whatsapp',minimum=0,maximum=60)
    profile['wechat']=s.field(data,'wechat',minimum=0,maximum=100)
    profile['license_number']=s.field(data,'license_number',minimum=0,maximum=150)
    if data.get('consent') is not True:raise s.WorkflowError('Confirm the private-data and email-verification notice.')
    if data.get('license_pdf'):
        raise s.WorkflowError('Document uploads are disabled until malware scanning and quarantine are implemented. Submit without a document.',503)
    profile['license_pdf']=''
    return profile


def issue(db, account):
    token=secrets.token_urlsafe(32)
    db.execute('UPDATE market_tokens SET used_at=? WHERE owner_id=? AND used_at IS NULL',(s.now(),account['id']))
    db.execute('INSERT INTO market_tokens VALUES (?,?,?,NULL)',(s.digest(token),account['id'],s.now()+86400))
    link=s.public_base()+'/access#market_token='+token
    return s.queue(db,account['email'],'STRATEVO — confirm your supplier email',
                   'Confirm your email to activate your supplier account and publish your submitted products. No manager approval is required. Email confirmation is not certification of your business or products.\n\n'+link+'\n\nThis link expires in 24 hours and can be used once. If you did not request this, ignore it.')


def register(data):
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
            db.execute('INSERT INTO market_products VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),owner,json.dumps(payload),image,'published',s.now()))
            message_id=issue(db,{'id':owner,'email':profile['email']})
            from app.intake import enqueue
            enqueue(db,'supplier',owner,'Product category: '+payload['category']+'; business country: '+profile['country'])
    return {'message':'If this email is eligible, a confirmation email is queued. Products appear only after email confirmation, without manager approval. If you already registered, request a fresh access link.'},message_id


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
    return {'status':'active','redirect':'/supplier/account','message':'Email confirmed. Your submitted products are now published. No manager approval is needed.'},session


def identity(raw):
    identity=s.authenticate(raw,'publisher')
    with s.database() as db:
        row=db.execute('SELECT id,email,private_profile FROM market_accounts WHERE id=? AND verified_at IS NOT NULL',(identity['application_id'],)).fetchone()
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
        clauses=["a.verified_at IS NOT NULL","p.visibility='published'","NOT EXISTS (SELECT 1 FROM account_controls c WHERE c.account_id=a.id AND c.suspended=1)"]
        values=[]
        if category:clauses.append(category_field+'=?');values.append(category)
        for word in query.lower().split()[:12]:
            clauses.append("LOWER("+title+" || ' ' || "+description+") LIKE ? ESCAPE '!'")
            values.append('%'+word.replace('!','!!').replace('%','!%').replace('_','!_')+'%')
        where=' AND '.join(clauses)
        total=db.execute('SELECT COUNT(*) AS n FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE '+where,tuple(values)).fetchone()['n']
        rows=db.execute("SELECT p.id,p.public_payload,CASE WHEN p.image='' THEN '' ELSE 'yes' END AS image FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE "+where+' ORDER BY p.created_at DESC,p.id LIMIT 24 OFFSET ?',tuple(values+[offset])).fetchall()
    return {'products':[public_product(row) for row in rows],'total':total,'has_more':total>offset+24,'offset':offset,'notice':NOTICE,'scan_limit':None}


def photo(product_id):
    with s.database() as db:
        row=db.execute("SELECT p.image FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE p.id=? AND a.verified_at IS NOT NULL AND p.visibility='published' AND NOT EXISTS (SELECT 1 FROM account_controls c WHERE c.account_id=a.id AND c.suspended=1)",(product_id,)).fetchone()
    if not row or not row['image']:raise s.WorkflowError('Photo not found.',404)
    return base64.b64decode(row['image'])


def mine(raw):
    account=identity(raw)
    profile=json.loads(account['private_profile'])
    with s.database() as db:rows=db.execute("SELECT id,public_payload,CASE WHEN image='' THEN '' ELSE 'yes' END AS image,visibility FROM market_products WHERE owner_id=? ORDER BY created_at DESC",(account['id'],)).fetchall()
    return {'profile':{k:profile[k] for k in ('company','contact','email','country')},'products':[{**public_product(r),'visibility':r['visibility']} for r in rows]}


def add_product(raw,data):
    account=identity(raw)
    s.rate_limit('market-add:'+account['id'],20,3600)
    payload,image=product_data(data,json.loads(account['private_profile']))
    with s.database() as db:
        controls.capacity(db,'product',len(image))
        if controls.suspended(db,account['id']):raise s.WorkflowError('This supplier account is suspended.',403)
        # Lock the owner row to make the 50-product cap atomic on PostgreSQL too.
        db.execute('UPDATE market_accounts SET created_at=created_at WHERE id=?',(account['id'],))
        count=db.execute("SELECT COUNT(*) AS n FROM market_products WHERE owner_id=? AND visibility='published'",(account['id'],)).fetchone()['n']
        stored=db.execute('SELECT COUNT(*) AS n FROM market_products WHERE owner_id=?',(account['id'],)).fetchone()['n']
        if count>=50 or stored>=500:raise s.WorkflowError('Account limit: 50 active listings or 500 retained records. Withdraw active listings or request retention review.',409)
        db.execute('INSERT INTO market_products VALUES (?,?,?,?,?,?)',(str(uuid.uuid4()),account['id'],json.dumps(payload),image,'published',s.now()))
    return {'message':'Product published to the Marketplace.'}


def withdraw(raw,data):
    account=identity(raw);product_id=s.field(data,'id',maximum=40)
    with s.database() as db:
        changed=db.execute("UPDATE market_products SET visibility='withdrawn' WHERE id=? AND owner_id=?",(product_id,account['id']))
        if changed.rowcount!=1:raise s.WorkflowError('Product not found.',404)
    return {'message':'Product withdrawn from the Marketplace.'}


def moderate(data):
    product_id=s.field(data,'id',maximum=40)
    with s.database() as db:
        changed=db.execute("UPDATE market_products SET visibility='hidden' WHERE id=?",(product_id,))
        if changed.rowcount!=1:raise s.WorkflowError('Product not found.',404)
    return {'message':'Product hidden. This is post-publication moderation, not an approval requirement.'}


def research_rows():
    with s.database() as db:
        rows=db.execute("SELECT p.id,p.public_payload FROM market_products p JOIN market_accounts a ON a.id=p.owner_id WHERE a.verified_at IS NOT NULL AND p.visibility='published' AND NOT EXISTS (SELECT 1 FROM account_controls c WHERE c.account_id=a.id AND c.suspended=1) ORDER BY p.created_at DESC LIMIT 2000").fetchall()
    result=[]
    for row in rows:
        p=json.loads(row['public_payload'])
        result.append({'reference':'P-'+row['id'][:12], 'description':p['title']+'. '+p['description'],
            'advertised_moq':{'quantity':p['moq'],'unit':p['unit']},
            'advertised_price':{'display':((p['currency']+' '+p['price']) if p['price'] else 'Not supplied'),'currency_code':p['currency'],'exact_variant_confirmed':False},
            'matrix':{'category':p['category'],'location':p['location'],'lead_time_days':None,'certifications_verified':[],'certifications_claimed':[]},
            'verification_status':'supplier_provided_unverified', 'source_note':NOTICE})
    return result


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
            records.append({'id':row['id'],'suspended':controls.suspended(db,row['id']),'email_confirmed':row['verified_at'] is not None,
                'created_at':db.execute('SELECT created_at FROM market_accounts WHERE id=?',(row['id'],)).fetchone()['created_at'],
                'review_status':(dict(db.execute('SELECT status FROM supplier_reviews WHERE account_id=?',(row['id'],)).fetchone() or {}).get('status','new')),
                'has_license':bool(profile.get('license_pdf')),
                'profile':{key:profile.get(key,'') for key in ('company','contact','country','city','email','whatsapp','wechat','license_number')},
                'products':[{**public_product(p),'visibility':p['visibility']} for p in products]})
    return {'accounts':records,'limit':25,'offset':offset,'has_more':len(rows)>25,'notice':'Private supplier registry. Email confirmation publishes products automatically; no approval action exists.'}


def license_document(account_id):
    with s.database() as db:row=db.execute('SELECT private_profile FROM market_accounts WHERE id=?',(account_id,)).fetchone()
    if not row:raise s.WorkflowError('Supplier account not found.',404)
    encoded=json.loads(row['private_profile']).get('license_pdf','')
    if not encoded:raise s.WorkflowError('No license was uploaded.',404)
    return base64.b64decode(encoded)
