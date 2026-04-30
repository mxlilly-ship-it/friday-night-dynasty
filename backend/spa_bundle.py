"""Detect whether the Vite production bundle under frontend/dist is stale vs frontend/src."""

from __future__ import annotations

import os
import re
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def spa_frontend_dir() -> Path:
    return project_root() / "frontend"


def spa_dist_dir() -> Path:
    return spa_frontend_dir() / "dist"


def spa_dist_index() -> Path:
    return spa_dist_dir() / "index.html"


def spa_src_dir() -> Path:
    return spa_frontend_dir() / "src"


def _max_mtime_under(path: Path, extensions: tuple[str, ...]) -> float | None:
    """Newest mtime for files under path with given suffixes (small trees only)."""
    if not path.is_dir():
        return None
    newest: float | None = None
    try:
        for p in path.rglob("*"):
            if not p.is_file():
                continue
            suf = p.suffix.lower()
            if suf not in extensions:
                continue
            try:
                t = p.stat().st_mtime
            except OSError:
                continue
            if newest is None or t > newest:
                newest = t
    except OSError:
        return None
    return newest


def _dist_index_and_entry_js_mt(dist_index: Path) -> tuple[float | None, float | None]:
    """Mtimes of dist/index.html and the main /assets/index-*.js it references (if any)."""
    idx_t: float | None = None
    try:
        idx_t = dist_index.stat().st_mtime
    except OSError:
        pass
    js_t: float | None = None
    try:
        text = dist_index.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return (idx_t, None)
    m = re.search(r'src="/assets/([^"]+\.js)"', text)
    if not m:
        return (idx_t, None)
    script = dist_index.parent / "assets" / m.group(1)
    try:
        js_t = script.stat().st_mtime
    except OSError:
        js_t = None
    return (idx_t, js_t)


def spa_dist_bundle_is_stale(dist_index: Path) -> bool:
    """
    True when Vite source is newer than the served dist bundle.

    Comparing only index.html mtime is wrong: index can be newer than the huge
    index-*.js file (e.g. checkout/touch), so we use the **older** of index + entry JS.
    """
    if os.environ.get("FND_IGNORE_STALE_SPA", "").strip().lower() in ("1", "true", "yes"):
        return False
    if not dist_index.is_file():
        return False
    src_dir = spa_src_dir()
    src_newest = _max_mtime_under(src_dir, (".tsx", ".ts", ".css"))
    if src_newest is None:
        return False
    idx_t, js_t = _dist_index_and_entry_js_mt(dist_index)
    parts = [t for t in (idx_t, js_t) if t is not None]
    if not parts:
        return False
    dist_anchor = min(parts)
    return src_newest > dist_anchor + 2.0


def spa_frontend_build_needed(dist_index: Path | None = None) -> bool:
    """
    True when a production build should run: dist missing, or src newer than bundle.

    Unlike spa_dist_bundle_is_stale(), this ignores FND_IGNORE_STALE_SPA so we can
    refresh dist even when the server is configured to serve an older bundle.
    """
    idx = spa_dist_index() if dist_index is None else dist_index
    if not idx.is_file():
        return True
    src_newest = _max_mtime_under(spa_src_dir(), (".tsx", ".ts", ".css"))
    if src_newest is None:
        return False
    idx_t, js_t = _dist_index_and_entry_js_mt(idx)
    parts = [t for t in (idx_t, js_t) if t is not None]
    if not parts:
        return False
    dist_anchor = min(parts)
    return src_newest > dist_anchor + 2.0


def spa_ui_debug_meta(dist_index: Path) -> dict:
    """Diagnostics for /_fnd/ui-meta (why / may show the rebuild banner)."""
    src_dir = spa_src_dir()
    src_newest = _max_mtime_under(src_dir, (".tsx", ".ts", ".css"))
    idx_t, js_t = _dist_index_and_entry_js_mt(dist_index)
    parts = [t for t in (idx_t, js_t) if t is not None]
    dist_anchor = min(parts) if parts else None
    stale = spa_dist_bundle_is_stale(dist_index)
    return {
        "spa_stale": stale,
        "ignore_stale_env": os.environ.get("FND_IGNORE_STALE_SPA", ""),
        "src_dir": str(src_dir),
        "dist_index": str(dist_index),
        "src_newest_mtime": src_newest,
        "dist_index_mtime": idx_t,
        "dist_entry_js_mtime": js_t,
        "dist_anchor_mtime": dist_anchor,
    }
