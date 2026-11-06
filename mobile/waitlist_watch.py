# -*- coding: UTF-8 -*-
"""Waitlist watcher: read-only page polling + local notifications.

It never taps purchase buttons.  Optional pull-to-refresh only reloads the
current page when nothing changed for a while.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from mobile.notify import notify

try:
    import uiautomator2 as u2
except ModuleNotFoundError:  # pragma: no cover
    u2 = None


AVAILABLE_TEXTS = ("可候补", "立即购买", "立即购票", "有票", "立即预订", "立即预定")
UNAVAILABLE_TEXTS = ("缺货登记", "售罄", "无票", "即将开抢")
QUEUE_TEXTS = ("人数过多", "排队中", "系统繁忙", "请稍后")


def _load_jsonc(path: str) -> dict:
    raw = open(path, encoding="utf-8").read()
    raw = re.sub(r"//.*", "", raw)
    raw = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def _texts(root: ET.Element) -> list[str]:
    values = []
    for node in root.iter("node"):
        for attr in ("text", "content-desc"):
            value = (node.get(attr) or "").strip()
            if value:
                values.append(value)
    return values


def _match_price(text: str, target: int, allow_lower: bool) -> bool:
    digits = re.findall(r"(\d{2,5})", text)
    prices = [int(item) for item in digits if 100 <= int(item) <= 9999]
    if not prices:
        return False
    if any(price == target for price in prices):
        return True
    return allow_lower and any(price < target for price in prices)


def detect_state(texts: list[str]) -> str:
    joined = " ".join(texts)
    if any(marker in joined for marker in QUEUE_TEXTS):
        return "queue"
    if any(marker in joined for marker in UNAVAILABLE_TEXTS):
        return "unavailable"
    if any(marker in joined for marker in AVAILABLE_TEXTS):
        return "available"
    return "unknown"


def _run_confirm_flow(cfg: dict, device) -> tuple[bool, str]:
    """Run the existing bot in validation mode; never submits the order."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root, "config", "waitlist-confirm.jsonc")
    payload = {
        "serial": None,
        "users": [],
        "session_index": int(cfg.get("session_index", 1)),
        "price_index": int(cfg.get("price_index", 1)),
        "preselected_sku": False,
        "probe_only": False,
        "if_commit_order": False,
        "skip_attendee_selection": True,
        "skip_quantity_adjustment": True,
        "auto_navigate": False,
        "sell_start_time": None,
        "rush_mode": True,
        "fast_retry_count": 1,
        "fast_retry_interval_ms": 80,
    }
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    python = os.path.join(root, ".venv", "Scripts", "python.exe")
    if not os.path.exists(python):
        python = sys.executable
    try:
        result = subprocess.run(
            [python, "-m", "mobile.damai_app", "--config", config_path],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=45,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        return False, f"启动失败: {exc}"

    activity = ""
    try:
        current = device.app_current() or {}
        activity = current.get("activity", "") or ""
    except Exception:
        pass
    if "DmOrderActivity" in activity:
        return True, "已到确认页"
    return False, f"未到确认页（exit={result.returncode}）"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="候补/放票监控（只读）")
    parser.add_argument("--config", required=True)
    args = parser.parse_args(argv)
    cfg = _load_jsonc(args.config)

    interval = max(1.0, float(cfg.get("poll_interval_ms", 3000)) / 1000.0)
    refresh_every = float(cfg.get("refresh_every_s", 0) or 0)
    refresh_each_poll = bool(cfg.get("refresh_each_poll", True))
    stale_limit = max(1, int(cfg.get("stale_limit", 3)))
    restart_when_stale = bool(cfg.get("restart_when_stale", False))
    cooldown = float(cfg.get("cooldown_s", 30))
    target_date = str(cfg.get("target_date", "") or "")
    target_price = int(cfg.get("target_price", 0) or 0)
    allow_lower = bool(cfg.get("allow_lower_price", True))
    auto_navigate = bool(cfg.get("auto_navigate", False))

    device = u2.connect() if u2 is not None else None
    if device is None:
        print("uiautomator2 不可用")
        return 2

    last_state = None
    last_notify = 0.0
    last_refresh = time.time()
    unchanged = 0
    last_fp = None
    same_fp = 0

    print(f"开始监控：间隔 {interval:.1f}s，刷新间隔 {refresh_every or '关闭'}s")
    try:
        while True:
            # The page does not push updates; a refresh is the only way to
            # learn about newly released tickets. Back off on throttling.
            if refresh_each_poll:
                try:
                    device.swipe(0.5, 0.25, 0.5, 0.7, duration=0.2)
                except Exception:
                    pass
                time.sleep(0.45)
            root = ET.fromstring(device.dump_hierarchy())
            texts = _texts(root)
            state = detect_state(texts)
            now = time.time()

            if state == "queue":
                interval = min(15.0, interval * 1.5)
            else:
                interval = max(3.0, interval / 1.2)

            fingerprint = hashlib.md5(
                "|".join(sorted(texts)).encode("utf-8", "ignore")
            ).hexdigest()
            if fingerprint == last_fp:
                same_fp += 1
            else:
                same_fp = 0
                last_fp = fingerprint

            if same_fp >= stale_limit:
                print(
                    f"[{time.strftime('%H:%M:%S')}] 连续 {same_fp} 次刷新页面无变化，"
                    "尝试强力刷新"
                )
                try:
                    device.swipe(0.5, 0.12, 0.5, 0.9, duration=0.35)
                    time.sleep(0.25)
                    device.swipe(0.5, 0.12, 0.5, 0.9, duration=0.35)
                except Exception:
                    pass
                if restart_when_stale:
                    try:
                        device.app_stop("cn.damai")
                        time.sleep(1.0)
                        device.app_start("cn.damai")
                        print("已重启大麦 App（需要重新进入目标页）")
                    except Exception:
                        pass
                same_fp = 0

            if state != last_state:
                print(f"[{time.strftime('%H:%M:%S')}] 状态: {last_state} -> {state}")
                last_state = state
                unchanged = 0
            else:
                unchanged += 1

            if state == "available" and now - last_notify >= cooldown:
                joined = " ".join(texts)
                date_ok = (not target_date) or (target_date in joined)
                price_ok = target_price <= 0 or _match_price(
                    joined, target_price, allow_lower
                )
                if date_ok and price_ok:
                    notify(
                        "大麦：检测到可购买",
                        f"日期匹配={date_ok} 价格匹配={price_ok}，准备进入确认页",
                    )
                    if auto_navigate:
                        ok, message = _run_confirm_flow(cfg, device)
                        notify(
                            "自动导航完成" if ok else "自动导航失败",
                            message,
                        )
                    last_notify = now
                else:
                    print(
                        f"[{time.strftime('%H:%M:%S')}] 可购买但目标不匹配 "
                        f"date={date_ok} price={price_ok}"
                    )

            if (
                not refresh_each_poll
                and refresh_every > 0
                and now - last_refresh >= refresh_every
                and unchanged >= 3
            ):
                print("下拉刷新当前页面")
                try:
                    device.swipe(0.5, 0.25, 0.5, 0.75, duration=0.25)
                except Exception:
                    pass
                last_refresh = now
                unchanged = 0

            time.sleep(interval)
    except KeyboardInterrupt:
        print("已停止")
        return 0


if __name__ == "__main__":
    sys.exit(main())
