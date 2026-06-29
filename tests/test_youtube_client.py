import httpx
import respx

import collector.youtube_client as yt
from collector.config import Settings
from collector.youtube_client import (
    SEARCH_URL,
    VIDEOS_URL,
    _main,
    explore,
    fetch_youtube,
    parse_search_ids,
    run,
    videos_to_docs,
)


def test_parse_search_ids():
    payload = {
        "items": [
            {"id": {"videoId": "abc"}, "snippet": {"title": "x"}},
            {"id": {"kind": "channel"}},  # no videoId -> skipped
            {"id": {"videoId": "def"}},
        ]
    }
    assert parse_search_ids(payload) == ["abc", "def"]


def test_videos_to_docs_builds_full_content():
    payload = {
        "items": [
            {
                "id": "abc",
                "snippet": {
                    "title": "32 Div/h Ritual Farming",
                    "description": "Step 1... step 2...",
                    "channelTitle": "MisoxShiru",
                },
            },
            {"id": "no", "snippet": {"description": "no title"}},  # skipped (no title)
        ]
    }
    docs = videos_to_docs(payload)
    assert len(docs) == 1
    d = docs[0]
    assert d.source_url == "https://www.youtube.com/watch?v=abc"
    assert d.title == "32 Div/h Ritual Farming"
    assert "MisoxShiru" in d.content and "Step 1" in d.content


def test_videos_to_docs_empty():
    assert videos_to_docs({}) == []
    assert videos_to_docs({"items": None}) == []


def test_videos_to_docs_attaches_discovery_query():
    payload = {"items": [
        {"id": "abc", "snippet": {"title": "t", "description": "d", "channelTitle": "c"}},
        {"id": "zzz", "snippet": {"title": "t2", "description": "d", "channelTitle": "c"}},
    ]}
    docs = videos_to_docs(payload, {"abc": "ritual farm"})
    by_id = {d.source_url.rsplit("=", 1)[-1]: d for d in docs}
    assert by_id["abc"].discovery_query == "ritual farm"
    assert by_id["zzz"].discovery_query is None  # no attribution for this id


async def test_fetch_youtube_returns_empty_without_key():
    # no API key -> short-circuit, never touches the network
    assert await fetch_youtube(Settings(youtube_api_key="")) == []


def _search(ids: list[str]) -> httpx.Response:
    return httpx.Response(200, json={"items": [{"id": {"videoId": i}} for i in ids]})


def _videos_for_requested_ids(request: httpx.Request) -> httpx.Response:
    batch = request.url.params.get("id", "").split(",")
    return httpx.Response(
        200,
        json={
            "items": [
                {"id": v, "snippet": {"title": f"T{v}", "description": "d", "channelTitle": "C"}}
                for v in batch
            ]
        },
    )


@respx.mock
async def test_fetch_youtube_dedupes_ids_across_queries():
    settings = Settings(youtube_api_key="k", youtube_queries="ritual,abyss")

    def search_response(request: httpx.Request) -> httpx.Response:
        ids = {"ritual": ["a", "b"], "abyss": ["b", "c"]}[request.url.params.get("q")]
        return _search(ids)

    respx.get(SEARCH_URL).mock(side_effect=search_response)
    videos = respx.get(VIDEOS_URL).mock(side_effect=_videos_for_requested_ids)

    docs = await fetch_youtube(settings)

    assert {d.source_url.rsplit("=", 1)[-1] for d in docs} == {"a", "b", "c"}
    # the duplicate "b" is collapsed and the single videos.list batch keeps insertion order
    assert videos.calls.last.request.url.params.get("id") == "a,b,c"
    # "b" was surfaced by BOTH queries — attributed to the first ("ritual"), not double-counted
    attribution = {d.source_url.rsplit("=", 1)[-1]: d.discovery_query for d in docs}
    assert attribution == {"a": "ritual", "b": "ritual", "c": "abyss"}


@respx.mock
async def test_fetch_youtube_skips_failing_query():
    settings = Settings(youtube_api_key="k", youtube_queries="good,bad")

    def search_response(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("q") == "bad":
            return httpx.Response(500)
        return _search(["a"])

    respx.get(SEARCH_URL).mock(side_effect=search_response)
    respx.get(VIDEOS_URL).mock(side_effect=_videos_for_requested_ids)

    docs = await fetch_youtube(settings)
    # the 500 on "bad" is swallowed; "good" still yields its video
    assert [d.title for d in docs] == ["Ta"]


@respx.mock
async def test_fetch_youtube_swallows_videos_batch_error():
    settings = Settings(youtube_api_key="k", youtube_queries="q")
    respx.get(SEARCH_URL).mock(return_value=_search(["a"]))
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(500))
    # a failing videos.list batch drops that batch, not the whole run
    assert await fetch_youtube(settings) == []


@respx.mock
async def test_fetch_youtube_batches_video_ids_in_fifties():
    settings = Settings(youtube_api_key="k", youtube_queries="q")
    ids = [f"v{i}" for i in range(60)]
    respx.get(SEARCH_URL).mock(return_value=_search(ids))
    videos = respx.get(VIDEOS_URL).mock(side_effect=_videos_for_requested_ids)

    docs = await fetch_youtube(settings)

    assert len(docs) == 60
    # videos.list accepts up to 50 ids -> 60 ids split into 50 + 10
    assert videos.call_count == 2
    assert len(videos.calls[0].request.url.params.get("id").split(",")) == 50
    assert len(videos.calls[1].request.url.params.get("id").split(",")) == 10


async def test_run_ingests_docs(monkeypatch):
    sentinels = ["doc1", "doc2"]

    async def fake_fetch(settings=None):
        return sentinels

    monkeypatch.setattr(yt, "fetch_youtube", fake_fetch)
    monkeypatch.setattr("collector.ingest.ingest_documents", lambda docs: len(docs))
    assert await run() == 2


@respx.mock
async def test_explore_prints_titles(capsys):
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"items": [{"snippet": {"title": "Hello"}}]})
    )
    await explore()
    assert "Hello" in capsys.readouterr().out


def test_main_unknown_command_returns_2():
    assert _main(["prog", "bogus"]) == 2


def test_main_run_dispatches(monkeypatch):
    called: list[str] = []

    async def fake_run():
        called.append("run")
        return 0

    monkeypatch.setattr(yt, "run", fake_run)
    assert _main(["prog", "run"]) == 0
    assert called == ["run"]


def test_main_explore_dispatches(monkeypatch):
    called: list[str] = []

    async def fake_explore():
        called.append("explore")

    monkeypatch.setattr(yt, "explore", fake_explore)
    assert _main(["prog", "explore"]) == 0
    assert called == ["explore"]
