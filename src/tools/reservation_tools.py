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

class BookingQueryInput(BaseModel):
    """Input for querying bookings by phone number"""
    phone: str = Field(..., description="Customer phone number to search for bookings")

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

class CancelBookingInput(BaseModel):
    """Input for canceling a booking by booking ID or phone number"""
    booking_id: Optional[str] = Field(None, description="Booking ID to cancel (preferred method)")
    phone: Optional[str] = Field(None, description="Customer phone number to find and cancel latest booking")
    
    @validator('phone')
    def validate_phone(cls, v):
        if v is None:
            return v
        # Basic Vietnamese phone validation
        if len(v) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        # Remove spaces and special characters
        cleaned_phone = ''.join(filter(str.isdigit, v))
        if len(cleaned_phone) < 10:
            raise ValueError("Phone number must have at least 10 digits")
        return cleaned_phone
    
    @validator('phone', always=True)
    def validate_input_provided(cls, v, values):
        # At least one of booking_id or phone must be provided
        booking_id = values.get('booking_id')
        if not booking_id and not v:
            raise ValueError("Either booking_id or phone number must be provided")
        return v

class ReservationInput(BaseModel):
    """Pydantic model for table reservation input validation"""
    restaurant_location: str = Field(..., description="Restaurant branch name or address")
    first_name: str = Field(..., description="Customer first name")
    last_name: str = Field(..., description="Customer last name")
    phone: str = Field(..., description="Customer phone number")
    email: Optional[str] = Field(None, description="Customer email (optional)")
    dob: Optional[str] = Field(None, description="Date of birth (dd/mm/yyyy or YYYY-MM-DD)")
    reservation_date: str = Field(..., description="Reservation date (dd/mm/yyyy or YYYY-MM-DD)")
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
        """Accept dd/mm/yyyy or YYYY-MM-DD and normalize to YYYY-MM-DD internally."""
        val = v.strip()
        parsed_date: date | None = None
        # Try dd/mm/yyyy first
        try:
            if '/' in val:
                d = datetime.strptime(val, '%d/%m/%Y').date()
                parsed_date = d
            else:
                d = datetime.strptime(val, '%Y-%m-%d').date()
                parsed_date = d
        except ValueError:
            # Secondary attempt: support d/m/yyyy without leading zeros
            try:
                d = datetime.strptime(val, '%d/%m/%Y').date()
                parsed_date = d
            except ValueError as e:
                raise ValueError(f"Invalid date format (dd/mm/yyyy or YYYY-MM-DD): {e}")
        if parsed_date < date.today():
            raise ValueError("Reservation date cannot be in the past")
        # Normalize to ISO for downstream API
        return parsed_date.strftime('%Y-%m-%d')

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

