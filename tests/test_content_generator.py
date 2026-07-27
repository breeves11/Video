import json

from backend import llm_client
from backend.content_generator import generate_content


def test_template_fallback_used_without_api_key():
    package = generate_content("home workout no equipment", "health_wellness")
    assert package.source == "template"
    assert len(package.titles) == 5
    assert "home workout no equipment" in package.description.lower() or package.video_topic in package.description
    assert package.tags
    assert package.script
    assert len(package.thumbnail_text_ideas) == 3


def test_video_topic_overrides_niche_keyword():
    package = generate_content("ai coding assistant comparison", "ai_tools_reviews", video_topic="Cursor vs Copilot")
    assert package.video_topic == "Cursor vs Copilot"
    assert any("Cursor Vs Copilot" in t or "cursor vs copilot" in t.lower() for t in package.titles)


def test_llm_path_used_when_available_and_valid(monkeypatch):
    fake_response = json.dumps(
        {
            "titles": ["Title A", "Title B", "Title C", "Title D", "Title E"],
            "description": "A Claude-written description.",
            "tags": ["tag1", "tag2"],
            "script": "HOOK...SECTION 1...CTA",
            "thumbnail_text_ideas": ["IDEA 1", "IDEA 2", "IDEA 3"],
        }
    )
    monkeypatch.setattr(llm_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_client, "generate_text", lambda prompt, max_tokens=1500: fake_response)

    package = generate_content("dividend investing for beginners", "personal_finance")

    assert package.source == "claude"
    assert package.titles == ["Title A", "Title B", "Title C", "Title D", "Title E"]
    assert package.description == "A Claude-written description."


def test_llm_path_falls_back_to_template_on_invalid_json(monkeypatch):
    monkeypatch.setattr(llm_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_client, "generate_text", lambda prompt, max_tokens=1500: "not valid json at all")

    package = generate_content("dividend investing for beginners", "personal_finance")

    assert package.source == "template"


def test_llm_path_falls_back_to_template_when_generate_text_returns_none(monkeypatch):
    monkeypatch.setattr(llm_client, "is_available", lambda: True)
    monkeypatch.setattr(llm_client, "generate_text", lambda prompt, max_tokens=1500: None)

    package = generate_content("dividend investing for beginners", "personal_finance")

    assert package.source == "template"


def test_title_templates_do_not_repeat_beginner_wording():
    package = generate_content("dividend investing for beginners", "personal_finance")
    for title in package.titles:
        assert title.lower().count("beginner") <= 1
