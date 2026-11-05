import pytest

from wanderlens.drafts import build_hashtags, clip_text, fit_post, hashtag
from wanderlens.semantic import coerce_score, extract_json_object, merge_frame_semantics, normalize_semantic
from wanderlens.domain import Asset
from wanderlens.trips import assign_trips
from wanderlens.media import frame_timestamps


def test_extract_json_accepts_fenced_and_wrapped_text():
    assert extract_json_object('```json\n{"caption_zh_hant": "山"}\n```')["caption_zh_hant"] == "山"
    assert extract_json_object('說明 {"caption_en": "sea"} 結束')["caption_en"] == "sea"


def test_extract_json_rejects_plain_text():
    with pytest.raises(ValueError):
        extract_json_object("沒有物件")


def test_normalize_semantic_clamps_scores_and_drops_unknown_products():
    semantic = normalize_semantic(
        {
            "caption_zh_hant": " 海岸 ",
            "caption_en": "Coast",
            "subjects": "山, 海",
            "contains_identifiable_people": "no",
            "aesthetic_score": 8,
            "suggested_products": ["wallpaper", "meme"],
            "sensitive_content": "false",
        }
    )
    assert semantic["subjects"] == ["山", "海"]
    assert semantic["contains_identifiable_people"] is False
    assert semantic["aesthetic_score"] == 0.8
    assert semantic["suggested_products"] == ["wallpaper"]
    assert coerce_score("100") == 1.0


def test_merge_frames_treats_any_person_as_present():
    merged = merge_frame_semantics(
        [
            normalize_semantic({"caption_zh_hant": "第一幀", "contains_identifiable_people": False, "subjects": ["海"]}),
            normalize_semantic(
                {
                    "caption_zh_hant": "第二幀",
                    "contains_identifiable_people": True,
                    "sensitive_content": False,
                    "subjects": ["人"],
                    "aesthetic_score": 0.4,
                }
            ),
        ]
    )
    assert merged["contains_identifiable_people"] is True
    assert merged["subjects"] == ["海", "人"]
    assert "第一幀" in merged["caption_zh_hant"]


def test_hashtags_and_x_length():
    assert hashtag("九州!") == "#九州"
    tags = build_hashtags("zh-Hant", ["海岸"], "九州")
    assert tags[0] == "#旅行攝影"
    assert "#九州" in tags
    fitted = fit_post("句子", ["#" + ("很長" * 100)], 20)
    assert len(fitted) <= 20


def test_clip_text_uses_an_ellipsis():
    assert clip_text("一二三四五", 4) == "一二三…"


def test_trip_gap_and_distance():
    first = Asset(id="a" * 16, relative_path="a.jpg", media_type="image", byte_size=1, captured_at="2024-03-01T10:00:00", gps={"lat": 0, "lon": 0})
    second = Asset(id="b" * 16, relative_path="b.jpg", media_type="image", byte_size=1, captured_at="2024-03-02T10:00:00", gps={"lat": 0, "lon": 1})
    third = Asset(id="c" * 16, relative_path="c.jpg", media_type="image", byte_size=1, captured_at="2024-03-06T10:00:00", gps={"lat": 0, "lon": 1})
    assign_trips([first, second, third], gap_hours_limit=72, distance_km=0)
    assert first.trip_id == second.trip_id
    assert third.trip_id != first.trip_id

    near = Asset(id="d" * 16, relative_path="d.jpg", media_type="image", byte_size=1, captured_at="2024-03-01T10:00:00", gps={"lat": 0, "lon": 0})
    far = Asset(id="e" * 16, relative_path="e.jpg", media_type="image", byte_size=1, captured_at="2024-03-01T12:00:00", gps={"lat": 0, "lon": 20})
    assign_trips([near, far], gap_hours_limit=72, distance_km=500)
    assert near.trip_id != far.trip_id


def test_frame_timestamps_cover_the_duration():
    stamps = frame_timestamps(10, 4)
    assert stamps[0] == 0.1
    assert stamps[-1] <= 9.75
    assert frame_timestamps(None, 3) == [0.5]
