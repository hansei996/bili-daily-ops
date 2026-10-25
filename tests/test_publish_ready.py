"""发布前的自检：README 不许吹、不许有死链、必须承认做不到的事。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")
TICK = chr(96)


def test_readme_states_what_it_cannot_do():
    assert "做不到" in README
    for must in ("预测哪条会火", "判断表达风格", "自动发布"):
        assert must in README, "README 少了这一条边界：" + must


def test_readme_never_promises_views_and_only_disclaims_replay():
    for banned in ("提升播放量", "保证播放", "预测哪条会火可以"):
        assert banned not in README, "README 里出现了不该承诺的东西：" + banned
    # 「确定性回放」只允许出现在否定语境里（我们明确说不能拿它当卖点）
    if "确定性回放" in README:
        index = README.index("确定性回放")
        window = README[max(0, index - 12): index + 12]
        assert "不拿" in window or "不" in window, "提到了回放但没有否定语气"


def test_readme_points_at_real_files():
    pattern = TICK + r"([A-Za-z0-9_.\-/]+\.(?:md|py))" + TICK
    links = set(re.findall(pattern, README))
    assert links, "README 至少应该指向 DECISION 与工具"
    missing = [l for l in links if not (ROOT / l).exists()]
    assert missing == [], "README 提到但仓库里没有：" + ", ".join(sorted(missing))


def test_readme_numbers_are_traceable_to_their_source():
    """README 里的统计数字必须能在 ENGINEERING.md 里找到出处 —— 手抄的数字迟早和推导分家。"""
    engineering = (ROOT / "ENGINEERING.md").read_text(encoding="utf-8")
    for number in ("0.6457", "25", "381", "0.36"):
        if number in README:
            assert number in engineering, "README 里的 " + number + " 在 ENGINEERING.md 里找不到出处"


def test_our_own_minimum_detectable_shrinks_with_samples():
    sys.path.insert(0, str(ROOT / "tools"))
    import cohort_check as cc

    assert cc.min_detectable(5) > cc.min_detectable(25) > cc.min_detectable(365)


def test_license_exists_and_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "WITHOUT WARRANTY" in text


def test_gitignore_keeps_generated_dirs_out():
    text = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("_live/", "_demo/", "__pycache__/"):
        assert entry in text