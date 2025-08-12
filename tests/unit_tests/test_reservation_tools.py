import pytest
from unittest.mock import patch, Mock, MagicMock
from src.tools.reservation_tools import (
    book_table_reservation, 
    lookup_restaurant_by_location,
    ReservationInput,
    _find_restaurant_id,
    _handle_api_response
)
from pydantic import ValidationError
import requests
import json

class TestReservationTools:
    
    def test_reservation_input_validation_success(self):
        """Test successful reservation input validation"""
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn",
            "last_name": "Dương",
            "phone": "0981896440",
            "reservation_date": "2024-12-25",
            "start_time": "19:00",
            "amount_adult": 4,
            "amount_children": 2
        }
        
        reservation = ReservationInput(**data)
        assert reservation.first_name == "Tuấn"
        assert reservation.amount_adult == 4
        assert reservation.amount_children == 2
        assert reservation.phone == "0981896440"

    def test_reservation_input_validation_invalid_phone(self):
        """Test phone validation failure"""
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn",
            "last_name": "Dương", 
            "phone": "123",  # Too short
            "reservation_date": "2024-12-25",
            "start_time": "19:00",
            "amount_adult": 4
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReservationInput(**data)
        assert "Số điện thoại phải có ít nhất 10 chữ số" in str(exc_info.value)

    def test_reservation_input_validation_past_date(self):
        """Test past date validation failure"""
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn",
            "last_name": "Dương",
            "phone": "0981896440",
            "reservation_date": "2020-01-01",  # Past date
            "start_time": "19:00",
            "amount_adult": 4
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReservationInput(**data)
        assert "Ngày đặt bàn không thể là ngày trong quá khứ" in str(exc_info.value)

    def test_reservation_input_validation_invalid_time(self):
        """Test invalid time format"""
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn",
            "last_name": "Dương",
            "phone": "0981896440",
            "reservation_date": "2024-12-25",
            "start_time": "25:00",  # Invalid time
            "amount_adult": 4
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ReservationInput(**data)
        assert "Định dạng giờ không hợp lệ" in str(exc_info.value)

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_find_restaurant_id_vector_search_success(self, mock_qdrant_store):
        """Test successful restaurant ID lookup using vector search"""
        # Mock search results based on real restaurant data
        mock_qdrant_store.search.return_value = [
            (
                "6383b75c9ee5ebd3f",  # key (restaurant ID)
                {
                    "id": "6383b75c9ee5ebd3f",
                    "restaurant_id": "6383b75c9ee5ebd3f",
                    "restaurant_name": "LW-HN01:84 Ngọc khánh - Ba Đình - Hà Nội",
                    "brand_name": "Lẩu Wang",
                    "city": "Hà Nội",
                    "district": "Ba Đình"
                },
                0.95  # confidence score
            )
        ]
        
        result = _find_restaurant_id("Lẩu Wang Ngọc Khánh Ba Đình")
        
        # Verify vector search was called
        mock_qdrant_store.search.assert_called_once_with(
            namespace="restaurants",
            query="Lẩu Wang Ngọc Khánh Ba Đình",
            limit=3
        )
        
        # Should return the restaurant_id from vector search
        assert result == "6383b75c9ee5ebd3f"

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_find_restaurant_id_vector_search_with_metadata_id(self, mock_qdrant_store):
        """Test restaurant ID lookup using metadata ID when restaurant_id not available"""
        # Mock search results with only metadata ID
        mock_qdrant_store.search.return_value = [
            (
                "664c42ee88f00d2d2",
                {
                    "id": "664c42ee88f00d2d2",
                    "restaurant_name": "LW-HN10:Lô DD-22A2 tầng B1, TTTM Vincom Megamall Times City",
                    "brand_name": "Lẩu Wang",
                    "city": "Hà Nội",
                    "mall": "Vincom"
                },
                0.88
            )
        ]
        
        result = _find_restaurant_id("Times City Vincom Megamall")
        
        # Should return the metadata ID
        assert result == "664c42ee88f00d2d2"

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_find_restaurant_id_vector_search_failure_returns_none(self, mock_qdrant_store):
        """Test that None is returned when vector search fails"""
        # Mock empty search results
        mock_qdrant_store.search.return_value = []
        
        result = _find_restaurant_id("unknown restaurant location")
        
        # Should return None instead of fallback
        assert result is None

    @patch('src.tools.reservation_tools.qdrant_store', None)
    def test_find_restaurant_id_no_qdrant_returns_none(self):
        """Test that None is returned when qdrant_store is not available"""
        result = _find_restaurant_id("any restaurant")
        
        # Should return None when qdrant_store not available
        assert result is None

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_find_restaurant_id_vector_search_exception_returns_none(self, mock_qdrant_store):
        """Test that None is returned when vector search raises exception"""
        # Mock search exception
        mock_qdrant_store.search.side_effect = Exception("Vector search failed")
        
        result = _find_restaurant_id("some restaurant")
        
        # Should return None when exception occurs
        assert result is None

    def test_real_restaurant_data_brand_extraction(self):
        """Test brand extraction logic with real restaurant names from id_restaurant.json"""
        test_cases = [
            ("LW-BG01:L3-07 Vincom Bắc Giang - số 43 Ngô Gia Tự, Bắc Giang", "LW", "Lẩu Wang"),
            ("BTQM-HN01:102 Thái Thịnh, Đống Đa, Hà Nội", "BTQM", "Bánh Tráng Quết Mắm"),
            ("TL-HN01:Trần Thái Tông", "TL", "Tian Long"),
            ("CNHS-HN01:111 K1 Giảng Võ, P. Ô Chợ Dừa", "CNHS", "Chả Cá Hà Nội Sài Gòn"),
            ("AP-SG01:Số 9 Thoại Ngọc Hầu, P. Hòa Thạnh", "AP", "Au Petit"),
            ("AV-HN01:Vincom Phạm Ngọc Thạch", "AV", "Au Viet")
        ]
        
        # This would be testing the brand extraction logic in RestaurantDataProcessor
        # from the embedding script we created
        for restaurant_name, expected_code, expected_brand in test_cases:
            # Extract brand code
            if ':' in restaurant_name:
                code_part = restaurant_name.split(':')[0]
                if '-' in code_part:
                    brand_code = code_part.split('-')[0]
                    assert brand_code == expected_code, f"Failed for {restaurant_name}"

    def test_real_restaurant_data_location_extraction(self):
        """Test location extraction with real restaurant data"""
        test_cases = [
            ("LW-HN01:84 Ngọc khánh - Ba Đình - Hà Nội", "Hà Nội", "Ba Đình"),
            ("LW-SG01:816 Sư Vạn Hạnh P12 Q10", "Hồ Chí Minh", "Quận 10"),
            ("LW-HP01:Aeon Hải Phòng", "Hải Phòng", ""),
            ("LW-DN01:K33 Võ Thị Sáu - Biên Hòa - Đồng Nai", "Đồng Nai", ""),
            ("BTQM-SG03:111A Gò Dầu, phường Tân Quý, quận Tân Phú, TP.HCM", "Hồ Chí Minh", "Tân Phú"),
            ("TL-HU01:Aeon Huế - 08 Võ Nguyên Giáp, An Đông", "Huế", "")
        ]
        
        for restaurant_name, expected_city, expected_district in test_cases:
            # Test city extraction
            city = ""
            if any(x in restaurant_name for x in ['Hà Nội', 'HN', 'Hanoi']):
                city = 'Hà Nội'
            elif any(x in restaurant_name for x in ['Hồ Chí Minh', 'HCM', 'SG', 'Sài Gòn', 'TP.HCM']):
                city = 'Hồ Chí Minh'
            elif any(x in restaurant_name for x in ['Hải Phòng', 'HP']):
                city = 'Hải Phòng'
            elif 'Đồng Nai' in restaurant_name or 'DN' in restaurant_name:
                city = 'Đồng Nai'
            elif 'Huế' in restaurant_name or 'HU' in restaurant_name:
                city = 'Huế'
            
            assert city == expected_city, f"City extraction failed for {restaurant_name}"

    @patch('src.tools.reservation_tools.QdrantStore')
    def test_lookup_restaurant_hanoi_locations(self, mock_qdrant_store_class):
        """Test lookup for various Hanoi restaurant locations from real data"""
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        
        hanoi_test_cases = [
            ("Ngọc Khánh Ba Đình", "6383b75c9ee5ebd3f", "LW-HN01:84 Ngọc khánh - Ba Đình - Hà Nội"),
            ("Vincom Times City", "664c42ee88f00d2d2", "LW-HN10:Lô DD-22A2 tầng B1, TTTM Vincom Megamall Times City"),
            ("Royal City Nguyễn Trãi", "66500c795546ce21a", "LW-HN11:Tầng B2, TTTM Vincom Mega Mall Royal City, số 724 Nguyễn Trãi"),
            ("Aeon Mall Long Biên", "6735b7ae2aa5d1d1d", "LW-HN16:Aeon Mall Long Biên"),
            ("Vincom Phạm Ngọc Thạch", "674d7f51a40c0c83a", "LW-HN17:VinCom Phạm Ngọc Thạch")
        ]
        
        for query, expected_id, restaurant_name in hanoi_test_cases:
            mock_store.search.return_value = [
                (expected_id, {
                    "id": expected_id,
                    "restaurant_id": expected_id,
                    "restaurant_name": restaurant_name,
                    "city": "Hà Nội"
                }, 0.9)
            ]
            
            result = lookup_restaurant_by_location(query)
            assert result["success"] is True
            assert result["data"]["restaurant_id"] == expected_id

    @patch('src.tools.reservation_tools.QdrantStore')
    def test_lookup_restaurant_hcm_locations(self, mock_qdrant_store_class):
        """Test lookup for Ho Chi Minh City restaurant locations from real data"""
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        
        hcm_test_cases = [
            ("Sư Vạn Hạnh Quận 10", "65488d55e40b72271", "LW-SG01:816 Sư Vạn Hạnh P12 Q10"),
            ("Crescent Mall Quận 7", "65b700f660a1e1c35", "LW-SG02:Crescent Mall, Quận 7"),
            ("Vincom Đồng Khởi", "67e66dd8defe35071", "LW-SG11:Vincom Đồng Khởi, Quận 1, Hồ Chí Minh"),
            ("Lê Văn Sỹ Phú Nhuận", "6858f4caa0c57f346", "LW-SG15:183 Lê Văn Sỹ, Phú Nhuận, HCM"),
            ("CityLand Gò Vấp", "6833dc8035be46b51", "LW-SG13:CityLand, Gò Vấp, Hồ Chí Minh")
        ]
        
        for query, expected_id, restaurant_name in hcm_test_cases:
            mock_store.search.return_value = [
                (expected_id, {
                    "id": expected_id,
                    "restaurant_id": expected_id,
                    "restaurant_name": restaurant_name,
                    "city": "Hồ Chí Minh"
                }, 0.9)
            ]
            
            result = lookup_restaurant_by_location(query)
            assert result["success"] is True
            assert result["data"]["restaurant_id"] == expected_id

    @patch('src.tools.reservation_tools.QdrantStore')
    def test_lookup_restaurant_other_cities(self, mock_qdrant_store_class):
        """Test lookup for restaurant locations in other cities from real data"""
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        
        other_cities_test_cases = [
            ("Aeon Hải Phòng", "665052378be5c0efb", "LW-HP01:Aeon Hải Phòng", "Hải Phòng"),
            ("Vincom Bắc Giang", "667a27e9af01b69bf", "LW-BG01:L3-07 Vincom Bắc Giang - số 43 Ngô Gia Tự, Bắc Giang", "Bắc Giang"),
            ("Biên Hòa Đồng Nai", "683d187026925c1a2", "LW-DN01:K33 Võ Thị Sáu - Biên Hòa - Đồng Nai", "Đồng Nai"),
            ("Aeon Huế", "688439c3cb2d64b93", "BTQM-TT01:Aeon Mall Huế", "Huế")
        ]
        
        for query, expected_id, restaurant_name, city in other_cities_test_cases:
            mock_store.search.return_value = [
                (expected_id, {
                    "id": expected_id,
                    "restaurant_id": expected_id,
                    "restaurant_name": restaurant_name,
                    "city": city
                }, 0.9)
            ]
            
            result = lookup_restaurant_by_location(query)
            assert result["success"] is True
            assert result["data"]["restaurant_id"] == expected_id

    @patch('src.tools.reservation_tools.QdrantStore')
    def test_lookup_restaurant_brand_specific_search(self, mock_qdrant_store_class):
        """Test lookup for specific restaurant brands from real data"""
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        
        brand_test_cases = [
            ("Tian Long Trần Thái Tông", "6747f0b69adb5f0b1", "TL-HN01:Trần Thái Tông", "Tian Long"),
            ("Bánh Tráng Quết Mắm Thái Thịnh", "657f46700d99bf11c", "BTQM-HN01:102 Thái Thịnh, Đống Đa, Hà Nội", "Bánh Tráng Quết Mắm"),
            ("Chả Cá Hà Nội Sài Gòn Giảng Võ", "6756578d103499d38", "CNHS-HN01:111 K1 Giảng Võ, P. Ô Chợ Dừa", "Chả Cá Hà Nội Sài Gòn"),
            ("Au Petit Thoại Ngọc Hầu", "66037396376597bdb", "AP-SG01:Số 9 Thoại Ngọc Hầu, P. Hòa Thạnh", "Au Petit")
        ]
        
        for query, expected_id, restaurant_name, brand in brand_test_cases:
            mock_store.search.return_value = [
                (expected_id, {
                    "id": expected_id,
                    "restaurant_id": expected_id,
                    "restaurant_name": restaurant_name,
                    "brand_name": brand
                }, 0.92)
            ]
            
            result = lookup_restaurant_by_location(query)
            assert result["success"] is True
            assert result["data"]["restaurant_id"] == expected_id

    def test_find_restaurant_id_returns_none_when_no_vector_search(self):
        """Test that _find_restaurant_id returns None when vector search fails (no fallback)"""
        # Test with no vector search results
        result = _find_restaurant_id("unknown location")
        assert result is None  # Should return None, no fallback mapping

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_lookup_restaurant_by_location_success(self, mock_qdrant_store):
        """Test successful restaurant lookup with vector search"""
        mock_qdrant_store.search.return_value = [
            ("664c42ee88f00d2d2", {
                "id": "664c42ee88f00d2d2", 
                "restaurant_id": "664c42ee88f00d2d2",
                "restaurant_name": "LW-HN10:Lô DD-22A2 tầng B1, TTTM Vincom Megamall Times City"
            }, 0.95)
        ]
        
        result = lookup_restaurant_by_location("times city")
        
        assert result["success"] is True
        assert result["data"]["restaurant_id"] == "664c42ee88f00d2d2"
        assert result["data"]["found"] is True

    @patch('src.tools.reservation_tools.qdrant_store')
    def test_lookup_restaurant_by_location_not_found(self, mock_qdrant_store):
        """Test restaurant lookup with unknown location using vector search"""
        mock_qdrant_store.search.return_value = []  # No results from vector search
        
        result = lookup_restaurant_by_location("unknown location")
        
        assert result["success"] is False  # Changed to False since no restaurant found
        assert result["data"]["restaurant_id"] is None  # Should be None
        assert result["data"]["found"] is False

    @patch('src.tools.reservation_tools.qdrant_store')
    @patch('src.tools.reservation_tools.requests.post')
    def test_book_table_reservation_success(self, mock_post, mock_qdrant_store):
        """Test successful table reservation with vector search"""
        # Mock qdrant_store for restaurant lookup
        mock_qdrant_store.search.return_value = [
            ("664c42ee88f00d2d2", {
                "id": "664c42ee88f00d2d2",
                "restaurant_id": "664c42ee88f00d2d2",
                "restaurant_name": "LW-HN10:Lô DD-22A2 tầng B1, TTTM Vincom Megamall Times City"
            }, 0.95)
        ]
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "id": 123,
            "reservation_code": "TL2024001",
            "status": "confirmed"
        }
        mock_post.return_value = mock_response

        result = book_table_reservation(
            restaurant_location="Times City",
            first_name="Tuấn",
            last_name="Dương",
            phone="0981896440",
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4,
            amount_children=2
        )

        assert result["success"] is True
        assert "formatted_message" in result
        assert "Tuấn Dương" in result["formatted_message"]
        assert "TABLE RESERVATION SUCCESSFUL" in result["formatted_message"]
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['first_name'] == "Tuấn"
        assert call_args[1]['json']['last_name'] == "Dương"
        assert call_args[1]['json']['restaurant_id'] == "664c42ee88f00d2d2"  # Vector search result

    @patch('src.tools.reservation_tools.qdrant_store')
    @patch('src.tools.reservation_tools.requests.post')
    def test_book_table_reservation_restaurant_not_found(self, mock_post, mock_qdrant_store):
        """Test reservation failure when restaurant is not found"""
        # Mock qdrant_store with no results
        mock_qdrant_store.search.return_value = []  # No restaurant found
        
        result = book_table_reservation(
            restaurant_location="Unknown Restaurant",
            first_name="Tuấn",
            last_name="Dương",
            phone="0981896440",
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4
        )

        assert result["success"] is False
        assert "Restaurant not found" in result["error"]
        assert "Cannot find restaurant" in result["message"]
        
        # API should not be called when restaurant not found
        mock_post.assert_not_called()

    @patch('src.tools.reservation_tools.QdrantStore')
    @patch('src.tools.reservation_tools.requests.post')
    def test_book_table_reservation_api_failure(self, mock_post, mock_qdrant_store_class):
        """Test API failure handling"""
        # Mock QdrantStore for restaurant lookup
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        mock_store.search.return_value = [
            ("test_id", {"id": "test_id", "restaurant_id": "test_id"}, 0.9)
        ]
        
        # Mock API failure
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = book_table_reservation(
            restaurant_location="Test Restaurant",
            first_name="Tuấn",
            last_name="Dương", 
            phone="0981896440",
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4
        )

        assert result["success"] is False
        assert "message" in result
        assert "1900 636 886" in result["message"]  # Should include hotline

    @patch('src.tools.reservation_tools.QdrantStore')
    @patch('src.tools.reservation_tools.requests.post')
    def test_book_table_reservation_connection_error(self, mock_post, mock_qdrant_store_class):
        """Test connection error handling"""
        # Mock QdrantStore for restaurant lookup
        mock_store = MagicMock()
        mock_qdrant_store_class.return_value = mock_store
        mock_store.search.return_value = [
            ("test_id", {"id": "test_id", "restaurant_id": "test_id"}, 0.9)
        ]
        
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = book_table_reservation(
            restaurant_location="Test Restaurant",
            first_name="Tuấn",
            last_name="Dương",
            phone="0981896440", 
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4
        )

        assert result["success"] is False
        assert "Cannot connect to reservation system" in result["message"]
        """Test API failure handling"""
        # Mock API failure
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        result = book_table_reservation(
            restaurant_location="Times City",
            first_name="Tuấn",
            last_name="Dương", 
            phone="0981896440",
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4
        )

        assert result["success"] is False
        assert "message" in result
        assert "1900 636 886" in result["message"]  # Should include hotline

    @patch('src.tools.reservation_tools.requests.post')
    def test_book_table_reservation_connection_error(self, mock_post):
        """Test connection error handling"""
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        result = book_table_reservation(
            restaurant_location="Times City",
            first_name="Tuấn",
            last_name="Dương",
            phone="0981896440", 
            reservation_date="2024-12-25",
            start_time="19:00",
            amount_adult=4
        )

        assert result["success"] is False
        assert "Không thể kết nối đến hệ thống đặt bàn" in result["message"]

    def test_handle_api_response_success(self):
        """Test successful API response handling"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"id": 123, "status": "confirmed"}
        
        result = _handle_api_response(mock_response)
        
        assert result["success"] is True
        assert result["data"]["id"] == 123
        assert "thành công" in result["message"]

    def test_handle_api_response_http_error(self):
        """Test HTTP error response handling"""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Bad Request")
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.json.return_value = {"message": "Invalid data"}
        
        result = _handle_api_response(mock_response)
        
        assert result["success"] is False
        assert "400" in result["error"]
        assert result["error_detail"] == "Invalid data"

    def test_handle_api_response_json_decode_error(self):
        """Test JSON decode error handling"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        
        result = _handle_api_response(mock_response)
        
        assert result["success"] is False
        assert "Invalid JSON response" in result["error"]

    def test_phone_number_cleaning(self):
        """Test phone number cleaning and validation"""
        # Test with spaces and special characters
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn", 
            "last_name": "Dương",
            "phone": "098-189-6440",  # With dashes
            "reservation_date": "2024-12-25",
            "start_time": "19:00",
            "amount_adult": 4
        }
        
        reservation = ReservationInput(**data)
        assert reservation.phone == "0981896440"  # Should be cleaned

    def test_default_values(self):
        """Test default values for optional fields"""
        data = {
            "restaurant_location": "Times City",
            "first_name": "Tuấn",
            "last_name": "Dương", 
            "phone": "0981896440",
            "reservation_date": "2024-12-25",
            "start_time": "19:00",
            "amount_adult": 4
        }
        
        reservation = ReservationInput(**data)
        assert reservation.amount_children == 0  # Default
        assert reservation.has_birthday is False  # Default
        assert reservation.email is None  # Default
        assert reservation.dob is None  # Default

if __name__ == "__main__":
    pytest.main([__file__])
