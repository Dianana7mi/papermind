from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import session
from app.models import User

passwords = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DB = Annotated[AsyncSession, Depends(session)]


def token_for(user_id: str):
    return jwt.encode(
        {
            "sub": user_id,
            "exp": datetime.now(UTC) + timedelta(minutes=settings().token_expiry_minutes),
            "iss": "papermind",
            "aud": "papermind-web",
        },
        settings().secret_key.get_secret_value(),
        algorithm="HS256",
    )


async def current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if not credentials:
        raise HTTPException(401, "Authentication required")
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings().secret_key.get_secret_value(),
            algorithms=["HS256"],
            issuer="papermind",
            audience="papermind-web",
        )
        user = await db.get(User, payload["sub"])
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(401, "Invalid or expired token") from None
    if not user:
        raise HTTPException(401, "User no longer exists")
    return user


Auth = Annotated[User, Depends(current_user)]
