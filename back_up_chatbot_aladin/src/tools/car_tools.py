from datetime import date, datetime
from typing import Optional, Union
from langchain_core.tools import tool
import pandas as pd
import sqlalchemy


from sqlalchemy.orm import Session
from src.database.database import get_db_session

__all__ = [
    "search_car_rentals",
    "book_car_rental",
    "update_car_rental",
    "cancel_car_rental",
]


@tool
def search_car_rentals(
    location: Optional[str] = None,
    name: Optional[str] = None,
    price_tier: Optional[str] = None,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> list[dict]:
    """
    Search for car rentals based on location, name, price tier, start date, and end date.

    Args:
        location (Optional[str]): The location of the car rental. Defaults to None.
        name (Optional[str]): The name of the car rental company. Defaults to None.
        price_tier (Optional[str]): The price tier of the car rental. Defaults to None.
        start_date (Optional[Union[datetime, date]]): The start date of the car rental. Defaults to None.
        end_date (Optional[Union[datetime, date]]): The end date of the car rental. Defaults to None.

    Returns:
        list[dict]: A list of car rental dictionaries matching the search criteria.
    """
    session: Session = get_db_session()
    # Build dynamic WHERE clause
    conditions = ["1=1"]
    params = {}
    if location:
        conditions.append("location ILIKE :location")
        params["location"] = f"%{location}%"
    if name:
        conditions.append("name ILIKE :name")
        params["name"] = f"%{name}%"
    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM car_rentals WHERE {where_clause}"
    try:
        df = pd.read_sql(query, session.bind, params=params)
        results = df.to_dict('records')
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()


@tool
def book_car_rental(rental_id: int) -> str:
    """
    Book a car rental by its ID.

    Args:
        rental_id (int): The ID of the car rental to book.

    Returns:
        str: A message indicating whether the car rental was successfully booked or not.
    """
    session: Session = get_db_session()
    try:
        # Check if rental exists
        check_query = "SELECT id FROM car_rentals WHERE id = :rental_id"
        check_df = pd.read_sql(check_query, session.bind, params={"rental_id": rental_id})
        if check_df.empty:
            return f"No car rental found with ID {rental_id}."
        # Update booking status
        update_query = "UPDATE car_rentals SET booked = 1 WHERE id = :rental_id"
        result = session.execute(
            sqlalchemy.text(update_query),
            {"rental_id": rental_id}
        )
        session.commit()
        if result.rowcount > 0:
            return f"Car rental {rental_id} successfully booked."
        else:
            return f"Failed to book car rental {rental_id}."
    except Exception as e:
        session.rollback()
        return f"Error booking car rental: {e}"
    finally:
        session.close()


@tool
def update_car_rental(
    rental_id: int,
    start_date: Optional[Union[datetime, date]] = None,
    end_date: Optional[Union[datetime, date]] = None,
) -> str:
    """
    Update a car rental's start and end dates by its ID.

    Args:
        rental_id (int): The ID of the car rental to update.
        start_date (Optional[Union[datetime, date]]): The new start date of the car rental. Defaults to None.
        end_date (Optional[Union[datetime, date]]): The new end date of the car rental. Defaults to None.

    Returns:
        str: A message indicating whether the car rental was successfully updated or not.
    """
    session: Session = get_db_session()
    try:
        # Check if rental exists
        check_query = "SELECT id FROM car_rentals WHERE id = :rental_id"
        check_df = pd.read_sql(check_query, session.bind, params={"rental_id": rental_id})
        if check_df.empty:
            return f"No car rental found with ID {rental_id}."
        updated = False
        if start_date:
            update_query = "UPDATE car_rentals SET start_date = :start_date WHERE id = :rental_id"
            result = session.execute(
                sqlalchemy.text(update_query),
                {"start_date": start_date, "rental_id": rental_id}
            )
            if result.rowcount > 0:
                updated = True
        if end_date:
            update_query = "UPDATE car_rentals SET end_date = :end_date WHERE id = :rental_id"
            result = session.execute(
                sqlalchemy.text(update_query),
                {"end_date": end_date, "rental_id": rental_id}
            )
            if result.rowcount > 0:
                updated = True
        session.commit()
        if updated:
            return f"Car rental {rental_id} successfully updated."
        else:
            return f"No updates made to car rental {rental_id}."
    except Exception as e:
        session.rollback()
        return f"Error updating car rental: {e}"
    finally:
        session.close()


@tool
def cancel_car_rental(rental_id: int) -> str:
    """
    Cancel a car rental by its ID.

    Args:
        rental_id (int): The ID of the car rental to cancel.

    Returns:
        str: A message indicating whether the car rental was successfully cancelled or not.
    """
    session: Session = get_db_session()
    try:
        # Check if rental exists
        check_query = "SELECT id FROM car_rentals WHERE id = :rental_id"
        check_df = pd.read_sql(check_query, session.bind, params={"rental_id": rental_id})
        if check_df.empty:
            return f"No car rental found with ID {rental_id}."
        # Cancel booking
        update_query = "UPDATE car_rentals SET booked = 0 WHERE id = :rental_id"
        result = session.execute(
            sqlalchemy.text(update_query),
            {"rental_id": rental_id}
        )
        session.commit()
        if result.rowcount > 0:
            return f"Car rental {rental_id} successfully cancelled."
        else:
            return f"Failed to cancel car rental {rental_id}."
    except Exception as e:
        session.rollback()
        return f"Error cancelling car rental: {e}"
    finally:
        session.close()
