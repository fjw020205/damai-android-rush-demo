"""Local control console for the Damai Android rush demo.

The console deliberately stays small: it writes local JSONC config files and
starts one of the existing batch entry points. The purchase logic remains in
``mobile.damai_app``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
CONSOLE_DIR = ROOT / "console"
CONFIG_DIR = ROOT / "config"
LOG_DIR = ROOT / "logs"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
HOST = "127.0.0.1"
PORT = 8765

_process: subprocess.Popen[str] | None = None
_process_action: str | None = None
_process_lock = threading.Lock()
_events: list[str] = []

ACTION_MAP = {
    "extra-rehearsal": {
        "template": "rehearsal.jsonc.example",
        "config": "rehearsal.jsonc",
        "bat": "start.bat",
        "formal": False,
        "label": "额外选择型 · 演练",
    },
    "extra-formal": {
        "template": "formal.jsonc.example",
        "config": "formal.jsonc",
        "bat": "start-formal.bat",
        "formal": True,
        "label": "额外选择型 · 正式",
    },
    "preselected-rehearsal": {
        "template": "preselected-rehearsal.jsonc.example",
        "config": "preselected-rehearsal.jsonc",
        "bat": "start-preselected.bat",
        "formal": False,
        "label": "连点型 · T0 演练",
    },
    "preselected-t10": {
        "template": "preselected-rehearsal.jsonc.example",
        "config": "preselected-rehearsal.jsonc",
        "bat": "start-preselected-t10.bat",
        "formal": False,
        "label": "连点型 · T0+10ms 演练",
    },
    "preselected-t20": {
        "template": "preselected-rehearsal.jsonc.example",
        "config": "preselected-rehearsal.jsonc",
        "bat": "start-preselected-t20.bat",
        "formal": False,
        "label": "连点型 · T0+20ms 演练",
    },
    "preselected-formal": {
        "template": "preselected-formal.jsonc.example",
        "config": "preselected-formal.jsonc",
        "bat": "start-preselected-formal.bat",
        "formal": True,
        "label": "连点型 · 正式",
    },
}


def _record(message: str) -> None:
    stamp = datetime.now().strftime("%H:%M:%S")
    _events.append(f"{stamp}  {message}")
    del _events[:-80]


def _jsonc_load(path: Path) -> dict[str, Any]:
    from mobile.config import _load_config_dict_from_path

    return _load_config_dict_from_path(str(path))


def _iso_time(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    raw = str(value).strip()
    if len(raw) == 16:
        raw += ":00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raw += "+08:00"
    return raw


def _int_field(payload: dict[str, Any], name: str, default: int | None = None) -> int | None:
    value = payload.get(name, default)
    if value in (None, ""):
        return default
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是正整数") from exc
    if result < 1:
        raise ValueError(f"{name} 必须是正整数")
    return result


WAITLIST_CONFIG = CONFIG_DIR / "waitlist.jsonc"
WAITLIST_EXAMPLE = CONFIG_DIR / "waitlist.jsonc.example"


def _waitlist_auto_submit() -> bool:
    path = WAITLIST_CONFIG if WAITLIST_CONFIG.exists() else WAITLIST_EXAMPLE
    try:
        return bool(_jsonc_load(path).get("auto_submit", False))
    except Exception:
        return False


def _set_waitlist_auto_submit(enabled: bool) -> bool:
    if not WAITLIST_CONFIG.exists():
        if not WAITLIST_EXAMPLE.exists():
            raise ValueError("缺少候补配置模板")
        shutil.copyfile(WAITLIST_EXAMPLE, WAITLIST_CONFIG)
    text = WAITLIST_CONFIG.read_text(encoding="utf-8")
    value = "true" if enabled else "false"
    pattern = re.compile(r'"auto_submit"\s*:\s*(?:true|false)')
    if pattern.search(text):
        text = pattern.sub(f'"auto_submit": {value}', text, count=1)
    else:
        index = text.rfind("}")
        if index < 0:
            raise ValueError("候补配置格式不正确")
        text = text[:index] + f',\n  "auto_submit": {value}\n' + text[index:]
    WAITLIST_CONFIG.write_text(text, encoding="utf-8")
    return enabled


def _build_config(action: str, payload: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    spec = ACTION_MAP.get(action)
    if not spec:
        raise ValueError("未知运行入口")
    template_path = CONFIG_DIR / spec["template"]
    target_path = CONFIG_DIR / spec["config"]
    config = _jsonc_load(template_path)

    config.update(
        {
            "serial": str(payload.get("serial", "")).strip() or None,
            "sell_start_time": _iso_time(payload.get("sell_start_time")),
            "if_commit_order": bool(spec["formal"]),
            "probe_only": False,
            "auto_navigate": False,
            "skip_attendee_selection": bool(payload.get("skip_attendee_selection", True)),
            "users": [],
            "preselected_sku": action.startswith("preselected"),
        }
    )
    if not config["skip_attendee_selection"]:
        names = [line.strip() for line in str(payload.get("users", "")).splitlines() if line.strip()]
        if not names:
            raise ValueError("请填写至少一名观演人，或保持“观演人已预选”")
        config["users"] = names

    if action.startswith("extra"):
        config["session_index"] = _int_field(payload, "session_index")
        config["price_index"] = _int_field(payload, "price_index")
    else:
        config["session_index"] = None
        config["price_index"] = 1

    from mobile.config import Config

    # Validate exactly what the existing runner will load before writing it.
    temp_path = target_path.with_suffix(target_path.suffix + ".console-check")
    temp_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        Config.load_config(str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)
    target_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _record(f"已保存 {spec['label']} 配置")
    return target_path, config


def _tail_log(limit: int = 30) -> list[str]:
    candidates = [ROOT / "mobile" / "hatickets_mobile.log"]
    candidates.extend(sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True) if LOG_DIR.exists() else [])
    for path in candidates:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
            except OSError:
                pass
    return []


def _devices() -> list[dict[str, str]]:
    try:
        import adbutils

        result = []
        for device in adbutils.adb.device_list():
            result.append({"serial": device.serial, "state": getattr(device, "state", "device")})
        return result
    except Exception:
        # The console should still work when setup.py has not installed the
        # optional Python wrapper but the Android platform-tools `adb` exists.
        adb = shutil.which("adb")
        if not adb:
            return []
        try:
            completed = subprocess.run(
                [adb, "devices", "-l"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        devices = []
        for line in completed.stdout.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2 and fields[0] != "*":
                devices.append({"serial": fields[0], "state": fields[1]})
        return devices


def _status() -> dict[str, Any]:
    global _process
    with _process_lock:
        process = _process
        running = bool(process and process.poll() is None)
        pid = process.pid if running and process else None
        active_action = _process_action if running else None
        if process and not running:
            _process = None
    config_status = {}
    for name in ("rehearsal.jsonc", "formal.jsonc", "preselected-rehearsal.jsonc", "preselected-formal.jsonc"):
        path = CONFIG_DIR / name
        config_status[name] = {"exists": path.exists(), "updated": path.stat().st_mtime if path.exists() else None}
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "venv": VENV_PYTHON.exists(),
        "adb": bool(shutil.which("adb")) or bool(_devices()),
        "devices": _devices(),
        "running": running,
        "pid": pid,
        "process_action": active_action,
        "formal_status": _formal_status(running, active_action),
        "configs": config_status,
        "events": _events[-40:],
        "log": _tail_log(),
    }


def _formal_status(running: bool, active_action: str | None) -> dict[str, Any]:
    """Return a user-facing readiness state for the configured formal task."""
    configured_times: list[tuple[float, str]] = []
    for filename in ("formal.jsonc", "preselected-formal.jsonc"):
        path = CONFIG_DIR / filename
        if not path.exists():
            continue
        try:
            value = _jsonc_load(path).get("sell_start_time")
            if isinstance(value, str) and value.strip():
                datetime.fromisoformat(value)
                configured_times.append((path.stat().st_mtime, value))
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue

    if running and active_action in {"extra-formal", "preselected-formal"}:
        target_value = max(configured_times, key=lambda item: item[0])[1] if configured_times else None
        return {"label": "已准备就绪", "kind": "good", "sell_start_time": target_value}
    if not configured_times:
        return {"label": "未设置时间", "kind": "warn", "sell_start_time": None}
    target_value = max(configured_times, key=lambda item: item[0])[1]
    try:
        target = datetime.fromisoformat(target_value)
        now = datetime.now().astimezone()
        if target.tzinfo is None:
            target = target.replace(tzinfo=now.tzinfo)
        label = "程序未就绪" if now < target else "正式任务未运行"
    except ValueError:
        label = "正式时间无效"
    return {"label": label, "kind": "danger", "sell_start_time": target_value}


def _read_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 64 * 1024:
        raise ValueError("请求内容过大")
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8")) if raw else {}


class Handler(BaseHTTPRequestHandler):
    server_version = "DamaiRushConsole/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, payload: Any, content_type: str = "application/json; charset=utf-8") -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            path = CONSOLE_DIR / "index.html"
            self._send(HTTPStatus.OK, path.read_bytes(), "text/html; charset=utf-8")
        elif parsed.path.startswith("/docs/"):
            relative = parsed.path.removeprefix("/docs/")
            path = (ROOT / "docs" / relative).resolve()
            docs_root = (ROOT / "docs").resolve()
            if path.parent == docs_root and path.suffix == ".md" and path.exists():
                self._send(HTTPStatus.OK, path.read_bytes(), "text/plain; charset=utf-8")
            else:
                self._send(HTTPStatus.NOT_FOUND, {"error": "Document not found"})
        elif parsed.path == "/api/status":
            self._send(HTTPStatus.OK, _status())
        elif parsed.path == "/api/waitlist":
            self._send(HTTPStatus.OK, {"auto_submit": _waitlist_auto_submit()})
        else:
            self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        global _process, _process_action
        parsed = urlparse(self.path)
        try:
            payload = _read_body(self)
            if parsed.path == "/api/config":
                action = str(payload.get("action", ""))
                path, config = _build_config(action, payload)
                self._send(HTTPStatus.OK, {"ok": True, "path": str(path.relative_to(ROOT)), "config": config})
                return
            if parsed.path == "/api/waitlist":
                enabled = payload.get("auto_submit") is True
                _set_waitlist_auto_submit(enabled)
                self._send(
                    HTTPStatus.OK,
                    {"ok": True, "auto_submit": enabled},
                )
                return
            if parsed.path == "/api/run":
                action = str(payload.get("action", ""))
                spec = ACTION_MAP.get(action)
                if not spec:
                    raise ValueError("未知运行入口")
                if spec["formal"] and payload.get("confirm") is not True:
                    raise ValueError("正式入口需要先确认只提交订单、不自动付款")
                _build_config(action, payload)
                with _process_lock:
                    if _process and _process.poll() is None:
                        raise ValueError("已有任务正在运行，请先等待它结束")
                    LOG_DIR.mkdir(exist_ok=True)
                    log_path = LOG_DIR / "console-run.log"
                    output = log_path.open("a", encoding="utf-8")
                    env = os.environ.copy()
                    env["PYTHONPATH"] = str(ROOT)
                    try:
                        _process = subprocess.Popen(
                            ["cmd.exe", "/d", "/c", str(ROOT / spec["bat"])],
                            cwd=ROOT,
                            env=env,
                            stdout=output,
                            stderr=subprocess.STDOUT,
                            text=True,
                            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                        )
                        _process_action = action
                    finally:
                        output.close()
                _record(f"已启动 {spec['label']}，PID {_process.pid}")
                self._send(HTTPStatus.OK, {"ok": True, "pid": _process.pid, "label": spec["label"]})
                return
            self._send(HTTPStatus.NOT_FOUND, {"error": "Not found"})
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
        except Exception as exc:  # keep the console responsive for environment errors
            _record(f"操作失败：{exc}")
            self._send(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    _record(f"控制台已启动：http://{HOST}:{PORT}")
    print(f"Damai rush console: http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
