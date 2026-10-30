"""Buyer-output boundary. Raw research stays private; source links never pass through.

This is defense in depth, not a substitute for reviewing descriptions for names,
phone numbers, or cleverly obfuscated identifying material.
"""
import html
import re
import unicodedata
from urllib.parse import unquote, urlsplit

# Catch explicit URLs, emails and bare DNS names (including Markdown targets).
LINK = re.compile(
    r'(?:https?://|www\.)[^\s<>"\']+'
    r'|[\w.+-]+@[\w.-]+\.[a-z]{2,}'
    r'|(?<![\w])(?:[\w-]+\.)+(?:com|net|org|io|co|cn|online|shop|biz|info|eu|gr)(?:/[^\s<>"\']*)?',
    re.IGNORECASE,
)
SOURCE = re.compile(r'\b(?:alibaba|alicdn|aliexpress|1688)\s*(?:\[?\s*(?:\.|dot)\s*\]?|。|．)\s*(?:com|cn)\b', re.IGNORECASE)
REDACTED = '[private source removed]'


def normalized(text):
    text = unicodedata.normalize('NFKC', html.unescape(text))
    for _ in range(3):
        decoded = unquote(text)
        if decoded == text:break
        text = decoded
    return ''.join(c for c in text if unicodedata.category(c) != 'Cf')


def buyer_safe(value):
    """Recursively strip source URLs/contact addresses from a public projection."""
    if isinstance(value, str):
        return LINK.sub(REDACTED, SOURCE.sub(REDACTED, normalized(value)))
    if isinstance(value, dict):
        return {key:buyer_safe(item) for key,item in value.items()}
    if isinstance(value, list):
        return [buyer_safe(item) for item in value]
    return value
