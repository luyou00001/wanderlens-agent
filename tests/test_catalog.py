from wanderlens.catalog import load_catalog, select_models


def test_catalog_is_consistent():
    catalog = load_catalog()
    models = catalog["models"]
    assert len(models) >= 30
    ids = [model["id"] for model in models]
    assert len(ids) == len(set(ids))
    recommended = [model for model in models if model["status"] == "recommended"]
    assert [model["id"] for model in recommended] == ["qwen3.5-9b"]
    assert recommended[0]["huggingface"] == "Qwen/Qwen3.5-9B"
    assert recommended[0]["commercial_use"] == "allowed"
    restricted = {model["id"]: model["commercial_use"] for model in models if model["status"] == "restricted"}
    assert restricted["musicgen-medium"] == "disallowed"
    assert restricted["jina-clip-v2"] == "disallowed"
    assert restricted["stable-audio-open-1.0"] == "conditional"
    vision = select_models(models, role="vision_language", commercial="allowed")
    assert any(model["id"] == "qwen3.5-9b" for model in vision)
    assert all(model["commercial_use"] == "allowed" for model in vision)


def test_prompt_forbids_invented_identity_and_place():
    from wanderlens.paths import prompt_path

    text = prompt_path().read_text(encoding="utf-8")
    assert "不要寫出任何人名" in text
    assert "不要猜測精確城市" in text
    assert "contains_identifiable_people" in text
