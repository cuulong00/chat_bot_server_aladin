"""
Hệ thống logging tập trung cho toàn bộ ứng dụng chatbot
Hỗ trợ file-based logging với rotation và multiple handlers
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional


def setup_advanced_logging(logs_dir: str = "logs", log_level: str = "INFO") -> None:
    """
    Setup comprehensive logging system with file output for errors and exceptions.
    
    Features:
    - Multiple log files: debug, error, warnings
    - Daily rotation based on filename
    - UTF-8 encoding for Vietnamese support
    - Console output for INFO+ levels
    - File output for all levels with detailed formatting
    
    Args:
        logs_dir: Directory to store log files (default: "logs")
        log_level: Minimum log level for console output (default: "INFO")
    """
    # Create logs directory if it doesn't exist
    logs_path = Path(logs_dir)
    logs_path.mkdir(exist_ok=True)
    
    # Clear existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set root logger level to DEBUG to capture everything
    root_logger.setLevel(logging.DEBUG)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Generate daily log file names
    date_str = datetime.now().strftime("%Y%m%d")
    debug_file = logs_path / f"debug_{date_str}.log"
    error_file = logs_path / f"error_{date_str}.log"
    warnings_file = logs_path / f"warnings_{date_str}.log"
    
    # 1. Console Handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 2. Debug File Handler (everything)
    debug_handler = logging.FileHandler(debug_file, encoding='utf-8')
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(debug_handler)
    
    # 3. Error File Handler (ERROR and above)
    error_handler = logging.FileHandler(error_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # 4. Warnings File Handler (WARNING and above)
    warnings_handler = logging.FileHandler(warnings_file, encoding='utf-8')
    warnings_handler.setLevel(logging.WARNING)
    warnings_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(warnings_handler)
    
    # Log initialization message
    logging.info(f"🔧 Advanced logging initialized - logs saved to: {logs_path.absolute()}")


def log_exception_details(exception: Exception, context: str = "", user_id: Optional[str] = None, module_name: str = "system") -> None:
    """
    Log detailed exception information to error files with full context.
    
    Args:
        exception: The exception that occurred
        context: Additional context about what was happening when the error occurred
        user_id: User ID for tracking user-specific errors (optional)
        module_name: Name of the module/service where error occurred (optional)
    """
    # Prepare detailed error information
    error_details = {
        "timestamp": datetime.now().isoformat(),
        "module": module_name,
        "exception_type": type(exception).__name__,
        "exception_message": str(exception),
        "context": context,
        "user_id": user_id or "unknown",
        "traceback": traceback.format_exc()
    }
    
    # Format detailed error message
    error_message = (
        f"🚨 EXCEPTION DETAILS:\n"
        f"Module: {error_details['module']}\n"
        f"Context: {error_details['context']}\n"
        f"User ID: {error_details['user_id']}\n"
        f"Exception Type: {error_details['exception_type']}\n"
        f"Exception Message: {error_details['exception_message']}\n"
        f"Full Traceback:\n{error_details['traceback']}"
    )
    
    # Log to error level (will appear in error and warnings files)
    logging.error(error_message)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module/service.
    
    Args:
        name: Name of the logger (usually __name__)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)


def log_business_event(event_type: str, details: dict, user_id: Optional[str] = None, level: str = "INFO") -> None:
    """
    Log business events with structured information.
    
    Args:
        event_type: Type of business event (e.g., "user_registration", "order_created")
        details: Dictionary containing event details
        user_id: User ID associated with the event (optional)
        level: Log level for the event (default: "INFO")
    """
    logger = get_logger("business_events")
    
    event_message = (
        f"📊 BUSINESS EVENT: {event_type}\n"
        f"User ID: {user_id or 'unknown'}\n"
        f"Details: {details}\n"
        f"Timestamp: {datetime.now().isoformat()}"
    )
    
    log_level = getattr(logging, level.upper())
    logger.log(log_level, event_message)


def log_performance_metric(operation: str, duration_ms: float, details: dict = None, user_id: Optional[str] = None) -> None:
    """
    Log performance metrics for monitoring.
    
    Args:
        operation: Name of the operation being measured
        duration_ms: Duration in milliseconds
        details: Additional details about the operation
        user_id: User ID associated with the operation (optional)
    """
    logger = get_logger("performance")
    
    metric_message = (
        f"⚡ PERFORMANCE METRIC: {operation}\n"
        f"Duration: {duration_ms:.2f}ms\n"
        f"User ID: {user_id or 'unknown'}\n"
        f"Details: {details or {}}\n"
        f"Timestamp: {datetime.now().isoformat()}"
    )
    
    logger.info(metric_message)


# Auto-initialize logging when module is imported
if not logging.getLogger().handlers:
    setup_advanced_logging()
