#!/usr/bin/env python3
"""
Startup test script to verify the app can start properly
"""

import sys
import os

def test_startup():
    print("🧪 Testing application startup...")
    
    try:
        # Test 1: Import the app
        print("1️⃣ Testing app import...")
        import app
        print("✅ App import successful")
        
        # Test 2: Check Flask app creation
        print("2️⃣ Testing Flask app...")
        flask_app = app.app
        print(f"✅ Flask app created: {flask_app}")
        
        # Test 3: Check database configuration
        print("3️⃣ Testing database config...")
        with flask_app.app_context():
            db_uri = flask_app.config['SQLALCHEMY_DATABASE_URI']
            if 'sqlite' in db_uri:
                print(f"✅ Database: SQLite ({db_uri})")
            elif 'postgresql' in db_uri:
                print(f"✅ Database: PostgreSQL")
            else:
                print(f"⚠️ Database: Unknown type ({db_uri})")
        
        # Test 4: Check routes
        print("4️⃣ Testing routes...")
        routes = [str(rule) for rule in flask_app.url_map.iter_rules()]
        print(f"✅ Found {len(routes)} routes")
        
        print("🎉 All startup tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_startup()
    sys.exit(0 if success else 1)
