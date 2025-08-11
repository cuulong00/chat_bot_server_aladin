import pytest
from langgraph.checkpoint.memory import MemorySaver
from src.graphs.travel.travel_graph import graph

@pytest.mark.asyncio
async def test_flight_assistant_delegation():
    config = {"configurable": {"thread_id": "test-flight-thread-2"}}
    messages = [
        ("user", "cho tôi biết những chuyến bay mà bạn có")
    ]
    final_state = await graph.ainvoke({"messages": messages}, config=config)
    
    # Check that the flight assistant was called and returned a response
    assert any("Chào bạn! Hiện tại, tôi có danh sách các chuyến bay có lịch khởi hành sau ngày 01-01-2025" in message.content for message in final_state['messages'])
