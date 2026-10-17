from datetime import UTC, datetime, timedelta
import jwt
from fastapi.security import OAuth2PasswordBearer
from config import settings
from pwdlib import PasswordHash
from typing import Annotated
from fastapi import Depends, HTTPException, status
import models
from database import get_db
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import secrets


pwd_hasher = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/users/token")

def hash_password(password: str) -> str:
    return pwd_hasher.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_hasher.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Create a JWT token with payload and expiration time. #<header>.<payload>.<signature>
    -- Here header contains the algorithm and token type (JWT)
    -- Payload contains the user_id and other data(if we pass) with expiration
    -- Signature contains the signed token using secret key
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key.get_secret_value(), 
        algorithm=settings.algorithm
        )
    return encoded_jwt


def verify_access_token(token: str) -> str | None:
    """
    Verify access token and return user_id if valid, None otherwise.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.secret_key.get_secret_value(), 
            algorithms=[settings.algorithm]
            )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")



#Generate reset token
def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


#Hashing resdet token
def hash_reset_token(token: str) -> str:
    """Hash a raw token using SHA-256 for secure database storage and lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


            
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> models.User:
    """
    Uses OAuth2PasswordBearer to get the token from the request header
    Verify access token and return user if valid, else raise HTTPException.
    """
    user_id = verify_access_token(token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials or token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    result = await db.execute(
        select(models.User).where(models.User.id == user_id_int)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[models.User, Depends(get_current_user)]