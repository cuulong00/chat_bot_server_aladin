import logging
from typing import Optional, Dict, Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database.database import get_db_session

logger = logging.getLogger(__name__)


class UserFacebookRepository:
    """
    Repository for minimal Facebook users table operations.
    Table schema expected:
        CREATE TABLE user_facebook (
            user_id VARCHAR(32) PRIMARY KEY NOT NULL,
            name VARCHAR(255),
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(20)
        );
    """

    @staticmethod
    def get_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        session: Session = get_db_session()
        try:
            row = session.execute(
                text("SELECT user_id, name, email, phone FROM user_facebook WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchone()
            if not row:
                return None
            return {
                "user_id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
            }
        except Exception as e:  # noqa: BLE001
            logger.error("Error querying user_facebook by id: %s", e, exc_info=True)
            return None
        finally:
            session.close()

    @staticmethod
    def ensure_user(user_id: str, name: Optional[str] = None, email: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Ensure a user row exists. If new, insert minimal record. If exists and any new
        non-empty fields provided, update missing ones.
        Portable approach (works beyond Postgres): SELECT then INSERT/UPDATE.
        """
        session: Session = get_db_session()
        try:
            existing = session.execute(
                text("SELECT user_id, name, email, phone FROM user_facebook WHERE user_id = :uid"),
                {"uid": user_id},
            ).fetchone()

            if existing is None:
                session.execute(
                    text(
                        """
                        INSERT INTO user_facebook (user_id, name, email, phone)
                        VALUES (:uid, :name, :email, :phone)
                        """
                    ),
                    {
                        "uid": user_id,
                        "name": name,
                        "email": email,
                        "phone": phone,
                    },
                )
                session.commit()
                logger.info("Inserted new user_facebook row: %s", user_id)
                return {"user_id": user_id, "name": name, "email": email, "phone": phone}

            # Update fields if new values are provided and existing is null/empty
            updates = {}
            if name and (existing[1] is None or existing[1] == ""):
                updates["name"] = name
            if email and (existing[2] is None or existing[2] == ""):
                updates["email"] = email
            if phone and (existing[3] is None or existing[3] == ""):
                updates["phone"] = phone

            if updates:
                set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
                params = {"uid": user_id, **updates}
                session.execute(text(f"UPDATE user_facebook SET {set_clause} WHERE user_id = :uid"), params)
                session.commit()
                logger.info("Updated user_facebook row: %s with %s", user_id, list(updates.keys()))

            return {
                "user_id": user_id,
                "name": updates.get("name", existing[1]),
                "email": updates.get("email", existing[2]),
                "phone": updates.get("phone", existing[3]),
            }
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error("Error ensuring user_facebook: %s", e, exc_info=True)
            raise
        finally:
            session.close()
