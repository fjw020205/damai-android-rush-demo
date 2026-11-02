# -*- coding: UTF-8 -*-
"""Semantic, multi-device UI locator for the Damai Android flow.

Why this module exists
----------------------
The bot already reads the UI hierarchy, but most hot-path decisions still end
up as cached pixel coordinates.  Coordinates captured on one phone (or one
font scale) do not survive a different resolution, density, or an App layout
change.  This module adds a small, dependency-free locator layer that prefers
*what the control is* over *where it was last time*:

1. page fingerprint  -> are we really on the expected page?
2. resource-id       -> the stable, developer-provided identifier
3. text / content-desc
4. xpath (when supplied)
5. calibrated ratio  -> last resort, per device profile, never blind

Profiles are stored as JSON under ``profiles/`` keyed by
``<model>_<width>x<height>_<density>.json`` so a phone only ever reuses a
ratio captured on the same class of screen.

The module has no third-party imports beyond ``uiautomator2`` in the CLI
entry point; everything else only needs ``device.dump_hierarchy()`` and
``device.click(x, y)``.
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

try:  # pragma: no cover - package import in production, flat import in tests
    from mobile.logger import get_logger
except ImportError:  # pragma: no cover
    from logger import get_logger  # type: ignore[no-redef]

logger = get_logger(__name__)

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
DEFAULT_PROFILE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles"
)


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rect:
    """Pixel rectangle as reported by uiautomator2 bounds attributes."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def center(self) -> Tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def is_valid(self) -> bool:
        return self.width > 0 and self.height > 0


def parse_bounds(value: Optional[str]) -> Optional[Rect]:
    """Parse ``"[l,t][r,b]"`` into a :class:`Rect` (``None`` when malformed)."""
    if not value:
        return None
    match = _BOUNDS_RE.match(str(value).strip())
    if not match:
        return None
    left, top, right, bottom = (int(part) for part in match.groups())
    if right <= left or bottom <= top:
        return None
    return Rect(left, top, right, bottom)


# ---------------------------------------------------------------------------
# Specs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ElementSpec:
    """A semantic description of one control we need to touch or verify.

    The lookup order is resource-id -> text -> content-desc -> xpath ->
    calibrated ratio.  ``page`` optionally pins the spec to a page
    fingerprint so a lookalike control on another page cannot match.
    """

    name: str
    resource_ids: Tuple[str, ...] = ()
    texts: Tuple[str, ...] = ()
    descs: Tuple[str, ...] = ()
    xpath: Optional[str] = None
    page: Optional[str] = None
    # Only nodes inside an ancestor carrying one of these ids may match.
    # Used to separate session cards from price cards (they share the same
    # ``ll_perform_item`` id on the Damai SKU page).
    scope_ids: Tuple[str, ...] = ()
    # Relative center (0..1) captured by a previous calibration run.
    fallback_ratio: Optional[Tuple[float, float]] = None
    # When True, prefer the nearest clickable ancestor's bounds as tap target.
    clickable_ancestor: bool = True
    # When True, a ratio hit requires an explicit profile entry (safe default).
    allow_ratio_fallback: bool = True


@dataclass(frozen=True)
class PageSpec:
    """Fingerprint of a page: any one marker is enough to confirm it."""

    name: str
    any_ids: Tuple[str, ...] = ()
    any_texts: Tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class Hit:
    """A resolved element with the source that produced it."""

    spec: str
    rect: Rect
    source: str  # resource-id | text | desc | xpath | profile-ratio | ratio
    node: Optional[ET.Element] = field(default=None, compare=False, repr=False)

    @property
    def point(self) -> Tuple[int, int]:
        return self.rect.center


# ---------------------------------------------------------------------------
# Built-in knowledge (kept small on purpose; extend via specs dictionaries)
# ---------------------------------------------------------------------------

