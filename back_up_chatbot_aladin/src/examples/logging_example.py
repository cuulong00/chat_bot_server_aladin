"""
Ví dụ về cách sử dụng hệ thống logging tập trung trong các module khác
"""

from src.core.logging_config import (
    get_logger,
    log_exception_details,
    log_business_event,
    log_performance_metric
)
import time

# Lấy logger cho module này
logger = get_logger(__name__)


class RestaurantService:
    """
    Ví dụ service sử dụng logging tập trung
    """
    
    def __init__(self):
        self.logger = get_logger(f"{__name__}.RestaurantService")
    
    def find_restaurant(self, user_id: str, restaurant_name: str):
        """Tìm kiếm nhà hàng với logging đầy đủ"""
        
        start_time = time.time()
        
        try:
            self.logger.info(f"🔍 Starting restaurant search for user {user_id}: {restaurant_name}")
            
            # Giả lập logic tìm kiếm
            if restaurant_name.lower() == "error":
                raise ValueError("Simulated restaurant not found error")
            
            # Giả lập thời gian xử lý
            time.sleep(0.1)
            
            restaurant_data = {
                "id": "rest_123",
                "name": restaurant_name,
                "address": "123 Main St"
            }
            
            # Log business event
            log_business_event(
                event_type="restaurant_search",
                details={
                    "restaurant_name": restaurant_name,
                    "found": True,
                    "restaurant_id": restaurant_data["id"]
                },
                user_id=user_id
            )
            
            # Log performance metric
            duration_ms = (time.time() - start_time) * 1000
            log_performance_metric(
                operation="restaurant_search",
                duration_ms=duration_ms,
                details={
                    "restaurant_name": restaurant_name,
                    "result_count": 1
                },
                user_id=user_id
            )
            
            self.logger.info(f"✅ Restaurant found: {restaurant_data['name']}")
            return restaurant_data
            
        except Exception as e:
            # Log detailed exception
            log_exception_details(
                exception=e,
                context=f"Restaurant search failed for: {restaurant_name}",
                user_id=user_id,
                module_name=f"{__name__}.RestaurantService"
            )
            
            # Log business event for failure
            log_business_event(
                event_type="restaurant_search_failed",
                details={
                    "restaurant_name": restaurant_name,
                    "error": str(e)
                },
                user_id=user_id,
                level="ERROR"
            )
            
            self.logger.error(f"❌ Restaurant search failed for {restaurant_name}")
            return None
    
    def make_reservation(self, user_id: str, restaurant_id: str, party_size: int):
        """Đặt bàn với logging"""
        
        start_time = time.time()
        
        try:
            self.logger.info(f"📅 Processing reservation for user {user_id} at restaurant {restaurant_id}")
            
            # Giả lập logic đặt bàn
            if party_size > 10:
                raise ValueError("Party size too large")
            
            time.sleep(0.2)  # Giả lập thời gian xử lý
            
            reservation_id = f"res_{int(time.time())}"
            
            # Log business event
            log_business_event(
                event_type="reservation_created",
                details={
                    "reservation_id": reservation_id,
                    "restaurant_id": restaurant_id,
                    "party_size": party_size
                },
                user_id=user_id
            )
            
            # Log performance metric
            duration_ms = (time.time() - start_time) * 1000
            log_performance_metric(
                operation="reservation_creation",
                duration_ms=duration_ms,
                details={
                    "restaurant_id": restaurant_id,
                    "party_size": party_size
                },
                user_id=user_id
            )
            
            self.logger.info(f"✅ Reservation created: {reservation_id}")
            return {"reservation_id": reservation_id, "status": "confirmed"}
            
        except Exception as e:
            log_exception_details(
                exception=e,
                context=f"Reservation failed for restaurant {restaurant_id}, party size {party_size}",
                user_id=user_id,
                module_name=f"{__name__}.RestaurantService"
            )
            
            self.logger.error(f"❌ Reservation failed for restaurant {restaurant_id}")
            return None


def demo_logging_usage():
    """Demo sử dụng logging trong business logic"""
    
    logger.info("🚀 Starting restaurant service demo")
    
    service = RestaurantService()
    user_id = "user_789"
    
    # Test thành công
    restaurant = service.find_restaurant(user_id, "Tian Long")
    if restaurant:
        reservation = service.make_reservation(user_id, restaurant["id"], 4)
        logger.info(f"Demo completed successfully: {reservation}")
    
    # Test lỗi tìm kiếm
    service.find_restaurant(user_id, "error")
    
    # Test lỗi đặt bàn
    service.make_reservation(user_id, "rest_123", 15)
    
    logger.info("📊 Demo completed - check log files for details")


if __name__ == "__main__":
    demo_logging_usage()
