#!/usr/bin/env python3
"""
Fix Playwright browser paths for browser-use compatibility
"""
import os
import glob
import shutil
from pathlib import Path

def fix_playwright_paths():
    """Fix Playwright browser paths to match browser-use expectations"""
    print("🔧 Fixing Playwright browser paths...")
    
    # Common Playwright installation paths
    playwright_paths = [
        "/root/.cache/ms-playwright",
        "/ms-playwright",
        os.path.expanduser("~/.cache/ms-playwright")
    ]
    
    found_browsers = []
    for path in playwright_paths:
        if os.path.exists(path):
            print(f"✅ Found Playwright path: {path}")
            # Find chromium installations
            chromium_dirs = glob.glob(f"{path}/chromium-*")
            for chromium_dir in chromium_dirs:
                chrome_exe = os.path.join(chromium_dir, "chrome-linux", "chrome")
                if os.path.exists(chrome_exe):
                    found_browsers.append((chromium_dir, chrome_exe))
                    print(f"✅ Found Chrome at: {chrome_exe}")
    
    if not found_browsers:
        print("❌ No Chrome installations found!")
        return False
    
    # Use the most recent installation
    latest_browser = sorted(found_browsers, key=lambda x: os.path.basename(x[0]))[-1]
    chromium_dir, chrome_exe = latest_browser
    
    print(f"🎯 Using latest Chrome: {chrome_exe}")
    
    # Create expected paths for browser-use
    expected_paths = [
        "/ms-playwright/chromium-1169/chrome-linux/chrome",
        "/ms-browsers/chromium-1169/chrome-linux/chrome"
    ]
    
    for expected_path in expected_paths:
        expected_dir = os.path.dirname(expected_path)
        expected_parent = os.path.dirname(expected_dir)
        
        # Create directory structure
        os.makedirs(expected_parent, exist_ok=True)
        
        # Create symlink to actual chrome installation
        if os.path.exists(expected_path) or os.path.islink(expected_path):
            os.unlink(expected_path)
        
        # Create symlink to the chrome-linux directory
        actual_chrome_linux = os.path.dirname(chrome_exe)
        if os.path.exists(expected_dir) or os.path.islink(expected_dir):
            if os.path.islink(expected_dir):
                os.unlink(expected_dir)
            else:
                shutil.rmtree(expected_dir)
        
        os.symlink(actual_chrome_linux, expected_dir)
        print(f"🔗 Created symlink: {expected_dir} -> {actual_chrome_linux}")
    
    # Verify the fix
    for expected_path in expected_paths:
        if os.path.exists(expected_path):
            print(f"✅ Verified: {expected_path}")
        else:
            print(f"❌ Failed to create: {expected_path}")
    
    return True

if __name__ == "__main__":
    success = fix_playwright_paths()
    exit(0 if success else 1)
