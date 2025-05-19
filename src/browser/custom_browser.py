import asyncio
import pdb
import os

from patchright.async_api import Browser as PlaywrightBrowser
from patchright.async_api import (
    BrowserContext as PlaywrightBrowserContext,
)
from patchright.async_api import (
    Playwright,
    async_playwright,
)
from browser_use.browser.browser import Browser, IN_DOCKER
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from patchright.async_api import BrowserContext as PlaywrightBrowserContext
import logging

from browser_use.browser.chrome import (
    CHROME_ARGS,
    CHROME_DETERMINISTIC_RENDERING_ARGS,
    CHROME_DISABLE_SECURITY_ARGS,
    CHROME_DOCKER_ARGS,
    CHROME_HEADLESS_ARGS,
)
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.utils.screen_resolution import get_screen_resolution, get_window_adjustments
from browser_use.utils import time_execution_async
import socket

from .custom_context import CustomBrowserContext, CustomBrowserContextConfig

logger = logging.getLogger(__name__)


class CustomBrowser(Browser):

    async def new_context(self, config: CustomBrowserContextConfig | None = None) -> CustomBrowserContext:
        """Create a browser context"""
        browser_config = self.config.model_dump() if self.config else {}
        context_config = config.model_dump() if config else {}
        merged_config = {**browser_config, **context_config}
        return CustomBrowserContext(config=CustomBrowserContextConfig(**merged_config), browser=self)

    async def _setup_builtin_browser(self, playwright: Playwright) -> PlaywrightBrowser:
        """Sets up and returns a Playwright Browser instance with anti-detection measures."""
        assert self.config.browser_binary_path is None, 'browser_binary_path should be None if trying to use the builtin browsers'

        if self.config.headless:
            screen_size = {'width': 1920, 'height': 1080}
            offset_x, offset_y = 0, 0
        else:
            screen_size = get_screen_resolution()
            offset_x, offset_y = get_window_adjustments()

        # Filter out unsafe flags from all sets of Chrome arguments
        filtered_chrome_args = {arg for arg in CHROME_ARGS if arg != '--disable-setuid-sandbox'}
        filtered_disable_security_args = {arg for arg in CHROME_DISABLE_SECURITY_ARGS if arg != '--disable-setuid-sandbox'}
        filtered_docker_args = {arg for arg in CHROME_DOCKER_ARGS if arg != '--disable-setuid-sandbox'}
        
        chrome_args = {
            *filtered_chrome_args,
            *CHROME_DETERMINISTIC_RENDERING_ARGS,
            *self.config.extra_browser_args,
        }

        if self.config.headless:
            chrome_args.update(CHROME_HEADLESS_ARGS)

        if self.config.disable_security:
            chrome_args.update(filtered_disable_security_args)

        if IN_DOCKER:
            chrome_args.update(filtered_docker_args)

        # Modified port checking logic - assign a random port if running in AWS/ECS
        remote_debugging_port = '9222'
        if os.environ.get("AWS_EXECUTION_ENV") or os.environ.get("ECS_CONTAINER_METADATA_URI"):
            # Don't use the default 9222 port in AWS/ECS to avoid conflicts
            is_port_in_use = True
            try_port = 9222
            while is_port_in_use and try_port < 9300:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    is_port_in_use = s.connect_ex(('localhost', try_port)) == 0
                if is_port_in_use:
                    try_port += 1
            
            if is_port_in_use:
                # If all ports tried are in use, don't use remote debugging
                chrome_args = {arg for arg in chrome_args if not arg.startswith('--remote-debugging')}
                logger.info(f"All remote debugging ports in range 9222-9300 are in use, disabling remote debugging")
            else:
                # Update the port if a free one was found
                remote_debugging_port = str(try_port)
                chrome_args = {arg for arg in chrome_args if not arg.startswith('--remote-debugging-port=')}
                chrome_args.add(f'--remote-debugging-port={remote_debugging_port}')
                logger.info(f"Using remote debugging port: {remote_debugging_port}")
        else:
            # Regular check for local development
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', 9222)) == 0:
                    chrome_args = {arg for arg in chrome_args if not arg.startswith('--remote-debugging-port=')}
                    logger.info("Port 9222 is already in use, removing remote debugging port argument")

        # FINAL CRUCIAL STEP: Remove any scale factor arguments and ensure ours is the last one
        chrome_args = chrome_args
        
        logger.info(f"Chrome args: {list(chrome_args)[:10]}")
        
        browser_class = getattr(playwright, self.config.browser_class)
        args = {
            'chromium': list(chrome_args),
            'firefox': [
                *{
                    '-no-remote',
                    *self.config.extra_browser_args,
                }
            ],
            'webkit': [
                *{
                    '--no-startup-window',
                    *self.config.extra_browser_args,
                }
            ],
        }

        browser = await browser_class.launch(
            headless=self.config.headless,
            args=args[self.config.browser_class],
            proxy=self.config.proxy.model_dump() if self.config.proxy else None,
            handle_sigterm=False,
            handle_sigint=False,
        )
        return browser
