import os
import sys
import time
import asyncio
from typing import Optional, Tuple
from app.config import (
    BASE_DIR,
    UPSTREAM_URL,
    UPSTREAM_EMAIL,
    UPSTREAM_PASSWORD,
    SESSION_STORAGE_DIR
)

ENV_FILE = os.path.join(BASE_DIR, ".env")

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class SessionRefresher:
    """
    Automated Session Manager.
    Logs into the upstream provider using credentials, extracts the fresh
    session cookie (connect.sid), and writes it directly to .env.
    """

    def __init__(self):
        self.email = UPSTREAM_EMAIL
        self.password = UPSTREAM_PASSWORD
        self.url = UPSTREAM_URL
        self.storage_dir = SESSION_STORAGE_DIR
        self._refresh_lock = asyncio.Lock()

    def update_env_cookie(self, new_cookie: str) -> bool:
        """Saves the fresh session cookie to .env file."""
        if not new_cookie or not os.path.exists(ENV_FILE):
            return False

        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            updated_upstream = False

            for line in lines:
                if line.strip().startswith("UPSTREAM_SESSION_COOKIE="):
                    new_lines.append(f"UPSTREAM_SESSION_COOKIE={new_cookie}\n")
                    updated_upstream = True
                elif line.strip().startswith("SESSION_COOKIE="):
                    new_lines.append(f"SESSION_COOKIE={new_cookie}\n")
                    updated_upstream = True
                else:
                    new_lines.append(line)

            if not updated_upstream:
                new_lines.append(f"UPSTREAM_SESSION_COOKIE={new_cookie}\n")

            with open(ENV_FILE, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            # Update live runtime variable in config
            import app.config as cfg
            cfg.SESSION_COOKIE = new_cookie

            print("[+] [SessionRefresher] Fresh session cookie successfully synced to .env & runtime memory!")
            return True
        except Exception as e:
            print(f"[-] [SessionRefresher] Failed to save cookie to .env: {e}")
            return False

    async def auto_refresh_session(self) -> Tuple[bool, str]:
        """
        Launches headless browser, navigates to login, signs in, and extracts fresh connect.sid.
        """
        if not HAS_PLAYWRIGHT:
            return False, "Playwright is not installed. Run: pip install playwright && playwright install"

        if not self.email or not self.password:
            return False, (
                "No UPSTREAM_EMAIL and UPSTREAM_PASSWORD configured in .env. "
                "Add your credentials to enable automatic session rejuvenation."
            )

        async with self._refresh_lock:
            print(f"[*] [SessionRefresher] Attempting automated headless login for: {self.email}...")

            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch_persistent_context(
                        user_data_dir=self.storage_dir,
                        headless=True,
                        viewport={"width": 1280, "height": 720},
                        args=["--disable-blink-features=AutomationControlled"]
                    )

                    page = browser.pages[0] if browser.pages else await browser.new_page()
                    await page.goto(f"{self.url}/login", timeout=30000)
                    await asyncio.sleep(2)

                    # Check if already logged in by inspecting cookies
                    cookies = await browser.cookies()
                    sid_cookie = next((c["value"] for c in cookies if c["name"] == "connect.sid"), None)

                    # Look for login form elements
                    email_input = await page.query_selector("input[type='email'], input[name='email'], input[name='username']")
                    password_input = await page.query_selector("input[type='password'], input[name='password']")

                    if email_input and password_input:
                        print("[*] [SessionRefresher] Entering credentials...")
                        await email_input.fill(self.email)
                        await password_input.fill(self.password)

                        # Click submit button
                        submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Login')")
                        if submit_btn:
                            await submit_btn.click()
                            print("[*] [SessionRefresher] Waiting for authentication...")
                            await asyncio.sleep(5)

                    # Poll for fresh connect.sid cookie
                    for _ in range(5):
                        cookies = await browser.cookies()
                        sid_cookie = next((c["value"] for c in cookies if c["name"] == "connect.sid"), None)
                        if sid_cookie:
                            break
                        await asyncio.sleep(2)

                    await browser.close()

                    if sid_cookie:
                        self.update_env_cookie(sid_cookie)
                        return True, f"Session refreshed successfully. Active cookie: {sid_cookie[:15]}..."
                    else:
                        return False, "Login completed but connect.sid cookie was not detected. Cloudflare CAPTCHA may be present."

            except Exception as e:
                print(f"[-] [SessionRefresher] Error during automated login: {e}")
                return False, f"Automated login error: {e}"

session_refresher = SessionRefresher()
