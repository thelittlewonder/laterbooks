"""Goodreads shelf automation via Playwright."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import settings

logger = logging.getLogger(__name__)

ShelfStatus = Literal["on_shelf", "added", "unknown", "failed"]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ShelfCheckResult:
    title: str
    status: ShelfStatus
    message: str | None = None


class GoodreadsAutomation:
    def __init__(self) -> None:
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._logged_in = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._browser is not None:
            return

        playwright = await async_playwright().start()
        self._browser = await playwright.chromium.launch(
            headless=settings.playwright_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )

        storage_state = _load_storage_state()
        self._context = await self._browser.new_context(
            user_agent=_USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            storage_state=storage_state,
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        self._page = await self._context.new_page()

        if storage_state:
            await self._verify_session()
        else:
            await self._login_with_credentials()

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False

    async def _verify_session(self) -> None:
        assert self._page is not None
        page = self._page

        await page.goto("https://www.goodreads.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        if await self._is_logged_in(page):
            self._logged_in = True
            logger.info("Goodreads session restored from storage state")
            return

        if settings.goodreads_email and settings.goodreads_password:
            logger.warning("Stored session expired — falling back to credential login")
            await self._login_with_credentials()
            return

        raise RuntimeError(
            "Goodreads session expired. Re-export session with "
            "python scripts/export_goodreads_session.py and update GOODREADS_STORAGE_STATE."
        )

    async def _login_with_credentials(self) -> None:
        if not settings.goodreads_email or not settings.goodreads_password:
            raise RuntimeError(
                "Goodreads not configured. Set GOODREADS_STORAGE_STATE or "
                "GOODREADS_EMAIL and GOODREADS_PASSWORD."
            )

        assert self._page is not None
        page = self._page

        await page.goto(
            "https://www.goodreads.com/user/sign_in",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(2000)

        await self._open_goodreads_email_form(page)

        if await self._try_goodreads_native_login(page):
            self._logged_in = True
            logger.info("Logged in to Goodreads with email/password")
            return

        logger.info("Goodreads email form not found — trying Amazon sign-in")
        await self._click_amazon_sign_in(page)

        if "amazon." not in page.url:
            await page.goto(
                "https://www.amazon.com/ap/signin?openid.return_to="
                + quote("https://www.goodreads.com/ap-handler/sign-in", safe="")
                + "&openid.assoc_handle=amzn_goodreads_desktop_us"
                + "&openid.mode=checkid_setup&siteState=xxx",
                wait_until="domcontentloaded",
            )

        await self._amazon_sign_in(page)

        try:
            await page.wait_for_url(re.compile(r"goodreads\.com"), timeout=60_000)
        except Exception:
            await self._raise_login_error(page)

        await page.wait_for_timeout(2000)

        if not await self._is_logged_in(page):
            await self._raise_login_error(page)

        self._logged_in = True
        logger.info("Logged in to Goodreads via Amazon")

    async def _open_goodreads_email_form(self, page: Page) -> None:
        """Switch from Amazon default to Goodreads email/password form if needed."""
        native_email = page.locator(
            'input[name="user[email]"], input#user_email, input#user_sign_in_email'
        ).first
        if await native_email.count() > 0 and await native_email.is_visible():
            return

        email_link = page.locator(
            'a:has-text("email"), a:has-text("Goodreads password"), '
            'a:has-text("standard sign"), .authPortalMobileMenu a'
        ).filter(has_not=page.locator('a[href*="amazon"]'))
        if await email_link.count() > 0:
            await email_link.first.click()
            await page.wait_for_timeout(1500)

    async def _try_goodreads_native_login(self, page: Page) -> bool:
        email_input = page.locator(
            'input[name="user[email]"], input#user_email, input#user_sign_in_email'
        ).first
        password_input = page.locator(
            'input[name="user[password]"], input#user_password, input#user_sign_in_password'
        ).first

        if await email_input.count() == 0 or await password_input.count() == 0:
            return False

        await email_input.fill(settings.goodreads_email)
        await password_input.fill(settings.goodreads_password)

        submit = page.locator(
            'input[type="submit"][name="commit"], '
            'button[type="submit"]:has-text("Sign in"), '
            'input.authPortalSignInButton, '
            'form[action*="sign_in"] input[type="submit"]'
        ).first
        if await submit.count() == 0:
            submit = page.locator('input[type="submit"], button[type="submit"]').first

        await submit.click()
        await page.wait_for_timeout(3000)

        try:
            await page.wait_for_url(re.compile(r"goodreads\.com"), timeout=30_000)
        except Exception:
            return False

        return await self._is_logged_in(page)

    async def _click_amazon_sign_in(self, page: Page) -> None:
        amazon = page.locator(
            'a[href*="amazon"], button:has-text("Amazon"), '
            'input[value*="Amazon"], .authPortal-mainMenu a'
        ).first
        if await amazon.count() > 0:
            await amazon.click()
            await page.wait_for_timeout(2000)

    async def _amazon_sign_in(self, page: Page) -> None:
        email_input = page.locator("#ap_email, input[name='email']").first
        await email_input.wait_for(state="visible", timeout=20_000)
        await email_input.fill(settings.goodreads_email)

        continue_btn = page.locator(
            "#continue, input#continue, button:has-text('Continue')"
        ).first
        if await continue_btn.count() > 0:
            await continue_btn.click()
            await page.wait_for_timeout(1500)

        password_input = page.locator("#ap_password, input[name='password']").first
        await password_input.wait_for(state="visible", timeout=20_000)
        await password_input.fill(settings.goodreads_password)

        submit = page.locator(
            "#signInSubmit, input[type='submit'], button[type='submit']"
        ).first
        await submit.click()

        await page.wait_for_timeout(3000)

        if await page.locator("input[name='otpCode'], #auth-mfa-otpcode").count() > 0:
            raise RuntimeError(
                "Amazon requested 2FA. Export a browser session locally instead: "
                "python scripts/export_goodreads_session.py"
            )

        if await page.locator("#ap_captcha_img, form[action*='cvf']").count() > 0:
            raise RuntimeError(
                "Amazon CAPTCHA detected. Headless login blocked. "
                "Export session locally: python scripts/export_goodreads_session.py"
            )

    async def _is_logged_in(self, page: Page) -> bool:
        if await page.locator('a[href*="/sign_out"], a[href*="sign_out"]').count() > 0:
            return True
        if await page.locator('a[href*="/review/list"]').count() > 0:
            return True
        if await page.locator(".siteHeader__topLevelLink, .menuIcon").count() > 0:
            profile = page.locator('a[href*="/user/show"]').first
            if await profile.count() > 0:
                return True
        return "sign_in" not in page.url and await page.locator(".gr-nav").count() > 0

    async def _raise_login_error(self, page: Page) -> None:
        alert = page.locator(".a-alert-content, #auth-error-message-box, .a-box-inner").first
        detail = ""
        if await alert.count() > 0:
            detail = (await alert.inner_text()).strip()

        await _save_debug_screenshot(page)
        hint = (
            "Headless login often fails on cloud servers. "
            "Run `python scripts/export_goodreads_session.py` on your Mac "
            "(works with Goodreads email login too), then set GOODREADS_STORAGE_STATE on Render."
        )
        msg = f"Goodreads login failed at {page.url}."
        if detail:
            msg += f" {detail}"
        msg += f" {hint}"
        raise RuntimeError(msg)

    async def check_and_add(self, title: str) -> ShelfCheckResult:
        async with self._lock:
            return await self._check_and_add(title)

    async def _check_and_add(self, title: str) -> ShelfCheckResult:
        if not self._logged_in or self._page is None:
            await self.start()

        page = self._page
        assert page is not None

        try:
            search_url = f"https://www.goodreads.com/search?q={quote(title)}"
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            book_link = page.locator("tr[itemscope] a.bookTitle, .bookTitle span").first
            if await book_link.count() == 0:
                return ShelfCheckResult(
                    title=title, status="unknown", message="No search results"
                )

            book_title = (await book_link.inner_text()).strip()
            await book_link.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(800)

            want_to_read = page.locator(
                'button:has-text("Want to Read"), a:has-text("Want to Read"), '
                '[data-shelf-name="to-read"], .wtrButton'
            ).first

            if await want_to_read.count() == 0:
                return ShelfCheckResult(
                    title=book_title,
                    status="unknown",
                    message="Could not find Want to Read button",
                )

            button_text = (await want_to_read.inner_text()).lower()
            aria_label = (await want_to_read.get_attribute("aria-label") or "").lower()

            if "on" in button_text or "shelved" in button_text or "remove" in aria_label:
                return ShelfCheckResult(title=book_title, status="on_shelf")

            await want_to_read.click()
            await page.wait_for_timeout(1200)

            shelf_option = page.locator(
                'button:has-text("Want to Read"), a:has-text("to-read"), '
                '[data-shelf-id="to-read"]'
            ).first
            if await shelf_option.count() > 0:
                option_text = (await shelf_option.inner_text()).lower()
                if "want" in option_text or "to read" in option_text:
                    await shelf_option.click()
                    await page.wait_for_timeout(800)

            return ShelfCheckResult(title=book_title, status="added")

        except Exception as exc:
            logger.exception("Goodreads automation failed for %s", title)
            return ShelfCheckResult(title=title, status="failed", message=str(exc))


def _load_storage_state() -> dict[str, Any] | None:
    raw = settings.goodreads_storage_state.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOODREADS_STORAGE_STATE is not valid JSON") from exc


async def _save_debug_screenshot(page: Page) -> None:
    try:
        path = "/tmp/goodreads_login_failure.png"
        await page.screenshot(path=path, full_page=True)
        logger.error("Saved login debug screenshot to %s", path)
    except Exception:
        logger.exception("Could not save login screenshot")