def _save_phone_number_to_memory(user_id: str, phone: str) -> bool:
    """
    Save phone number to user memory using the new intelligent system.
    
    Args:
        user_id: User identifier
        phone: Phone number to save
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        from src.tools.memory_tools import smart_save_user_info
        
        # Clean phone number
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Format phone number nicely
        if len(clean_phone) >= 10:
            if clean_phone.startswith('84'):
                formatted_phone = f"+84 {clean_phone[2:5]} {clean_phone[5:8]} {clean_phone[8:]}"
            elif clean_phone.startswith('0'):
                formatted_phone = f"{clean_phone[:4]} {clean_phone[4:7]} {clean_phone[7:]}"
            else:
                formatted_phone = clean_phone
        else:
            formatted_phone = phone
            
        # Use smart save to automatically handle phone number with intelligence
        result = smart_save_user_info.invoke({
            "user_id": user_id,
            "content": f"Số điện thoại: {formatted_phone}",
            "context": "Provided during table reservation process"
        })
        
        logger.info(f"📞 Smart phone save result: {result}")
        
        # Consider success if no error occurred  
        return not result.startswith("Error")
        
    except Exception as e:
        logger.error(f"❌ Error saving phone to memory: {e}")
        return False

def _save_booking_to_file(payload: Dict[str, Any], restaurant_location: str) -> Dict[str, Any]:
    """
    Save booking data to booking.json file (temporary solution until API is ready)
    """
    try:
        # Get repository root
        repo_root = _resolve_repo_root()
        bookings_file = repo_root / "booking.json"
        
        # Read existing bookings
        existing_bookings: List[Dict[str, Any]] = []
        if bookings_file.exists():
            try:
                existing_obj = json.loads(bookings_file.read_text(encoding="utf-8"))
                if isinstance(existing_obj, list):
                    existing_bookings = existing_obj
                else:
                    logger.warning("booking.json is not a list; resetting to empty list")
            except Exception as e:
                logger.warning(f"Failed to parse existing booking.json: {e}; resetting to empty list")
        
        # Generate unique reservation ID
        reservation_id = str(uuid.uuid4())
        
        # Create booking record
        booking_record = {
            "id": reservation_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "restaurant_location": restaurant_location,
            "status": "confirmed",
            "source": "chatbot",
            **payload  # Include all reservation data
        }
        
        # Add to existing bookings
        existing_bookings.append(booking_record)
        
        # Save to file
        bookings_file.write_text(
            json.dumps(existing_bookings, ensure_ascii=False, indent=2), 
            encoding="utf-8"
        )
        
        logger.info(f"Booking saved to file with ID: {reservation_id}")
        
        return {
            "success": True,
            "data": {"id": reservation_id, **payload},
            "message": "Table reservation successful!"
        }
        
    except Exception as e:
        logger.error(f"Error saving booking to file: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "An error occurred while saving the reservation. Please try again later or call hotline 1900 636 886."
        }
   

def _get_bookings_by_phone(phone: str) -> List[Dict[str, Any]]:
    """
    Get all bookings for a phone number from booking.json file
    """
    try:
        repo_root = _resolve_repo_root()
        bookings_file = repo_root / "booking.json"
        
        if not bookings_file.exists():
            return []
        
        bookings = json.loads(bookings_file.read_text(encoding="utf-8"))
        if not isinstance(bookings, list):
            return []
        
        # Clean phone number for comparison
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Find matching bookings
        matching_bookings = []
        for booking in bookings:
            booking_phone = booking.get('phone', '')
            clean_booking_phone = ''.join(filter(str.isdigit, booking_phone))
            
            if clean_booking_phone == clean_phone:
                matching_bookings.append(booking)
        
        # Sort by creation date (newest first)
        matching_bookings.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        return matching_bookings
        
    except Exception as e:
        logger.error(f"Error reading bookings from file: {e}")
        return []

def _cancel_booking_from_file(booking_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel a booking by removing it from booking.json file
    """
    try:
        repo_root = _resolve_repo_root()
        bookings_file = repo_root / "booking.json"
        
        if not bookings_file.exists():
            return {
                "success": False,
                "error": "No bookings found",
                "message": "Không tìm thấy file đặt bàn."
            }
        
        # Read existing bookings
        bookings = json.loads(bookings_file.read_text(encoding="utf-8"))
        if not isinstance(bookings, list):
            return {
                "success": False,
                "error": "Invalid bookings file format",
                "message": "File đặt bàn không hợp lệ."
            }
        
        original_count = len(bookings)
        booking_to_cancel = None
        
        if booking_id:
            # Find by booking ID (exact match or partial match for first 8 characters)
            for i, booking in enumerate(bookings):
                if (booking.get('id') == booking_id or 
                    booking.get('id', '').startswith(booking_id)):
                    booking_to_cancel = bookings.pop(i)
                    break
        elif phone:
            # Find by phone number (cancel the most recent booking)
            clean_phone = ''.join(filter(str.isdigit, phone))
            for i, booking in enumerate(bookings):
                booking_phone = booking.get('phone', '')
                clean_booking_phone = ''.join(filter(str.isdigit, booking_phone))
                
                if clean_booking_phone == clean_phone:
                    booking_to_cancel = bookings.pop(i)
                    break  # Remove the first match (should be most recent due to append order)
        
        if booking_to_cancel is None:
            search_term = booking_id if booking_id else phone
            return {
                "success": False,
                "error": "Booking not found",
                "message": f"Không tìm thấy đặt bàn với thông tin: {search_term}"
            }
        
        # Save updated bookings back to file
        bookings_file.write_text(
            json.dumps(bookings, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        logger.info(f"Canceled booking: {booking_to_cancel.get('id', 'unknown')} for {booking_to_cancel.get('first_name', '')} {booking_to_cancel.get('last_name', '')}")
        
        return {
            "success": True,
            "data": {
                "canceled_booking": booking_to_cancel,
                "remaining_bookings": len(bookings),
                "original_count": original_count
            },
            "message": "Hủy đặt bàn thành công!"
        }
        
    except Exception as e:
        logger.error(f"Error canceling booking from file: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Có lỗi xảy ra khi hủy đặt bàn. Vui lòng liên hệ hotline 1900 636 886."
        }

@tool("cancel_booking", args_schema=CancelBookingInput)
def cancel_booking(booking_id: Optional[str] = None, phone: Optional[str] = None) -> Dict[str, Any]:
    """
    Cancel a table reservation by booking ID or phone number.
    
    This tool helps customers cancel their existing reservations.
    Priority: booking_id (exact match) > phone (cancels most recent booking)
    """
    try:
        print(f"------------cancel_booking----------------")
        result = _cancel_booking_from_file(booking_id=booking_id, phone=phone)
        
        if result.get('success'):
            canceled_booking = result['data']['canceled_booking']
            remaining_count = result['data']['remaining_bookings']
            
            # Format cancellation confirmation
            try:
                # Parse date for display
                reservation_date = canceled_booking.get('reservation_date', '')
                if reservation_date:
                    try:
                        if '/' in reservation_date:
                            date_obj = datetime.strptime(reservation_date, '%d/%m/%Y')
                        else:
                            date_obj = datetime.strptime(reservation_date, '%Y-%m-%d')
                        display_date = date_obj.strftime('%d/%m/%Y')
                    except:
                        display_date = reservation_date
                else:
                    display_date = 'N/A'
                
                customer_name = f"{canceled_booking.get('first_name', '')} {canceled_booking.get('last_name', '')}".strip()
                
                result["formatted_message"] = (
                    f"✅ **HỦY ĐẶT BÀN THÀNH CÔNG!**\n\n"
                    f"❌ **Thông tin đặt bàn đã hủy:**\n"
                    f"📋 **Mã đặt bàn:** {canceled_booking.get('id', 'N/A')[:8]}...\n"
                    f"👤 **Khách hàng:** {customer_name}\n"
                    f"📞 **SĐT:** {canceled_booking.get('phone', '')}\n"
                    f"🏪 **Chi nhánh:** {canceled_booking.get('restaurant_location', 'N/A')}\n"
                    f"📅 **Ngày:** {display_date}\n"
                    f"⏰ **Giờ:** {canceled_booking.get('start_time', 'N/A')} - {canceled_booking.get('end_time', 'N/A')}\n"
                    f"👥 **Số khách:** {canceled_booking.get('amount_adult', 0)} người lớn"
                    + (f", {canceled_booking.get('amount_children', 0)} trẻ em" if canceled_booking.get('amount_children', 0) > 0 else "")
                    + f" (tổng: {canceled_booking.get('guest', 0)} khách)\n\n"
                    + (f"📝 **Ghi chú:** {canceled_booking.get('note', '')}\n\n" if canceled_booking.get('note') else "\n")
                    + f"📊 **Số đặt bàn còn lại:** {remaining_count}\n\n"
                    + f"📞 **Hotline hỗ trợ:** 1900 636 886\n"
                    + f"💡 **Lưu ý:** Nếu cần đặt bàn mới, vui lòng liên hệ lại!"
                )
            except Exception as e:
                logger.error(f"Error formatting cancel message: {e}")
                result["formatted_message"] = result["message"]
        
        return result
        
    except Exception as e:
        logger.error(f"Error in cancel_booking tool: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Có lỗi xảy ra khi hủy đặt bàn. Vui lòng liên hệ hotline 1900 636 886 để được hỗ trợ."
        }

@tool("get_user_bookings", args_schema=BookingQueryInput)
def get_user_bookings(phone: str) -> Dict[str, Any]:
    """
    Get all table reservations for a customer by phone number.
    
    This tool helps customers check their existing reservations and booking history.
    """
    print(f"------------get_user_bookings----------------")
    try:
        bookings = _get_bookings_by_phone(phone)
        
        if not bookings:
            return {
                "success": True,
                "data": {
                    "phone": phone,
                    "bookings": [],
                    "count": 0
                },
                "message": f"Không tìm thấy đặt bàn nào cho số điện thoại {phone}."
            }
        
        # Format booking information for display
        formatted_bookings = []
        for booking in bookings:
            try:
                # Parse date for display
                reservation_date = booking.get('reservation_date', '')
                if reservation_date:
                    try:
                        # Try both formats
                        if '/' in reservation_date:
                            date_obj = datetime.strptime(reservation_date, '%d/%m/%Y')
                        else:
                            date_obj = datetime.strptime(reservation_date, '%Y-%m-%d')
                        display_date = date_obj.strftime('%d/%m/%Y')
                    except:
                        display_date = reservation_date
                else:
                    display_date = 'N/A'
                
                formatted_booking = {
                    "id": booking.get('id', 'N/A'),
                    "customer_name": f"{booking.get('first_name', '')} {booking.get('last_name', '')}".strip(),
                    "phone": booking.get('phone', ''),
                    "restaurant_location": booking.get('restaurant_location', 'N/A'),
                    "reservation_date": display_date,
                    "start_time": booking.get('start_time', 'N/A'),
                    "end_time": booking.get('end_time', 'N/A'),
                    "guests": booking.get('guest', 0),
                    "adults": booking.get('amount_adult', 0),
                    "children": booking.get('amount_children', 0),
                    "has_birthday": booking.get('has_birthday', False),
                    "note": booking.get('note', ''),
                    "status": str(booking.get('status', 'confirmed')),  # Convert to string
                    "created_at": booking.get('created_at', ''),
                    "source": booking.get('source', 'unknown')
                }
                formatted_bookings.append(formatted_booking)
            except Exception as e:
                logger.error(f"Error formatting booking: {e}")
                continue
        
        # Create formatted message for display
        if len(formatted_bookings) == 1:
            booking = formatted_bookings[0]
            formatted_message = (
                f"📋 **THÔNG TIN ĐẶT BÀN**\n\n"
                f"📋 **Mã đặt bàn:** {booking['id'][:8]}...\n"
                f"👤 **Khách hàng:** {booking['customer_name']}\n"
                f"📞 **SĐT:** {booking['phone']}\n"
                f"🏪 **Chi nhánh:** {booking['restaurant_location']}\n"
                f"📅 **Ngày:** {booking['reservation_date']}\n"
                f"⏰ **Giờ:** {booking['start_time']} - {booking['end_time']}\n"
                f"👥 **Số khách:** {booking['adults']} người lớn"
                + (f", {booking['children']} trẻ em" if booking['children'] > 0 else "")
                + f" (tổng: {booking['guests']} khách)\n"
                + (f"🎂 **Sinh nhật**\n" if booking['has_birthday'] else "")
                + (f"📝 **Ghi chú:** {booking['note']}\n" if booking['note'] else "")
                + f"✅ **Trạng thái:** {booking['status'].title()}\n\n"
                + f"📞 **Hotline hỗ trợ:** 1900 636 886"
            )
        else:
            formatted_message = f"📋 **LỊCH SỬ ĐẶT BÀN - SĐT: {phone}**\n\n"
            for i, booking in enumerate(formatted_bookings[:5], 1):  # Show max 5 recent bookings
                formatted_message += (
                    f"**#{i}. {booking['reservation_date']} - {booking['start_time']}**\n"
                    f"👤 {booking['customer_name']} | 🏪 {booking['restaurant_location']}\n"
                    f"👥 {booking['guests']} khách | ✅ {booking['status'].title()}\n\n"
                )
            
            if len(formatted_bookings) > 5:
                formatted_message += f"... và {len(formatted_bookings) - 5} đặt bàn khác\n\n"
            
            formatted_message += f"📞 **Hotline hỗ trợ:** 1900 636 886"
        
        return {
            "success": True,
            "data": {
                "phone": phone,
                "bookings": formatted_bookings,
                "count": len(formatted_bookings)
            },
            "message": f"Tìm thấy {len(formatted_bookings)} đặt bàn cho số điện thoại {phone}.",
            "formatted_message": formatted_message
        }
        
    except Exception as e:
        logger.error(f"Error in get_user_bookings: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Có lỗi xảy ra khi tìm kiếm thông tin đặt bàn. Vui lòng liên hệ hotline 1900 636 886 để được hỗ trợ."
        }
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
    # 🚨 CRITICAL DEBUG: Log tool được gọi
    logger.warning("🔥🔥🔥 BOOK_TABLE_RESERVATION TOOL ĐƯỢC GỌI! 🔥🔥🔥")
    logger.warning(f"🔍 Tool params: location={restaurant_location}, name={first_name} {last_name}, phone={phone}, date={reservation_date}, time={start_time}, adults={amount_adult}, children={amount_children}, birthday={has_birthday}")
    print(f"-------------------------------tool call book_table_reservation---------------------------")
    
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
        
        # TODO: Uncomment when API is ready
        # response = requests.post(
        #     f"{RESERVATION_API_BASE}/api/v1/restaurant/reservation/booking",
        #     json=payload,
        #     headers=_get_headers(),
        #     timeout=REQUEST_TIMEOUT
        # )
        # result = _handle_api_response(response)
        
        # Temporary: Save to booking.json file instead of API call
        result = _save_booking_to_file(payload, restaurant_location)
        
        if result["success"]:
            logger.info(f"Reservation successful for {first_name} {last_name}")
            
            # 📞 SAVE PHONE NUMBER TO USER MEMORY (avoid duplicates)
            try:
                # Try to get user_id from state/context (if available)
                user_id = f"phone_{phone}"  # Fallback: use phone as user_id
                phone_saved = _save_phone_number_to_memory(user_id, phone)
                if phone_saved:
                    logger.info(f"📞 Phone number saved to user memory for {user_id}")
                else:
                    logger.warning(f"📞 Failed to save phone number to memory for {user_id}")
            except Exception as e:
                logger.error(f"📞 Error saving phone to memory: {e}")
            
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
                f"📅 **Date:** {datetime.strptime(reservation_date, '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
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
    # 🚨 CRITICAL DEBUG: Log tool được gọi
    logger.warning("🔥🔥🔥 BOOK_TABLE_RESERVATION_TEST TOOL ĐƯỢC GỌI! 🔥🔥🔥")
    logger.warning(f"🔍 Tool params: location={restaurant_location}, name={first_name} {last_name}, phone={phone}, date={reservation_date}, time={start_time}, adults={amount_adult}, children={amount_children}, birthday={has_birthday}")
    
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
        print(f"repo_root:{repo_root}")
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
            f"📅 **Date:** {datetime.strptime(reservation_date, '%Y-%m-%d').strftime('%d/%m/%Y')}\n"
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
reservation_tools = [lookup_restaurant_by_location, get_user_bookings, cancel_booking, book_table_reservation]
