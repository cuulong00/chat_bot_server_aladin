#!/usr/bin/env python3
"""
Test script để kiểm tra hệ thống file-based error logging tập trung
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.logging_config import (
    setup_advanced_logging,
    log_exception_details,
    get_logger,
    log_business_event,
    log_performance_metric
)


def test_centralized_logging_system():
    """Test comprehensive centralized logging system functionality"""
    
    print("🔍 Testing centralized logging system...")
    
    # Initialize logging explicitly (though it's auto-initialized on import)
    setup_advanced_logging()
    print("✅ Centralized logging initialized")
    
    # Get logger for this module
    logger = get_logger(__name__)
    
    # Test different log levels
    logger.debug("Debug message - should appear in debug file only")
    logger.info("Info message - should appear in console and debug file")
    logger.warning("Warning message - should appear in console, debug, and warnings files")
    logger.error("Error message - should appear in all files")
    
    print("✅ Various log levels tested")
    
    # Test exception logging
    try:
        # Intentionally cause an error
        x = 1 / 0
    except Exception as e:
        log_exception_details(
            exception=e,
            context="Test division by zero error",
            user_id="test_user_123",
            module_name="test_module"
        )
        print("✅ Exception logged to file with module context")
    
    # Test business event logging
    log_business_event(
        event_type="user_registration",
        details={"user_id": "123", "email": "test@example.com"},
        user_id="123"
    )
    print("✅ Business event logged")
    
    # Test performance metric logging
    log_performance_metric(
        operation="database_query",
        duration_ms=123.45,
        details={"query": "SELECT * FROM users", "rows_returned": 10},
        user_id="test_user_123"
    )
    print("✅ Performance metric logged")
    
    # Check if log files exist
    logs_dir = Path("logs")
    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.log"))
        print(f"✅ Found {len(log_files)} log files:")
        for log_file in log_files:
            file_size = log_file.stat().st_size
            print(f"  - {log_file.name}: {file_size} bytes")
    else:
        print("❌ Logs directory not found")
    
    print("\n🎉 Centralized logging system test completed!")


if __name__ == "__main__":
    test_centralized_logging_system()
