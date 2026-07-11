#!/usr/bin/env python3
"""Export a Goodreads browser session for use on Render.

Goodreads login goes through Amazon, which often blocks headless cloud servers.
Log in once in a visible browser on your Mac, then paste the printed JSON into
Render as GOODREADS_STORAGE_STATE.

Usage:
    cd backend
    source .venv/bin/activate
    playwright install chromium
    python scripts/export_goodreads_session.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

SIGN_IN_URL = "https://www.goodreads.com/user/sign_in"
OUTPUT_FILE = Path(__file__).resolve().parent.parent / "goodreads_session.json"


async def main() -> None:
    print("Opening a browser window...")
    print("1. Sign in to Goodreads with your email and password")
    print("2. Wait until you see your Goodreads home page / profile")
    print("3. Return here and press Enter\n")

    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=False)
    except Exception as exc:
        if "Executable doesn't exist" in str(exc):
            print("Chromium not installed. Run this first:\n")
            print("  playwright install chromium\n")
        raise
    context = await browser.new_context(
        viewport={"width": 1280, "height": 800},
        locale="en-US",
    )
    page = await context.new_page()
    await page.goto(SIGN_IN_URL, wait_until="domcontentloaded")

    await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

    await page.goto("https://www.goodreads.com/", wait_until="domcontentloaded")
    state = await context.storage_state()

    OUTPUT_FILE.write_text(json.dumps(state), encoding="utf-8")
    print(f"\nSaved session to {OUTPUT_FILE}")
    print("\n--- Paste this into Render as GOODREADS_STORAGE_STATE ---\n")
    print(json.dumps(state))
    print("\n--- end ---\n")
    print("Session usually lasts weeks. Re-export if login starts failing.")

    await browser.close()
    await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
