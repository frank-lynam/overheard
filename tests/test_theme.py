"""Light mode: every mode's page background is its own, and text on it is readable (WCAG AA)."""

import importlib.util
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "contrast.py"
spec = importlib.util.spec_from_file_location("contrast", TOOL)
contrast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contrast)


def test_text_meets_aa_on_cards_and_every_mode_background():
    short = [p for p in contrast.pairs() if p[3] < contrast.AA]
    assert not short, short


def test_each_mode_has_its_own_light_background():
    themes = contrast.light_themes(contrast.CSS.read_text())
    backgrounds = [themes[f"mode {m}"]["bg"].lower() for m in "0123"]
    assert len(set(backgrounds)) == 4, backgrounds
    assert all(themes[f"mode {m}"]["panel"].lower() == "#ffffff" for m in "123")   # cards stay white on the tint


def test_the_checker_catches_a_bad_pair():
    css = ":root { --bg: #ffffff; --panel: #ffffff; --ink: #000000; --muted: #bbbbbb; }"
    assert any(r < contrast.AA for *_, r in contrast.pairs(css))
