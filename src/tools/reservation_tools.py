from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from langchain_core.tools import tool
import requests
import os
import logging
from datetime import datetime, date
from pathlib import Path
import uuid
import json

# Import vector database for restaurant search
try:
    from src.database.qdrant_store import qdrant_store
except ImportError:
    qdrant_store = None

logger = logging.getLogger(__name__)

# Configuration
RESERVATION_API_BASE = os.getenv("RESERVATION_API_BASE", "http://192.168.10.136:2108")
RESERVATION_API_KEY = os.getenv("RESERVATION_API_KEY", "8b63f9534aee46f86bfb370b4681a20a")
REQUEST_TIMEOUT = int(os.getenv("RESERVATION_TIMEOUT", "30"))

# Restaurant lookup is now handled exclusively through vector database
# No hardcoded mapping - all restaurant data comes from embedded restaurant information

class RestaurantLookupInput(BaseModel):
    """Input for restaurant lookup by name or address"""
    location_query: str = Field(..., description="Restaurant branch name or address for searching restaurant_id")

class ReservationInput(BaseModel):
    """Pydantic model for table reservation input validation"""
    restaurant_location: str = Field(..., description="Restaurant branch name or address")
    first_name: str = Field(..., description="Customer first name")
    last_name: str = Field(..., description="Customer last name")
    phone: str = Field(..., description="Customer phone number")
    email: Optional[str] = Field(None, description="Customer email (optional)")
    dob: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    reservation_date: str = Field(..., description="Reservation date (YYYY-MM-DD)")
    start_time: str = Field(..., description="Start time (HH:MM)")
    end_time: Optional[str] = Field(None, description="End time (HH:MM, optional)")
    amount_adult: int = Field(..., ge=1, description="Number of adults")
    amount_children: int = Field(default=0, ge=0, description="Number of children")
    note: Optional[str] = Field(None, description="Reservation note")
    has_birthday: bool = Field(default=False, description="Is it a birthday celebration")

    @validator('phone')
    def validate_phone(cls, v):
        # Basic Vietnamese phone validation
        if not v or len(v) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        # Remove spaces and special characters
        cleaned_phone = ''.join(filter(str.isdigit, v))
        if len(cleaned_phone) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return cleaned_phone

    @validator('reservation_date')
    def validate_date(cls, v):
        try:
            parsed_date = datetime.strptime(v, '%Y-%m-%d').date()
            if parsed_date < date.today():
                raise ValueError("Reservation date cannot be in the past")
            return v
        except ValueError as e:
            raise ValueError(f"Invalid date format (YYYY-MM-DD): {e}")

    @validator('start_time')
    def validate_time(cls, v):
        try:
            datetime.strptime(v, '%H:%M')
            return v
        except ValueError:
            raise ValueError("Invalid time format (HH:MM)")

def _get_headers() -> Dict[str, str]:
    """Get API headers with authentication"""
    return {
        "Content-Type": "application/json",
        "X-Api-Key": RESERVATION_API_KEY
    }

def _find_restaurant_id(location_query: str) -> Optional[str]:
    """
    Find restaurant ID by location query using semantic search in vector database.
    Returns None if no restaurant is found.
    """
    try:
        # Create a restaurant-specific store with correct model for restaurant collection
        # Use text-embedding-004 model to match existing collection dimension (768)
        from src.database.qdrant_store import QdrantStore
        restaurant_store = QdrantStore(
            embedding_model="text-embedding-004",  # Use text-embedding-004 to match collection
            output_dimensionality_query=768,  # Match the dimension in existing collection
            collection_name="restaurants"
        )
        
        search_results = restaurant_store.search(
            namespace="restaurants", 
            query=location_query, 
            limit=3
        )
        
        if search_results:
            # Get the best match (highest score)
            best_match = search_results[0]
            key, value, score = best_match
            
            # Extract restaurant_id from the result
            if isinstance(value, dict):
                restaurant_id = value.get('restaurant_id')
                if restaurant_id:
                    logger.info(f"Found restaurant_id {restaurant_id} for location '{location_query}' with confidence {score:.2f}")
                    return str(restaurant_id)
                
                # Try to extract from metadata if restaurant_id not directly available
                metadata_id = value.get('id')
                if metadata_id:
                    logger.info(f"Found restaurant via metadata ID {metadata_id} for location '{location_query}' with confidence {score:.2f}")
                    return str(metadata_id)
        
        logger.warning(f"No restaurant found for location query: '{location_query}'")
        return None
        
    except Exception as e:
        logger.error(f"Error during vector search for restaurant: {e}")
        return None

