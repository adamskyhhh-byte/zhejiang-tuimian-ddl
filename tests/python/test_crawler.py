import json

import httpx

from tuimian.crawler import crawl
from tuimian.fetch import Fetcher
from tuimian.storage import load_catalog, read_json


def setup_root(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    configs = {
        "schools": [
            {
                "id": "s",
                "name": "测试大学",
                "province": "浙江",
                "groups": ["常规"],
                "rosterSources": ["https://s.edu.cn/roster"],
                "homepage": "https://s.edu.cn",
            }
        ],
        "units": [
            {
                "id": "s-ai",
                "schoolId": "s",
                "name": "人工智能学院",
                "disciplines": ["AI"],
                "relevance": "core",
                "directoryUrl": "https://s.edu.cn",
                "admissionUrl": "https://s.edu.cn/list",
            }
        ],
        "sources": [
            {
                "id": "list",
                "schoolId": "s",
                "unitId": "s-ai",
                "kind": "listing",
                "url": "https://s.edu.cn/list",
                "title": "招生公告",
            }
        ],
        "seeds": [],
        "overrides": {},
    }
    for name, value in configs.items():
        (data / f"{name}.json").write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def run(root, handler, source_ids=None):
    import asyncio

    async def execute():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await crawl(
                root, source_ids=source_ids, fetcher=Fetcher(client, delay=0, respect_robots=False)
            )

    return asyncio.run(execute())


def notice(day="10", batch=""):
    return f"<html><h1>2027年硕士预推免{batch}报名通知</h1><article>硕士学术学位预推免。<p>报名时间：2026年9月1日9:00至9月{day}日17:00。</p></article></html>"


def test_incremental_id_no_duplicate_original_url_extension_and_failure(tmp_path):
    root = setup_root(tmp_path)
    deadline = "10"
    failed = False

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<p>学院研究生招生通知列表公告</p><a href="/1">2027年硕士预推免报名通知</a>',
            )
        if failed:
            return httpx.Response(403, text="Forbidden")
        return httpx.Response(200, text=notice(deadline), headers={"etag": deadline})

    run(root, handler)
    first = load_catalog(root)
    assert len(first.opportunities) == 1
    first_id = first.opportunities[0].id
    run(root, handler)
    assert len(load_catalog(root).changes) == 1
    deadline = "12"
    run(root, handler)
    changed = load_catalog(root)
    assert changed.opportunities[0].id == first_id
    assert changed.opportunities[0].applicationEnd.value == "2026-09-12T17:00:00+08:00"
    assert changed.changes[-1].kind == "extended"
    failed = True
    run(root, handler)
    retained = load_catalog(root)
    assert retained.opportunities[0].applicationEnd.value == "2026-09-12T17:00:00+08:00"
    assert retained.run.status == "partial"
    assert any(source.error for source in retained.sources)


def test_multiple_batches_and_manual_override_conflict(tmp_path):
    root = setup_root(tmp_path)

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<p>研究生学院招生通知列表公告信息</p><a href="/1">2027年硕士预推免第一批</a><a href="/2">2027年硕士预推免第二批</a>',
            )
        return httpx.Response(
            200, text=notice("10", "第一批" if request.url.path == "/1" else "第二批")
        )

    run(root, handler)
    catalog = load_catalog(root)
    assert len(catalog.opportunities) == 2
    item = catalog.opportunities[0]
    override = {
        item.id: {
            "reason": "招生办人工核验",
            "applicationEnd": {
                "value": "2026-09-11",
                "precision": "date",
                "raw": "9月11日",
                "sourceId": item.sourceIds[0],
            },
        }
    }
    (root / "data/overrides.json").write_text(json.dumps(override), encoding="utf-8")
    run(root, handler)
    updated = load_catalog(root)
    overridden = next(o for o in updated.opportunities if o.id == item.id)
    assert overridden.applicationEnd.value == "2026-09-11"
    assert overridden.verification == "conflict"
    assert "人工" in overridden.notes
    assert (
        read_json(root / "data/state.json", {})["opportunities"][item.id]["applicationEnd"]["value"]
        != "2026-09-11"
    )


def test_empty_reparse_preserves_known_good_dates(tmp_path):
    root = setup_root(tmp_path)
    broken = False

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200, text='<p>研究生学院招生通知列表公告信息</p><a href="/1">2027年硕士预推免</a>'
            )
        return httpx.Response(200, text="" if broken else notice())

    run(root, handler)
    broken = True
    run(root, handler)
    assert load_catalog(root).opportunities[0].applicationEnd.value is not None


def test_school_wide_notice_does_not_assign_other_unit_deadline(tmp_path):
    root = setup_root(tmp_path)
    sources = read_json(root / "data/sources.json", [])
    sources[0].update(unitId=None, unitIds=["s-ai"])
    (root / "data/sources.json").write_text(json.dumps(sources), encoding="utf-8")

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200, text='<p>研究生学院招生通知列表公告信息</p><a href="/1">2027年硕士预推免</a>'
            )
        return httpx.Response(200, text=notice())

    run(root, handler)
    assert load_catalog(root).opportunities == []


