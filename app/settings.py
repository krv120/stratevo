"""Public configuration and deployment separation. Never infer trusted URLs from Host."""
import html
import os
import re
from urllib.parse import urlsplit

DEFAULT_CANONICAL = 'https://stratevo.online'  # Owner-supplied, not DNS/redirect verification.
DEFAULT_BOOKING = 'https://app.minup.io/book/stratevo'  # Owner-authorized destination.


def environment():
    value=os.environ.get('APP_ENV') or os.environ.get('VERCEL_ENV') or 'local'
    if value not in ('local','test','preview','staging','production'):raise ValueError('Invalid APP_ENV')
    platform=os.environ.get('VERCEL_ENV')
    if platform=='production' and value!='production':raise ValueError('Production environment cannot be downgraded')
    if platform=='preview' and value not in ('preview','staging'):raise ValueError('Preview environment cannot use local or production settings')
    return value


def origin(name, default='', local=False):
    value=os.environ.get(name,default).strip().rstrip('/')
    p=urlsplit(value)
    if not p.hostname or p.username or p.password or p.path or p.query or p.fragment or any(c.isspace() for c in value):raise ValueError('Invalid '+name)
    if p.scheme!='https' and not (local and p.scheme=='http' and p.hostname in ('localhost','127.0.0.1')):raise ValueError('HTTPS required for '+name)
    return value


def canonical():return origin('CANONICAL_BASE_URL',DEFAULT_CANONICAL)


def public_origin():
    value=origin('PUBLIC_BASE_URL',local=environment() in ('local','test'))
    if environment() not in ('local','test') and os.environ.get('PUBLIC_ORIGIN_VERIFIED')!='true':raise ValueError('PUBLIC_ORIGIN_VERIFIED is required')
    return value


def booking():
    value=os.environ.get('BOOKING_URL',DEFAULT_BOOKING).strip()
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or any(c.isspace() for c in value):raise ValueError('Invalid BOOKING_URL')
    return value


def contact():
    if os.environ.get('PUBLIC_CONTACT_VERIFIED')!='true':return ''
    value=os.environ.get('PUBLIC_CONTACT_EMAIL','').strip()
    from app.suppliers import email_address, WorkflowError
    try:return email_address({'email':value}) if value else ''
    except WorkflowError:raise ValueError('Invalid verified contact configuration') from None


def database_guard():
    env=environment()
    if (env in ('staging','production') or os.environ.get('VERCEL')) and not os.environ.get('DATABASE_URL'):raise ValueError('Persistent database is required')
    if os.environ.get('DATABASE_URL') and env not in ('local','test') and os.environ.get('DATABASE_ENVIRONMENT')!=env:raise ValueError('Database environment binding does not match deployment')
    if env=='production' and (os.environ.get('COOKIE_SECURE','true')!='true' or os.environ.get('ALLOW_PREVIEW_EMBEDDING','false')=='true'):raise ValueError('Unsafe production cookie/frame configuration')


def render_public(html_text):
    """Resolve legacy static contact/link copy at the HTTP boundary, from trusted settings."""
    email=contact()
    replacement=('<a href="mailto:'+html.escape(email,quote=True)+'">'+html.escape(email)+'</a>') if email else '<a href="/inquiry">Contact through a sourcing inquiry</a>'
    html_text=re.sub(r'<a data-public-contact href="/inquiry">Contact through a sourcing inquiry</a>',lambda _:replacement,html_text)
    html_text=html_text.replace(DEFAULT_BOOKING,html.escape(booking(),quote=True))
    return html_text