def _handle_api_response(response: requests.Response) -> Dict[str, Any]:
    """Handle API response with proper error handling"""
    try:
        response.raise_for_status()
        response_data = response.json()
        return {
            "success": True,
            "data": response_data,
            "message": "Table reservation successful!"
        }
    except requests.exceptions.HTTPError as e:
        logger.error(f"API HTTP Error: {e}, Response: {response.text}")
        error_detail = ""
        try:
            error_json = response.json()
            error_detail = error_json.get("message", "")
        except:
            pass
        
        return {
            "success": False,
            "error": f"API Error: {response.status_code}",
            "error_detail": error_detail,
            "message": "An error occurred while making the reservation. Please try again later or call hotline 1900 636 886."
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"API Request Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Cannot connect to reservation system. Please try again later or call hotline 1900 636 886."
        }
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error: {e}")
        return {
            "success": False,
            "error": "Invalid JSON response",
            "message": "Invalid response from system. Please contact hotline 1900 636 886."
        }

@tool("lookup_restaurant_by_location", args_schema=RestaurantLookupInput)
def lookup_restaurant_by_location(location_query: str) -> Dict[str, Any]:
    """
    Find restaurant_id based on branch name or address.
    
    This tool helps identify the correct restaurant_id for use in the reservation API.
    """
    try:
        restaurant_id = _find_restaurant_id(location_query)
        
        if restaurant_id is None:
            return {
                "success": False,
                "data": {
                    "restaurant_id": None,
                    "location_query": location_query,
                    "found": False
                },
                "message": f"No restaurant found for location: {location_query}. Please check the location name or try a different search term."
            }
        
        # Get restaurant info from vector database
        restaurant_info = {
            "restaurant_id": restaurant_id,
            "location_query": location_query,
            "found": True
        }
        
        return {
            "success": True,
            "data": restaurant_info,
            "message": f"Found restaurant with ID: {restaurant_id}"
        }
    except Exception as e:
        logger.error(f"Error in lookup_restaurant_by_location: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Error occurred while searching restaurant information."
        }

