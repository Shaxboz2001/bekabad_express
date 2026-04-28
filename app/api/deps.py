from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)

    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati o'tgan")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token noto'g'ri")

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi yoki bloklangan")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin huquqi talab etiladi")
    return current_user


def require_driver(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in [UserRole.DRIVER, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Haydovchi huquqi talab etiladi")
    return current_user


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
