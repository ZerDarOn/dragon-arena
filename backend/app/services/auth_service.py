"""JWT signing/verification and bcrypt password hashing utilities.

Security notes:
- HMAC-SHA256 signing (HS256). SECRET_KEY read from env DRAGON_ARENA_JWT_SECRET,
  falls back to a dev-only constant. NEVER use the fallback in production.
- Token TTL: 4 hours (short to mitigate lack of server-side revocation).
- bcrypt rounds: 12 (industry standard).
"""
import os
import time
from typing import Optional

import bcrypt
from jose import jwt, JWTError

# Config
_DEFAULT_SECRET = "DEV_ONLY_DO_NOT_USE_IN_PRODUCTION_PLEASE_SET_DRAGON_ARENA_JWT_SECRET"
SECRET_KEY = os.environ.get("DRAGON_ARENA_JWT_SECRET", _DEFAULT_SECRET)
ALGORITHM = "HS256"
TOKEN_TTL_SEC = 4 * 3600  # 4 hours
BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return bcrypt hash. Handles bytes conversion."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt compare."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, is_admin: bool) -> str:
    """Sign a JWT carrying user_id and is_admin claim."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "is_admin": is_admin,
        "iat": now,
        "exp": now + TOKEN_TTL_SEC,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Return payload if valid & unexpired, else None."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