@tool("book_table_reservation", args_schema=ReservationInput)
def book_table_reservation(
    restaurant_location: str,
    first_name: str,
    last_name: str,
    phone: str,
    reservation_date: str,
    start_time: str,
    amount_adult: int,
    email: Optional[str] = None,
    dob: Optional[str] = None,
    end_time: Optional[str] = None,
    amount_children: int = 0,
    note: Optional[str] = None,
    has_birthday: bool = False
) -> Dict[str, Any]:
    """
    Book a table at Tian Long Restaurant.
    
    This tool performs table reservation with complete customer information.
    Automatically finds restaurant_id based on location and calls the reservation API.
    """
    try:
        # Validate input using Pydantic model
        reservation_data = ReservationInput(
            restaurant_location=restaurant_location,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            dob=dob,
            reservation_date=reservation_date,
            start_time=start_time,
            end_time=end_time,
            amount_adult=amount_adult,
            amount_children=amount_children,
            note=note,
            has_birthday=has_birthday
        )
        print(f"book_table_reservation->reservation_data:{reservation_data}")
        # Find restaurant ID
        restaurant_id = _find_restaurant_id(restaurant_location)
        
        if restaurant_id is None:
            return {
                "success": False,
                "error": "Restaurant not found",
                "message": f"Cannot find restaurant for location '{restaurant_location}'. Please check the location name and try again, or contact hotline 1900 636 886 for assistance."
            }
        
        # Calculate total guests
        total_guests = amount_adult + amount_children
        
        # Default end time if not provided (3 hours later)
        if not end_time:
            try:
                start_dt = datetime.strptime(start_time, '%H:%M')
                end_hour = (start_dt.hour + 3) % 24
                end_dt = start_dt.replace(hour=end_hour)
                end_time = end_dt.strftime('%H:%M')
            except:
                end_time = "22:00"  # Default fallback

        # Generate email if not provided
        if not email:
            email = f"{phone}@tianlong.placeholder"

        # Prepare API payload according to the specification
        payload = {
            "restaurant_id": restaurant_id,
            "first_name": reservation_data.first_name,
            "last_name": reservation_data.last_name,
            "phone": reservation_data.phone,
            "email": email,
            "dob": reservation_data.dob or "1990-01-01",  # Default if not provided
            "reservation_date": reservation_data.reservation_date,
            "start_time": reservation_data.start_time,
            "end_time": end_time,
            "guest": total_guests,
            "note": reservation_data.note or "",
            "table_id": [],  # Optional, will be assigned by system
            "amount_children": reservation_data.amount_children,
            "amount_adult": reservation_data.amount_adult,
            "has_birthday": reservation_data.has_birthday,
            "status": 1,  # Active reservation
            "from_sale": False,  # false = created by receptionist (customer service)
            "info_order": "",  # Optional
            "table": "",  # Optional, will be assigned by system
            "is_online": False,  # false = dine-in (not delivery)
            "nguon_khach": 1  # 1: returning customer via Zalo restaurant
        }

        logger.info(f"Making reservation request for {first_name} {last_name} at restaurant_id {restaurant_id}")
        logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
        
        # Make API request
        response = requests.post(
            f"{RESERVATION_API_BASE}/api/v1/restaurant/reservation/booking",
            json=payload,
            headers=_get_headers(),
            timeout=REQUEST_TIMEOUT
        )

        result = _handle_api_response(response)
        
        if result["success"]:
            logger.info(f"Reservation successful for {first_name} {last_name}")
            
            # Extract reservation details from response
            reservation_details = result.get("data", {})
            reservation_id = reservation_details.get("id", "N/A")
            
            # Create formatted success message
            result["formatted_message"] = (
                f"✅ **TABLE RESERVATION SUCCESSFUL!**\n\n"
                f"🎉 **Reservation Details:**\n"
                f"📋 **Reservation ID:** {reservation_id}\n"
                f"👤 **Customer:** {first_name} {last_name}\n"
                f"📞 **Phone:** {phone}\n"
                f"🏪 **Branch:** {restaurant_location}\n"
                f"📅 **Date:** {reservation_date}\n"
                f"⏰ **Time:** {start_time} - {end_time}\n"
                f"👥 **Guests:** {amount_adult} adults"
                + (f", {amount_children} children" if amount_children > 0 else "") + f" (total: {total_guests} guests)\n"
                + (f"🎂 **Birthday celebration**\n" if has_birthday else "")
                + (f"📝 **Note:** {note}\n\n" if note else "\n")
                + f"📞 **Support Hotline:** 1900 636 886\n"
                + f"🌐 **Website:** https://tianlong.vn/\n\n"
                + f"⚠️ **Note:** Please arrive on time to ensure your table is reserved properly!"
            )
        else:
            logger.error(f"Reservation failed for {first_name} {last_name}: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Unexpected error in book_table_reservation: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred. Please contact hotline 1900 636 886 for reservation assistance."
        }

def _resolve_repo_root() -> Path:
    """Resolve the repository root by walking up until a known marker is found."""
    # Check if running on production server (Linux path)
    production_path = Path("/home/administrator/project/chatbot_aladdin/chat_bot_server_aladin")
    if production_path.exists():
        return production_path
    
    # For local development
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists() or (parent / "README.md").exists():
            return parent
    # Fallback: assume two levels up from src/tools
    return Path(__file__).resolve().parent.parent

