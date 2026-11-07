"""Check the console's light-mode colours for contrast: text (--ink) and secondary text (--muted) against the
cards (--panel) and every page background (each mode's --bg), to WCAG AA (4.5:1 for normal text).

    python tools/contrast.py          # prints each pair and its ratio; exits 1 if any falls short
"""

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "src" / "overheard" / "static" / "css" / "app.css"
AA = 4.5


def tokens(block: str) -> dict[str, str]:
    """`--name: #hex` pairs in a block of CSS."""
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def light_themes(css: str) -> dict[str, dict[str, str]]:
    """Each light theme's tokens: the base (:root, outside any media query) and each mode's overrides on it."""
    css_light = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)   # drop media blocks (dark mode, phones)
    base = tokens(re.search(r":root\s*\{([^}]*)\}", css_light).group(1))
    themes = {"base": base}
    for mode, block in re.findall(r'body\[data-mode="(\d)"\]\s*\{([^}]*)\}', css_light):
        themes[f"mode {mode}"] = {**themes.get(f"mode {mode}", base), **tokens(block)}
    return themes


def luminance(hex_: str) -> float:
    def channel(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def pairs(css: str | None = None) -> list[tuple[str, str, str, float]]:
    """(theme, text token, background token, ratio) for every pair that must pass."""
    out = []
    for theme, t in light_themes(css if css is not None else CSS.read_text()).items():
        for fg in ("ink", "muted"):
            for bg in ("panel", "bg"):
                out.append((theme, fg, bg, round(ratio(t[fg], t[bg]), 2)))
    return out


if __name__ == "__main__":
    bad = 0
    for theme, fg, bg, r in pairs():
        ok = r >= AA
        bad += not ok
        print(f"{theme:7} --{fg:6} on --{bg:6} {r:5.2f}:1  {'ok' if ok else 'BELOW AA'}")
    sys.exit(1 if bad else 0)
