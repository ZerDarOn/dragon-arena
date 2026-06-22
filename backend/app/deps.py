"""FastAPI dependencies for auth: get_current_user / require_admin."""
import os
from fastapi import Depends, HTTPException, Request, WebSocket, status
from typing import Optional

from app.services.auth_service import verify_token
from app.services.user_storage import UserStorage
from app.schemas.auth import User

# Singleton storage instance. DB path override via env for tests.
_DB_PATH = os.environ.get("DRAGON_ARENA_DB_PATH", "backend/data/users.db")
user_storage = UserStorage(db_path=_DB_PATH)


def _extract_token(request: Optional[Request] = None,
                   websocket: Optional[WebSocket] = None) -> Optional[str]:
    """Pull bearer token from Authorization header or ws query param."""
    if request is not None:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
    if websocket is not None:
        # query params injected via endpoint signature
        token = websocket.query_params.get("token")
        if token:
            return token
    return None


async def get_current_user(request: Request) -> User:
    """Resolve JWT to User. Raise 401 if missing/invalid."""
    token = _extract_token(request=request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing token")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token")
    user = user_storage.get_user(payload["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure current user is admin. Raise 403 otherwise."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user


async def get_current_user_ws(websocket: WebSocket) -> Optional[User]:
    """WS variant: returns None if auth fails (caller closes connection)."""
    token = _extract_token(websocket=websocket)
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    return user_storage.get_user(payload["sub"])
