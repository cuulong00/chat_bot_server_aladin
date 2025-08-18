#!/usr/bin/env python3
"""
Quick debug script to see how LangChain tool descriptions work
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def debug_tool_properties():
    """Check what properties are available on the tool for LLM."""
    from src.tools.enhanced_memory_tools import save_user_preference_with_refresh_flag
    from src.tools.memory_tools import save_user_preference
    
    print("🔍 Enhanced Tool Properties:")
    print("=" * 50)
    
    enhanced = save_user_preference_with_refresh_flag
    original = save_user_preference
    
    print(f"Enhanced tool name: {enhanced.name}")
    print(f"Enhanced tool description: {enhanced.description}")
    print(f"Enhanced tool args_schema: {enhanced.args_schema}")
    print(f"Enhanced tool docstring: {enhanced.__doc__}")
    
    print("\n🔍 Original Tool Properties:")  
    print("=" * 50)
    print(f"Original tool name: {original.name}")
    print(f"Original tool description: {original.description}")
    print(f"Original tool args_schema: {original.args_schema}")
    print(f"Original tool docstring: {original.__doc__}")
    
    # Check if we can set description manually
    print(f"\n🔧 Attempting to update enhanced tool description...")
    enhanced.description = (
        "Save user preference information and automatically refresh user profile. "
        "This tool stores user preferences, habits, or personal information in their memory profile "
        "and signals that the user profile needs to be refreshed for immediate availability. "
        "Use this tool when: When the user provides new information about their preferences, habits, or interests; "
        "When user mentions likes/dislikes about food, drinks, atmosphere, service; "
        "When user shares personal details like dietary restrictions, allergies; "
        "When user mentions frequency of visits, usual group sizes, preferred times; "
        "When user talks about special occasions, celebrations, birthdays; "
        "When user expresses satisfaction/dissatisfaction with previous experiences. "
        "Examples: User says 'Tôi thích ăn cay' → preference_type='food_preference', preference_value='cay'; "
        "User says 'Tôi thường đặt bàn 6 người' → preference_type='group_size', preference_value='6 người'; "
        "User says 'Hôm nay sinh nhật con tôi' → preference_type='occasion', preference_value='sinh nhật con'"
    )
    
    print(f"✅ Updated description length: {len(enhanced.description)}")
    print(f"✅ Updated description contains 'preferences': {'preferences' in enhanced.description}")
    print(f"✅ Updated description contains 'Tôi thích ăn cay': {'Tôi thích ăn cay' in enhanced.description}")

if __name__ == "__main__":
    debug_tool_properties()
