"""Ed25519 signature verification in pure Python (RFC 8032).

fal.ai signs completion webhooks with Ed25519 and publishes the public keys as
a JWKS. The project deliberately keeps its dependency list tiny (see
requirements.txt), so verification is implemented here instead of adding
PyNaCl/cryptography. Only signature *verification* is implemented: the
application never holds a private key. Tests mint fixtures with the arithmetic
helpers at the bottom of this module.

Implementation follows the RFC 8032 reference arithmetic (extended twisted
Edwards coordinates). It is not constant-time, which is acceptable here: the
inputs are public keys, public request identifiers and attacker-supplied
signatures, never secrets.
"""
import hashlib

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _I % _P
    if (x * x - x2) % _P:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


def _decode(data):
    """Decode a 32-byte compressed point into extended coordinates."""
    if len(data) != 32:
        return None
    y = int.from_bytes(data, 'little') & ((1 << 255) - 1)
    x = _recover_x(y, data[31] >> 7)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _encode(point):
    x, y, z, _ = point
    zinv = pow(z, _P - 2, _P)
    x, y = x * zinv % _P, y * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, 'little')


def _add(left, right):
    x1, y1, z1, t1 = left
    x2, y2, z2, t2 = right
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    d = 2 * z1 * z2 % _P
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _multiply(scalar, point):
    result = (0, 1, 1, 0)
    while scalar > 0:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _same(left, right):
    return ((left[0] * right[2] - right[0] * left[2]) % _P == 0
            and (left[1] * right[2] - right[1] * left[2]) % _P == 0)


_BASE = _decode(int.to_bytes(
    4 * pow(5, _P - 2, _P) % _P, 32, 'little'))


def verify(public_key, message, signature):
    """Return True only for a valid Ed25519 signature over ``message``."""
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != 64:
        return False
    if not isinstance(message, (bytes, bytearray)):
        return False
    public = _decode(bytes(public_key))
    if public is None:
        return False
    r_bytes = bytes(signature[:32])
    r_point = _decode(r_bytes)
    if r_point is None:
        return False
    scalar_s = int.from_bytes(bytes(signature[32:]), 'little')
    if scalar_s >= _Q:
        return False
    digest = hashlib.sha512(r_bytes + bytes(public_key) + bytes(message)).digest()
    challenge = int.from_bytes(digest, 'little') % _Q
    return _same(_multiply(scalar_s, _BASE), _add(r_point, _multiply(challenge, public)))


def sign_for_tests(seed, message):
    """Mint a signature for fixtures. Application code must never call this."""
    digest = hashlib.sha512(bytes(seed)).digest()
    scalar = int.from_bytes(digest[:32], 'little')
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    public = _encode(_multiply(scalar, _BASE))
    nonce = int.from_bytes(hashlib.sha512(digest[32:] + bytes(message)).digest(), 'little') % _Q
    r_bytes = _encode(_multiply(nonce, _BASE))
    challenge = int.from_bytes(hashlib.sha512(r_bytes + public + bytes(message)).digest(), 'little') % _Q
    return r_bytes + ((nonce + challenge * scalar) % _Q).to_bytes(32, 'little')


def public_key_for_tests(seed):
    digest = hashlib.sha512(bytes(seed)).digest()
    scalar = int.from_bytes(digest[:32], 'little')
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return _encode(_multiply(scalar, _BASE))
