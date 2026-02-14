#!/usr/bin/env python3
"""Mahakaleshwar Bhasma Aarti booking assistant.

Supports on-demand execution and continuous polling.
This tool automates only basic page interactions and does not bypass
captchas/OTP/manual verification steps.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError, sync_playwright


BOOKING_URL = "https://www.shrimahakaleshwar.mp.gov.in/services/bhasmaarti-booking"
LOGIN_URL = "https://www.shrimahakaleshwar.mp.gov.in/services/login"


@dataclass
class AppConfig:
    headless: bool = True
    interval_seconds: int = 300
    timeout_ms: int = 20000
    dry_run: bool = True
    # Login (required before booking)
    mobile_number: str = ""
    mobile_input_selector: str = (
        "input[formcontrolname='mobile'], "
        "input[placeholder='Enter your mobile number'], "
        "input[placeholder*='mobile'], input[name*='mobile'], input[type='tel']"
    )
    get_otp_selector: str = "button:has-text('Get OTP'), button:has-text('Get Otp')"
    otp_wait_seconds: int = 120
    # Selectors are configurable because booking portals frequently change markup.
    open_calendar_selector: str = "input[type='date'], .datepicker, [data-toggle='datepicker']"
    enabled_date_selector: str = ".ui-datepicker-calendar td:not(.ui-datepicker-unselectable):not(.disabled) a, .available-date"
    proceed_selector: str = "button:has-text('Proceed'), button:has-text('Book'), input[type='submit']"


def load_config(path: Optional[str]) -> AppConfig:
    if path is None:
        return AppConfig()

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return AppConfig(**data)


def do_login(page: Page, config: AppConfig) -> bool:
    """Open login page, fill mobile number, click Get OTP, then wait for user to enter OTP."""
    mobile = config.mobile_number or os.getenv("MOBILE_NUMBER", "")
    if not mobile:
        logging.warning(
            "No mobile_number set. Set mobile_number in config or MOBILE_NUMBER in .env to enable login."
        )
        return False

    logging.info("Opening login page: %s", LOGIN_URL)
    page.goto(LOGIN_URL, timeout=config.timeout_ms, wait_until="domcontentloaded")

    # Wait for login form (often in a modal/card) to be visible before filling
    mobile_input = page.locator(config.mobile_input_selector).first
    mobile_input.wait_for(state="visible", timeout=config.timeout_ms)
    mobile_input.click()
    mobile_input.fill(mobile)
    logging.info("Entered mobile number; clicking Get OTP.")
    page.locator(config.get_otp_selector).first.click(timeout=config.timeout_ms)

    logging.info(
        "Please enter the OTP in the browser window. Waiting up to %s seconds for login to complete...",
        config.otp_wait_seconds,
    )
    try:
        page.wait_for_url(
            lambda url: "login" not in url,
            timeout=config.otp_wait_seconds * 1000,
        )
        logging.info("Login completed (left login page).")
    except TimeoutError:
        logging.warning(
            "OTP wait timed out after %s s. Continuing; booking may redirect to login again.",
            config.otp_wait_seconds,
        )
    return True


def find_next_available_date(page: Page, config: AppConfig) -> Optional[str]:
    """Try to locate and click the first available date.

    Returns selected date label/text, if any.
    """
    try:
        page.locator(config.open_calendar_selector).first.click(timeout=config.timeout_ms)
    except TimeoutError:
        logging.warning("Could not open date picker using selector: %s", config.open_calendar_selector)

    dates = page.locator(config.enabled_date_selector)
    count = dates.count()
    if count == 0:
        return None

    first = dates.first
    label = first.inner_text().strip() or first.get_attribute("aria-label") or "unknown-date"
    first.click(timeout=config.timeout_ms)
    return label


def try_booking_once(config: AppConfig) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=config.headless)
        page = browser.new_page()
        try:
            # Login first (mobile + OTP); user enters OTP in browser if headful.
            do_login(page, config)
            page.goto(BOOKING_URL, timeout=config.timeout_ms, wait_until="domcontentloaded")
            selected_date = find_next_available_date(page, config)
            if not selected_date:
                logging.info("No available date was visible at %s", datetime.now().isoformat())
                return False

            logging.info("Selected next available date candidate: %s", selected_date)

            if config.dry_run:
                logging.info("Dry run enabled; stopping before final booking action.")
                return True

            page.locator(config.proceed_selector).first.click(timeout=config.timeout_ms)
            logging.info(
                "Clicked booking/proceed button. Complete captcha/OTP/manual details if prompted."
            )
            return True
        finally:
            browser.close()


def run_continuous(config: AppConfig) -> None:
    logging.info("Starting continuous mode (interval=%ss)", config.interval_seconds)
    while True:
        try:
            success = try_booking_once(config)
            if success:
                logging.info("Attempt completed successfully.")
            else:
                logging.info("Attempt completed; no date booked.")
        except Exception as exc:  # noqa: BLE001 - keep loop resilient
            logging.exception("Attempt failed due to unexpected error: %s", exc)

        time.sleep(config.interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Book next available Bhasma Aarti slot on demand or continuously."
    )
    parser.add_argument(
        "--mode",
        choices=["once", "continuous"],
        default="once",
        help="Run one booking attempt or keep trying at intervals.",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML config file to override defaults.",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser with UI (helpful for login/captcha/manual checks).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually click proceed button. Without this flag script is dry-run.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = parse_args()
    config = load_config(args.config)

    if args.headful:
        config.headless = False
    if args.execute:
        config.dry_run = False

    if args.mode == "once":
        ok = try_booking_once(config)
        raise SystemExit(0 if ok else 1)

    run_continuous(config)


if __name__ == "__main__":
    main()
