"""
Flight tools updated to use PostgreSQL instead of SQLite
"""

import pandas as pd
import sqlalchemy
from datetime import date, datetime
from typing import Optional
from langchain_core.tools import tool
import pytz
from langchain_core.runnables import RunnableConfig

from sqlalchemy.orm import Session
from src.database.database import get_db_session

__all__ = [
    "fetch_user_flight_information",
    "search_flights",
    "update_ticket_to_new_flight",
    "cancel_ticket",
    "book_ticket",
    "list_available_flights",
]

# Tool: Book a new ticket (insert into tickets, ticket_flights, boarding_passes)
@tool
def book_ticket(
    flight_id: int,
    passenger_id: str = None,
    book_ref: str = None,
    fare_conditions: str = "Economy",
    amount: float = None,
    seat_no: str = None,
    boarding_no: int = None,
) -> str:
    """Book a new ticket for a user, including ticket, ticket_flights, and boarding_passes records.


    Args:
        flight_id: Flight ID to book (required)
        passenger_id: User's passenger ID (optional, auto-generate if not provided)
        book_ref: Booking reference code (optional, auto-generate if not provided)
        fare_conditions: Fare class (Economy/Business/First, default: Economy)
        amount: Ticket price (optional, auto-generate if not provided)
        seat_no: Seat assignment (optional, auto-generate if not provided)
        boarding_no: Boarding number (optional, auto-generate if not provided)

    Returns:
        A message confirming the booking or describing any error.
    """
    import random
    import string
    session: Session = get_db_session()

    # Auto-generate book_ref if not provided (6 uppercase letters/digits)
    if not book_ref:
        book_ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Auto-generate passenger_id if not provided (simulate 10-digit number with space)
    if not passenger_id:
        passenger_id = f"{random.randint(1000,9999)} {random.randint(100000,999999)}"

    # Generate a new unique ticket_no (simulate airline logic)
    ticket_no = str(random.randint(1000000000000000, 9999999999999999))

    # Auto-generate amount if not provided (simulate price)
    if amount is None:
        amount = float(random.randint(50, 500)) * 100.0

    # Auto-generate seat_no if not provided (e.g., 12A)
    if seat_no is None:
        row = random.randint(1, 40)
        seat = random.choice('ABCDEF')
        seat_no = f"{row}{seat}"

    # Auto-generate boarding_no if not provided
    if boarding_no is None:
        boarding_no = random.randint(1, 100)

    try:
        # Insert into tickets
        insert_ticket = sqlalchemy.text(
            """
            INSERT INTO tickets (ticket_no, book_ref, passenger_id)
            VALUES (:ticket_no, :book_ref, :passenger_id)
            """
        )
        session.execute(insert_ticket, {
            "ticket_no": ticket_no,
            "book_ref": book_ref,
            "passenger_id": passenger_id
        })

        # Insert into ticket_flights
        insert_ticket_flight = sqlalchemy.text(
            """
            INSERT INTO ticket_flights (ticket_no, flight_id, fare_conditions, amount)
            VALUES (:ticket_no, :flight_id, :fare_conditions, :amount)
            """
        )
        session.execute(insert_ticket_flight, {
            "ticket_no": ticket_no,
            "flight_id": flight_id,
            "fare_conditions": fare_conditions,
            "amount": amount
        })

        # Always insert into boarding_passes (auto-generated if not provided)
        insert_boarding_pass = sqlalchemy.text(
            """
            INSERT INTO boarding_passes (ticket_no, flight_id, boarding_no, seat_no)
            VALUES (:ticket_no, :flight_id, :boarding_no, :seat_no)
            """
        )
        session.execute(insert_boarding_pass, {
            "ticket_no": ticket_no,
            "flight_id": flight_id,
            "boarding_no": boarding_no,
            "seat_no": seat_no
        })

        session.commit()
        return f"Ticket booked successfully: ticket_no={ticket_no}, flight_id={flight_id}, seat_no={seat_no}"
    except Exception as e:
        session.rollback()
        return f"Error booking ticket: {e}"
    finally:
        session.close()


@tool
def fetch_user_flight_information(user_id: str) -> list[dict]:
    """Fetch all tickets for the user along with corresponding flight information and seat assignments.

    Returns:
        A list of dictionaries where each dictionary contains the ticket details,
        associated flight details, and the seat assignments for each ticket belonging to the user.
    """
    print(f"user_id:{user_id}")
    if not user_id:
        raise ValueError("No passenger ID configured.")

    session: Session = get_db_session()

    query = """
    SELECT 
        t.ticket_no, t.book_ref,
        f.flight_id, f.flight_no, f.departure_airport, f.arrival_airport, 
        f.scheduled_departure, f.scheduled_arrival,
        bp.seat_no, tf.fare_conditions
    FROM 
        tickets t
        JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
        JOIN flights f ON tf.flight_id = f.flight_id
        JOIN boarding_passes bp ON bp.ticket_no = t.ticket_no AND bp.flight_id = f.flight_id
    WHERE 
        t.passenger_id = :user_id
    """

    try:
        df = pd.read_sql(query, session.bind, params={"user_id": user_id})
        results = df.to_dict("records")
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()


@tool

