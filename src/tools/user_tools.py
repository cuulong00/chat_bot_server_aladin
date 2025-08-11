from langchain_core.tools import tool
from pydantic import BaseModel, Field
import pandas as pd
from sqlalchemy.orm import Session
from src.database.database import get_db_session


class GetUserInfoInput(BaseModel):
    """Input for the get_user_info tool."""

    user_id: str = Field(description="The unique identifier for the user.")


@tool("get_user_info", args_schema=GetUserInfoInput)
def get_user_info(user_id: str) -> dict:
    """
    Retrieves basic information for a given user from the database.
    Args:
        user_id: The unique identifier for the user.
    Returns:
        A dictionary containing the user's information (user_id, name, email, phone, address)
        or an error message if the user is not found.
    """
    session: Session = get_db_session()
    try:
        query = "SELECT user_id, name, email, phone, address FROM users WHERE user_id = %(user_id)s"
        result = pd.read_sql(query, session.bind, params={"user_id": user_id})
        if not result.empty:
            user_data = result.to_dict(orient="records")[0]
            return user_data
        else:
            return {"error": f"User with ID '{user_id}' not found."}
    except Exception as e:
        # Rollback the transaction in case of error
        try:
            session.rollback()
        except Exception:
            pass  # If rollback fails, ignore it
        return {"error": f"An error occurred while fetching user information: {e}"}
    finally:
        session.close()


# Tool: get_user_by_email
class GetUserByEmailInput(BaseModel):
    email: str = Field(description="The email address of the user.")


@tool("get_user_by_email", args_schema=GetUserByEmailInput)
def get_user_by_email(email: str) -> dict:
    """
    Retrieve user info by email.
    """
    session: Session = get_db_session()
    try:
        query = "SELECT user_id, name, email, phone, address FROM users WHERE email = %(email)s"
        result = pd.read_sql(query, session.bind, params={"email": email})
        if not result.empty:
            return result.to_dict(orient="records")[0]
        else:
            return {"error": f"User with email '{email}' not found."}
    except Exception as e:
        # Rollback the transaction in case of error
        try:
            session.rollback()
        except Exception:
            pass  # If rollback fails, ignore it
        return {"error": f"An error occurred while fetching user by email: {e}"}
    finally:
        session.close()


# Tool: get_user_by_phone
class GetUserByPhoneInput(BaseModel):
    phone: str = Field(description="The phone number of the user.")


@tool("get_user_by_phone", args_schema=GetUserByPhoneInput)
def get_user_by_phone(phone: str) -> dict:
    """
    Retrieve user info by phone number.
    """
    session: Session = get_db_session()
    try:
        query = "SELECT user_id, name, email, phone, address FROM users WHERE phone = %(phone)s"
        result = pd.read_sql(query, session.bind, params={"phone": phone})
        if not result.empty:
            return result.to_dict(orient="records")[0]
        else:
            return {"error": f"User with phone '{phone}' not found."}
    except Exception as e:
        # Rollback the transaction in case of error
        try:
            session.rollback()
        except Exception:
            pass  # If rollback fails, ignore it
        return {"error": f"An error occurred while fetching user by phone: {e}"}
    finally:
        session.close()


# Tool: list_users (for admin/debug)
@tool("list_users")
def list_users() -> list:
    """
    List all users (for admin/debug only).
    """
    session: Session = get_db_session()
    try:
        query = "SELECT user_id, name, email, phone, address FROM users LIMIT 100"
        result = pd.read_sql(query, session.bind)
        return result.to_dict(orient="records")
    except Exception as e:
        return {"error": f"An error occurred while listing users: {e}"}
    finally:
        session.close()


# Tool: get_latest_thread_id_by_user
class GetLatestThreadIdInput(BaseModel):
    user_id: str = Field(description="The unique identifier for the user.")


@tool("get_latest_thread_id_by_user", args_schema=GetLatestThreadIdInput)
def get_latest_thread_id_by_user(user_id: str) -> dict:
    """
    Lấy thread_id gần nhất của user dựa vào bảng user_threads (theo created_at mới nhất).
    """
    session: Session = get_db_session()
    try:
        query = """
            SELECT thread_id FROM user_threads
            WHERE user_id = %(user_id)s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """
        result = pd.read_sql(query, session.bind, params={"user_id": user_id})
        if not result.empty:
            return {"thread_id": result.iloc[0]["thread_id"]}
        else:
            return None
    except Exception as e:
        # Rollback the transaction in case of error
        try:
            session.rollback()
        except Exception:
            pass  # If rollback fails, ignore it
        return None
    finally:
        session.close()
