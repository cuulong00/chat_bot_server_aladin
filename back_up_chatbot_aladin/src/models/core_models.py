from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, UniqueConstraint, Index, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from src.models.base import Base

class AircraftData(Base):
    __tablename__ = "aircrafts_data"
    aircraft_code = Column(Text, primary_key=True)
    model = Column(Text)
    range = Column(BigInteger)

class AirportData(Base):
    __tablename__ = "airports_data"
    airport_code = Column(Text, primary_key=True)
    airport_name = Column(Text)
    city = Column(Text)
    coordinates = Column(Text)
    timezone = Column(Text)

class BoardingPass(Base):
    __tablename__ = "boarding_passes"
    ticket_no = Column(Text, primary_key=True)
    flight_id = Column(BigInteger, primary_key=True)
    boarding_no = Column(BigInteger)
    seat_no = Column(Text)

class Booking(Base):
    __tablename__ = "bookings"
    book_ref = Column(Text, primary_key=True)
    book_date = Column(DateTime(timezone=True))
    total_amount = Column(BigInteger)

class CarRental(Base):
    __tablename__ = "car_rentals"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    location = Column(Text)
    price_tier = Column(Text)
    start_date = Column(Text)
    end_date = Column(Text)
    booked = Column(BigInteger)

class Flight(Base):
    __tablename__ = "flights"
    flight_id = Column(BigInteger, primary_key=True)
    flight_no = Column(Text)
    scheduled_departure = Column(DateTime(timezone=True))
    scheduled_arrival = Column(DateTime(timezone=True))
    departure_airport = Column(Text)
    arrival_airport = Column(Text)
    status = Column(Text)
    aircraft_code = Column(Text)
    actual_departure = Column(DateTime(timezone=True))
    actual_arrival = Column(DateTime(timezone=True))

class Hotel(Base):
    __tablename__ = "hotels"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    location = Column(Text)
    price_tier = Column(Text)
    checkin_date = Column(Text)
    checkout_date = Column(Text)
    booked = Column(BigInteger)

class Seat(Base):
    __tablename__ = "seats"
    aircraft_code = Column(Text, primary_key=True)
    seat_no = Column(Text, primary_key=True)
    fare_conditions = Column(Text)

class Store(Base):
    __tablename__ = "store"
    prefix = Column(Text, primary_key=True)
    key = Column(Text, primary_key=True)
    value = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    ttl_minutes = Column(Integer)

class TicketFlight(Base):
    __tablename__ = "ticket_flights"
    ticket_no = Column(Text, primary_key=True)
    flight_id = Column(BigInteger, primary_key=True)
    fare_conditions = Column(Text)
    amount = Column(BigInteger)

class Ticket(Base):
    __tablename__ = "tickets"
    ticket_no = Column(Text, primary_key=True)
    book_ref = Column(Text)
    passenger_id = Column(Text)

class TripRecommendation(Base):
    __tablename__ = "trip_recommendations"
    id = Column(BigInteger, primary_key=True)
    name = Column(Text)
    location = Column(Text)
    keywords = Column(Text)
    details = Column(Text)
    booked = Column(BigInteger)

class UserThread(Base):
    __tablename__ = "user_threads"
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, nullable=False)
    thread_id = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'thread_id', name='user_threads_user_id_thread_id_key'),
        Index('idx_user_threads_composite', 'user_id', 'thread_id'),
        Index('idx_user_threads_thread_id', 'thread_id'),
        Index('idx_user_threads_user_id', 'user_id'),
    )

class UserTicket(Base):
    __tablename__ = "user_tickets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Text, nullable=False)
    ticket_no = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now())
    __table_args__ = (
        UniqueConstraint('user_id', 'ticket_no', name='unique_user_ticket'),
        Index('idx_user_tickets_composite', 'user_id', 'ticket_no'),
        Index('idx_user_tickets_ticket_no', 'ticket_no'),
        Index('idx_user_tickets_user_id', 'user_id'),
    )
