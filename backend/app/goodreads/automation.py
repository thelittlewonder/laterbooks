"""Goodreads shelf automation via Playwright."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.config import settings

logger = logging.getLogger(__name__)

ShelfStatus = Literal["on_shelf", "added", "unknown", "failed"]


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
            headless=settings.playwright_headless
        )
        self._context = await self._browser.new_context()
        self._page = await self._context.new_page()
        await self._login()

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        self._browser = None
        self._context = None
        self._page = None
        self._logged_in = False

    async def _login(self) -> None:
        if not settings.goodreads_email or not settings.goodreads_password:
            raise RuntimeError(
                "Goodreads credentials not configured. "
                "Set GOODREADS_EMAIL and GOODREADS_PASSWORD."
            )

        assert self._page is not None
        page = self._page

        await page.goto(
            "https://www.goodreads.com/user/sign_in",
            wait_until="domcontentloaded",
        )
        await page.wait_for_timeout(1500)

        email_input = page.locator(
            'input[name="user[email]"], input#ap_email, input[type="email"]'
        ).first
        if await email_input.count() > 0:
            await email_input.fill(settings.goodreads_email)

        password_input = page.locator(
            'input[name="user[password]"], input#ap_password, input[type="password"]'
        ).first
        if await password_input.count() > 0:
            await password_input.fill(settings.goodreads_password)

        submit = page.locator(
            'input[type="submit"], button[type="submit"], '
            '#signInSubmit, .authPortal-signInButton'
        ).first
        if await submit.count() > 0:
            await submit.click()
            await page.wait_for_load_state("networkidle", timeout=30000)

        logged_in = (
            await page.locator('a[href*="/review/list"], .siteHeader__topLevelLink').count()
            > 0
        )
        if not logged_in:
            raise RuntimeError("Goodreads login failed. Check credentials.")

        self._logged_in = True
        logger.info("Logged in to Goodreads")

    async def check_and_add(self, title: str) -> ShelfCheckResult:
        async with self._lock:
            return await self._check_and_add(title)

    async def _check_and_add(self, title: str) -> ShelfCheckResult:
        if not self._logged_in or self._page is None:
            await self.start()

        page = self._page
        assert page is not None

        try:
            search_url = f"https://www.goodreads.com/search?q={title.replace(' ', '+')}"
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