def search_flights(
    departure_airport: Optional[str] = None,
    arrival_airport: Optional[str] = None,
    start_time: Optional[date | datetime] = None,
    end_time: Optional[date | datetime] = None,
    flight_no: Optional[str] = None,
    aircraft_code: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """Search for flights based on departure airport, arrival airport, flight number, aircraft code, and departure time range.

    Args:
        departure_airport: IATA code of the departure airport
        arrival_airport: IATA code of the arrival airport
        start_time: Start of the departure time range
        end_time: End of the departure time range
        flight_no: Flight number (optional, exact match)
        aircraft_code: Aircraft code (optional, exact match)
        limit: Maximum number of results to return

    Returns:
        A list of flight dictionaries matching the search criteria.
    """
    session: Session = get_db_session()

    # Build dynamic WHERE clause
    conditions = []
    params = {}

    if departure_airport:
        conditions.append("departure_airport = :departure_airport")
        params["departure_airport"] = departure_airport
    if arrival_airport:
        conditions.append("arrival_airport = :arrival_airport")
        params["arrival_airport"] = arrival_airport
    if start_time:
        conditions.append("scheduled_departure >= :start_time")
        params["start_time"] = start_time
    if end_time:
        conditions.append("scheduled_departure <= :end_time")
        params["end_time"] = end_time
    if flight_no:
        conditions.append("flight_no = :flight_no")
        params["flight_no"] = flight_no
    if aircraft_code:
        conditions.append("aircraft_code = :aircraft_code")
        params["aircraft_code"] = aircraft_code

    conditions.append("scheduled_arrival > '2025-01-01'")

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    query = f"""
    SELECT 
        flight_id, flight_no, departure_airport, arrival_airport,
        scheduled_departure, scheduled_arrival, status, aircraft_code
    FROM flights
    {where_clause}
    ORDER BY scheduled_departure
    LIMIT :limit
    """
    params["limit"] = limit

    try:
        df = pd.read_sql(sqlalchemy.text(query), session.bind, params=params)
        results = df.to_dict("records")
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()


@tool
def update_ticket_to_new_flight(ticket_no: str, new_flight_id: int) -> str:
    """Update the user's ticket to a new flight.

    Args:
        ticket_no: The ticket number to update
        new_flight_id: The ID of the new flight

    Returns:
        A message confirming the update or describing any error.
    """
    session: Session = get_db_session()

    try:
        # Kiểm tra ticket tồn tại
        ticket_check_query = (
            "SELECT ticket_no FROM tickets WHERE ticket_no = :ticket_no"
        )
        ticket_df = pd.read_sql(
            sqlalchemy.text(ticket_check_query),
            session.bind,
            params={"ticket_no": ticket_no},
        )
        if ticket_df.empty:
            return f"No ticket found with number {ticket_no}"
        # Kiểm tra flight mới tồn tại
        flight_check_query = (
            "SELECT flight_id FROM flights WHERE flight_id = :flight_id"
        )
        flight_df = pd.read_sql(
            sqlalchemy.text(flight_check_query),
            session.bind,
            params={"flight_id": new_flight_id},
        )
        if flight_df.empty:
            return f"No flight found with ID {new_flight_id}"
        # Cập nhật ticket_flights
        update_query = """
        UPDATE ticket_flights 
        SET flight_id = :new_flight_id 
        WHERE ticket_no = :ticket_no
        """
        # Execute update
        result = session.execute(
            sqlalchemy.text(update_query),
            {"new_flight_id": new_flight_id, "ticket_no": ticket_no},
        )
        session.commit()
        if result.rowcount > 0:
            return (
                f"Ticket {ticket_no} successfully updated to flight {new_flight_id}"
            )
        else:
            return f"No ticket_flights record found for ticket {ticket_no}"
    except Exception as e:
        session.rollback()
        return f"Error updating ticket: {e}"
    finally:
        session.close()


@tool
def cancel_ticket(ticket_no: str) -> str:
    """Cancel a user's ticket and remove it from the system.

    Args:
        ticket_no: The ticket number to cancel

    Returns:
        A message confirming the cancellation or describing any error.
    """
    session: Session = get_db_session()

    try:
        # Kiểm tra ticket tồn tại
        ticket_check_query = (
            "SELECT ticket_no FROM tickets WHERE ticket_no = :ticket_no"
        )
        ticket_df = pd.read_sql(
            sqlalchemy.text(ticket_check_query), session.bind, params={"ticket_no": ticket_no}
        )
        if ticket_df.empty:
            return f"No ticket found with number {ticket_no}"
        # Xóa boarding passes trước (foreign key constraint)
        delete_bp_query = "DELETE FROM boarding_passes WHERE ticket_no = :ticket_no"
        session.execute(sqlalchemy.text(delete_bp_query), {"ticket_no": ticket_no})
        # Xóa ticket_flights
        delete_tf_query = "DELETE FROM ticket_flights WHERE ticket_no = :ticket_no"
        session.execute(sqlalchemy.text(delete_tf_query), {"ticket_no": ticket_no})
        # Xóa ticket
        delete_ticket_query = "DELETE FROM tickets WHERE ticket_no = :ticket_no"
        result = session.execute(
            sqlalchemy.text(delete_ticket_query), {"ticket_no": ticket_no}
        )
        session.commit()
        if result.rowcount > 0:
            return f"Ticket {ticket_no} successfully cancelled"
        else:
            return f"Failed to cancel ticket {ticket_no}"
    except Exception as e:
        session.rollback()
        return f"Error cancelling ticket: {e}"
    finally:
        session.close()


@tool
def list_available_flights(limit: int = 50) -> list[dict]:
    """List available flights with a departure time after.

    Args:
        limit: The maximum number of flights to return (default: 50).
    Returns:
        A list of flight dictionaries.
    """
    session: Session = get_db_session()
    query = """
    SELECT flight_id, flight_no, scheduled_departure, scheduled_arrival, departure_airport, arrival_airport, status, aircraft_code
    FROM flights
    WHERE scheduled_departure > '2025-01-01'
    ORDER BY scheduled_departure
    LIMIT :limit
    """
    try:
        df = pd.read_sql(sqlalchemy.text(query), session.bind, params={"limit": limit})
        results = df.to_dict("records")
        return results
    except Exception as e:
        raise Exception(f"Database error: {e}")
    finally:
        session.close()
