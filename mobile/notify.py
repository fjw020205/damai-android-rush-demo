# -*- coding: UTF-8 -*-
"""Local notifications for the Damai helper (lowest latency: no network)."""

from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

_TOAST_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$template = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{title}</text>
      <text>{message}</text>
    </binding>
  </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('DamaiHelper').Show($toast)
"""


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def notify(title: str, message: str) -> bool:
    """Show a Windows toast and beep; never raises."""
    try:
        if sys.platform == "win32":
            script = _TOAST_PS.format(
                title=_escape(title), message=_escape(message)
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
    except Exception:
        logger.debug("toast failed", exc_info=True)
    try:
        import winsound

        winsound.Beep(1200, 120)
        winsound.Beep(1600, 120)
    except Exception:
        pass
    logger.info("通知: %s | %s", title, message)
    return True
