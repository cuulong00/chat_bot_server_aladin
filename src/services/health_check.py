"""
Health Check và Monitoring cho Redis Message Processing System
"""

import asyncio
import time
import json
from typing import Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

try:
    from .redis_message_queue import RedisMessageQueue
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

router = APIRouter(prefix="/health", tags=["Health Check"])

# Global references - sẽ được set bởi main app
_redis_queue: RedisMessageQueue = None
_message_aggregator = None
_facebook_service = None

def set_health_check_components(redis_queue, message_aggregator, facebook_service):
    """Set components for health checking"""
    global _redis_queue, _message_aggregator, _facebook_service
    _redis_queue = redis_queue
    _message_aggregator = message_aggregator
    _facebook_service = facebook_service

@router.get("/redis")
async def redis_health():
    """Kiểm tra sức khỏe Redis connection và streams"""
    if not REDIS_AVAILABLE:
        return JSONResponse({
            "status": "unavailable",
            "message": "Redis components not available",
            "timestamp": time.time()
        }, status_code=503)
    
    if not _redis_queue:
        return JSONResponse({
            "status": "not_initialized", 
            "message": "Redis queue not initialized",
            "timestamp": time.time()
        }, status_code=503)
    
    try:
        # Test Redis connection
        await asyncio.to_thread(_redis_queue.redis.ping)
        
        # Get stream info
        stream_info = await _redis_queue.get_stream_info()
        
        return JSONResponse({
            "status": "healthy",
            "redis": "connected",
            "stream_name": _redis_queue.config.stream_name,
            "consumer_group": _redis_queue.config.consumer_group,
            "stream_length": stream_info.get("length", 0),
            "last_generated_id": stream_info.get("last-generated-id", "N/A"),
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }, status_code=503)

@router.get("/messaging")
async def messaging_health():
    """Kiểm tra sức khỏe message processing system"""
    if not _message_aggregator:
        return JSONResponse({
            "status": "not_initialized",
            "message": "Message aggregator not initialized",
            "timestamp": time.time()
        }, status_code=503)
    
    try:
        metrics = _message_aggregator.get_metrics()
        
        # Calculate health score
        total_messages = metrics.get('total_messages', 0)
        processing_errors = metrics.get('processing_errors', 0)
        error_rate = (processing_errors / total_messages * 100) if total_messages > 0 else 0
        
        status = "healthy"
        if error_rate > 10:
            status = "degraded"
        elif error_rate > 25:
            status = "unhealthy"
        
        return JSONResponse({
            "status": status,
            "metrics": metrics,
            "error_rate_percent": round(error_rate, 2),
            "redis_available": REDIS_AVAILABLE,
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }, status_code=500)

@router.get("/facebook")
async def facebook_health():
    """Kiểm tra sức khỏe Facebook Messenger integration"""
    if not _facebook_service:
        return JSONResponse({
            "status": "not_initialized",
            "message": "Facebook service not initialized", 
            "timestamp": time.time()
        }, status_code=503)
    
    try:
        # Basic configuration check
        has_token = bool(_facebook_service.page_access_token)
        has_secret = bool(_facebook_service.app_secret)
        has_verify_token = bool(_facebook_service.verify_token)
        
        redis_processor_started = getattr(_facebook_service, '_redis_processor_started', False)
        
        return JSONResponse({
            "status": "healthy" if all([has_token, has_secret, has_verify_token]) else "misconfigured",
            "configuration": {
                "has_access_token": has_token,
                "has_app_secret": has_secret,
                "has_verify_token": has_verify_token,
                "api_version": _facebook_service.api_version,
                "page_id_configured": bool(_facebook_service.page_id)
            },
            "processing": {
                "redis_processor_started": redis_processor_started,
                "redis_available": REDIS_AVAILABLE,
                "legacy_mode": not REDIS_AVAILABLE
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }, status_code=500)

@router.get("/overall")
async def overall_health():
    """Tổng quan sức khỏe toàn bộ system"""
    try:
        # Get component health statuses
        redis_status = "unknown"
        messaging_status = "unknown" 
        facebook_status = "unknown"
        
        try:
            redis_response = await redis_health()
            redis_status = json.loads(redis_response.body.decode())["status"]
        except:
            redis_status = "error"
            
        try:
            messaging_response = await messaging_health()
            messaging_status = json.loads(messaging_response.body.decode())["status"]
        except:
            messaging_status = "error"
            
        try:
            facebook_response = await facebook_health()
            facebook_status = json.loads(facebook_response.body.decode())["status"]
        except:
            facebook_status = "error"
        
        # Determine overall status
        statuses = [redis_status, messaging_status, facebook_status]
        if all(s in ["healthy", "not_initialized"] for s in statuses):
            overall_status = "healthy"
        elif any(s == "unhealthy" for s in statuses):
            overall_status = "unhealthy"  
        else:
            overall_status = "degraded"
        
        return JSONResponse({
            "status": overall_status,
            "components": {
                "redis": redis_status,
                "messaging": messaging_status,
                "facebook": facebook_status
            },
            "system_info": {
                "redis_available": REDIS_AVAILABLE,
                "processing_mode": "smart_aggregation" if REDIS_AVAILABLE else "legacy_merging"
            },
            "timestamp": time.time()
        })
        
    except Exception as e:
        return JSONResponse({
            "status": "system_error",
            "error": str(e),
            "timestamp": time.time()
        }, status_code=500)

@router.get("/metrics")
async def detailed_metrics():
    """Chi tiết metrics để monitoring và debugging"""
    if not _message_aggregator:
        raise HTTPException(status_code=503, detail="Message aggregator not available")
    
    try:
        metrics = _message_aggregator.get_metrics()
        
        # Additional calculated metrics
        total_messages = metrics.get('total_messages', 0)
        merged_messages = metrics.get('merged_messages', 0)
        timeout_processed = metrics.get('timeout_processed', 0)
        
        merge_rate = (merged_messages / total_messages * 100) if total_messages > 0 else 0
        timeout_rate = (timeout_processed / total_messages * 100) if total_messages > 0 else 0
        
        enhanced_metrics = {
            **metrics,
            "calculated_metrics": {
                "merge_rate_percent": round(merge_rate, 2),
                "timeout_rate_percent": round(timeout_rate, 2),
                "immediate_processing_rate": round(100 - merge_rate - timeout_rate, 2)
            },
            "system_config": {
                "redis_available": REDIS_AVAILABLE,
                "smart_delay_enabled": getattr(_message_aggregator.config, 'smart_delay_enabled', False) if _message_aggregator else False
            },
            "timestamp": time.time()
        }
        
        return JSONResponse(enhanced_metrics)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics error: {str(e)}")

# Utility endpoint for testing
@router.post("/test/message-flow")
async def test_message_flow(test_data: Dict[str, Any]):
    """Test endpoint để simulate message flow"""
    if not REDIS_AVAILABLE or not _redis_queue:
        raise HTTPException(status_code=503, detail="Redis not available for testing")
    
    try:
        user_id = test_data.get("user_id", "test_user_123")
        event_type = test_data.get("event_type", "text")
        data = test_data.get("data", {})
        
        # Enqueue test event
        message_id = await _redis_queue.enqueue_event(user_id, event_type, data)
        
        return JSONResponse({
            "status": "test_enqueued",
            "message_id": message_id,
            "user_id": user_id,
            "event_type": event_type,
            "timestamp": time.time()
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")
