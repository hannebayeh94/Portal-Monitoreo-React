from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
import hmac
import hashlib
import base64

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return plain == hashed

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")

def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None

def generar_token_seguro(uid: int) -> str:
    uid_str = str(uid)
    firma = hmac.new(settings.secret_key.encode(), uid_str.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{uid_str}:{firma}".encode()).decode()

def validar_token_seguro(token_b64: str) -> Optional[str]:
    try:
        decodificado = base64.urlsafe_b64decode(token_b64).decode()
        uid_str, firma_recibida = decodificado.split(":")
        firma_esperada = hmac.new(settings.secret_key.encode(), uid_str.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(firma_recibida, firma_esperada):
            return uid_str
    except Exception:
        pass
    return None
