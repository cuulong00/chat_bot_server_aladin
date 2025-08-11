from langchain_core.tools import tool
import pandas as pd
import sqlalchemy
from typing import Optional, Union
from datetime import datetime, date

from sqlalchemy.orm import Session
from src.database.database import get_db_session

__all__ = [
    "search_hotels",
    "book_hotel", 
    "update_hotel",
    "cancel_hotel",
]

@tool
def search_hotels(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """
    Search for hotels based on location, name, price tier, check-in and check-out dates.

    Args:
        location (Optional[str]): The location of the hotel. Defaults to None.
        name (Optional[str]): The name of the hotel. Defaults to None.
        price_tier (Optional[str]): The price tier of the hotel. Defaults to None.
        checkin_date (Optional[Union[datetime, date]]): The check-in date. Defaults to None.
        checkout_date (Optional[Union[datetime, date]]): The check-out date. Defaults to None.

    Returns:
        list[dict]: A list of hotel dictionaries matching the search criteria.
    """
    session: Session = get_db_session()
    conditions = ["1=1"]
    params = {}
    if location:
        conditions.append("location ILIKE :location")
        params["location"] = f"%{location}%"
    if name:
        conditions.append("name ILIKE :name")
        params["name"] = f"%{name}%"
    if price_tier:
        conditions.append("price_tier = :price_tier")
        params["price_tier"] = price_tier
    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM hotels WHERE {where_clause}"
    try:
        df = pd.read_sql(sqlalchemy.text(query), session.bind, params=params)
        results = df.to_dict('records')
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()

@tool
def book_hotel(hotel_id: int) -> str:
    """
    Book a hotel by its ID.

    Args:
        hotel_id (int): The ID of the hotel to book.

    Returns:
        str: A message indicating whether the hotel was successfully booked or not.
    """
    session: Session = get_db_session()
    try:
        check_query = "SELECT id FROM hotels WHERE id = :hotel_id"
        check_df = pd.read_sql(sqlalchemy.text(check_query), session.bind, params={"hotel_id": hotel_id})
        if check_df.empty:
            return f"No hotel found with ID {hotel_id}."
        update_query = "UPDATE hotels SET booked = 1 WHERE id = :hotel_id"
        result = session.execute(sqlalchemy.text(update_query), {"hotel_id": hotel_id})
        session.commit()
        if result.rowcount > 0:
            return f"Hotel {hotel_id} successfully booked."
        else:
            return f"Failed to book hotel {hotel_id}."
    except Exception as e:
        session.rollback()
        return f"Error booking hotel: {e}"
    finally:
        session.close()

@tool
def update_hotel(
    hotel_id: int,
    checkin_date: Optional[Union[datetime, date]] = None,
    checkout_date: Optional[Union[datetime, date]] = None,
) -> str:
    """
    Update a hotel's check-in and check-out dates by its ID.

    Args:
        hotel_id (int): The ID of the hotel to update.
        checkin_date (Optional[Union[datetime, date]]): The new check-in date. Defaults to None.
        checkout_date (Optional[Union[datetime, date]]): The new check-out date. Defaults to None.

    Returns:
        str: A message indicating whether the hotel was successfully updated or not.
    """
    session: Session = get_db_session()
    try:
        check_query = "SELECT id FROM hotels WHERE id = :hotel_id"
        check_df = pd.read_sql(sqlalchemy.text(check_query), session.bind, params={"hotel_id": hotel_id})
        if check_df.empty:
            return f"No hotel found with ID {hotel_id}."
        updated = False
        if checkin_date:
            update_query = "UPDATE hotels SET checkin_date = :checkin_date WHERE id = :hotel_id"
            result = session.execute(sqlalchemy.text(update_query), {"checkin_date": checkin_date, "hotel_id": hotel_id})
            if result.rowcount > 0:
                updated = True
        if checkout_date:
            update_query = "UPDATE hotels SET checkout_date = :checkout_date WHERE id = :hotel_id"
            result = session.execute(sqlalchemy.text(update_query), {"checkout_date": checkout_date, "hotel_id": hotel_id})
            if result.rowcount > 0:
                updated = True
        session.commit()
        if updated:
            return f"Hotel {hotel_id} successfully updated."
        else:
            return f"No updates made to hotel {hotel_id}."
    except Exception as e:
        session.rollback()
        return f"Error updating hotel: {e}"
    finally:
        session.close()

@tool
def cancel_hotel(hotel_id: int) -> str:
    """
    Cancel a hotel booking by its ID.

    Args:
        hotel_id (int): The ID of the hotel to cancel.

    Returns:
        str: A message indicating whether the hotel was successfully cancelled or not.
    """
    session: Session = get_db_session()
    try:
        check_query = "SELECT id FROM hotels WHERE id = :hotel_id"
        check_df = pd.read_sql(sqlalchemy.text(check_query), session.bind, params={"hotel_id": hotel_id})
        if check_df.empty:
            return f"No hotel found with ID {hotel_id}."
        update_query = "UPDATE hotels SET booked = 0 WHERE id = :hotel_id"
        result = session.execute(sqlalchemy.text(update_query), {"hotel_id": hotel_id})
        session.commit()
        if result.rowcount > 0:
            return f"Hotel {hotel_id} successfully cancelled."
        else:
            return f"Failed to cancel hotel {hotel_id}."
    except Exception as e:
        session.rollback()
        return f"Error cancelling hotel: {e}"
    finally:
        session.close()