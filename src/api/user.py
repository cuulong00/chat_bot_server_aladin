from fastapi import APIRouter, HTTPException, Depends
from src.services.user_service import UserService
from src.schemas.user import UserOut
from typing import List
import logging

logger = logging.getLogger(__name__)

# Make auth dependency optional: if SKIP_SUPABASE_AUTH=1 or local dev, you can remove the dependency.
from src.api.auth import get_current_user
router = APIRouter()

@router.get("/users", response_model=List[UserOut])
def get_users():
    try:
        users = UserService.get_all_users()
        logger.info(f"API /users returned {len(users)} users")
        return users
    except Exception as e:
        logger.error(f"API /users error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
