import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from tuimian.fetch import Fetcher, extract_page
from tuimian.models import SourceConfig


def source():
    return SourceConfig(
        id="s", schoolId="school", kind="notice", title="通知", url="https://school.edu.cn/notice"
    )


def test_pdfjs_viewer_resolves_relative_file_and_rejects_external_file():
    page = extract_page(
        b'<h1>2027 notice</h1><iframe src="/pdfjs/web/viewer.html?file=notice.pdf"></iframe>',
        "text/html",
        source(),
    )
    assert page.attachmentOnly
    assert page.links[0]["url"] == "https://school.edu.cn/pdfjs/web/notice.pdf"
    html = '<h1>2027 notice</h1><article>研究生招生公告正文信息，请按照正式通知要求提交申请材料，并注意不同项目的报名截止时间。</article><iframe src="/pdfjs/viewer.html?file=https://external.test/notice.pdf"></iframe>'
    assert extract_page(html.encode(), "text/html", source()).links == []


def test_conditional_request_304_and_periodic_force():
    headers = []

    def handler(request):
        headers.append(dict(request.headers))
        if request.headers.get("if-none-match"):
            return httpx.Response(304)
        return httpx.Response(
            200,
            headers={"etag": "v1"},
            text="<h1>2027年硕士预推免报名通知</h1><p>报名时间2026年9月1日至9月9日。请及时完成报名申请。</p>",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetcher = Fetcher(client, delay=0, respect_robots=False)
            page = await fetcher.fetch(source())
            second = await fetcher.fetch(source(), page.to_dict())
            assert page.hash == second.hash
            cache = second.to_dict()
            cache["lastFullAt"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
            fetcher.requests.clear()
            await fetcher.fetch(source(), cache)

    asyncio.run(check())
    assert "if-none-match" not in headers[0]
    assert headers[1]["if-none-match"] == "v1"
    assert "if-none-match" not in headers[2]


def test_robots_disallow_does_not_request_notice():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        return httpx.Response(200, text="User-agent: *\nDisallow: /notice")

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetcher = Fetcher(client, delay=0)
            with pytest.raises(ValueError, match="robots"):
                await fetcher.fetch(source())

    asyncio.run(check())
    assert paths == ["/robots.txt"]


def test_gbk_encoding_and_table_rows():
    html = '<meta charset="gbk"><h1>2027年预推免通知</h1><table><tr><td>人工智能学院</td><td>报名截止9月9日</td></tr><tr><td>计算机学院</td><td>报名截止9月10日</td></tr></table>'
    page = extract_page(html.encode("gbk"), "text/html", source())
    assert "人工智能学院 报名截止9月9日" in page.text
    assert "计算机学院 报名截止9月10日" in page.text
    assert len(page.text.splitlines()) >= 2


def test_blank_pdf_requires_manual_review():
    import io

    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    with pytest.raises(ValueError, match="扫描件"):
        extract_page(output.getvalue(), "application/pdf", source())


def test_missing_content_selector_is_failure():
    config = source()
    config.contentSelector = ".missing"
    with pytest.raises(ValueError, match="选择器"):
        extract_page(
            b"<html><body><p>A real page without the expected selector.</p></body></html>",
            "text/html",
            config,
        )


@pytest.mark.parametrize(
    "attachment",
    [
        '<span class="wp_pdf_player" pdfsrc="/files/notice.pdf" id="2027年硕士预报名通知.pdf"></span>',
        '<span class="edui-pdf" data-pdf="/files/notice.pdf">2027年硕士预报名通知</span>',
        '<script>showVsbpdfIframe("/files/notice.pdf", "100%", "600");</script>',
        '<iframe src="/files/notice.pdf"></iframe>',
    ],
)
def test_embedded_pdf_notice_is_discoverable_even_without_text_body(attachment):
    from tuimian.crawler import discover

    html = (
        '<h3>2027年接收推荐免试硕士研究生预报名通知</h3><div class="wp_articlecontent">'
        + attachment
        + "</div>"
    )
    page = extract_page(html.encode(), "text/html", source())
    assert page.title == "2027年接收推荐免试硕士研究生预报名通知"
    found = discover(source(), page, page_count={})
    assert len(found) == 1
    assert found[0].url == "https://school.edu.cn/files/notice.pdf"
    assert found[0].identityKey == source().url


def test_table_cells_with_paragraphs_keep_header_and_row_association():
    html = "<h1>2027年硕士预报名汇总</h1><table><tr><td><p>学院</p></td><td><p>报名截止时间</p></td></tr><tr><td><p>人工智能学院</p></td><td><p>9月10日17:00</p></td></tr><tr><td><p>法学院</p></td><td><p>9月12日</p></td></tr></table>"
    page = extract_page(html.encode(), "text/html", source())
    assert "人工智能学院 报名截止时间：9月10日17:00" in page.text
    assert "法学院 报名截止时间：9月12日" in page.text


def test_pdf_replacement_changes_parent_fingerprint_and_cancellation_is_not_skipped():
    html = '<h1>2027年硕士预推免</h1><article><iframe src="/a.pdf"></iframe></article>'
    first = extract_page(html.encode(), "text/html", source())
    second = extract_page(html.replace("/a.pdf", "/b.pdf").encode(), "text/html", source())
    assert first.hash != second.hash
    cancelled = html.replace(
        "<iframe", "<p>因招生计划调整，现取消本批次预推免报名，请及时关注后续相关通知。</p><iframe"
    )
    assert not extract_page(cancelled.encode(), "text/html", source()).attachmentOnly


def test_unsupported_json_is_visible_failure():
    with pytest.raises(ValueError, match="JSON"):
        extract_page(b'{"data": []}', "application/json", source())


def test_zju_json_adapter_keeps_each_unit_deadline_independent():
    import json

    from test_parser import unit

    from tuimian.parser import parse_notice

    config = source().model_copy(
        update={
            "url": "https://yjsy.zju.edu.cn/dataapi/open/zsss/listBksm?nf=2027&bksmlx=2",
            "adapter": "zju_admissions",
            "unitIds": ["s-ai"],
            "schoolId": "s",
        }
    )
    template = {"nf": "2027", "bksmlx": "2", "bksmlx_dictText": "免试生", "fbzt": "1", "qrzt": "1"}
    rows = [
        template
        | {
            "sysOrgCode_dictText": "人工智能学院",
            "jzrq": "2026年8月10日9:00开始报名，2026年9月10日24：00报名截止。",
        },
        template | {"sysOrgCode_dictText": "法学院", "jzrq": "2026年9月12日报名截止"},
    ]
    page = extract_page(
        json.dumps({"result": {"records": rows}}).encode(), "application/json", config
    )
    parsed = parse_notice(page.title, page.text, config, unit())
    assert parsed.applicationStart.value == "2026-08-10T09:00:00+08:00"
    assert parsed.applicationEnd.value == "2026-09-11T00:00:00+08:00"
    assert "9月12日" not in parsed.evidence[0].excerpt


def test_gzip_body_is_decoded_exactly_once():
    import gzip

    html = "<h1>2027年硕士预推免报名通知</h1><p>硕士预推免报名截止2026年9月10日，请及时完成报名申请。</p>"

    def handler(request):
        return httpx.Response(
            200,
            headers={"Content-Encoding": "gzip"},
            stream=httpx.ByteStream(gzip.compress(html.encode())),
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetcher = Fetcher(client, delay=0, respect_robots=False)
            page = await fetcher.fetch(source())
            assert "2026年9月10日" in page.text

    asyncio.run(check())


def test_section_or_column_h1_does_not_replace_admission_title():
    for heading in ["一、招生专业", "招生就业"]:
        html = f'<title>信息工程学院2027年第二批硕士预推免报名通知</title><h1>{heading}</h1><article>硕士预推免报名截止2026年9月10日，请按学院招生通知要求及时提交报名申请。</article><a href=" /notice/2 ">下一项</a>'
        page = extract_page(html.encode(), "text/html", source())
        assert "第二批" in page.title
        assert page.links[0]["url"] == "https://school.edu.cn/notice/2"


def test_non_ascii_download_headers_and_invalid_etag_do_not_break_fetch():
    headers = []

    def handler(request):
        headers.append(dict(request.headers))
        return httpx.Response(
            200,
            headers=[(b"content-disposition", 'attachment; filename="通知.pdf"'.encode())],
            text="<h1>2027年硕士预推免报名通知</h1><p>硕士预推免报名截止2026年9月10日，请及时完成报名申请。</p>",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetcher = Fetcher(client, delay=0, respect_robots=False)
            page = await fetcher.fetch(source())
            cache = page.to_dict() | {"etag": "“错误的引号”"}
            fetcher.requests.clear()
            await fetcher.fetch(source(), cache)
            assert "if-none-match" not in headers[-1]

    asyncio.run(check())


def test_robots_crawl_delay_applies_only_to_its_host(monkeypatch):
    waits = []

    async def fake_sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("tuimian.fetch.time.monotonic", lambda: 1000.0)
    monkeypatch.setattr("tuimian.fetch.asyncio.sleep", fake_sleep)

    def handler(request):
        if request.url.path == "/robots.txt":
            robots = "User-agent: *\nAllow: /"
            if request.url.host == "slow.edu.cn":
                robots += "\nCrawl-delay: 10"
            return httpx.Response(200, text=robots)
        return httpx.Response(
            200,
            text="<h1>2027年硕士预推免报名通知</h1><p>硕士预推免报名截止2026年9月10日，请及时完成报名申请。</p>",
        )

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            fetcher = Fetcher(client, delay=1)
            slow = source().model_copy(update={"url": "https://slow.edu.cn/notice"})
            await fetcher.fetch(slow)
            assert waits == [10]
            waits.clear()
            await fetcher.fetch(source())
            assert waits == [1]
            assert fetcher.delay == 1

    asyncio.run(check())
