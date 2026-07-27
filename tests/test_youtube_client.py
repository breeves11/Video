from backend import config, youtube_client


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_get_niche_stats_uses_mock_when_no_api_key(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "")
    stats = youtube_client.get_niche_stats("test keyword", base_interest=50, base_competition=40, trend_bias=2)
    assert stats.source == "estimated"
    assert stats.avg_views > 0


def test_get_niche_stats_uses_live_api_when_key_set_and_call_succeeds(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "fake-key")

    def fake_get(url, params, timeout):
        if url == youtube_client.YOUTUBE_SEARCH_URL:
            return FakeResponse({"items": [{"id": {"videoId": f"vid{i}"}} for i in range(5)]})
        if url == youtube_client.YOUTUBE_VIDEOS_URL:
            return FakeResponse(
                {"items": [{"statistics": {"viewCount": str(1000 * (i + 1))}} for i in range(5)]}
            )
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(youtube_client.requests, "get", fake_get)

    stats = youtube_client.get_niche_stats("real keyword", base_interest=50, base_competition=40, trend_bias=2)

    assert stats.source == "youtube_api"
    assert stats.avg_views == 3000
    assert stats.competitor_uploads_per_month == 5


def test_get_niche_stats_falls_back_to_mock_when_live_call_raises(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "fake-key")

    def fake_get(*args, **kwargs):
        raise youtube_client.requests.RequestException("boom")

    monkeypatch.setattr(youtube_client.requests, "get", fake_get)

    stats = youtube_client.get_niche_stats("real keyword", base_interest=50, base_competition=40, trend_bias=2)

    assert stats.source == "estimated"


def test_get_niche_stats_falls_back_to_mock_when_no_videos_found(monkeypatch):
    monkeypatch.setattr(config, "YOUTUBE_API_KEY", "fake-key")

    def fake_get(url, params, timeout):
        return FakeResponse({"items": []})

    monkeypatch.setattr(youtube_client.requests, "get", fake_get)

    stats = youtube_client.get_niche_stats("real keyword", base_interest=50, base_competition=40, trend_bias=2)

    assert stats.source == "estimated"