@tool("book_table_reservation_test", args_schema=ReservationInput)
def book_table_reservation_test(
    restaurant_location: str,
    first_name: str,
    last_name: str,
    phone: str,
    reservation_date: str,
    start_time: str,
    amount_adult: int,
    email: Optional[str] = None,
    dob: Optional[str] = None,
    end_time: Optional[str] = None,
    amount_children: int = 0,
    note: Optional[str] = None,
    has_birthday: bool = False
) -> Dict[str, Any]:
    """
    Test-only variant of table reservation.

    Performs the same validation and data preparation as the real tool but,
    instead of calling the reservation API, appends the booking to a JSON file
    named 'booking.json' at the repository root. The file stores a list of bookings.
    """
    try:
        # Validate input
        reservation_data = ReservationInput(
            restaurant_location=restaurant_location,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            dob=dob,
            reservation_date=reservation_date,
            start_time=start_time,
            end_time=end_time,
            amount_adult=amount_adult,
            amount_children=amount_children,
            note=note,
            has_birthday=has_birthday
        )

        # Find restaurant ID as in production flow
        restaurant_id = _find_restaurant_id(restaurant_location)
        if restaurant_id is None:
            return {
                "success": False,
                "error": "Restaurant not found",
                "message": f"Cannot find restaurant for location '{restaurant_location}'. Please check the location name and try again, or contact hotline 1900 636 886 for assistance.",
            }

        # Calculate total guests
        total_guests = amount_adult + amount_children

        # Default end time if not provided (3 hours later)
        if not end_time:
            try:
                start_dt = datetime.strptime(start_time, "%H:%M")
                end_hour = (start_dt.hour + 3) % 24
                end_dt = start_dt.replace(hour=end_hour)
                end_time = end_dt.strftime("%H:%M")
            except Exception:
                end_time = "22:00"

        # Generate email if not provided
        if not email:
            email = f"{phone}@tianlong.placeholder"

        # Prepare payload (mirrors real API payload)
        payload: Dict[str, Any] = {
            "restaurant_id": restaurant_id,
            "first_name": reservation_data.first_name,
            "last_name": reservation_data.last_name,
            "phone": reservation_data.phone,
            "email": email,
            "dob": reservation_data.dob or "1990-01-01",
            "reservation_date": reservation_data.reservation_date,
            "start_time": reservation_data.start_time,
            "end_time": end_time,
            "guest": total_guests,
            "note": reservation_data.note or "",
            "table_id": [],
            "amount_children": reservation_data.amount_children,
            "amount_adult": reservation_data.amount_adult,
            "has_birthday": reservation_data.has_birthday,
            "status": 1,
            "from_sale": False,
            "info_order": "",
            "table": "",
            "is_online": False,
            "nguon_khach": 1,
        }

        # Persist to booking.json at repo root
        repo_root = _resolve_repo_root()
        bookings_file = repo_root / "booking.json"

        # Read existing bookings (ensure list)
        existing: List[Dict[str, Any]] = []
        if bookings_file.exists():
            try:
                existing_obj = json.loads(bookings_file.read_text(encoding="utf-8"))
                if isinstance(existing_obj, list):
                    existing = existing_obj
                else:
                    logger.warning("booking.json is not a list; resetting to an empty list for testing")
            except Exception as e:
                logger.warning(f"Failed to parse existing booking.json: {e}; resetting to an empty list")

        reservation_id = str(uuid.uuid4())
        record = {
            "id": reservation_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "restaurant_location": restaurant_location,
            "payload": payload,
            "source": "test_file",
        }

        existing.append(record)
        bookings_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(
            f"[TEST] Saved reservation for {first_name} {last_name} at restaurant_id {restaurant_id} to '{bookings_file}'"
        )

        # Build response similar to production path
        result: Dict[str, Any] = {
            "success": True,
            "data": {"id": reservation_id, **payload},
            "message": "Table reservation saved to booking.json (test mode)",
        }

        # Attach formatted message for UX parity
        result["formatted_message"] = (
            f"✅ **TABLE RESERVATION SAVED (TEST MODE)!**\n\n"
            f"🎉 **Reservation Details:**\n"
            f"📋 **Reservation ID:** {reservation_id}\n"
            f"👤 **Customer:** {first_name} {last_name}\n"
            f"📞 **Phone:** {phone}\n"
            f"🏪 **Branch:** {restaurant_location}\n"
            f"📅 **Date:** {reservation_date}\n"
            f"⏰ **Time:** {start_time} - {end_time}\n"
            f"👥 **Guests:** {amount_adult} adults"
            + (f", {amount_children} children" if amount_children > 0 else "")
            + f" (total: {total_guests} guests)\n"
            + ("🎂 **Birthday celebration**\n" if has_birthday else "")
            + (f"📝 **Note:** {note}\n\n" if note else "\n")
            + f"📞 **Support Hotline:** 1900 636 886\n"
            + f"🌐 **Website:** https://tianlong.vn/\n\n"
            + f"⚠️ **Note:** This is a test booking saved locally and not sent to the live system."
        )

        return result

    except Exception as e:
        logger.error(f"Unexpected error in book_table_reservation_test: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "An unexpected error occurred while saving test booking.",
        }

# Export tools list for easy import
reservation_tools = [lookup_restaurant_by_location, book_table_reservation, book_table_reservation_test]
