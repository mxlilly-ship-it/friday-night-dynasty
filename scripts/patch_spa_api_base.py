"""One-off patch: ensure production bundle uses same-origin API base (empty string)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "dist" / "assets" / "index-5E64wc3T.js"


def main() -> None:
    t = JS.read_text(encoding="utf-8")
    # After first patch: empty template literal; prefer explicit "" for maximum JS engine compatibility
    old = "var En=``,Dn=!1"
    new = 'var En="",Dn=!1'
    if old not in t:
        if new.split(",")[0] in t:
            print("Already patched:", JS)
            return
        raise SystemExit(f"Pattern not found in {JS}")
    JS.write_text(t.replace(old, new, 1), encoding="utf-8")
    print("Patched:", JS)


if __name__ == "__main__":
    main()
