"""用隔离快照验证界面行为，不受真实报名日期或高校网络波动影响。"""

import copy
import functools
import json
import os
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-09-08T12:00:00+08:00"


def point(value: str | None, precision: str = "datetime") -> dict:
    return {
        "value": value,
        "precision": precision if value else "unknown",
        "raw": value or "官方未公布截止日期",
        "sourceId": "fixture-source",
    }


@pytest.fixture(scope="session")
def catalog() -> dict:
    schools = json.loads((ROOT / "data/schools.json").read_text(encoding="utf-8"))
    unit = {
        "id": "fixture-unit", "schoolId": "zju", "name": "计算机学院测试培养单位",
        "campus": "杭州", "disciplines": ["计算机"], "relevance": "core",
        "directoryUrl": "https://www.zju.edu.cn/", "admissionUrl": "https://www.zju.edu.cn/",
        "coverage": "published", "note": "浏览器测试数据，不发布到生产快照。",
    }
    source = {
        "id": "fixture-source", "schoolId": "zju", "unitId": unit["id"],
        "url": "https://www.zju.edu.cn/", "title": "官方报名通知", "kind": "notice",
        "lastAttemptAt": NOW, "lastSuccessAt": NOW, "lastParsedAt": NOW, "error": None,
    }
    base = {
        "id": "fixture-1", "schoolId": "zju", "unitId": unit["id"],
        "title": "硕士预推免第一批", "year": 2027, "season": 2026, "batch": "第一批",
        "degrees": ["academic", "professional"], "disciplines": ["计算机"],
        "relevance": "core", "stage": "pre_admission",
        "applicationStart": point("2026-09-01T09:00:00+08:00"),
        "applicationEnd": point("2026-09-10T12:00:00+08:00"),
        "materialsEnd": point("2026-09-11T12:00:00+08:00"), "assessment": "考核另行通知",
        "applicationUrl": "https://www.zju.edu.cn/", "noticeUrl": "https://www.zju.edu.cn/",
        "sourceIds": [source["id"]],
        "evidence": [{"sourceId": source["id"], "url": source["url"], "title": source["title"],
                      "excerpt": "报名截至9月10日12:00，材料截至9月11日12:00。"}],
        "verification": "verified", "availability": "open", "firstSeenAt": NOW,
        "updatedAt": NOW, "notes": "浏览器隔离测试样例。",
    }
    opportunities = []
    for number in range(1, 6):
        item = copy.deepcopy(base)
        item.update(id=f"fixture-{number}", title=f"硕士预推免批次{number}", batch=f"批次{number}")
        if number <= 3:
            item["assessmentMode"] = ["online", "offline", "hybrid"][number - 1]
        if number == 2:
            item["programTags"] = ["joint"]
        opportunities.append(item)
    day = copy.deepcopy(base)
    day.update(id="fixture-date", title="仅日期项目", batch="仅日期批次")
    day["applicationEnd"] = point("2026-09-08", "date")
    opportunities.append(day)
    unknown = copy.deepcopy(base)
    unknown.update(id="fixture-unknown", title="截止未知项目", batch="未知截止批次")
    unknown["applicationEnd"] = point(None)
    opportunities.append(unknown)
    closed = copy.deepcopy(base)
    closed.update(id="fixture-closed", title="历史批次项目", batch="历史批次")
    closed["applicationEnd"] = point("2026-09-07T12:00:00+08:00")
    opportunities.append(closed)
    stale = copy.deepcopy(base)
    stale.update(id="fixture-stale", title="单源失效项目", batch="来源失效批次")
    stale["sourceIds"] = ["fixture-stale-source"]
    stale_source = {**source, "id": "fixture-stale-source",
                    "lastSuccessAt": "2026-09-05T12:00:00+08:00", "error": "HTTP 503"}
    opportunities.append(stale)
    return {
        "schemaVersion": 1, "generatedAt": NOW, "rosterYear": 2026, "admissionYear": 2027,
        "season": 2026, "schools": schools, "units": [unit], "sources": [source, stale_source],
        "opportunities": opportunities, "changes": [],
        "run": {"startedAt": NOW, "finishedAt": NOW, "status": "partial", "checked": 2,
                "succeeded": 1, "failed": 1, "discovered": 0, "changed": 0},
    }


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        pass


@pytest.fixture(scope="session")
def site_url():
    if not (ROOT / "dist/index.html").exists():
        pytest.fail("请先执行 pnpm build，再运行浏览器测试。")
    handler = functools.partial(QuietHandler, directory=str(ROOT / "dist"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        options = {"headless": True}
        local_chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        configured = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
        if configured:
            options["executable_path"] = configured
        elif os.name == "nt" and local_chrome.exists():
            options["executable_path"] = str(local_chrome)
        instance = playwright.chromium.launch(**options)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, catalog, site_url):
    context = browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="America/Los_Angeles")
    page = context.new_page()
    page.clock.set_fixed_time(datetime(2026, 9, 8, 4, tzinfo=timezone.utc))
    page.route("**/data/catalog.json", lambda route: route.fulfill(json=catalog))
    page.goto(site_url, wait_until="networkidle")
    page.get_by_test_id("tab-list").wait_for()
    yield page
    context.close()
