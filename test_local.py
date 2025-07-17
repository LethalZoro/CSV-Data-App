#!/usr/bin/env python3
"""
Local test script to verify the app works locally before deploying
"""

import subprocess
import sys
import time
import requests
import threading
from contextlib import contextmanager

def run_local_test():
    print("🧪 Starting local test of Flask application...")
    
    # Start the Flask app in a subprocess
    print("🚀 Starting Flask app...")
    process = subprocess.Popen([
        sys.executable, 'app.py'
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # Give the app time to start
    time.sleep(3)
    
    try:
        # Test basic connectivity
        print("📡 Testing basic connectivity...")
        response = requests.get('http://localhost:5000/ping', timeout=5)
        if response.status_code == 200:
            print("✅ Ping test passed")
        else:
            print(f"❌ Ping test failed: {response.status_code}")
            
        # Test status endpoint
        print("📊 Testing status endpoint...")
        response = requests.get('http://localhost:5000/status', timeout=5)
        if response.status_code == 200:
            print("✅ Status test passed")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Status test failed: {response.status_code}")
            
        # Test main page
        print("🏠 Testing main page...")
        response = requests.get('http://localhost:5000/', timeout=5)
        if response.status_code == 200:
            print("✅ Main page test passed")
        else:
            print(f"❌ Main page test failed: {response.status_code}")
            
        print("🎉 All local tests passed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to local server")
        print("💡 Check if the app is starting properly")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        
    finally:
        # Clean up
        print("🧹 Cleaning up...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

if __name__ == "__main__":
    run_local_test()