def test_parser_error_counts_failure_and_preserves_last_parsed_time(tmp_path):
    root = setup_root(tmp_path)
    source = {
        "id": "notice",
        "schoolId": "s",
        "unitId": "s-ai",
        "kind": "notice",
        "url": "https://s.edu.cn/1",
        "title": "2027年硕士预推免报名通知",
    }
    path = root / "data/sources.json"
    path.write_text(json.dumps([source]), encoding="utf-8")

    def handler(request):
        return httpx.Response(200, text=notice())

    run(root, handler)
    last_parsed = load_catalog(root).sources[0].lastParsedAt
    source["scope"] = "("
    path.write_text(json.dumps([source]), encoding="utf-8")
    run(root, handler)
    catalog = load_catalog(root)
    assert catalog.run.status == "failed"
    assert catalog.run.succeeded == 0
    assert catalog.run.failed == 1
    assert catalog.sources[0].lastParsedAt == last_parsed
    assert catalog.sources[0].error


def test_unparseable_notice_recovers_when_original_content_returns(tmp_path):
    root = setup_root(tmp_path)
    broken = False

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200, text='<p>研究生学院招生通知列表公告信息</p><a href="/1">2027年硕士预推免</a>'
            )
        if broken:
            return httpx.Response(
                200,
                text="<h1>网站正在维护</h1><p>网站内容调整中，本页面目前正在维护更新，请联系学院管理员获取后续信息。</p>",
            )
        return httpx.Response(200, text=notice())

    run(root, handler)
    assert load_catalog(root).opportunities[0].verification == "verified"
    broken = True
    run(root, handler)
    assert load_catalog(root).opportunities[0].verification == "pending"
    broken = False
    run(root, handler)
    assert load_catalog(root).opportunities[0].verification == "verified"


def test_pagination_limit_applies_on_every_run(tmp_path):
    root = setup_root(tmp_path)
    configs = read_json(root / "data/sources.json", [])
    configs[0]["maxPages"] = 2
    configs[0]["id"] = "zzz-root"
    (root / "data/sources.json").write_text(json.dumps(configs), encoding="utf-8")
    paths = []

    def handler(request):
        paths.append(request.url.path)
        number = int(request.url.path.removeprefix("/list") or "1")
        return httpx.Response(
            200, text=f'<p>研究生学院招生通知列表公告信息</p><a href="/list{number + 1}">下一页</a>'
        )

    for _ in range(3):
        paths.clear()
        run(root, handler)
        assert set(paths) == {"/list", "/list2"}


def test_extension_discovered_before_original_is_one_project_and_stays_stable(tmp_path):
    root = setup_root(tmp_path)

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<p>研究生学院招生通知列表公告信息</p><a href="/extension">2027年硕士预推免延期通知</a><a href="/original">2027年硕士预推免报名通知</a>',
            )
        if request.url.path == "/extension":
            return httpx.Response(
                200,
                text='<h1>2027年硕士预推免延期通知</h1><article>硕士预推免报名延期至2026年9月12日17:00。<a href="/original">原公告：2027年硕士预推免报名通知</a></article>',
            )
        return httpx.Response(200, text=notice())

    run(root, handler)
    first = load_catalog(root)
    assert len(first.opportunities) == 1
    assert first.opportunities[0].applicationEnd.value == "2026-09-12T17:00:00+08:00"
    assert first.opportunities[0].verification == "verified"
    change_count = len(first.changes)
    for _ in range(2):
        run(root, handler)
        repeated = load_catalog(root)
        assert len(repeated.opportunities) == 1
        assert repeated.opportunities[0].verification == "verified"
        assert len(repeated.changes) == change_count


def test_shared_school_listing_does_not_assign_unrelated_special_program(tmp_path):
    root = setup_root(tmp_path)
    path = root / "data/units.json"
    units = read_json(path, [])
    units.append(units[0] | {"id": "s-software", "name": "软件学院"})
    path.write_text(json.dumps(units), encoding="utf-8")
    path = root / "data/sources.json"
    sources = read_json(path, [])
    sources.append(sources[0] | {"id": "list-software", "unitId": "s-software"})
    path.write_text(json.dumps(sources), encoding="utf-8")

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200,
                text='<p>学校研究生招生公告列表</p><a href="/law">2027年法律硕士预报名</a>'
                '<a href="/ai">人工智能学院2027年硕士预推免</a>',
            )
        title = "法律硕士" if request.url.path == "/law" else "人工智能学院硕士"
        return httpx.Response(
            200,
            text=f"<h1>2027年{title}预报名</h1><article>本学院接收学术学位硕士研究生，预报名截止9月10日。欢迎符合推荐免试资格的同学报名。</article>",
        )

    run(root, handler)
    items = load_catalog(root).opportunities
    assert len(items) == 1
    assert items[0].unitId == "s-ai"


def test_listing_discovery_rechecks_all_explicit_batches_for_the_same_notice(tmp_path):
    root = setup_root(tmp_path)
    path = root / "data/sources.json"
    sources = read_json(path, [])
    for batch in ["第一批", "第二批"]:
        sources.append(
            sources[0]
            | {"id": batch, "kind": "notice", "url": "https://s.edu.cn/1", "batch": batch}
        )
    path.write_text(json.dumps(sources), encoding="utf-8")

    def handler(request):
        if request.url.path == "/list":
            return httpx.Response(
                200, text='<p>学院研究生招生公告列表</p><a href="/1">2027年硕士预推免报名通知</a>'
            )
        return httpx.Response(200, text=notice())

    run(root, handler, source_ids=["list"])
    assert {item.batch for item in load_catalog(root).opportunities} == {"第一批", "第二批"}