DEFAULT_PAGES: Tuple[PageSpec, ...] = (
    # SKU must be checked before detail: both pages carry ``btn_buy_view``,
    # and the SKU activity is what the purchase flow actually opens.
    PageSpec(
        "sku",
        any_ids=(
            "cn.damai:id/layout_sku",
            "cn.damai:id/project_detail_perform_price_flowlayout",
            "cn.damai:id/sku_panel_dates",
        ),
        description="票档/场次选择面板",
    ),
    PageSpec(
        "confirm",
        any_texts=("确认购买", "确认订单", "实名观演人", "立即提交", "提交订单", "去结算", "购买数量"),
        description="确认订单页",
    ),
    PageSpec(
        "login",
        any_texts=("登录", "手机号登录", "验证码登录"),
        description="登录页",
    ),
    PageSpec(
        "detail",
        any_ids=(
            "cn.damai:id/btn_buy_view",
            "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl",
        ),
        description="演出详情页（底部购票栏）",
    ),
)

DEFAULT_SPECS: Tuple[ElementSpec, ...] = (
    ElementSpec(
        "detail_cta",
        resource_ids=(
            "cn.damai:id/btn_buy_view",
            "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl",
        ),
        texts=("立即购票", "立即购买", "立即预订", "立即预定", "立即抢票"),
        page="detail",
    ),
    ElementSpec(
        "sku_session_container",
        resource_ids=("cn.damai:id/project_detail_perform_flowlayout",),
        page="sku",
    ),
    ElementSpec(
        "sku_session_card",
        resource_ids=("cn.damai:id/ll_perform_item",),
        scope_ids=("cn.damai:id/project_detail_perform_flowlayout",),
        page="sku",
    ),
    ElementSpec(
        "sku_price_container",
        resource_ids=("cn.damai:id/project_detail_perform_price_flowlayout",),
        page="sku",
    ),
    ElementSpec(
        "sku_price_card",
        resource_ids=("cn.damai:id/ll_perform_item",),
        scope_ids=("cn.damai:id/project_detail_perform_price_flowlayout",),
        page="sku",
    ),
    ElementSpec(
        "sku_confirm",
        resource_ids=("cn.damai:id/btn_buy_view",),
        page="sku",
        allow_ratio_fallback=False,
    ),
    ElementSpec(
        "sku_qty_plus",
        resource_ids=("cn.damai:id/img_jia",),
        page="sku",
    ),
    ElementSpec(
        "sku_qty_minus",
        resource_ids=("cn.damai:id/img_jian",),
        page="sku",
    ),
    ElementSpec(
        "attendee_checkbox",
        resource_ids=("cn.damai:id/checkbox",),
        # Keep this list narrow: a loose "观演人" text match can hit the
        # section title instead of the checkbox row.
        texts=("选择观演人",),
    ),
    ElementSpec(
        "attendee_name",
        resource_ids=("cn.damai:id/text_name",),
    ),
    ElementSpec(
        "confirm_submit",
        texts=("立即提交", "提交订单"),
        page="confirm",
        allow_ratio_fallback=False,
    ),
    ElementSpec(
        "confirm_attendee_checkbox",
        resource_ids=("cn.damai:id/checkbox",),
        page="confirm",
    ),
    ElementSpec(
        "confirm_attendee_name",
        resource_ids=("cn.damai:id/text_name",),
        page="confirm",
    ),
)


# ---------------------------------------------------------------------------
# Device profile
# ---------------------------------------------------------------------------


