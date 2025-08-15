#!/usr/bin/env python3
"""
Fix Playwright browser paths for browser-use compatibility
This script ensures that the correct Chromium executable is available
"""
import os
import sys
import subprocess
from pathlib import Path
import glob

def find_chromium_executable():
    """Find the actual Chromium executable installed by Playwright"""
    possible_paths = [
        "/ms-playwright/chromium-*/chrome-linux/chrome",
        "/root/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
        "/home/*/.cache/ms-playwright/chromium-*/chrome-linux/chrome",
    ]
    
    for pattern in possible_paths:
        matches = glob.glob(pattern)
        if matches:
            # Return the first match (should be the most recent)
            return matches[0]
    
    return None

def create_symlinks(actual_path, target_path="/ms-playwright/chromium-1169/chrome-linux/chrome"):
    """Create symlinks to make browser-use find the correct executable"""
    try:
        # Create target directory structure
        target_dir = Path(target_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing symlink if it exists
        if Path(target_path).exists():
            Path(target_path).unlink()
        
        # Create symlink
        Path(target_path).symlink_to(actual_path)
        print(f"✅ Created symlink: {target_path} -> {actual_path}")
        
        # Also create the directory structure that browser-use expects
        browser_dir = Path(actual_path).parent.parent
        target_browser_dir = Path("/ms-playwright/chromium-1169")
        
        if not target_browser_dir.exists():
            target_browser_dir.symlink_to(browser_dir)
            print(f"✅ Created browser directory symlink: {target_browser_dir} -> {browser_dir}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create symlinks: {e}")
        return False

def test_playwright_installation():
    """Test if Playwright can launch Chromium"""
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Try default launch first
            try:
                browser = p.chromium.launch(headless=True)
                print("✅ Playwright can launch Chromium with default settings")
                browser.close()
                return True
            except Exception as e1:
                print(f"⚠️ Default launch failed: {e1}")
                
                # Try with chrome channel as fallback
                try:
                    browser = p.chromium.launch(channel="chrome", headless=True)
                    print("✅ Playwright can launch Chromium with chrome channel")
                    browser.close()
                    return True
                except Exception as e2:
                    print(f"❌ Chrome channel launch also failed: {e2}")
                    return False
                    
    except ImportError:
        print("❌ Playwright not installed")
        return False

def main():
    print("🔧 Fixing Playwright browser paths for browser-use compatibility...")
    
    # First, try to find the actual Chromium executable
    actual_chrome = find_chromium_executable()
    
    if actual_chrome:
        print(f"📍 Found Chromium at: {actual_chrome}")
        
        # Make sure it's executable
        os.chmod(actual_chrome, 0o755)
        
        # Create symlinks for browser-use compatibility
        if create_symlinks(actual_chrome):
            print("✅ Symlinks created successfully")
        else:
            print("⚠️ Failed to create symlinks")
    else:
        print("❌ Could not find Chromium executable")
        print("🔍 Available Playwright browsers:")
        try:
            result = subprocess.run(['playwright', 'list'], capture_output=True, text=True)
            print(result.stdout)
        except:
            print("Could not list browsers")
    
    # Test the installation
    print("\n🧪 Testing Playwright installation...")
    if test_playwright_installation():
        print("✅ Playwright installation test passed")
        sys.exit(0)
    else:
        print("❌ Playwright installation test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
