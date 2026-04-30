"""
Windows file path helpers: optional \\\\?\\ long-path prefix and open/makedirs retry
when the plain path hits EINVAL (errno 22) on some setups.
"""

import os
from typing import List, Optional, Tuple


def windows_file_arg_error(exc: BaseException) -> bool:
    """True for OSError cases where retrying with an extended path may help."""
    if not isinstance(exc, OSError):
        return False
    if exc.errno == 22:  # EINVAL
        return True
    we = getattr(exc, "winerror", None)
    # 123 invalid name, 161 bad path, 267 directory name invalid
    if we in (123, 161, 267):
        return True
    return False


def extended_abs_path(path: str) -> str:
    """Return \\\\?\\ absolute path on Windows when applicable; otherwise absolute path."""
    if os.name != "nt" or not path or not str(path).strip():
        return path
    try:
        ap = os.path.abspath(os.path.normpath(path))
    except (OSError, ValueError, TypeError):
        return path
    if ap.startswith("\\\\?\\"):
        return ap
    if ap.startswith("\\\\"):
        return "\\\\?\\UNC\\" + ap[2:]
    return "\\\\?\\" + ap


def io_path_candidates(plain_abs: str) -> List[str]:
    """Try plain absolute path first, then extended (if different)."""
    try:
        plain = os.path.abspath(os.path.normpath(plain_abs))
    except (OSError, ValueError, TypeError):
        return [plain_abs]
    if os.name != "nt":
        return [plain]
    ext = extended_abs_path(plain)
    return [plain, ext] if ext != plain else [plain]


def open_text_with_path_fallback(plain_path: str, mode: str):
    """
    Open a UTF-8 text file; try plain path then extended on Windows file-arg errors.
    Returns an opened file handle (caller must close).
    """
    if mode not in ("r", "w", "a"):
        raise ValueError("mode must be r, w, or a")
    last: Optional[OSError] = None
    paths = io_path_candidates(plain_path)
    for i, p in enumerate(paths):
        try:
            return open(p, mode, encoding="utf-8")
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(paths) - 1:
                continue
            raise
    assert last is not None
    raise last


def path_exists_any(plain_path: str) -> bool:
    for p in io_path_candidates(plain_path):
        try:
            if os.path.exists(p):
                return True
        except OSError:
            continue
    return False


def isfile_any(plain_path: str) -> bool:
    for p in io_path_candidates(plain_path):
        try:
            if os.path.isfile(p):
                return True
        except OSError:
            continue
    return False


def makedirs_with_path_fallback(plain_dir: str) -> None:
    """Create directory tree; retry with extended path on Windows EINVAL-style errors."""
    paths = io_path_candidates(plain_dir)
    last: Optional[OSError] = None
    for i, p in enumerate(paths):
        try:
            os.makedirs(p, exist_ok=True)
            return
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(paths) - 1:
                continue
            raise
    assert last is not None
    raise last


def open_binary_with_path_fallback(plain_path: str, mode: str):
    """Open binary (e.g. mode 'wb'); try plain then extended path on Windows file-arg errors."""
    if mode != "wb":
        raise ValueError("only wb supported")
    paths = io_path_candidates(plain_path)
    last: Optional[OSError] = None
    for i, p in enumerate(paths):
        try:
            return open(p, mode)
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(paths) - 1:
                continue
            raise
    assert last is not None
    raise last


def os_replace_with_path_fallback(src_plain: str, dst_plain: str) -> None:
    """os.replace(src, dst) with plain then extended path pairs on Windows EINVAL-style errors."""
    try:
        src_abs = os.path.abspath(os.path.normpath(src_plain))
        dst_abs = os.path.abspath(os.path.normpath(dst_plain))
    except (OSError, ValueError, TypeError):
        os.replace(src_plain, dst_plain)
        return
    if os.name != "nt":
        os.replace(src_abs, dst_abs)
        return
    pairs = list(zip(io_path_candidates(src_abs), io_path_candidates(dst_abs)))
    last: Optional[OSError] = None
    for i, (s, d) in enumerate(pairs):
        try:
            os.replace(s, d)
            return
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(pairs) - 1:
                continue
            raise
    assert last is not None
    raise last


def unlink_if_exists_any(plain_path: str) -> None:
    """Remove file if it exists at plain or extended path."""
    for p in io_path_candidates(plain_path):
        try:
            if os.path.isfile(p):
                os.remove(p)
                return
        except OSError:
            continue


def shutil_move_with_fallback(src: str, dst: str) -> None:
    """shutil.move with plain paths first, then extended paths on Windows EINVAL-style errors."""
    import shutil

    src_abs = os.path.abspath(os.path.normpath(src))
    dst_abs = os.path.abspath(os.path.normpath(dst))
    pairs: List[Tuple[str, str]] = [(src_abs, dst_abs)]
    if os.name == "nt":
        se, de = extended_abs_path(src_abs), extended_abs_path(dst_abs)
        if (se, de) != (src_abs, dst_abs):
            pairs.append((se, de))
    last: Optional[OSError] = None
    for i, (s, d) in enumerate(pairs):
        try:
            shutil.move(s, d)
            return
        except OSError as e:
            last = e
            if windows_file_arg_error(e) and i < len(pairs) - 1:
                continue
            raise
    assert last is not None
    raise last
