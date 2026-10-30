"""Conservative field normalization; never converts a marketing claim into verified evidence."""
import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit
from app import suppliers as s


def text(value):
    return unicodedata.normalize('NFKC',value).strip() if isinstance(value,str) else value


def website(value):
    value=text(value or '')
    if not isinstance(value,str):raise s.WorkflowError('Enter a company website.',field='website')
    linked=re.fullmatch(r'\[[^\]]+\]\(([^)]+)\)',value)
    if linked:value=linked[1]
    if not value:return ''
    if '://' not in value:value='https://'+value
    if not safe_web_url(value):raise s.WorkflowError('Enter a public HTTP/HTTPS company website without a username or password.',field='website')
    p=urlsplit(value)
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path,p.query,''))


def sequence(value,name):
    if not value:return []
    items=re.split(r'[,;\n]',value) if isinstance(value,str) else value
    if not isinstance(items,list) or len(items)>30 or any(not isinstance(v,str) or len(v)>120 for v in items):raise s.WorkflowError('Use up to 30 comma-separated values.',field=name)
    return list(dict.fromkeys(text(v) for v in items if text(v)))


def quantity(value):
    if value in ('',None):return None
    if isinstance(value,bool):raise s.WorkflowError('Enter a positive MOQ.',field='moq')
    if isinstance(value,(float,int)):return value
    match=re.fullmatch(r'\s*([0-9][0-9, ]*(?:\.[0-9]+)?)\s*([kKmM]?)\s*(?:(?:pieces|pcs|sets|kg|kilograms|litres|metres|units))?\s*',str(value))
    if not match:raise s.WorkflowError('Use a minimum quantity such as 1000, 1,000 pcs or 1k. Put ranges or special conditions in the description.',field='moq')
    return float(re.sub('[, ]','',match[1]))*({'k':1000,'m':1000000}.get(match[2].lower(),1))


def safe_web_url(value):
    """Validate operator-configured webhook URLs without following redirects."""
    from urllib.parse import urlsplit
    import ipaddress
    if not isinstance(value,str) or len(value)>2000 or any(c.isspace() for c in value):return None
    try:
        parsed=urlsplit(value)
        if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password:return None
        host=parsed.hostname.lower()
        if parsed.port is not None and not 1<=parsed.port<=65535:return None
        if host=='localhost' or host.endswith(('.local','.internal')):return None
        try:
            if not ipaddress.ip_address(host).is_global:return None
        except ValueError:
            ascii_host=host.encode('idna').decode()
            if '.' not in ascii_host or not all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?',label) for label in ascii_host.split('.')):return None
        return value
    except (ValueError,UnicodeError):return None
