"""Tools package for the LangGraph agent."""

# Import all tools to make them available
from . import car_tools
from . import excursion_tools 
from . import flight_tools
from . import hotel_tools
from . import primary_assistant_tools

# Import memory tools if they exist
try:
    from . import memory_tools
    from .memory_tools import save_user_preference, get_user_profile
    __all__ = [
        "car_tools", 
        "excursion_tools", 
        "flight_tools", 
        "hotel_tools", 
        "primary_assistant_tools",
        "memory_tools",
        "save_user_preference", 
        "get_user_profile"
    ]
except ImportError:
    __all__ = [
        "car_tools", 
        "excursion_tools", 
        "flight_tools", 
        "hotel_tools", 
        "primary_assistant_tools"
    ]
