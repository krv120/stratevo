"""Public configuration and deployment separation. Never infer trusted URLs from Host."""
import html
import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

DEFAULT_CANONICAL = 'https://stratevo.online'  # Owner-supplied, not DNS/redirect verification.
DEFAULT_BOOKING = 'https://app.minup.io/book/stratevo'  # Owner-authorized destination.


def environment():
    value=os.environ.get('APP_ENV') or os.environ.get('VERCEL_ENV') or ('production' if os.environ.get('VERCEL')=='1' else 'local')
    if value=='development':value='local'
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


DATABASE_VARIABLES = ('DATABASE_URL', 'STRATEVO_DATABASE_URL', 'POSTGRES_URL',
                      'POSTGRES_URL_NON_POOLING', 'NEON_DATABASE_URL', 'SUPABASE_DB_URL')


def database_url():
    """Resolve once per call; never log the DSN, even when validation fails."""
    value = next((os.environ[n].strip() for n in DATABASE_VARIABLES if os.environ.get(n, '').strip()), '')
    if not value:return ''
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('postgres', 'postgresql') or parsed.fragment:raise ValueError()
        # Prisma/Supabase client hints are not libpq connection parameters.
        ignored = {'pgbouncer','connection_limit','pool_timeout','supa','statement_cache_size','prepared_statements','prepare_threshold','schema'}
        pairs = [(k,v) for k,v in parse_qsl(parsed.query,keep_blank_values=True) if k.lower() not in ignored]
        modes = [v for k,v in pairs if k=='sslmode']
        if modes:
            ranks = {'disable':0,'allow':1,'prefer':2,'require':3,'verify-ca':4,'verify-full':5}
            if any(v not in ranks for v in modes):raise ValueError()
            strongest = max(modes,key=ranks.get)
            pairs = [(k,v) for k,v in pairs if k!='sslmode'] + [('sslmode',strongest)]
        elif parsed.hostname not in (None,'localhost','127.0.0.1','::1'):
            pairs.append(('sslmode','require'))
        return urlunsplit(('postgresql',parsed.netloc,parsed.path,urlencode(pairs),''))
    except (ValueError,TypeError):raise ValueError('Invalid PostgreSQL configuration') from None


def ephemeral_storage():
    return not database_url() and (bool(os.environ.get('VERCEL')) or environment() in ('production','staging','preview'))


def storage_status():
    mode = 'postgres' if database_url() else 'ephemeral_fallback' if ephemeral_storage() else 'sqlite_local'
    return {'mode':mode,'durable':mode=='postgres', 'shared':mode=='postgres',
            'warning':('Temporary instance-local storage: records and sessions may disappear on restart or be unavailable on another instance. Usage limits are also instance-local. Do not rely on this for durable submissions.' if mode=='ephemeral_fallback' else '')}


def database_guard():
    env=environment()
    url=database_url()
    if not url and os.environ.get('STRICT_PERSISTENT_DB','false').lower()=='true':raise ValueError('Strict persistent storage requires PostgreSQL')
    # Reject explicit environment mismatches, without making an unset optional attestation a dead-end.
    binding=os.environ.get('DATABASE_ENVIRONMENT','')
    if url and binding and env not in ('local','test') and binding!=env:raise ValueError('Database environment binding does not match deployment')
    if env=='production' and (os.environ.get('COOKIE_SECURE','true')!='true' or os.environ.get('ALLOW_PREVIEW_EMBEDDING','false')=='true'):raise ValueError('Unsafe production cookie/frame configuration')


def render_public(html_text):
    """Resolve legacy static contact/link copy at the HTTP boundary, from trusted settings."""
    email=contact()
    replacement=('<a href="mailto:'+html.escape(email,quote=True)+'">'+html.escape(email)+'</a>') if email else '<a href="/inquiry">Contact through a sourcing inquiry</a>'
    html_text=re.sub(r'<a data-public-contact href="/inquiry">Contact through a sourcing inquiry</a>',lambda _:replacement,html_text)
    html_text=html_text.replace(DEFAULT_BOOKING,html.escape(booking(),quote=True))
    return html_text

AI_KEY_VARIABLES=('OPENAI_API_KEY','STRATEVO_AI_API_KEY','AI_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','ANTHROPIC_API_KEY','PERPLEXITY_API_KEY','OPENROUTER_API_KEY','GROQ_API_KEY')
AI_DEFAULTS={
 'openai':('https://api.openai.com/v1','gpt-4o-mini'),
 'gemini':('https://generativelanguage.googleapis.com/v1beta','gemini-2.5-flash'),
 'anthropic':('https://api.anthropic.com/v1','claude-sonnet-4-5'),
 'perplexity':('https://api.perplexity.ai','sonar-pro'),
 'openrouter':('https://openrouter.ai/api/v1','openai/gpt-4o-mini'),
 'groq':('https://api.groq.com/openai/v1','llama-3.3-70b-versatile')}


def ai_configuration():
    variable=next((n for n in AI_KEY_VARIABLES if os.environ.get(n,'').strip()),'')
    key=os.environ.get(variable,'').strip()
    inferred=next((p for prefix,p in [('sk-ant-','anthropic'),('AIza','gemini'),('pplx-','perplexity'),('sk-or-','openrouter'),('gsk_','groq')] if key.startswith(prefix)),None)
    names={'GEMINI_API_KEY':'gemini','GOOGLE_API_KEY':'gemini','ANTHROPIC_API_KEY':'anthropic','PERPLEXITY_API_KEY':'perplexity','OPENROUTER_API_KEY':'openrouter','GROQ_API_KEY':'groq'}
    provider=os.environ.get('AI_PROVIDER','').strip().lower() or inferred or names.get(variable,'openai')
    provider={'google':'gemini','claude':'anthropic'}.get(provider,provider)
    if provider not in AI_DEFAULTS:raise ValueError('Unsupported AI_PROVIDER')
    base,default=AI_DEFAULTS[provider]
    override=os.environ.get('AI_BASE_URL','').strip().rstrip('/')
    # The old template set the OpenAI default even for unrelated provider keys.
    base=(override if override!='https://api.openai.com/v1' or provider=='openai' else '') or base
    parsed=urlsplit(base)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() for c in base) or base.endswith('/chat/completions'):raise ValueError('AI_BASE_URL must be an HTTPS API base URL')
    return {'key':key,'provider':provider,'base':base,'model':os.environ.get('AI_MODEL','').strip() or default,'key_variable':variable}
