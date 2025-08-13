#!/usr/bin/env python3
"""
Monitor Facebook Webhook Activity
Real-time monitoring script để theo dõi webhook calls
"""

import requests
import time
import json
from datetime import datetime

def check_webhook_health():
    """Check if webhook is still responding"""
    try:
        response = requests.get("https://ai-agent.onl/api/facebook/webhook", params={
            "hub.mode": "subscribe",
            "hub.verify_token": "gauvatho", 
            "hub.challenge": f"health_check_{int(time.time())}"
        }, timeout=5)
        
        return response.status_code == 200
    except:
        return False

def check_server_status():
    """Check overall server status"""
    try:
        response = requests.get("https://ai-agent.onl", timeout=5)
        return response.status_code in [200, 404, 405]
    except:
        return False

def main():
    print("🔍 Facebook Webhook Activity Monitor")
    print("=" * 50)
    print("Monitoring webhook health every 30 seconds...")
    print("Press Ctrl+C to stop\n")
    
    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check webhook
            webhook_ok = check_webhook_health()
            webhook_status = "✅ OK" if webhook_ok else "❌ FAIL"
            
            # Check server
            server_ok = check_server_status()
            server_status = "✅ OK" if server_ok else "❌ FAIL"
            
            print(f"[{timestamp}] Webhook: {webhook_status} | Server: {server_status}")
            
            if not webhook_ok or not server_ok:
                print("⚠️ Alert: Issues detected!")
                
            time.sleep(30)
            
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped.")
            break
        except Exception as e:
            print(f"❌ Monitor error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
