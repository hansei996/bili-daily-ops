"""seed_from_ranking：真实形状的 fixture + 风控回退。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import seed_from_ranking as seed  # noqa: E402
import validate_run  # noqa: E402

FIX = ROOT / "examples" / "fixtures" / "ranking.json"


def test_fixture_has_the_shape_we_expect():
    payload = json.loads(FIX.read_text(encoding="utf-8"))
    items = payload["data"]["list"]
    assert items and all("bvid" in i and "stat" in i for i in items)


def test_seeding_from_fixture_produces_valid_runs(tmp_path):
    code = seed.main(["--top", "3", "--cohort", "x", "--out", str(tmp_path / "r"),
                      "--transport", str(FIX)])
    assert code == 0
    runs = sorted((tmp_path / "r").iterdir())
    assert len(runs) == 3
    for run in runs:
        problems = validate_run.check(validate_run.load(run / "events.jsonl"), incomplete=True)
        assert [p for p in problems if p[0].startswith("V")] == [], problems


def test_seeded_events_never_invent_completion(tmp_path):
    seed.main(["--top", "1", "--cohort", "x", "--out", str(tmp_path / "one"), "--transport", str(FIX)])
    run = next((tmp_path / "one").iterdir())
    for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("type") == "metrics":
            assert "avg_view_sec" not in event, "接口不给我们就不能填"


def test_rate_limit_is_reported_rather_than_silently_empty(tmp_path):
    limited = tmp_path / "limited.json"
    limited.write_text(json.dumps({"code": -352, "message": "风控校验失败", "data": {}}), encoding="utf-8")
    code = seed.main(["--top", "3", "--out", str(tmp_path / "x"), "--transport", str(limited)])
    assert code == 1
    assert not (tmp_path / "x").exists() or not any((tmp_path / "x").iterdir())


def test_slug_is_stable_and_ascii_safe():
    assert seed.slug("BV1U3n46GEzY") == "BV1U3n46GEzY"
    assert seed.slug("【官方 MV】x") == "官方MVx"
