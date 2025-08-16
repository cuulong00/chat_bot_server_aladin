"""
Integration test cho toàn bộ hệ thống memory với LangGraph
"""

import os
import sys

# Thêm root directory vào Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid

# Import với absolute path từ root
from src.graphs.travel.travel_graph import graph

# Import memory tools
try:
    from src.tools.memory_tools import save_user_preference, get_user_profile

    MEMORY_AVAILABLE = True
except ImportError as e:
    print(f"Memory tools not available: {e}")
    MEMORY_AVAILABLE = False


def test_memory_integration():
    """Test tích hợp memory system với LangGraph"""
    if not MEMORY_AVAILABLE:
        print("❌ Memory tools not available, skipping integration test")
        return

    print("🧪 Testing Full Memory Integration with LangGraph...")

    # Setup
    test_user_id = "test_integration_user"
    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "user_id": test_user_id,
            "thread_id": thread_id,
        }
    }

    # Test 1: Trước tiên, lưu một số preference
    print("\n1. Setting up user preferences...")
    preferences = [
        (
            "dietary_restriction",
            "vegetarian, no seafood",
            "mentioned during conversation",
        ),
        ("seat_preference", "window seat", "prefers to look outside"),
        (
            "budget_range",
            "economy to premium economy",
            "cost-conscious but values comfort",
        ),
    ]

    for pref_type, content, context in preferences:
        result = save_user_preference.invoke(
            {
                "user_id": test_user_id,
                "preference_type": pref_type,
                "content": content,
                "context": context,
            }
        )
        print(f"  ✅ {result}")

    # Test 2: Test conversation với memory
    print("\n2. Testing conversation with memory...")

    test_conversations = [
        "Xin chào, tôi muốn tìm hiểu về chuyến bay của mình",
        "Tôi có thể thay đổi chỗ ngồi không?",
        "Tôi muốn đặt phòng khách sạn",
        "Có khuyến nghị gì về ăn uống không?",
    ]

    for i, message in enumerate(test_conversations, 1):
        print(f"\n  Test {i}: {message}")
        try:
            # Stream events from the graph
            events = list(
                graph.stream(
                    {"messages": [("user", message)]}, config, stream_mode="values"
                )
            )

            if events:
                final_event = events[-1]
                if "messages" in final_event:
                    last_message = final_event["messages"][-1]
                    if hasattr(last_message, "content"):
                        print(f"    Bot response: {last_message.content[:200]}...")

                # Check if user_profile was retrieved
                if "user_profile" in final_event:
                    print(f"    User profile: {final_event['user_profile'][:100]}...")

        except Exception as e:
            print(f"    ❌ Error in conversation {i}: {e}")

    # Test 3: Kiểm tra việc lưu preference mới trong conversation
    print("\n3. Testing automatic preference saving...")
    preference_message = (
        "Tôi thích bay vào buổi sáng và không thích chỗ ngồi giữa máy bay"
    )

    try:
        events = list(
            graph.stream(
                {"messages": [("user", preference_message)]},
                config,
                stream_mode="values",
            )
        )
        print("  ✅ Conversation completed, checking if preferences were saved...")

        # Check if new preferences were saved
        profile = get_user_profile.invoke(
            {"user_id": test_user_id, "query_context": "flight preferences"}
        )
        print(f"  Updated profile: {profile}")

    except Exception as e:
        print(f"  ❌ Error testing preference saving: {e}")

    print("\n✅ Full memory integration test completed!")


def test_memory_retrieval_context():
    """Test context-aware memory retrieval"""
    if not MEMORY_AVAILABLE:
        print("❌ Memory tools not available, skipping context test")
        return

    print("\n🧪 Testing Context-Aware Memory Retrieval...")

    test_user_id = "context_test_user"

    # Setup diverse preferences
    preferences = [
        ("flight_preference", "morning flights, aisle seat", "business travel"),
        ("hotel_preference", "4-star, near city center", "work trips"),
        ("dietary_restriction", "gluten-free", "health condition"),
        ("travel_companion", "usually travels alone", "business traveler"),
        ("car_rental_preference", "compact, automatic", "city driving"),
    ]

    for pref_type, content, context in preferences:
        save_user_preference.invoke(
            {
                "user_id": test_user_id,
                "preference_type": pref_type,
                "content": content,
                "context": context,
            }
        )

    # Test context-specific retrieval
    contexts = [
        ("flight booking", "flight"),
        ("hotel booking", "hotel"),
        ("car rental", "car"),
        ("meal planning", "dietary"),
        ("general travel", ""),
    ]

    for context_name, context_query in contexts:
        profile = get_user_profile.invoke(
            {"user_id": test_user_id, "query_context": context_query}
        )
        print(f"\n  Context '{context_name}':")
        print(f"    Profile: {profile}")


if __name__ == "__main__":
    # Hệ thống được khởi tạo khi import (database.py, graph.py)
    # nên không cần gọi setup riêng ở đây nữa.
    print("🚀 Starting integration tests...")

    print("\n" + "=" * 50)

    # Run integration test
    test_memory_integration()

    print("\n" + "=" * 50)

    # Run context test
    test_memory_retrieval_context()

    print("\n" + "=" * 50)
    print("✅ All tests completed.")
