from src.repositories.users import UserRepository
import logging

logger = logging.getLogger(__name__)

class UserService:
    @staticmethod
    def get_all_users():
        try:
            users = UserRepository.get_all_users()
            logger.info(f"UserService returned {len(users)} users")
            return users
        except Exception as e:
            logger.error(f"UserService error: {e}", exc_info=True)
            raise
