import logging
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database.database import get_db_session

logger = logging.getLogger(__name__)

class UserRepository:
    @staticmethod
    def get_all_users():
        session: Session = get_db_session()
        query = text("SELECT user_id, name FROM users")
        try:
            result = session.execute(query)
            rows = result.fetchall()
            logger.info(f"Fetched {len(rows)} users from DB")
            logger.debug(f"Raw rows: {rows}")
            users = []
            for row in rows:
                logger.debug(f"Row: {row}")
                users.append({"user_id": row[0], "name": row[1]})
            return users
        except Exception as e:
            logger.error(f"Error fetching users: {e}", exc_info=True)
            raise
        finally:
            session.close()
