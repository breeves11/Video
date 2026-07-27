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
