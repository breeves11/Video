"""Seed catalog of candidate niches to evaluate.

Each category carries a baseline monetization estimate (rpm, i.e. revenue per
1,000 views), a rough audience-interest score, a rough competition score, and
a trend bias. These baselines are directional industry estimates, not
guarantees -- they exist so the app has a sane starting point to rank
candidates even before real YouTube data is wired in via YOUTUBE_API_KEY.
"""

NICHE_CATEGORIES = {
    "personal_finance": {
        "rpm": 18.0,
        "base_interest": 80,
        "base_competition": 75,
        "trend_bias": 5,
        "keywords": [
            "dividend investing for beginners",
            "high yield savings account strategies",
            "debt payoff journey vlog",
        ],
    },
    "ai_tools_reviews": {
        "rpm": 14.0,
        "base_interest": 92,
        "base_competition": 55,
        "trend_bias": 15,
        "keywords": [
            "ai coding assistant comparison",
            "ai automation for small business",
            "best ai tools for content creators",
        ],
    },
    "make_money_online": {
        "rpm": 16.0,
        "base_interest": 88,
        "base_competition": 85,
        "trend_bias": 4,
        "keywords": [
            "print on demand side hustle",
            "freelance skills that pay in 2026",
            "faceless youtube automation channel",
        ],
    },
    "software_tutorials": {
        "rpm": 12.0,
        "base_interest": 65,
        "base_competition": 60,
        "trend_bias": 6,
        "keywords": [
            "python automation scripts",
            "excel formulas for data analysts",
            "notion productivity setup",
        ],
    },
    "productivity_apps": {
        "rpm": 10.0,
        "base_interest": 60,
        "base_competition": 50,
        "trend_bias": 3,
        "keywords": [
            "best productivity apps 2026",
            "second brain note taking system",
            "time blocking for remote workers",
        ],
    },
    "health_wellness": {
        "rpm": 9.0,
        "base_interest": 72,
        "base_competition": 78,
        "trend_bias": 2,
        "keywords": [
            "home workout no equipment",
            "sleep optimization routine",
            "gut health diet plan",
        ],
    },
    "pet_care": {
        "rpm": 6.0,
        "base_interest": 52,
        "base_competition": 35,
        "trend_bias": 1,
        "keywords": [
            "senior dog care tips",
            "cat behavior training",
            "budget pet supplies review",
        ],
    },
    "budget_travel": {
        "rpm": 8.0,
        "base_interest": 62,
        "base_competition": 55,
        "trend_bias": 2,
        "keywords": [
            "digital nomad visa guide",
            "budget travel hacks 2026",
            "solo travel safety tips",
        ],
    },
    "career_remote_work": {
        "rpm": 11.0,
        "base_interest": 58,
        "base_competition": 48,
        "trend_bias": 4,
        "keywords": [
            "remote job interview prep",
            "resume tips for tech jobs",
            "salary negotiation scripts",
        ],
    },
    "sustainable_living": {
        "rpm": 7.0,
        "base_interest": 48,
        "base_competition": 32,
        "trend_bias": 1,
        "keywords": [
            "zero waste kitchen swaps",
            "diy solar setup for renters",
            "thrifting and upcycling clothes",
        ],
    },
    # "Made for Kids" content routinely posts some of the highest view counts on
    # all of YouTube (nursery rhymes, learning songs, toy unboxing), so demand
    # here is set near the top of the scale. But COPPA requires these channels
    # to disable personalized ads and comments, which collapses RPM well below
    # every other category -- real per-video revenue depends on massive volume,
    # not per-view rate. Competition is also extremely high (a handful of
    # channels like Cocomelon dominate search).
    "kids_shorts_content": {
        "rpm": 2.0,
        "base_interest": 95,
        "base_competition": 90,
        "trend_bias": 3,
        "keywords": [
            "nursery rhymes for toddlers shorts",
            "learn colors and shapes for kids",
            "kids abc learning songs",
            "surprise toy unboxing for kids",
        ],
    },
}
