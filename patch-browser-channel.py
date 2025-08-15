#!/usr/bin/env python3
"""
Patch browser-use to use Chrome channel as fallback for better compatibility
"""
import os
import re

def patch_browser_channel():
    """Patch the custom_browser.py to use Chrome channel as fallback"""
    print("🔧 Patching browser channel for better compatibility...")
    
    browser_file = "/app/src/browser/custom_browser.py"
    
    if not os.path.exists(browser_file):
        print(f"❌ Browser file not found: {browser_file}")
        return False
    
    # Read the current file
    with open(browser_file, 'r') as f:
        content = f.read()
    
    # Original browser launch code
    original_pattern = r"browser = await browser_class\.launch\(\s*channel='chromium',.*?\)"
    
    # New browser launch code with fallback
    replacement = """try:
            # Try with chromium channel first
            browser = await browser_class.launch(
                channel='chromium',
                headless=self.config.headless,
                args=args[self.config.browser_class],
                proxy=self.config.proxy.model_dump() if self.config.proxy else None,
                handle_sigterm=False,
                handle_sigint=False,
            )
        except Exception as e:
            logger.warning(f"Failed to launch with chromium channel: {e}")
            logger.info("Trying with chrome channel as fallback...")
            try:
                # Fallback to chrome channel
                browser = await browser_class.launch(
                    channel='chrome',
                    headless=self.config.headless,
                    args=args[self.config.browser_class],
                    proxy=self.config.proxy.model_dump() if self.config.proxy else None,
                    handle_sigterm=False,
                    handle_sigint=False,
                )
            except Exception as e2:
                logger.error(f"Failed to launch with chrome channel: {e2}")
                logger.info("Trying without channel specification...")
                # Final fallback without channel
                browser = await browser_class.launch(
                    headless=self.config.headless,
                    args=args[self.config.browser_class],
                    proxy=self.config.proxy.model_dump() if self.config.proxy else None,
                    handle_sigterm=False,
                    handle_sigint=False,
                )"""
    
    # Apply the patch
    new_content = re.sub(
        original_pattern,
        replacement,
        content,
        flags=re.DOTALL | re.MULTILINE
    )
    
    if new_content == content:
        print("❌ Failed to find browser launch code to patch")
        return False
    
    # Write the patched file
    with open(browser_file, 'w') as f:
        f.write(new_content)
    
    print("✅ Successfully patched browser channel with fallback logic")
    return True

if __name__ == "__main__":
    success = patch_browser_channel()
    exit(0 if success else 1)
