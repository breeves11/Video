import json
import re
from dataclasses import asdict, dataclass
from typing import List, Optional

from . import llm_client

TITLE_TEMPLATES = [
    "5 {topic} Mistakes to Avoid in 2026",
    "I Tried {topic} For 30 Days — Here's What Happened",
    "The Truth About {topic} Nobody Tells You",
    "{topic}: The Complete Guide",
    "Why {topic} Is Blowing Up Right Now",
]


@dataclass
class ContentPackage:
    niche_keyword: str
    video_topic: str
    titles: List[str]
    description: str
    tags: List[str]
    script: str
    thumbnail_text_ideas: List[str]
    source: str

    def to_dict(self):
        return asdict(self)


def _template_titles(topic: str) -> List[str]:
    return [t.format(topic=topic.title()) for t in TITLE_TEMPLATES]


def _template_description(topic: str, category: str) -> str:
    return (
        f"In this video we break down {topic} and what actually works in {category.replace('_', ' ')} "
        f"right now. If you're getting started with {topic}, this walkthrough covers the key mistakes to "
        f"avoid, the fastest path to results, and what to do next.\n\n"
        f"Subscribe for more {category.replace('_', ' ')} videos every week.\n\n"
        f"#{category.replace('_', '')} #{topic.replace(' ', '')}"
    )


def _template_tags(topic: str, category: str) -> List[str]:
    base = topic.split()
    return list(dict.fromkeys(base + [topic, category.replace("_", " "), f"{topic} 2026", f"{topic} for beginners"]))


def _template_script(topic: str, category: str) -> str:
    return (
        f"HOOK (0:00-0:15)\n"
        f"\"If you're interested in {topic}, the next few minutes could save you months of trial and error.\"\n\n"
        f"INTRO (0:15-0:45)\n"
        f"Quick channel/creator intro + what this video covers.\n\n"
        f"SECTION 1 — Why {topic} matters right now\n"
        f"Explain the trend/opportunity in {category.replace('_', ' ')}.\n\n"
        f"SECTION 2 — The 3 biggest mistakes people make\n"
        f"List and explain three common pitfalls.\n\n"
        f"SECTION 3 — Step-by-step walkthrough\n"
        f"Concrete, actionable steps the viewer can follow along with.\n\n"
        f"SECTION 4 — Results / proof / example\n"
        f"Show a real example, case study, or before/after.\n\n"
        f"CALL TO ACTION\n"
        f"Ask viewers to comment their experience, like, and subscribe for the next video in this series.\n\n"
        f"OUTRO\n"
        f"Tease the next video topic related to {topic}."
    )


def _template_thumbnail_ideas(topic: str) -> List[str]:
    return [
        f"\"{topic.upper()}\" in bold text over a shocked/curious face",
        "Before / After split image with a red arrow",
        "Big red X over a common mistake, green check over the fix",
    ]


def _template_package(niche_keyword: str, category: str, video_topic: Optional[str]) -> ContentPackage:
    topic = video_topic or niche_keyword
    return ContentPackage(
        niche_keyword=niche_keyword,
        video_topic=topic,
        titles=_template_titles(topic),
        description=_template_description(topic, category),
        tags=_template_tags(topic, category),
        script=_template_script(topic, category),
        thumbnail_text_ideas=_template_thumbnail_ideas(topic),
        source="template",
    )


def _extract_json(text: str) -> Optional[dict]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _llm_package(niche_keyword: str, category: str, video_topic: Optional[str]) -> Optional[ContentPackage]:
    topic = video_topic or niche_keyword
    prompt = (
        "You are a YouTube content strategist. Generate a content package for a video about "
        f'"{topic}" in the "{category.replace("_", " ")}" niche. Respond with ONLY valid JSON '
        "matching this schema, no prose before or after:\n"
        "{\n"
        '  "titles": [5 click-worthy but not clickbait-dishonest title options],\n'
        '  "description": "a 2-3 paragraph YouTube description with a soft CTA and hashtags",\n'
        '  "tags": [10-15 relevant search tags],\n'
        '  "script": "a full scene-by-scene script outline with a hook, 3-4 main sections, and a CTA",\n'
        '  "thumbnail_text_ideas": [3 short punchy thumbnail text ideas]\n'
        "}"
    )
    raw = llm_client.generate_text(prompt)
    if not raw:
        return None
    data = _extract_json(raw)
    if not data:
        return None
    try:
        return ContentPackage(
            niche_keyword=niche_keyword,
            video_topic=topic,
            titles=list(data["titles"]),
            description=str(data["description"]),
            tags=list(data["tags"]),
            script=str(data["script"]),
            thumbnail_text_ideas=list(data["thumbnail_text_ideas"]),
            source="claude",
        )
    except (KeyError, TypeError):
        return None


def generate_content(niche_keyword: str, category: str = "general", video_topic: Optional[str] = None) -> ContentPackage:
    if llm_client.is_available():
        package = _llm_package(niche_keyword, category, video_topic)
        if package is not None:
            return package
    return _template_package(niche_keyword, category, video_topic)
