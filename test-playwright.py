#!/usr/bin/env python3
"""
Quick test script to verify Playwright browser installation
"""
import os
import sys
from pathlib import Path

def test_playwright_installation():
    """Test if Playwright browsers are properly installed"""
    print("🔍 Testing Playwright browser installation...")
    
    # Check environment variables
    print(f"PLAYWRIGHT_BROWSERS_PATH: {os.getenv('PLAYWRIGHT_BROWSERS_PATH', 'Not set')}")
    print(f"CHROME_PATH: {os.getenv('CHROME_PATH', 'Not set')}")
    
    # Check common browser paths
    browser_paths = [
        "/ms-playwright/chromium-1169/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-1169/chrome-linux/chrome",
        "/ms-browsers/chromium-1169/chrome-linux/chrome"
    ]
    
    print("\n📁 Checking browser paths:")
    found_chrome = None
    for path in browser_paths:
        if Path(path).exists():
            print(f"✅ Found: {path}")
            found_chrome = path
        else:
            print(f"❌ Missing: {path}")
    
    # Try to import and test Playwright
    try:
        from playwright.sync_api import sync_playwright
        print("\n🎭 Testing Playwright import: ✅ Success")
        
        with sync_playwright() as p:
            print("🌐 Testing browser launch...")
            try:
                # Try with default settings first
                browser = p.chromium.launch(headless=True)
                print("✅ Browser launch successful with default settings")
                browser.close()
                return True
            except Exception as e:
                print(f"❌ Default browser launch failed: {e}")
                
                # Try with explicit executable path if found
                if found_chrome:
                    try:
                        browser = p.chromium.launch(
                            headless=True,
                            executable_path=found_chrome
                        )
                        print(f"✅ Browser launch successful with explicit path: {found_chrome}")
                        browser.close()
                        return True
                    except Exception as e2:
                        print(f"❌ Explicit path launch failed: {e2}")
                
                return False
                
    except ImportError as e:
        print(f"❌ Playwright import failed: {e}")
        return False

if __name__ == "__main__":
    success = test_playwright_installation()
    sys.exit(0 if success else 1)