class DeviceProfile:
    """Per-device calibration data: screen geometry + learned ratios."""

    def __init__(
        self,
        width: int,
        height: int,
        density: Optional[int] = None,
        model: str = "",
        serial: str = "",
        ratios: Optional[Dict[str, List[float]]] = None,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self.density = int(density) if density else None
        self.model = model or ""
        self.serial = serial or ""
        self.ratios: Dict[str, Tuple[float, float]] = {
            name: (float(value[0]), float(value[1]))
            for name, value in (ratios or {}).items()
            if isinstance(value, (list, tuple)) and len(value) == 2
        }

    @property
    def key(self) -> str:
        model = re.sub(r"[^A-Za-z0-9._-]+", "-", self.model) or "device"
        density = str(self.density) if self.density else "unknown"
        return f"{model}_{self.width}x{self.height}_{density}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "density": self.density,
            "model": self.model,
            "serial": self.serial,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "ratios": {name: [round(x, 6), round(y, 6)] for name, (x, y) in self.ratios.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeviceProfile":
        return cls(
            width=data.get("width", 0),
            height=data.get("height", 0),
            density=data.get("density"),
            model=data.get("model", ""),
            serial=data.get("serial", ""),
            ratios=data.get("ratios") or {},
        )


class ProfileStore:
    """Tiny JSON store for per-device profiles (no external dependencies)."""

    def __init__(self, directory: Optional[str] = None) -> None:
        self.directory = directory or DEFAULT_PROFILE_DIR

    def _path(self, profile: DeviceProfile) -> str:
        return os.path.join(self.directory, f"{profile.key}.json")

    def load(self, profile: DeviceProfile) -> Optional[DeviceProfile]:
        path = self._path(profile)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return DeviceProfile.from_dict(json.load(handle))
        except (OSError, ValueError) as exc:  # pragma: no cover - corrupted file
            logger.warning("读取设备 profile 失败 %s: %s", path, exc)
            return None

    def save(self, profile: DeviceProfile) -> str:
        os.makedirs(self.directory, exist_ok=True)
        path = self._path(profile)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(profile.to_dict(), handle, ensure_ascii=False, indent=2)
        logger.info("设备 profile 已保存: %s", path)
        return path


# ---------------------------------------------------------------------------
# Locator
# ---------------------------------------------------------------------------


class LocatorError(RuntimeError):
    """Raised when a spec cannot be resolved and no safe fallback exists."""


class PageMismatchError(LocatorError):
    """Raised when the current page does not match the spec's fingerprint."""


class Locator:
    """Resolve semantic element specs against a uiautomator2-like device.

    Parameters
    ----------
    device:
        Object exposing ``dump_hierarchy()`` and ``click(x, y)``.  Extra
        attributes such as ``window_size()`` / ``info`` are used when present.
    profile_dir:
        Directory used by :class:`ProfileStore`.  Defaults to ``profiles/``.
    pages / specs:
        Override the built-in fingerprints and element specs.
    """

    def __init__(
        self,
        device: Any,
        profile_dir: Optional[str] = None,
        pages: Sequence[PageSpec] = DEFAULT_PAGES,
        specs: Sequence[ElementSpec] = DEFAULT_SPECS,
    ) -> None:
        self.device = device
        self.pages = tuple(pages)
        self.specs = {spec.name: spec for spec in specs}
        self.store = ProfileStore(profile_dir)
        self._xml: str = ""
        self._root: Optional[ET.Element] = None
        self._profile: Optional[DeviceProfile] = None
        self._last_refresh: float = 0.0
        # Default freshness window for one resolution pass; a single ADB dump
        # is reused by page detection and every spec lookup in that window.
        self.snapshot_ttl: float = 0.3

    # -- device facts ------------------------------------------------------

    def _device_info(self) -> Dict[str, Any]:
        try:
            info = self.device.info
            merged = dict(info) if isinstance(info, dict) else {}
        except Exception:  # pragma: no cover - defensive
            merged = {}
        # uiautomator2 does not always expose density/model/serial in .info,
        # so fall back to cheap shell queries once and cache the result.
        if "_shell_meta" not in self.__dict__:
            meta: Dict[str, Any] = {}
            density = self._shell("wm density")
            match = re.search(r"(?:Physical|Override) density:\s*(\d+)", density or "")
            if match:
                meta["displayDensity"] = int(match.group(1))
            model = self._shell("getprop ro.product.model")
            if model:
                meta["model"] = model
            self._shell_meta = meta
        for key, value in self._shell_meta.items():
            merged.setdefault(key, value)
        return merged

    def _shell(self, command: str) -> str:
        """Run a read-only adb shell command, returning '' on failure."""
        try:
            result = self.device.shell(command)
        except Exception:  # pragma: no cover - backend without shell()
            return ""
        # uiautomator2 >= 3.x returns a ShellResponse object; older versions
        # and test doubles return a plain string.
        output = getattr(result, "output", result)
        return str(output or "").strip()

    def _screen_size(self) -> Tuple[int, int]:
        try:
            width, height = self.device.window_size()
            if width and height:
                return int(width), int(height)
        except Exception:  # pragma: no cover - old u2 versions
            pass
        info = self._device_info()
        return int(info.get("displayWidth") or 0), int(info.get("displayHeight") or 0)

    def _serial(self) -> str:
        for attr in ("serial",):
            value = getattr(self.device, attr, None)
            if value:
                return str(value)
        info = self._device_info()
        for key in ("serial", "deviceSerial", "udid"):
            value = info.get(key)
            if value:
                return str(value)
        return ""

    def profile(self) -> DeviceProfile:
        """Return the current device profile, loading learned ratios once."""
        if self._profile is not None:
            return self._profile
        width, height = self._screen_size()
        info = self._device_info()
        draft = DeviceProfile(
            width=width,
            height=height,
            density=info.get("displayDensity"),
            model=str(info.get("model") or info.get("productName") or ""),
            serial=self._serial(),
        )
        loaded = self.store.load(draft)
        self._profile = loaded or draft
        return self._profile

    # -- hierarchy ---------------------------------------------------------

    def refresh(self, force: bool = False, max_age: Optional[float] = None) -> ET.Element:
        """Dump (or reuse) the UI hierarchy and return its root element.

        ``max_age`` keeps a single resolution pass from dumping the hierarchy
        once per spec (each dump costs an ADB round-trip).  Pass ``force=True``
        when the caller knows the screen has changed.
        """
        if max_age is None:
            max_age = self.snapshot_ttl
        now = time.time()
        if not force and self._root is not None and (now - self._last_refresh) <= max_age:
            return self._root
        xml_text = ""
        try:
            xml_text = self.device.dump_hierarchy() or ""
        except Exception as exc:  # pragma: no cover - device hiccup
            logger.debug("dump_hierarchy 失败: %s", exc)
        self._xml = xml_text
        try:
            self._root = ET.fromstring(xml_text) if xml_text else None
        except ET.ParseError as exc:
            logger.debug("解析 UI 层级失败: %s", exc)
            self._root = None
        self._last_refresh = now
        return self._root  # type: ignore[return-value]

    def _iter_nodes(self) -> Iterable[ET.Element]:
        root = self.refresh()
        if root is None:
            return ()
        return root.iter("node")

    # -- page fingerprint --------------------------------------------------

    def detect_page(self) -> Optional[str]:
        """Return the first matching page fingerprint name, else ``None``."""
        return self._detect_page_in(self.refresh())

    def _detect_page_in(self, root: Optional[ET.Element]) -> Optional[str]:
        """Page fingerprint detection over an already-dumped hierarchy."""
        if root is None:
            return None
        ids: set = set()
        texts: set = set()
        for node in root.iter("node"):
            rid = (node.get("resource-id") or "").strip()
            if rid:
                ids.add(rid)
            text = (node.get("text") or "").strip()
            if text:
                texts.add(text)
        for page in self.pages:
            if page.any_ids and any(item in ids for item in page.any_ids):
                return page.name
            if page.any_texts and any(item in texts for item in page.any_texts):
                return page.name
        return None

    def hits_in(self, root: ET.Element, spec: Union[ElementSpec, str]) -> List[Hit]:
        """Resolve a spec against a caller-provided hierarchy dump.

        The rush pipeline already owns an XML dump (one ADB round-trip); this
        lets it use semantic card resolution without paying for a second dump.
        """
        if isinstance(spec, str):
            spec = self.specs[spec]
        if spec.page and self._detect_page_in(root) != spec.page:
            return []
        nodes = list(root.iter("node"))
        parent_map = {child: parent for parent in root.iter("node") for child in parent}
        return self._resource_hits(spec, nodes, parent_map)

    def assert_page(self, name: str) -> None:
        """Raise :class:`PageMismatchError` unless ``name`` is the current page."""
        current = self.detect_page()
        if current != name:
            raise PageMismatchError(f"页面不匹配：期望 {name}，实际 {current}")

    # -- resolution --------------------------------------------------------

    def _within_screen(self, rect: Rect) -> bool:
        width, height = self._screen_size()
        if not (width and height):
            return True
        x, y = rect.center
        return 0 <= x < width and 0 <= y < height

    @staticmethod
    def _clickable_rect(
        node: ET.Element, parent_map: Dict[ET.Element, ET.Element]
    ) -> Rect:
        current: Optional[ET.Element] = node
        while current is not None:
            if current.get("clickable") == "true":
                rect = parse_bounds(current.get("bounds"))
                if rect is not None:
                    return rect
            current = parent_map.get(current)
        return parse_bounds(node.get("bounds")) or Rect(0, 0, 0, 0)

    def _match_by_resource_id(
        self, spec: ElementSpec, nodes: List[ET.Element]
    ) -> Optional[Hit]:
        wanted = set(spec.resource_ids)
        if not wanted:
            return None
        parent_map = {child: parent for parent in self._iter_nodes() for child in parent}
        for node in nodes:
            rid = (node.get("resource-id") or "").strip()
            if rid not in wanted:
                continue
            if spec.scope_ids and not self._in_scope(node, parent_map, spec.scope_ids):
                continue
            rect = self._clickable_rect(node, parent_map) if spec.clickable_ancestor else parse_bounds(node.get("bounds") or "")
            if rect is None or not rect.is_valid() or not self._within_screen(rect):
                continue
            return Hit(spec.name, rect, "resource-id", node)
        return None

    @staticmethod
    def _in_scope(
        node: ET.Element,
        parent_map: Dict[ET.Element, ET.Element],
        scope_ids: Tuple[str, ...],
    ) -> bool:
        """True when an ancestor (or the node itself) carries a scope id."""
        wanted = set(scope_ids)
        current: Optional[ET.Element] = node
        while current is not None:
            if (current.get("resource-id") or "").strip() in wanted:
                return True
            current = parent_map.get(current)
        return False

    def _resource_hits(
        self, spec: ElementSpec, nodes: List[ET.Element], parent_map: Dict[ET.Element, ET.Element]
    ) -> List[Hit]:
        wanted = set(spec.resource_ids)
        hits: List[Hit] = []
        for node in nodes:
            rid = (node.get("resource-id") or "").strip()
            if rid not in wanted:
                continue
            if spec.scope_ids and not self._in_scope(node, parent_map, spec.scope_ids):
                continue
            rect = (
                self._clickable_rect(node, parent_map)
                if spec.clickable_ancestor
                else parse_bounds(node.get("bounds") or "")
            )
            if rect is None or not rect.is_valid() or not self._within_screen(rect):
                continue
            hits.append(Hit(spec.name, rect, "resource-id", node))
        # Document order is usually top-to-bottom, left-to-right already, but
        # sort explicitly so callers can index cards deterministically.
        hits.sort(key=lambda hit: (hit.rect.top, hit.rect.left))
        return hits

    def _match_by_text(
        self, spec: ElementSpec, nodes: List[ET.Element], source: str
    ) -> Optional[Hit]:
        attr = "text" if source == "text" else "content-desc"
        wanted = spec.texts if source == "text" else spec.descs
        if not wanted:
            return None
        parent_map = {child: parent for parent in self._iter_nodes() for child in parent}
        # Pass 1: exact match, pass 2: containment (only for text/desc specs)
        for exact in (True, False):
            for node in nodes:
                value = (node.get(attr) or "").strip()
                if not value:
                    continue
                matched = value in wanted if exact else any(item in value for item in wanted)
                if not matched:
                    continue
                rect = (
                    self._clickable_rect(node, parent_map)
                    if spec.clickable_ancestor
                    else parse_bounds(node.get("bounds") or "")
                )
                if rect is None or not rect.is_valid() or not self._within_screen(rect):
                    continue
                return Hit(spec.name, rect, source, node)
        return None

    def _match_by_xpath(self, spec: ElementSpec) -> Optional[Hit]:
        if not spec.xpath:
            return None
        try:
            elements = self.device.xpath(spec.xpath).all()
        except Exception:  # pragma: no cover - optional backend
            return None
        for element in elements:
            try:
                info = element.info or {}
                rect = parse_bounds(info.get("bounds"))
            except Exception:  # pragma: no cover
                rect = None
            if rect is None or not rect.is_valid() or not self._within_screen(rect):
                continue
            return Hit(spec.name, rect, "xpath")
        return None

    def _ratio_point(self, spec: ElementSpec) -> Optional[Tuple[int, int]]:
        if not spec.allow_ratio_fallback:
            return None
        width, height = self._screen_size()
        if not (width and height):
            return None
        ratio = spec.fallback_ratio
        source = "ratio"
        if ratio is None:
            ratio = self.profile().ratios.get(spec.name)
            source = "profile-ratio"
        if ratio is None:
            return None
        x = max(0, min(width - 1, int(round(ratio[0] * width))))
        y = max(0, min(height - 1, int(round(ratio[1] * height))))
        self._last_ratio_source = source
        return x, y

    def resolve(self, spec: Union[ElementSpec, str]) -> Optional[Hit]:
        """Resolve one spec; returns ``None`` when nothing safe matched."""
        if isinstance(spec, str):
            spec = self.specs[spec]
        if spec.page and self.detect_page() != spec.page:
            logger.debug("spec %s 跳过：页面不符", spec.name)
            return None
        nodes = list(self._iter_nodes())
        for matcher in (
            lambda: self._match_by_resource_id(spec, nodes),
            lambda: self._match_by_text(spec, nodes, "text"),
            lambda: self._match_by_text(spec, nodes, "desc"),
            lambda: self._match_by_xpath(spec),
        ):
            hit = matcher()
            if hit is not None:
                return hit
        point = self._ratio_point(spec)
        if point is not None:
            width, height = self._screen_size()
            rect = Rect(point[0], point[1], point[0] + 1, point[1] + 1)
            return Hit(spec.name, rect, getattr(self, "_last_ratio_source", "ratio"))
        return None

    def resolve_all(self, spec: Union[ElementSpec, str]) -> List[Hit]:
        """Resolve every matching node, ordered top-to-bottom then left-to-right.

        Card lists such as session/price options need positional indexing:
        ``tap_index("sku_price_card", 3)`` selects the third card in reading
        order without depending on any pixel coordinate from another phone.
        """
        if isinstance(spec, str):
            spec = self.specs[spec]
        if spec.page and self.detect_page() != spec.page:
            return []
        if not spec.resource_ids:
            hit = self.resolve(spec)
            return [] if hit is None else [hit]
        nodes = list(self._iter_nodes())
        parent_map = {child: parent for parent in self._iter_nodes() for child in parent}
        return self._resource_hits(spec, nodes, parent_map)

    def tap_index(self, spec: Union[ElementSpec, str], index: int) -> Hit:
        """Tap the ``index``-th (1-based) match of ``spec`` in reading order."""
        hits = self.resolve_all(spec)
        if not hits:
            # Page transitions (activity resume, panel animation) can produce
            # one incomplete dump; retry once with a fresh snapshot.
            time.sleep(0.3)
            self.refresh(force=True)
            hits = self.resolve_all(spec)
        if index < 1 or index > len(hits):
            raise LocatorError(
                f"{getattr(spec, 'name', spec)} 只有 {len(hits)} 个匹配，无法选择第 {index} 个"
            )
        hit = hits[index - 1]
        x, y = hit.point
        self.device.click(x, y)
        logger.debug("tap_index %s[%d] at (%s, %s)", hit.spec, index, x, y)
        return hit

    def tap(self, spec: Union[ElementSpec, str], duration: float = 0.05) -> Hit:
        """Resolve ``spec`` and click its center; raises :class:`LocatorError`."""
        hit = self.resolve(spec)
        if hit is None:
            raise LocatorError(f"无法定位控件: {getattr(spec, 'name', spec)}")
        x, y = hit.point
        try:
            if duration and duration > 0.0 and hasattr(self.device, "long_click"):
                self.device.click(x, y)
            else:
                self.device.click(x, y)
        except TypeError:  # pragma: no cover - backend without click(x, y)
            self.device.click(x=x, y=y)
        logger.debug("tap %s at (%s, %s) via %s", hit.spec, x, y, hit.source)
        return hit

    # -- calibration -------------------------------------------------------

    def learn(self, specs: Optional[Iterable[ElementSpec]] = None) -> Dict[str, List[float]]:
        """Record ratios for every currently resolvable spec and persist them."""
        width, height = self._screen_size()
        if not (width and height):
            raise LocatorError("无法获取屏幕尺寸，不能校准")
        profile = self.profile()
        learned: Dict[str, List[float]] = {}
        previous_ttl = self.snapshot_ttl
        self.snapshot_ttl = 5.0
        try:
            self.refresh(force=True)
            for spec in self.specs.values() if specs is None else specs:
                hit = self.resolve(spec)
                if hit is None:
                    continue
                x, y = hit.point
                ratio = [round(x / width, 6), round(y / height, 6)]
                profile.ratios[spec.name] = (ratio[0], ratio[1])
                learned[spec.name] = ratio
        finally:
            self.snapshot_ttl = previous_ttl
        self.store.save(profile)
        return learned

    def self_check(self) -> Dict[str, Any]:
        """Report page fingerprint and every spec's resolution state."""
        previous_ttl = self.snapshot_ttl
        self.snapshot_ttl = 5.0
        try:
            self.refresh(force=True)
            page = self.detect_page()
            results = {}
            for spec in self.specs.values():
                hits = self.resolve_all(spec)
                results[spec.name] = (
                    None
                    if not hits
                    else {
                        "source": hits[0].source,
                        "point": list(hits[0].point),
                        "count": len(hits),
                    }
                )
        finally:
            self.snapshot_ttl = previous_ttl
        return {
            "page": page,
            "screen": list(self._screen_size()),
            "profile": self.profile().key,
            "specs": results,
        }

    def scan(self, limit: int = 80) -> Dict[str, Any]:
        """Dump the current page's resource-ids and texts for fingerprint work.

        Used when a page is not recognised yet: open it on the phone, run
        ``python -m mobile.locator scan`` and use the output to extend
        :data:`DEFAULT_PAGES` / :data:`DEFAULT_SPECS`.
        """
        self.refresh(force=True)
        ids: Dict[str, int] = {}
        texts: Dict[str, int] = {}
        descs: Dict[str, int] = {}
        clickable_ids: Dict[str, int] = {}
        for node in self._iter_nodes():
            rid = (node.get("resource-id") or "").strip()
            if rid:
                ids[rid] = ids.get(rid, 0) + 1
                if node.get("clickable") == "true":
                    clickable_ids[rid] = clickable_ids.get(rid, 0) + 1
            text = (node.get("text") or "").strip()
            if text:
                texts[text] = texts.get(text, 0) + 1
            desc = (node.get("content-desc") or "").strip()
            if desc:
                descs[desc] = descs.get(desc, 0) + 1

        def top(counter: Dict[str, int]) -> List[Dict[str, Any]]:
            items = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
            return [{"value": value, "count": count} for value, count in items[:limit]]

        return {
            "page": self.detect_page(),
            "screen": list(self._screen_size()),
            "resource_ids": top(ids),
            "clickable_ids": top(clickable_ids),
            "texts": top(texts),
            "content_descs": top(descs),
        }


# ---------------------------------------------------------------------------
# CLI: python -m mobile.locator selfcheck [--serial SERIAL] [--learn]
# ---------------------------------------------------------------------------


def _connect(serial: Optional[str] = None) -> Any:
    import uiautomator2 as u2  # imported lazily so the module stays testable

    return u2.connect(serial) if serial else u2.connect()


def main(argv: Optional[Sequence[str]] = None) -> int:
    import argparse
    import sys

    # Windows consoles/redirects may default to GBK, which cannot encode every
    # icon glyph found in the hierarchy dump; force UTF-8 for JSON output.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):  # pragma: no cover
            pass

    parser = argparse.ArgumentParser(description="Damai 多机型控件定位自检")
    parser.add_argument(
        "command",
        choices=("selfcheck", "learn", "scan"),
        nargs="?",
        default="selfcheck",
    )
    parser.add_argument("--serial", default=os.environ.get("ANDROID_SERIAL") or None)
    parser.add_argument("--profile-dir", default=None)
    args = parser.parse_args(argv)

    device = _connect(args.serial)
    locator = Locator(device, profile_dir=args.profile_dir)
    if args.command == "learn":
        learned = locator.learn()
        print(json.dumps({"learned": learned}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "scan":
        print(json.dumps(locator.scan(), ensure_ascii=False, indent=2))
        return 0
    report = locator.self_check()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["page"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
