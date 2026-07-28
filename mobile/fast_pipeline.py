# -*- coding: UTF-8 -*-
"""
FastPipeline — Global-deadline ticket purchase pipeline.

Replaces the cascading-timeout approach (SKU 6s + confirm 8s = 14s dead time)
with a single 5s global deadline shared across all phases.
"""

import threading
import time
import re
import xml.etree.ElementTree as ET
from typing import Callable, List, Optional, Tuple

from selenium.webdriver.common.by import By

try:
    from mobile.ui_primitives import ANDROID_UIAUTOMATOR
except ImportError:
    pass

try:
    from mobile.logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)

_PIPELINE_DEADLINE_S = 8.0
_ACTION_RETRY_INTERVAL_S = 0.10
_SESSION_PANEL_ID = "cn.damai:id/project_detail_perform_flowlayout"
_PRICE_PANEL_ID = "cn.damai:id/project_detail_perform_price_flowlayout"
_QUANTITY_LAYOUT_ID = "cn.damai:id/layout_num"
_QUANTITY_PLUS_ID = "cn.damai:id/img_jia"
_DETAIL_CTA_ID = "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"

# Keys that must all exist in _cached_coords for a warm run.
_WARM_REQUIRED_KEYS = frozenset(
    {
        "detail_buy",
        "price",
        "sku_buy",
        "attendee_checkboxes",
    }
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def poll_until(
    condition_fn: Callable[[], bool], deadline: float, interval_s: float = 0.05
) -> bool:
    """Poll *condition_fn* until it returns True or *deadline* is exceeded.

    Returns True if the condition was met before the deadline, False otherwise.
    """
    while time.time() < deadline:
        if condition_fn():
            return True
        time.sleep(interval_s)
    return False


def batch_shell_taps(device, coordinates: List[Tuple[int, int]]) -> None:
    """Send multiple ``input tap x y`` commands in a single shell call."""
    if not coordinates:
        return
    cmd = "; ".join(f"input tap {x} {y}" for x, y in coordinates)
    device.shell(cmd)


# ---------------------------------------------------------------------------
# FastPipeline
# ---------------------------------------------------------------------------


class FastPipeline:
    """Coordinate-driven pipeline with a single global deadline."""

    def __init__(self, device, config, probe: bool, guard):
        self._device = device
        self._config = config
        self._probe = probe
        self._guard = guard
        self._bot = None

        self._cached_coords: dict = {}
        self._cached_no_match: set = set()
        self._zero_sleep_rehearsal = False
        self._cta_click_perf: Optional[float] = None
        self._cta_click_wall: Optional[float] = None
        self._confirm_ready_perf: Optional[float] = None
        self._hot_path_start_perf: Optional[float] = None

    def set_bot(self, bot) -> None:
        """Set DamaiBot reference for delegation."""
        self._bot = bot

    def set_zero_sleep_rehearsal(self, enabled: bool) -> None:
        """Enable the diagnostic path that never adds a Python-side sleep."""
        self._zero_sleep_rehearsal = bool(enabled)

    def _skip_attendee_selection(self) -> bool:
        """Whether the user has already selected attendees in the Damai app."""
        return getattr(self._config, "skip_attendee_selection", False) is True

    def _skip_quantity_adjustment(self) -> bool:
        """Whether the Damai reservation has already fixed the ticket quantity."""
        return getattr(self._config, "skip_quantity_adjustment", False) is True

    def _confirm_page_ready(self) -> bool:
        """Detect confirm-page readiness with lighter-weight fallbacks."""
        bot = self._bot
        if bot._has_element(By.ID, "cn.damai:id/checkbox"):
            return True
        if bot._attendee_checkbox_elements():
            return True

        confirm_selectors = [
            (
                ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("确认购买")',
            ),
            (
                ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("实名观演人")',
            ),
            (
                ANDROID_UIAUTOMATOR,
                'new UiSelector().textContains("立即提交")',
            ),
        ]
        return any(bot._has_element(by, value) for by, value in confirm_selectors)

    def _wait_for_purchase_entry(self, deadline: float):
        """Detect the Activity transition and quickly resend a dropped CTA tap."""
        poll_deadline = min(deadline, time.time() + 2.5)
        retry_coords = self._cached_coords.get("detail_buy")
        next_retry_at = time.perf_counter() + _ACTION_RETRY_INTERVAL_S
        retry_count = 0
        while time.time() < poll_deadline:
            activity = self._current_focus_activity()
            if "NcovSkuActivity" in activity:
                if self._cta_click_perf is not None:
                    logger.info(
                        "CTA->SKU activity: %.3fs",
                        time.perf_counter() - self._cta_click_perf,
                    )
                return {"state": "sku_page", "session_picker": True}
            if "DmOrderActivity" in activity:
                self._confirm_ready_perf = time.perf_counter()
                return {"state": "order_confirm_page", "submit_button": True}
            if retry_coords is not None and time.perf_counter() >= next_retry_at:
                batch_shell_taps(self._device, [retry_coords])
                retry_count += 1
                next_retry_at = time.perf_counter() + _ACTION_RETRY_INTERVAL_S
            if not self._zero_sleep_rehearsal:
                time.sleep(0.01)
        logger.error(
            "fast path stopped at stage=cta_to_sku after %d retry tap(s)",
            retry_count,
        )
        return None

    def _current_focus_activity(self) -> str:
        """Read the focused Activity through a low-latency Android shell query."""
        try:
            response = self._device.shell("dumpsys window | grep mCurrentFocus")
            output = getattr(response, "output", None)
            if output is None and isinstance(response, (tuple, list)) and response:
                output = response[0]
            if isinstance(output, str):
                match = re.search(r"\b[\w.]+/([\w.$]+)", output)
                if match:
                    return match.group(1)
        except Exception:
            pass

        try:
            current = self._device.app_current() or {}
            activity = current.get("activity", "") if isinstance(current, dict) else ""
            return activity if isinstance(activity, str) else ""
        except Exception:
            return ""

    def _wait_for_confirm_ready(
        self, deadline: float, poll_window_s: float = 0.22
    ) -> bool:
        """Poll briefly for the confirm page without triggering heavier probes."""
        poll_end = min(time.time() + poll_window_s, deadline)
        while time.time() < poll_end:
            if self._confirm_page_ready():
                return True
            if not self._zero_sleep_rehearsal:
                time.sleep(0.02)
        return False

    def _resource_exists(self, resource_id: str) -> bool:
        """Check one u2 resource id without dumping the full hierarchy."""
        try:
            return bool(self._device(resourceId=resource_id).exists)
        except Exception:
            try:
                return bool(self._bot._has_element(By.ID, resource_id))
            except Exception:
                return False

    def _resource_center(
        self, resource_id: str, horizontal_ratio: float = 0.5
    ) -> Optional[Tuple[int, int]]:
        """Read a point inside one resource directly, without a hierarchy dump."""
        try:
            info = self._device(resourceId=resource_id).info
        except Exception:
            return None
        if not isinstance(info, dict):
            return None
        bounds = info.get("bounds")
        if not isinstance(bounds, dict):
            return None
        try:
            left = int(bounds["left"])
            top = int(bounds["top"])
            right = int(bounds["right"])
            bottom = int(bounds["bottom"])
        except (KeyError, TypeError, ValueError):
            return None
        if right <= left or bottom <= top:
            return None
        ratio = min(1.0, max(0.0, float(horizontal_ratio)))
        x = int(left + (right - left) * ratio)
        return (x, (top + bottom) // 2)

    def _extract_session_coords(self, xml_root) -> Optional[Tuple[int, int]]:
        """Return the configured Canvas session card center from one XML dump."""
        session_index = getattr(self._config, "session_index", None)
        if session_index is None or xml_root is None:
            return None

        panel = next(
            (
                node
                for node in xml_root.iter("node")
                if node.get("resource-id") == _SESSION_PANEL_ID
            ),
            None,
        )
        if panel is None:
            return None

        cards = [
            child
            for child in list(panel)
            if child.tag == "node" and child.get("clickable") == "true"
        ]
        if not 0 <= session_index < len(cards):
            logger.warning(
                "session_index=%d out of range for %d visible session cards",
                session_index,
                len(cards),
            )
            return None
        return self._bot._extract_coords_from_xml_node(cards[session_index])

    def _wait_for_session_coords(self, deadline: float) -> Optional[Tuple[int, int]]:
        """Wait for the Canvas panel, then parse it at most twice."""
        panel_deadline = min(deadline, time.time() + 0.7)
        while time.time() < panel_deadline:
            if self._resource_exists(_SESSION_PANEL_ID):
                break
            time.sleep(0.01)
        else:
            logger.debug("session panel did not appear before the fast deadline")
            return None

        for attempt in range(2):
            session_coords = self._extract_session_coords(
                self._bot._dump_hierarchy_xml()
            )
            if session_coords is not None:
                return session_coords
            if attempt == 0 and time.time() < panel_deadline:
                time.sleep(min(0.08, max(0.0, panel_deadline - time.time())))
        logger.debug("session panel appeared without selectable session cards")
        return None

    def _select_session_until_price_ready(self, deadline: float) -> bool:
        """Tap the configured session, retrying every 100ms until prices appear."""
        if self._resource_exists(_PRICE_PANEL_ID):
            return True

        session_coords = self._wait_for_session_coords(deadline)
        if session_coords is None:
            return False

        self._cached_coords["session"] = session_coords
        local_deadline = min(deadline, time.time() + 1.2)
        attempts = 0
        while time.time() < local_deadline:
            attempts += 1
            batch_shell_taps(self._device, [session_coords])
            check_at = min(local_deadline, time.time() + _ACTION_RETRY_INTERVAL_S)
            while time.time() < check_at:
                if self._resource_exists(_PRICE_PANEL_ID):
                    logger.info(
                        "session_index=%d selected; price panel ready after %d tap(s)",
                        self._config.session_index,
                        attempts,
                    )
                    return True
                time.sleep(0.01)
        return self._resource_exists(_PRICE_PANEL_ID)

    def _select_price_and_quantity(self, price_coords, deadline: float) -> bool:
        """Select a price and immediately set quantity from configured attendees."""
        if not price_coords or time.time() >= deadline:
            return False

        required_count = max(1, len(self._config.users or []))
        batch_shell_taps(self._device, [price_coords])
        if self._skip_quantity_adjustment():
            logger.info("预约已锁定购票数量，跳过数量加号")
            return True
        if required_count == 1:
            return True

        local_deadline = min(deadline, time.time() + 1.0)
        next_price_retry = time.time() + _ACTION_RETRY_INTERVAL_S
        while time.time() < local_deadline:
            if self._resource_exists(_QUANTITY_LAYOUT_ID):
                try:
                    plus = self._device(resourceId=_QUANTITY_PLUS_ID)
                    if not bool(plus.exists):
                        return False
                    for _ in range(required_count - 1):
                        plus.click()
                    logger.info("quantity set to %d for configured attendees", required_count)
                    return True
                except Exception:
                    return False

            if time.time() >= next_price_retry:
                batch_shell_taps(self._device, [price_coords])
                next_price_retry = time.time() + _ACTION_RETRY_INTERVAL_S
            time.sleep(0.01)
        return False

    def _click_buy_until_confirm(self, sku_buy_coords, deadline: float) -> bool:
        """Retry the SKU confirm tap every 100ms until the confirm page appears."""
        if not sku_buy_coords or time.time() >= deadline:
            return False

        local_deadline = min(deadline, time.time() + 1.4)
        attempts = 0
        while time.time() < local_deadline:
            attempts += 1
            if attempts == 1:
                batch_shell_taps(self._device, [sku_buy_coords])
            else:
                # A coordinate retry could land on the confirm-page submit
                # button during the transition. Resource-scoped retries become
                # harmless as soon as btn_buy_view disappears.
                self._bot._click_sku_buy_button_element(burst_count=1)
            check_at = min(local_deadline, time.time() + _ACTION_RETRY_INTERVAL_S)
            while time.time() < check_at:
                if self._resource_exists("cn.damai:id/checkbox"):
                    self._confirm_ready_perf = time.perf_counter()
                    logger.info("confirm page ready after %d buy tap(s)", attempts)
                    return True
                time.sleep(0.01)
        return self._resource_exists("cn.damai:id/checkbox")

    def _open_purchase_panel(self, detail_buy_coords, deadline: float):
        """Leave detail_page using shell double-tap first, then u2 click fallback."""
        bot = self._bot
        if not detail_buy_coords or time.time() >= deadline:
            return False

        batch_shell_taps(self._device, [detail_buy_coords, detail_buy_coords])
        entry_probe = self._wait_for_purchase_entry(deadline)
        if entry_probe:
            return entry_probe

        if time.time() >= deadline:
            return None
        bot._click_coordinates(*detail_buy_coords, duration=25)
        return self._wait_for_purchase_entry(deadline)

    def _select_price_with_pipeline(self, price_coords) -> bool:
        """Select the configured price using the same robust path as normal flow."""
        bot = self._bot
        return bool(bot._click_price_option_by_config_index(coords=price_coords))

    def _click_sku_buy_with_pipeline(self, sku_buy_coords) -> bool:
        """Click SKU buy/confirm button with element-first fallback."""
        bot = self._bot
        burst_count = 1 if not self._config.if_commit_order else 2
        if bot._click_sku_buy_button_element(burst_count=burst_count):
            return True
        if sku_buy_coords:
            bot._burst_click_coordinates(
                *sku_buy_coords,
                count=burst_count,
                interval_ms=25,
                duration=25,
            )
            return True
        return False

    def _shell_price_and_buy_until_confirm(
        self, price_coords, sku_buy_coords, deadline: float
    ) -> bool:
        """Fast-path SKU selection using raw shell taps before element fallbacks."""
        if (
            not price_coords
            or not sku_buy_coords
            or time.time() >= deadline
        ):
            return False

        shell_deadline = min(deadline, time.time() + 0.9)
        while time.time() < shell_deadline:
            batch_shell_taps(
                self._device,
                [price_coords, sku_buy_coords, sku_buy_coords],
            )
            if self._wait_for_confirm_ready(shell_deadline):
                return True
        return False

    # -- Public helpers -----------------------------------------------------

    def has_warm_coords(self) -> bool:
        """True when all keys required for a warm run are cached."""
        required_keys = _WARM_REQUIRED_KEYS
        if self._skip_attendee_selection():
            required_keys = required_keys - {"attendee_checkboxes"}
        return required_keys.issubset(self._cached_coords.keys())

    # -- Warm path ----------------------------------------------------------

    def run_warm(self, start_time: float) -> Optional[bool]:
        """Execute the warm (cached-coordinate) pipeline.

        Returns True on success, None on timeout / failure.
        """
        deadline = start_time + _PIPELINE_DEADLINE_S

        # Step 1: batch city + detail_buy taps
        taps: List[Tuple[int, int]] = []
        city_coord = self._cached_coords.get("city")
        if city_coord is not None:
            taps.append(city_coord)
        detail_buy_coord = self._cached_coords.get("detail_buy")
        if detail_buy_coord is not None:
            taps.append(detail_buy_coord)
        if taps:
            batch_shell_taps(self._device, taps)

        if time.time() >= deadline:
            return None

        # Step 2: background blind clicker (price + sku_buy every 20ms)
        stop_event = threading.Event()
        price_coord = self._cached_coords.get("price")
        sku_buy_coord = self._cached_coords.get("sku_buy")

        def _blind_clicker():
            blind_taps: List[Tuple[int, int]] = []
            if price_coord is not None:
                blind_taps.append(price_coord)
            if sku_buy_coord is not None:
                blind_taps.append(sku_buy_coord)
            if not blind_taps:
                return
            while not stop_event.is_set():
                batch_shell_taps(self._device, blind_taps)
                stop_event.wait(0.02)

        clicker_thread = threading.Thread(target=_blind_clicker, daemon=True)
        clicker_thread.start()

        try:
            # Step 3: poll for attendee checkbox
            checkbox_found = poll_until(
                lambda: self._has_checkbox(),
                deadline=deadline,
            )
            if not checkbox_found:
                return None

            # Step 4: click attendee coordinates
            attendee_coord = self._cached_coords.get("attendee_checkboxes")
            if attendee_coord is not None:
                batch_shell_taps(self._device, [attendee_coord])
            return True
        finally:
            stop_event.set()
            clicker_thread.join(timeout=1.0)

    # -- Cold path ----------------------------------------------------------

    def run_cold(self, start_time: float) -> Optional[bool]:
        """Execute the cold (XML-dump) pipeline.

        Returns True on success, None on timeout / failure.
        """
        deadline = start_time + _PIPELINE_DEADLINE_S

        # Phase 1: initial XML dump
        if time.time() >= deadline:
            return None
        try:
            xml_src = self._device.dump_hierarchy()
            if xml_src:
                ET.fromstring(xml_src)
        except Exception:
            logger.debug("cold pipeline: initial XML dump failed")

        # Phase 2: poll for SKU page
        if time.time() >= deadline:
            return None
        sku_found = poll_until(
            lambda: self._has_sku_layout(),
            deadline=deadline,
        )
        if not sku_found:
            return None

        # Phase 3: SKU XML dump
        if time.time() >= deadline:
            return None
        try:
            xml_src = self._device.dump_hierarchy()
            if xml_src:
                ET.fromstring(xml_src)
        except Exception:
            logger.debug("cold pipeline: SKU XML dump failed")

        # Phase 4: poll for confirm checkbox
        if time.time() >= deadline:
            return None
        checkbox_found = poll_until(
            lambda: self._has_checkbox(),
            deadline=deadline,
        )
        if not checkbox_found:
            return None

        return True

    # -- Private helpers ----------------------------------------------------

    def _has_checkbox(self) -> bool:
        """Check for attendee checkbox via u2 element lookup."""
        try:
            el = self._device(resourceId="cn.damai:id/checkbox")
            return el.exists
        except Exception:
            return False

    def _has_sku_layout(self) -> bool:
        """Check for SKU layout via u2 element lookup."""
        try:
            el = self._device(resourceId="cn.damai:id/layout_sku")
            return el.exists
        except Exception:
            return False

    # -- Migrated pipeline methods (from DamaiBot) --------------------------

    def rush_preselect_and_buy_via_xml(self):
        """Cold rush path: single XML dump to find city/date/buy button and cache coords.

        Replaces 3-6 sequential _cached_tap HTTP calls (~3-4s cold) with 1 dump_hierarchy
        (~0.3s) + local XML parsing + 2-3 cached clicks (~0.2-0.3s).
        Returns (buy_clicked: bool).
        """
        bot = self._bot
        # The exposed resource is a non-clickable Canvas container. Its visual
        # CTA occupies the right side; the geometric center can hit dead space.
        direct_buy_coords = self._resource_center(_DETAIL_CTA_ID, horizontal_ratio=0.75)
        if direct_buy_coords is not None:
            self._cached_coords["detail_buy"] = direct_buy_coords
            self._cta_click_perf = time.perf_counter()
            self._cta_click_wall = time.time()
            if self._hot_path_start_perf is not None:
                logger.info(
                    "hot path entry->CTA dispatch: %.3fs",
                    self._cta_click_perf - self._hot_path_start_perf,
                )
            logger.info("点击购票按钮...")
            batch_shell_taps(self._device, [direct_buy_coords, direct_buy_coords])
            return True

        logger.debug("direct CTA lookup missed; falling back to one hierarchy dump")
        bot._dismiss_fast_blocking_dialogs()
        xml_root = bot._dump_hierarchy_xml()
        if xml_root is None:
            return False

        # --- Extract coords from single XML dump ---
        buy_coords = None
        city_coords = None
        date_coords = None

        for node in xml_root.iter("node"):
            rid = node.get("resource-id", "")
            text = node.get("text", "")

            # Purchase button (detail page)
            if not buy_coords and rid in (
                "trade_project_detail_purchase_status_bar_container_fl",
                "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl",
            ):
                buy_coords = bot._extract_coords_from_xml_node(node)

            # City match
            if (
                not city_coords
                and self._config.city
                and text
                and self._config.city in text
            ):
                city_coords = bot._extract_coords_from_xml_node(node)

            # Date match
            if (
                not date_coords
                and self._config.date
                and text
                and self._config.date in text
            ):
                date_coords = bot._extract_coords_from_xml_node(node)

        # --- Cache coords and batch-click via shell ---
        tap_cmds = []
        if date_coords:
            self._cached_coords["date"] = date_coords
            tap_cmds.append(f"input tap {int(date_coords[0])} {int(date_coords[1])}")
            logger.info(f"极速模式预选日期: {self._config.date}")
        elif self._config.date:
            self._cached_no_match.add("date")

        if city_coords:
            self._cached_coords["city"] = city_coords
            tap_cmds.append(f"input tap {int(city_coords[0])} {int(city_coords[1])}")
            logger.info(f"极速模式预选城市: {self._config.city}")
        elif self._config.city:
            self._cached_no_match.add("city")

        if buy_coords:
            self._cached_coords["detail_buy"] = buy_coords
            logger.info("点击购票按钮...")
            tap_cmds.append(f"input tap {int(buy_coords[0])} {int(buy_coords[1])}")
            tap_cmds.append(f"input tap {int(buy_coords[0])} {int(buy_coords[1])}")
        if tap_cmds:
            if buy_coords:
                self._cta_click_perf = time.perf_counter()
                self._cta_click_wall = time.time()
            self._device.shell("; ".join(tap_cmds))
            return bool(buy_coords)
        return False

    def run_cold_validation(self, start_time):
        """Fast cold validation: XML dump -> shell batch -> concurrent polling.

        Returns True on success, None to fall back to the normal flow.
        """
        bot = self._bot
        self._hot_path_start_perf = time.perf_counter()
        if self._zero_sleep_rehearsal:
            return self._run_cold_zero_sleep_validation(start_time)

        # --- Phase 1: detail page --- XML dump for city/buy coords, shell batch click ---
        if not self.rush_preselect_and_buy_via_xml():
            logger.error("fast path stopped at stage=detail_cta: CTA coordinates unavailable")
            return None

        cta_wall_start = self._cta_click_wall or time.time()
        global_deadline = cta_wall_start + _PIPELINE_DEADLINE_S
        entry_probe = self._wait_for_purchase_entry(global_deadline)
        if not entry_probe:
            logger.error("fast path stopped at stage=cta_to_sku")
            return None

        if entry_probe["state"] == "order_confirm_page" or self._confirm_page_ready():
            return self._finish_confirm(start_time)

        if entry_probe["state"] != "sku_page":
            logger.error("fast path stopped at stage=entry_state: %s", entry_probe)
            return None

        # The first SKU state can be the Canvas session picker. Dispatch the
        # configured session immediately, then use a cheap resource-id probe to
        # detect the price panel and resend only when the app drops the tap.
        if not self._select_session_until_price_ready(global_deadline):
            logger.error("fast path stopped at stage=session_to_price")
            return None

        # --- Phase 3: SKU page --- single XML dump for price + sku_buy coords ---
        sku_xml = bot._dump_hierarchy_xml()
        if sku_xml is None:
            logger.error("fast path stopped at stage=price_xml")
            return None
        price_coords = bot._get_price_option_coordinates_by_config_index(
            xml_root=sku_xml
        )
        sku_buy_coords = bot._get_buy_button_coordinates(xml_root=sku_xml)
        if not price_coords or not sku_buy_coords:
            logger.error("fast path stopped at stage=sku_coordinates")
            return None

        # Cache for future warm-pipeline runs.
        self._cached_coords["price"] = price_coords
        self._cached_coords["sku_buy"] = sku_buy_coords

        logger.info("选择票价...")
        logger.info(f"通过配置索引直接选择票价: price_index={self._config.price_index}")
        logger.info("选择数量...")
        if not self._select_price_and_quantity(price_coords, global_deadline):
            logger.error("fast path stopped at stage=price_to_quantity")
            return None
        logger.info("确定购买...")

        # --- Phase 4: state-driven fast taps, then element-based fallbacks ---
        confirmed = self._click_buy_until_confirm(sku_buy_coords, global_deadline)
        sold_out_checked = False
        if not confirmed:
            if not self._select_price_with_pipeline(price_coords):
                return None

            while time.time() < global_deadline:
                if not self._click_sku_buy_with_pipeline(sku_buy_coords):
                    return None

                if self._wait_for_confirm_ready(global_deadline, poll_window_s=0.55):
                    confirmed = True
                    break

                # Check for sold-out once midway to avoid wasting the full deadline.
                if (
                    not sold_out_checked
                    and time.time() > start_time + _PIPELINE_DEADLINE_S * 0.5
                ):
                    sold_out_checked = True
                    if bot._is_buy_button_sold_out():
                        logger.warning("购买按钮区域检测到缺货/售罄标识，管道提前退出")
                        bot._set_terminal_failure("sold_out")
                        return False

        if not confirmed:
            return None

        return self._finish_confirm(start_time)

    def _run_cold_zero_sleep_validation(self, start_time):
        """Run the verified detail-to-confirm path without artificial waits.

        The app still renders its next screen asynchronously, so this performs
        immediate hierarchy probes rather than sleeping between steps.  It is
        intentionally validation-only and never falls back to the slower flow.
        """
        bot = self._bot
        deadline = start_time + _PIPELINE_DEADLINE_S

        # One hierarchy dump is needed to locate the detail-page CTA.  Do not
        # scan optional dialogs in this diagnostic path.
        xml_root = bot._dump_hierarchy_xml()
        if xml_root is None:
            return False

        detail_buy = None
        for node in xml_root.iter("node"):
            if node.get("resource-id") in (
                "trade_project_detail_purchase_status_bar_container_fl",
                "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl",
            ):
                detail_buy = bot._extract_coords_from_xml_node(node)
                break
        if detail_buy is None:
            return False

        logger.info("零休眠演练：立即点击购票按钮")
        batch_shell_taps(self._device, [detail_buy, detail_buy])
        entry_probe = self._wait_for_purchase_entry(deadline)
        if not entry_probe or entry_probe["state"] != "sku_page":
            return False

        # This is the previously verified explicit first session.  The helper
        # performs one direct XML read and one click, without an element wait.
        if not bot.select_performance_date(timeout=0.0):
            return False
        logger.info("零休眠演练：已立即选择 session_index=%d", self._config.session_index)

        # The new Damai SKU cards are created after the session click.  Probe
        # continuously with no sleep and issue the next raw taps at first sight.
        while time.time() < deadline:
            sku_xml = bot._dump_hierarchy_xml()
            if sku_xml is None:
                continue
            price_coords = bot._get_price_coords_from_xml(sku_xml)
            sku_buy_coords = bot._get_buy_button_coordinates(xml_root=sku_xml)
            if not price_coords or not sku_buy_coords:
                continue

            logger.info(
                "零休眠演练：直接选择 price_index=%d 并确定购买",
                self._config.price_index,
            )
            batch_shell_taps(
                self._device,
                [price_coords, sku_buy_coords, sku_buy_coords],
            )
            if self._wait_for_confirm_ready(deadline, poll_window_s=0.08):
                return self._finish_confirm(start_time)

        return False

    def _finish_confirm(self, start_time):
        """Shared tail for the cold pipeline: optionally select attendees."""
        bot = self._bot
        if self._skip_attendee_selection():
            logger.info("开发验证极速路径：沿用 App 中已预选的观演人")
        else:
            required_count = max(1, len(self._config.users or []))
            logger.info(f"检测到观演人未选择完成，尝试自动补选（已选 0/{required_count}）")
            logger.info("开发验证极速路径：按勾选框顺序快速补选观演人")

            # Find and click attendee checkboxes (also caches coords for warm pipeline).
            checkbox_elements = bot._attendee_checkbox_elements()
            if checkbox_elements:
                _coords = []
                for el in checkbox_elements:
                    try:
                        bt = getattr(el, "bounds", None)
                        if isinstance(bt, (list, tuple)) and len(bt) == 4:
                            left, top, right, bottom = [int(v) for v in bt]
                            _coords.append(((left + right) // 2, (top + bottom) // 2))
                    except Exception:
                        pass
                if _coords:
                    self._cached_coords["attendee_checkboxes"] = _coords
                for checkbox in checkbox_elements[:required_count]:
                    bot._click_attendee_checkbox_fast(checkbox)

        ready_perf = time.perf_counter()
        if self._config.if_commit_order:
            submit_selectors = [
                (ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                (
                    ANDROID_UIAUTOMATOR,
                    'new UiSelector().textMatches(".*提交.*|.*确认.*")',
                ),
                (By.XPATH, '//*[contains(@text,"提交")]'),
            ]
            logger.info("正式极速路径：立即提交订单")
            result = bot._submit_order_fast(submit_selectors)
            return bot._finalize_submit_result(result, start_time=start_time)

        bot._set_run_outcome("validation_ready")
        if self._skip_attendee_selection():
            logger.info('if_commit_order=False，沿用 App 预选观演人，停止在"立即提交"前')
        else:
            logger.info('if_commit_order=False，已完成观演人勾选，停止在"立即提交"前')
        if self._cta_click_perf is not None:
            if self._confirm_ready_perf is not None:
                logger.info(
                    "CTA->confirm page: %.3fs",
                    self._confirm_ready_perf - self._cta_click_perf,
                )
            logger.info(
                "CTA->submit ready: %.3fs",
                ready_perf - self._cta_click_perf,
            )
        logger.info(
            f"已到订单确认页且观演人已勾选，未提交订单（开发验证），耗时: {time.time() - start_time:.2f}秒"
        )
        return True

    def run_warm_validation(self, start_time):
        """Ultra-fast warm validation: blind shell clicks + concurrent polling.

        Returns True on success, None to fall back to the normal flow.
        """
        bot = self._bot
        coords = self._cached_coords
        no_match = self._cached_no_match

        detail_buy = coords["detail_buy"]
        price = coords["price"]
        sku_buy = coords["sku_buy"]
        attendees = coords.get("attendee_checkboxes", [])
        date = coords.get("date")
        city = coords.get("city")
        required_count = max(1, len(self._config.users or []))

        # --- Step 1: apply cached filters, then enter purchase panel --------
        tap_cmds = []
        if date and "date" not in no_match:
            tap_cmds.append(f"input tap {int(date[0])} {int(date[1])}")
            logger.info(f"极速模式预选日期: {self._config.date}")
        if city and "city" not in no_match:
            tap_cmds.append(f"input tap {int(city[0])} {int(city[1])}")
            logger.info(f"极速模式预选城市: {self._config.city}")
        tap_cmds.extend(
            [
                f"input tap {int(detail_buy[0])} {int(detail_buy[1])}",
                f"input tap {int(detail_buy[0])} {int(detail_buy[1])}",
            ]
        )
        self._device.shell("; ".join(tap_cmds))
        logger.info("点击购票按钮...")
        deadline = start_time + _PIPELINE_DEADLINE_S
        entry_probe = self._wait_for_purchase_entry(deadline)
        if not entry_probe:
            self._bot._click_coordinates(*detail_buy, duration=25)
            entry_probe = self._wait_for_purchase_entry(deadline)
        if not entry_probe:
            return None
        if entry_probe["state"] == "order_confirm_page" or self._confirm_page_ready():
            entry_probe = {"state": "order_confirm_page"}
        elif entry_probe["state"] != "sku_page":
            return None

        # --- Step 2: select price + click buy, poll for confirm ---
        logger.info("选择票价...")
        logger.info(f"通过配置索引直接选择票价: price_index={self._config.price_index}")
        logger.info("选择数量...")
        logger.info("确定购买...")

        confirmed = False
        if entry_probe["state"] == "sku_page":
            confirmed = self._shell_price_and_buy_until_confirm(price, sku_buy, deadline)
            if not confirmed and not self._select_price_with_pipeline(price):
                return None
            while (
                time.time() < deadline
                and entry_probe["state"] == "sku_page"
                and not confirmed
            ):
                if not self._click_sku_buy_with_pipeline(sku_buy):
                    return None
                if self._wait_for_confirm_ready(deadline, poll_window_s=0.55):
                    confirmed = True
                    break

        if entry_probe["state"] == "sku_page" and not confirmed:
            return None

        # --- Step 4: click attendees only when they were not preselected ---
        if self._skip_attendee_selection():
            logger.info("开发验证极速路径：沿用 App 中已预选的观演人")
        else:
            logger.info(f"检测到观演人未选择完成，尝试自动补选（已选 0/{required_count}）")
            logger.info("开发验证极速路径：按勾选框顺序快速补选观演人")
            for c in attendees[:required_count]:
                bot._click_coordinates(*c)

        bot._set_run_outcome("validation_ready")
        if self._skip_attendee_selection():
            logger.info('if_commit_order=False，沿用 App 预选观演人，停止在"立即提交"前')
        else:
            logger.info('if_commit_order=False，已完成观演人勾选，停止在"立即提交"前')
        logger.info(
            f"已到订单确认页且观演人已勾选，未提交订单（开发验证），耗时: {time.time() - start_time:.2f}秒"
        )
        return True
