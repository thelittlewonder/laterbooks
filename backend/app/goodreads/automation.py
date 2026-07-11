"""Goodreads shelf automation via Playwright."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
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

_NAV_TIMEOUT_MS = 120_000
_ACTION_TIMEOUT_MS = 60_000
_SESSION_COOKIE_NAMES = {"_session_id2", "loggedin", "session_id", "ccsid"}
_MIN_QUERY_LEN = 4
_MIN_MATCH_SCORE = 0.32


def _normalize_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _title_match_score(query: str, candidate: str) -> float:
    query_norm = _normalize_title(query)
    candidate_norm = _normalize_title(candidate)
    if not query_norm or not candidate_norm:
        return 0.0

    sequence_score = SequenceMatcher(None, query_norm, candidate_norm).ratio()
    query_tokens = set(query_norm.split())
    candidate_tokens = set(candidate_norm.split())
    if not query_tokens or not candidate_tokens:
        return sequence_score

    overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
    return max(sequence_score, overlap)


def _configure_page(page: Page) -> None:
    page.set_default_navigation_timeout(_NAV_TIMEOUT_MS)
    page.set_default_timeout(_ACTION_TIMEOUT_MS)


async def _goto(page: Page, url: str) -> None:
    """Navigate with retries — Render free tier + Goodreads can be very slow."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            await page.goto(url, wait_until="commit", timeout=_NAV_TIMEOUT_MS)
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Navigation attempt %s failed for %s: %s", attempt + 1, url, exc)
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError(
        f"Could not load {url} (Goodreads may be slow from Render — retry in a minute). "
        f"Last error: {last_error}"
    ) from last_error


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
        _configure_page(self._page)

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
        assert self._context is not None
        page = self._page

        cookies = await self._context.cookies("https://www.goodreads.com")
        cookie_names = {cookie["name"] for cookie in cookies}
        if not cookie_names & _SESSION_COOKIE_NAMES:
            logger.warning("No Goodreads session cookies found in storage state")

        # Lighter than homepage — confirms login for shelf operations
        for url in (
            "https://www.goodreads.com/review/list/1?shelf=to-read",
            "https://www.goodreads.com/",
        ):
            try:
                await _goto(page, url)
                await page.wait_for_timeout(2000)
                if await self._is_logged_in(page):
                    self._logged_in = True
                    logger.info("Goodreads session restored from storage state")
                    return
            except Exception as exc:
                logger.warning("Session verify failed at %s: %s", url, exc)

        if settings.goodreads_email and settings.goodreads_password:
            logger.warning("Stored session expired — falling back to credential login")
            await self._login_with_credentials()
            return

        raise RuntimeError(
            "Goodreads session expired or timed out. Re-export with "
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

        await _goto(page, "https://www.goodreads.com/user/sign_in")
        await page.wait_for_timeout(2000)

        if settings.goodreads_login_method == "goodreads":
            await self._login_goodreads_email(page)
            return

        await self._login_amazon(page)

    async def _login_goodreads_email(self, page: Page) -> None:
        await self._open_goodreads_email_form(page)

        if await self._try_goodreads_native_login(page):
            self._logged_in = True
            logger.info("Logged in to Goodreads with email/password")
            return

        await self._raise_login_error(page)

    async def _login_amazon(self, page: Page) -> None:
        await self._click_amazon_sign_in(page)

        if "amazon." not in page.url:
            await _goto(
                page,
                "https://www.amazon.com/ap/signin?openid.return_to="
                + quote("https://www.goodreads.com/ap-handler/sign-in", safe="")
                + "&openid.assoc_handle=amzn_goodreads_desktop_us"
                + "&openid.mode=checkid_setup&siteState=xxx",
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
        if await self._has_native_form(page):
            return

        # Links that switch to Goodreads email login (not Amazon)
        switchers = [
            page.get_by_role("link", name=re.compile(r"sign in with email", re.I)),
            page.get_by_role("link", name=re.compile(r"not a member of amazon", re.I)),
            page.get_by_role("link", name=re.compile(r"goodreads password", re.I)),
        ]
        for switcher in switchers:
            if await switcher.count() > 0:
                await switcher.first.click()
                await page.wait_for_timeout(1500)
                if await self._has_native_form(page):
                    return

        # Some regions show email form on a direct sign-in tab
        email_tab = page.locator(
            'button:has-text("Email"), a:has-text("Email"), [data-tab="email"]'
        ).first
        if await email_tab.count() > 0:
            await email_tab.click()
            await page.wait_for_timeout(1500)

    async def _has_native_form(self, page: Page) -> bool:
        email = self._native_email_locator(page)
        password = self._native_password_locator(page)
        if await email.count() == 0 or await password.count() == 0:
            return False
        try:
            return await email.is_visible() and await password.is_visible()
        except Exception:
            return False

    def _native_email_locator(self, page: Page):
        return page.locator(
            'input[name="user[email]"], input#user_email, input#user_sign_in_email, '
            'input[type="email"]:not(#ap_email)'
        ).first

    def _native_password_locator(self, page: Page):
        return page.locator(
            'input[name="user[password]"], input#user_password, '
            'input#user_sign_in_password, input[type="password"]:not(#ap_password)'
        ).first

    async def _try_goodreads_native_login(self, page: Page) -> bool:
        email_input = self._native_email_locator(page)
        password_input = self._native_password_locator(page)

        try:
            await email_input.wait_for(state="visible", timeout=10_000)
            await password_input.wait_for(state="visible", timeout=10_000)
        except Exception:
            logger.warning("Goodreads email form not visible at %s", page.url)
            return False

        await email_input.fill(settings.goodreads_email)
        await password_input.fill(settings.goodreads_password)

        submit = page.locator(
            'form[action*="sign_in"] input[type="submit"], '
            'input.authPortalSignInButton, '
            'button[type="submit"]:has-text("Sign in")'
        ).first
        if await submit.count() == 0:
            submit = page.locator(
                'input[type="submit"], button[type="submit"]'
            ).filter(has_not=page.locator("#signInSubmit, #continue"))

        await submit.click()
        await page.wait_for_timeout(3000)

        if await page.locator(".flash.error, .errorMessage, #error_message").count() > 0:
            logger.warning("Goodreads rejected credentials on sign-in form")
            return False

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
            "Automated login often fails on Render. "
            "On your Mac run: python scripts/export_goodreads_session.py "
            "then set GOODREADS_STORAGE_STATE on Render (skip email/password there)."
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
            query = title.strip()
            if len(query) < _MIN_QUERY_LEN:
                return ShelfCheckResult(
                    title=query,
                    status="unknown",
                    message="Detected title too short to search safely",
                )

            search_url = f"https://www.goodreads.com/search?q={quote(query)}"
            await _goto(page, search_url)
            await page.wait_for_timeout(1000)

            book_link = page.locator("tr[itemscope] a.bookTitle, .bookTitle span").first
            if await book_link.count() == 0:
                return ShelfCheckResult(
                    title=query, status="unknown", message="No search results"
                )

            book_title = (await book_link.inner_text()).strip()
            match_score = _title_match_score(query, book_title)
            if match_score < _MIN_MATCH_SCORE:
                return ShelfCheckResult(
                    title=query,
                    status="unknown",
                    message=(
                        f"Top result “{book_title}” doesn’t match detected title "
                        f"(score {match_score:.2f})"
                    ),
                )

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
