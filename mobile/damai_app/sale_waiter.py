# -*- coding: UTF-8 -*-
"""Sale-start waiting helpers for DamaiBot.

Methods relocated from ``mobile/damai_app.py`` (W4-01 split, zero behavior
change).  Reads constants from the package namespace so that tests'
``patch("mobile.damai_app.time")`` / ``patch("mobile.damai_app.datetime")``
patches still take effect via the package's mirror hook.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta

from . import (
    SALE_READY_TEXTS,
    _CTA_BLOCKED_KEYWORDS,
    _CTA_READY_KEYWORDS,
    logger,
)

try:
    from mobile.logger import log_event
except ImportError:  # pragma: no cover
    from logger import log_event  # type: ignore[no-redef]

try:
    from mobile.item_resolver import normalize_text
except ImportError:  # pragma: no cover
    from item_resolver import normalize_text  # type: ignore[no-redef]

try:
    from mobile.ui_primitives import ANDROID_UIAUTOMATOR
except ImportError:  # pragma: no cover
    from ui_primitives import ANDROID_UIAUTOMATOR  # type: ignore[no-redef]

try:
    from selenium.webdriver.common.by import By
except ModuleNotFoundError:  # pragma: no cover
    raise


class SaleWaiterMixin:
    """Mixin contributing sale-start detection helpers to ``DamaiBot``."""

    def _dispatch_sale_cta(self, coords) -> bool:
        """Send the cached CTA tap immediately when the sale clock reaches zero."""
        if not coords:
            return False
        try:
            self._cached_hot_path_coords["detail_buy"] = coords
            self._click_coordinates(*coords, duration=25)
            self._sale_cta_click_dispatched = True
            return True
        except Exception as exc:  # pragma: no cover - device failures are logged
            logger.warning("开售 CTA 直点失败: %s", exc)
            return False

    def _purchase_bar_text_ready(self):
        """Inspect the detail-page CTA text and decide whether sale has opened."""
        try:
            purchase_bar = self._find(
                By.ID,
                "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl",
            )
        except Exception:
            return False

        texts = [
            text.strip()
            for text in self._collect_descendant_texts(purchase_bar)
            if text.strip()
        ]
        merged = normalize_text("".join(texts))
        if not merged:
            return False
        if any(normalize_text(keyword) in merged for keyword in _CTA_BLOCKED_KEYWORDS):
            return False
        return any(normalize_text(keyword) in merged for keyword in _CTA_READY_KEYWORDS)

    def _is_sale_ready(self):
        """Check whether the current UI state is actionable for purchase.

        Sale-readiness is detected via :data:`SALE_READY_TEXTS` (开售文案) plus
        a small set of post-confirm CTAs ("立即购买" / "选座购买" / "提交订单" 等)
        that may appear once the user has already entered the SKU/order page.
        """
        ready_texts = (
            *SALE_READY_TEXTS,
            "立即购买",
            "选座购买",
            "立即提交",
            "提交订单",
        )
        for text in ready_texts:
            if self._has_element(
                ANDROID_UIAUTOMATOR,
                f'new UiSelector().textContains("{text}")',
            ):
                self._last_sale_ready_text = text
                return True

        if self._has_element(
            By.ID, "cn.damai:id/project_detail_perform_price_flowlayout"
        ):
            return not self.is_reservation_sku_mode()

        if self._has_element(
            By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"
        ):
            return self._purchase_bar_text_ready()

        return False

    def wait_for_sale_start(self):
        """等待开售时间，在开售前 countdown_lead_ms 毫秒开始轮询。"""
        if self.config.sell_start_time is None:
            if self.config.wait_cta_ready_timeout_ms > 0:
                logger.info("未配置 sell_start_time，已跳过 CTA 等待，直接开始执行")
            return

        _tz_shanghai = timezone(timedelta(hours=8))
        sell_time = datetime.fromisoformat(self.config.sell_start_time)
        # Ensure timezone-aware
        if sell_time.tzinfo is None:
            sell_time = sell_time.replace(tzinfo=_tz_shanghai)

        now = datetime.now(tz=_tz_shanghai)
        if now >= sell_time:
            logger.info("开售时间已过，跳过等待")
            return

        lead_delta = timedelta(milliseconds=self.config.countdown_lead_ms)
        poll_start = sell_time - lead_delta
        sleep_seconds = (poll_start - now).total_seconds()

        if sleep_seconds > 0:
            logger.info(
                f"等待开售，将在 {self.config.sell_start_time} 前 "
                f"{self.config.countdown_lead_ms}ms 开始轮询"
            )
            time.sleep(sleep_seconds)

        # 交错轮询循环（issue #41）：每轮依次做「guard 文案读取（廉价）→ Canvas
        # 坐标兜底 → 页面结构多信号兜底」。旧实现先串行烧 guard.wait_until_safe
        # 8s，再串行烧文案轮询 8s；大麦 ≥9.0.2x 详情页 CTA 为 Canvas 自绘
        # （btn_buy_view 已移除、无任何文案节点），两段全部超时，开抢比配置晚 ~8s。
        deadline = sell_time + timedelta(seconds=8)
        polls = 0
        saw_cta_text = False
        guard = getattr(self, "_guard", None)
        # 开售前预判 CTA 是否为 Canvas 自绘（大麦 ≥9.0.2x）：读不到任何文案、但能
        # 按候选 resource-id 定位到中心坐标。若是，则开售前不再每轮跑昂贵的
        # _is_sale_ready（对 Canvas 详情页恒 False，单次 ~1s 串行 u2 查询）——否则
        # 当 sell_time 落在某轮 in-flight 的 _is_sale_ready 期间，开抢会被这一次
        # 查询整体拖后 ~1 个周期（真机实测晚 ~2s）。get_current_text 在前，短路
        # 保证 v8.x（有文案）路径不会触发多余的坐标查询（issue #41 收尾）。
        canvas_cta = False
        canvas_coords = None
        if guard is not None:
            try:
                canvas_coords = guard.get_cta_center_coords()
                canvas_cta = guard.get_current_text() is None and canvas_coords is not None
            except Exception:
                canvas_cta = False
                canvas_coords = None
        loop_t0 = time.monotonic()
        while True:
            now = datetime.now(tz=_tz_shanghai)
            if now >= deadline:
                break
            polls += 1

            # 严格定时门：配置 sell_start_time 时，任何 CTA 文案或结构信号都不能
            # 提前放行。否则把未来时刻用于普通可购页演练时，"立即购买" 会绕过
            # Canvas 分支而在目标时间前触发，既污染定时测试也违背配置语义。
            if now < sell_time:
                time.sleep(0.02)
                continue

            # (0) Canvas 自绘 CTA 快路径（大麦 >=9.0.2x）：到点即按候选
            # resource-id 中心坐标派发，避免一轮完整 UI 查询拖慢开售首击。
            if canvas_cta and not saw_cta_text:
                if self._dispatch_sale_cta(canvas_coords):
                    log_event(
                        logger,
                        "cta_canvas_fallback",
                        resource_id=guard._last_matched_resource_id,
                        coords=canvas_coords,
                        waited_ms=int((time.monotonic() - loop_t0) * 1000),
                        polls=polls,
                        dispatched=True,
                    )
                    return
                # 坐标意外丢失：放弃 Canvas 快路径，回落通用轮询兜底。
                canvas_cta = False

            # (1) v8.x 文案路径：读到安全购买文案立即返回（保留开售前文案翻转
            #     即提前返回的能力，SAFE/BLOCKED 校验行为不变）。
            text = guard.get_current_text() if guard is not None else None
            if text:
                saw_cta_text = True
                if guard.is_safe_to_click(text):
                    coords = guard.get_cta_center_coords()
                    dispatched = self._dispatch_sale_cta(coords)
                    log_event(
                        logger,
                        "sale_ready",
                        source="buy_button_guard",
                        cta_text=text,
                        polls=polls,
                        duration_ms=int((time.monotonic() - loop_t0) * 1000),
                        dispatched=dispatched,
                    )
                    return

            # (2) Canvas 自绘 CTA 兜底（issue #41 核心）：已到开售时刻、全程未读到
            #     任何 CTA 文案、且能按候选 resource-id 定位到 CTA 中心坐标时立即
            #     返回，把点击交给下游 _enter_purchase_flow_from_detail_page 的
            #     容器 ID/坐标路径（预约风险由 SKU 页 reservation_mode 检测兜底）。
            #     必须置于 _is_sale_ready 之前，避免被其每轮 ~1s 的串行 u2 查询拖后。
            if now >= sell_time and not saw_cta_text and guard is not None:
                if self._dispatch_sale_cta(canvas_coords):
                    log_event(
                        logger,
                        "cta_canvas_fallback",
                        resource_id=guard._last_matched_resource_id,
                        coords=canvas_coords,
                        waited_ms=int((time.monotonic() - loop_t0) * 1000),
                        polls=polls,
                        dispatched=True,
                    )
                    return

            # (3) 老版页面结构兜底：多购买信号文案轮询（行为不变）。
            if self._is_sale_ready():
                cta_text = getattr(self, "_last_sale_ready_text", None) or "?"
                log_event(
                    logger,
                    "sale_ready",
                    source="poll_loop",
                    cta_text=cta_text,
                    polls=polls,
                    duration_ms=int((time.monotonic() - loop_t0) * 1000),
                )
                return
            time.sleep(0.05)

        log_event(
            logger,
            "sale_wait_timeout",
            level=logging.WARNING,
            polls=polls,
            duration_ms=int((time.monotonic() - loop_t0) * 1000),
        )
