"""Unit tests for the streaming_signed provider plugin's StreamingService.

Exercises the URL-issuing logic directly (no ProviderContext/plugin
loading machinery needed - same style as other provider adapter tests in
this suite).
"""

from media_platform.plugins.providers.streaming_signed.plugin import SignedStreamingService
from media_platform.services import stream_tokens


async def test_get_playback_url_contains_a_verifiable_signature():
    service = SignedStreamingService(secret="s3cr3t", base_url="https://example.test/")
    playback_url = await service.get_playback_url("movie-1", 42, expiry_seconds=60)

    assert playback_url.url.startswith("https://example.test/stream/movie-1?")
    query = dict(part.split("=") for part in playback_url.url.split("?", 1)[1].split("&"))
    assert query["u"] == "42"
    assert stream_tokens.verify("s3cr3t", "movie-1", 42, int(query["exp"]), query["sig"])


async def test_get_playback_url_strips_trailing_slash_from_base_url():
    service = SignedStreamingService(secret="s3cr3t", base_url="https://example.test/////")
    playback_url = await service.get_playback_url("movie-1", 42)
    assert "example.test/////stream" not in playback_url.url
    assert playback_url.url.startswith("https://example.test/stream/movie-1?")


async def test_revoke_is_a_documented_no_op():
    service = SignedStreamingService(secret="s3cr3t", base_url="https://example.test")
    await service.revoke("movie-1", 42)  # must not raise
