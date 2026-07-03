import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from app.utils.logger import logger

security = HTTPBearer()

SUPABASE_JWK = {
    "alg": "ES256",
    "crv": "P-256",
    "kty": "EC",
    "use": "sig",
    "kid": "e2008f4c-0be0-4822-9366-5d8eb22d35dc",
    "x": "R0Nd5PiQylyeaqAwx0h67wAZlu650_yNl-J_hsa9Hw8",
    "y": "4122TCXOKa_RpwD2uPKwOKMwvMSXFf0pjv6PEWW5BUg"
}

_cached_jwks = None

def get_jwk_by_kid(kid: str) -> dict:
    global _cached_jwks
    if _cached_jwks:
        for key in _cached_jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
    try:
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        # The service role key works as API key to authenticate requests
        resp = httpx.get(url, headers={"apikey": settings.supabase_service_key}, timeout=5.0)
        if resp.status_code == 200:
            _cached_jwks = resp.json()
            for key in _cached_jwks.get("keys", []):
                if key.get("kid") == kid:
                    return key
    except Exception as e:
        logger.warning(f"Dynamic JWKS fetch failed: {e}")

    # Fallback to local hardcoded key
    if kid == SUPABASE_JWK["kid"]:
        return SUPABASE_JWK
    return None

async def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extracts and cryptographically verifies the Supabase JWT sent in the
    Authorization header, and returns the authenticated user's UUID.
    Supports both ES256 and HS256 algorithms.
    """
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        kid = header.get("kid")

        if alg == "ES256":
            key = get_jwk_by_kid(kid)
            if not key:
                raise HTTPException(status_code=401, detail="JWK not found for kid")
            payload = jwt.decode(
                token,
                key,
                algorithms=["ES256"],
                audience="authenticated",
            )
        else:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing user id")

    return user_id

