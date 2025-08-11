from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional

# Secret key & algorithm for JWT (nên để ở config/env thực tế)
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

security = HTTPBearer()

def decode_jwt_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = decode_jwt_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Bạn có thể tuỳ chỉnh thêm logic kiểm tra user/roles ở đây
    request.state.user = payload  # Lưu user info vào request.state
    return payload
