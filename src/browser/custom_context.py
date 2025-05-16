import json
import logging
import os

from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from patchright.async_api import Browser as PlaywrightBrowser
from patchright.async_api import BrowserContext as PlaywrightBrowserContext
from patchright.async_api import ViewportSize, HttpCredentials, Geolocation
from typing import Optional, cast
from browser_use.browser.context import BrowserContextState

logger = logging.getLogger(__name__)


class CustomBrowserContextConfig(BrowserContextConfig):
    force_new_context: bool = False  # force to create new context


class CustomBrowserContext(BrowserContext):
    def __init__(
            self,
            browser: 'Browser',
            config: BrowserContextConfig | None = None,
            state: Optional[BrowserContextState] = None,
    ):
        super(CustomBrowserContext, self).__init__(browser=browser, config=config, state=state)

    async def _create_context(self, browser: PlaywrightBrowser):
        """Creates a new browser context with anti-detection measures and loads cookies if available."""
        if not self.config.force_new_context and self.browser.config.cdp_url and len(browser.contexts) > 0:
            context = browser.contexts[0]
        elif not self.config.force_new_context and self.browser.config.browser_binary_path and len(
                browser.contexts) > 0:
            # Connect to existing Chrome instance instead of creating new one
            context = browser.contexts[0]
        else:
            # Original code for creating new context
            context = await browser.new_context(
                no_viewport=True,
                user_agent=self.config.user_agent,
                java_script_enabled=True,
                bypass_csp=self.config.disable_security,
                ignore_https_errors=self.config.disable_security,
                record_video_dir=self.config.save_recording_path,
                record_video_size=ViewportSize(
                    width=self.config.browser_window_size.width,
                    height=self.config.browser_window_size.height
                ),
                record_har_path=self.config.save_har_path,
                locale=self.config.locale,
                http_credentials=cast(HttpCredentials, self.config.http_credentials) if self.config.http_credentials else None,
                is_mobile=self.config.is_mobile,
                has_touch=self.config.has_touch,
                geolocation=cast(Geolocation, self.config.geolocation) if self.config.geolocation else None,
                permissions=self.config.permissions,
                timezone_id=self.config.timezone_id,
            )

        if self.config.trace_path:
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        # Load cookies if they exist
        if self.config.cookies_file and os.path.exists(self.config.cookies_file):
            with open(self.config.cookies_file, 'r') as f:
                try:
                    cookies = json.load(f)

                    valid_same_site_values = ['Strict', 'Lax', 'None']
                    for cookie in cookies:
                        if 'sameSite' in cookie:
                            if cookie['sameSite'] not in valid_same_site_values:
                                logger.warning(
                                    f"Fixed invalid sameSite value '{cookie['sameSite']}' to 'None' for cookie {cookie.get('name')}"
                                )
                                cookie['sameSite'] = 'None'
                    logger.info(f'🍪  Loaded {len(cookies)} cookies from {self.config.cookies_file}')
                    await context.add_cookies(cookies)

                except json.JSONDecodeError as e:
                    logger.error(f'Failed to parse cookies file: {str(e)}')

        # Expose anti-detection scripts
        await context.add_init_script(
            """
            // Webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US']
            });

            // Plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Chrome runtime
            window.chrome = { runtime: {} };

            // Set real zoom on page load - cross-browser
            document.addEventListener('DOMContentLoaded', function() {
                // Create a style element
                const style = document.createElement('style');
                style.textContent = `
                    html {
                        transform: scale(0.8);
                        transform-origin: 0 0;
                        width: 125%; /* 100% / 0.7 */
                        height: 125%; /* 100% / 0.7 */
                        overflow-x: hidden;
                    }
                `;
                document.head.appendChild(style);
                
                // Alternative direct method for Chrome
                if (document.body) {
                    document.body.style.zoom = '0.8';
                }
                
                console.log('Applied custom zoom via CSS transform');
            });

            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            (function () {
                const originalAttachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function attachShadow(options) {
                    return originalAttachShadow.call(this, { ...options, mode: "open" });
                };
            })();
            """
        )

        return context
