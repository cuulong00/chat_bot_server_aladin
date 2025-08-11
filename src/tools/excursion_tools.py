from langchain_core.tools import tool
import pandas as pd
import sqlalchemy
from typing import Optional

from sqlalchemy.orm import Session
from src.database.database import get_db_session

__all__ = [
    "search_trip_recommendations",
    "book_excursion",
    "update_excursion", 
    "cancel_excursion",
]


@tool
def search_trip_recommendations(
    location: Optional[str] = None,
    name: Optional[str] = None,
    keywords: Optional[str] = None,
) -> list[dict]:
    """
    Search for trip recommendations based on location, name, and keywords.

    Args:
        location (Optional[str]): The location of the trip recommendation. Defaults to None.
        name (Optional[str]): The name of the trip recommendation. Defaults to None.
        keywords (Optional[str]): The keywords associated with the trip recommendation. Defaults to None.

    Returns:
        list[dict]: A list of trip recommendation dictionaries matching the search criteria.
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
    if keywords:
        keyword_list = [k.strip() for k in keywords.split(",")]
        keyword_conditions = []
        for i, keyword in enumerate(keyword_list):
            param_name = f"keyword_{i}"
            keyword_conditions.append(f"keywords ILIKE :{param_name}")
            params[param_name] = f"%{keyword}%"
        if keyword_conditions:
            conditions.append(f"({' OR '.join(keyword_conditions)})")
    where_clause = " AND ".join(conditions)
    query = f"SELECT * FROM trip_recommendations WHERE {where_clause}"
    try:
        df = pd.read_sql(query, session.bind, params=params)
        results = df.to_dict('records')
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()


@tool
def book_excursion(recommendation_id: int) -> str:
    """
    Book a trip recommendation by its ID.

    Args:
        recommendation_id (int): The ID of the trip recommendation to book.

    Returns:
        str: A message indicating whether the trip recommendation was successfully booked or not.
    """
    session: Session = get_db_session()
    try:
        # Check if excursion exists
        check_query = "SELECT id FROM trip_recommendations WHERE id = :recommendation_id"
        check_df = pd.read_sql(check_query, session.bind, params={"recommendation_id": recommendation_id})
        if check_df.empty:
            return f"No trip recommendation found with ID {recommendation_id}."
        # Update booking status
        update_query = "UPDATE trip_recommendations SET booked = 1 WHERE id = :recommendation_id"
        result = session.execute(
            sqlalchemy.text(update_query),
            {"recommendation_id": recommendation_id}
        )
        session.commit()
        if result.rowcount > 0:
            return f"Trip recommendation {recommendation_id} successfully booked."
        else:
            return f"Failed to book trip recommendation {recommendation_id}."
    except Exception as e:
        session.rollback()
        return f"Error booking trip recommendation: {e}"
    finally:
        session.close()


@tool
def update_excursion(
    recommendation_id: int,
    location: Optional[str] = None,
    name: Optional[str] = None,
    keywords: Optional[str] = None,
) -> str:
    """
    Update a trip recommendation's details by its ID.

    Args:
        recommendation_id (int): The ID of the trip recommendation to update.
        location (Optional[str]): The new location of the trip recommendation. Defaults to None.
        name (Optional[str]): The new name of the trip recommendation. Defaults to None.
        keywords (Optional[str]): The new keywords for the trip recommendation. Defaults to None.

    Returns:
        str: A message indicating whether the trip recommendation was successfully updated or not.
    """
    session: Session = get_db_session()
    try:
        # Check if excursion exists
        check_query = "SELECT id FROM trip_recommendations WHERE id = :recommendation_id"
        check_df = pd.read_sql(check_query, session.bind, params={"recommendation_id": recommendation_id})
        if check_df.empty:
            return f"No trip recommendation found with ID {recommendation_id}."
        updated = False
        if location:
            update_query = "UPDATE trip_recommendations SET location = :location WHERE id = :recommendation_id"
            result = session.execute(
                sqlalchemy.text(update_query),
                {"location": location, "recommendation_id": recommendation_id}
            )
            if result.rowcount > 0:
                updated = True
        if name:
            update_query = "UPDATE trip_recommendations SET name = :name WHERE id = :recommendation_id"
            result = session.execute(
                sqlalchemy.text(update_query),
                {"name": name, "recommendation_id": recommendation_id}
            )
            if result.rowcount > 0:
                updated = True
        if keywords:
            update_query = "UPDATE trip_recommendations SET keywords = :keywords WHERE id = :recommendation_id"
            result = session.execute(
                sqlalchemy.text(update_query),
                {"keywords": keywords, "recommendation_id": recommendation_id}
            )
            if result.rowcount > 0:
                updated = True
        session.commit()
        if updated:
            return f"Trip recommendation {recommendation_id} successfully updated."
        else:
            return f"No updates made to trip recommendation {recommendation_id}."
    except Exception as e:
        session.rollback()
        return f"Error updating trip recommendation: {e}"
    finally:
        session.close()


@tool
def cancel_excursion(recommendation_id: int) -> str:
    """
    Cancel a trip recommendation booking by its ID.

    Args:
        recommendation_id (int): The ID of the trip recommendation to cancel.

    Returns:
        str: A message indicating whether the trip recommendation was successfully cancelled or not.
    """
    session: Session = get_db_session()
    try:
        # Check if excursion exists
        check_query = "SELECT id FROM trip_recommendations WHERE id = :recommendation_id"
        check_df = pd.read_sql(check_query, session.bind, params={"recommendation_id": recommendation_id})
        if check_df.empty:
            return f"No trip recommendation found with ID {recommendation_id}."
        # Cancel booking
        update_query = "UPDATE trip_recommendations SET booked = 0 WHERE id = :recommendation_id"
        result = session.execute(
            sqlalchemy.text(update_query),
            {"recommendation_id": recommendation_id}
        )
        session.commit()
        if result.rowcount > 0:
            return f"Trip recommendation {recommendation_id} successfully cancelled."
        else:
            return f"Failed to cancel trip recommendation {recommendation_id}."
    except Exception as e:
        session.rollback()
        return f"Error cancelling trip recommendation: {e}"
    finally:
        session.close()
