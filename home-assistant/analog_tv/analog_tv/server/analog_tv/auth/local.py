"""Local credentials and process-local Admin sessions."""
import hashlib
import re
from urllib.parse import urlsplit

from analog_tv.core.config import get_settings

USERNAME = re.compile(r"[A-Za-z0-9_.@+-]{1,64}")
HASH = re.compile(r"scrypt:([0-9a-f]{32}):([0-9a-f]{64})")
SESSION_AGE = 8 * 3600


def derive(password, salt):
    return hashlib.scrypt(password, salt=salt, n=2**17, r=8, p=1,
                          maxmem=192 * 1024**2, dklen=32)


def configured():
    s = get_settings()
    if not (USERNAME.fullmatch(s.admin_username) and HASH.fullmatch(s.admin_password_hash)
            and re.fullmatch(r"[A-Za-z0-9_-]{64,128}", s.session_secret)):
        return False
    try:
        origin = urlsplit(s.public_base_url)
        _ = origin.port
        if (not origin.hostname or origin.username is not None or
                s.public_base_url != f"{origin.scheme}://{origin.netloc}" or
                re.search(r"[\s\\]", s.public_base_url)):
            return False
        return ((origin.scheme == "https" and s.cookie_secure) or
                (origin.scheme == "http" and s.cookie_secure is False and
                 origin.hostname in {"localhost", "127.0.0.1", "::1"}))
    except ValueError:
        return False
