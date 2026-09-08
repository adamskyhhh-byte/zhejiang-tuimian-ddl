"""有限并发、域名限速与条件请求；网页和附件共用缓存及异常语义。"""

import asyncio
import hashlib
import io
import re
import ssl
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .adapters import nudt_admissions, zju_admissions
from .models import SourceConfig
from .parser import now_iso

USER_AGENT = "TuimianDDLBot/1.0 (+official-admission-deadline-research)"
MAX_BYTES = 12 * 1024 * 1024


@dataclass
class Page:
    title: str
    text: str
    links: list[dict[str, str]]
    hash: str
    etag: str | None = None
    lastModified: str | None = None
    lastFullAt: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def allowed_url(url: str, source: SourceConfig) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"https", "http"} and parsed.hostname in {
        urlparse(source.url).hostname,
        *source.allowedHosts,
    }


def extract_page(
    content: bytes, content_type: str, source: SourceConfig, encoding: str = "utf-8"
) -> Page:
    if "json" in content_type.lower() or content.lstrip().startswith((b"{", b"[")):
        if source.adapter != "zju_admissions":
            raise ValueError("JSON 来源尚无已核验字段适配器，请配置公告 HTML 列表入口")
        title, text, links = zju_admissions(content, source)
        digest = hashlib.sha256((title + "\n" + text).encode()).hexdigest()
        return Page(title=title, text=text, links=links, hash=digest)
    if "pdf" in content_type.lower() or content.startswith(b"%PDF"):
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if len(text.strip()) < 30:
            raise ValueError("PDF 无可提取正文，可能为扫描件，需人工核验")
        title, links = source.title, []
    else:
        # 优先读取网页声明编码；不少高校沿用 GBK 页面。
        declared = re.search(rb"charset\s*=\s*[\"']?([\w-]+)", content[:8000], re.I)
        encoding = declared[1].decode("ascii") if declared else encoding
        try:
            html = content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            html = content.decode("gb18030", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        headings = [
            node.get_text(" ", strip=True)
            for node in soup.select("h1, .arti_title, .article-title, .news-title, title")
        ]
        meaningful = [
            value
            for value in headings
            if re.search(r"20\d{2}|预推免|预报名|第[一二三四五\d]+[批轮]", value)
            and not re.match(r"^\s*[一二三四五六七八九十\d]+\s*[、．.]", value)
        ]
        if meaningful:
            title = meaningful[0]
        elif re.search(r"20\d{2}|预推免|预报名", source.title) and any(
            re.search(r"20\d{2}|预推免|预报名", value) for value in [soup.get_text(" ", strip=True)]
        ):
            # 列表中的完整公告标题可补足详情的栏目 h1，但不把维护页冒充原公告。
            title = source.title
        else:
            title = headings[0] if headings else source.title
        links = []
        for anchor in soup.select(source.linkSelector):
            url = urldefrag(urljoin(source.url, anchor.get("href", "").strip()))[0]
            if allowed_url(url, source):
                links.append(
                    {
                        "url": url,
                        "title": anchor.get_text(" ", strip=True) or anchor.get("title", ""),
                    }
                )
        for node in soup.select("script, style, noscript, nav, header, footer"):
            node.decompose()
        if source.adapter == "nudt_admissions":
            title, body, links = nudt_admissions(soup, source)
        elif source.contentSelector:
            body = soup.select_one(source.contentSelector)
            if body is None:
                raise ValueError(f"正文选择器无匹配: {source.contentSelector}")
        elif source.kind != "listing":
            body = (
                soup.select_one(
                    ".v_news_content, .wp_articlecontent, #vsb_content, .TRS_Editor, article, main"
                )
                or soup.body
                or soup
            )
        else:
            body = soup.body or soup
        # 保留学院表格行和段落边界；行内链接不会截断一句报名时间。
        for node in body.select("p, tr, li, h1, h2, h3, h4, br"):
            node.insert_before("\n")
            node.insert_after("\n")
        text = "\n".join(
            re.sub(r"[ \t\r\f\v]+", " ", line).strip()
            for line in body.get_text(" ").splitlines()
            if line.strip()
        )
        if source.adapter == "nudt_admissions" and source.kind == "notice":
            text = title + "\n" + text
        if len(text) < (10 if source.kind == "listing" else 30):
            raise ValueError("正文为空或过短，保留此前数据")
        if re.search(
            r"验证码|访问过于频繁|人机验证|access denied|verify you are human", text, re.I
        ):
            # 通知内讲招生系统验证码不应被当作网站拦截页。
            if len(text) < 1800:
                raise ValueError("来源返回验证或访问限制页面")
    digest = hashlib.sha256((title + "\n" + text).encode()).hexdigest()
    return Page(title=title, text=text, links=links, hash=digest)


class Fetcher:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        delay: float = 1.0,
        respect_robots: bool = True,
    ):
        nudt_tls = ssl.create_default_context()
        nudt_tls.set_ciphers("DEFAULT")
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(25, connect=12),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            # NUDT 旧服务器仅支持系统 DEFAULT 套件中的 RSA TLS 套件，仍严格校验证书。
            mounts={"https://yjszs.nudt.edu.cn": httpx.AsyncHTTPTransport(verify=nudt_tls)},
        )
        self.owns_client = client is None
        self.semaphore = asyncio.Semaphore(6)
        self.delay = delay
        self.host_delays: dict[str, float] = {}
        self.respect_robots = respect_robots
        self.locks: dict[str, asyncio.Lock] = {}
        self.last_request: dict[str, float] = {}
        self.robots: dict[str, RobotFileParser] = {}
        self.robot_locks: dict[str, asyncio.Lock] = {}
        self.requests: dict[tuple, asyncio.Task] = {}

    async def close(self):
        if self.owns_client:
            await self.client.aclose()

    async def _request(self, url: str, headers: dict | None = None) -> httpx.Response:
        # 同一校级 URL 可映射多个培养单位；本轮共用响应，避免重复请求官网。
        key = (url, tuple(sorted((headers or {}).items())))
        if key not in self.requests:
            self.requests[key] = asyncio.create_task(self._uncached_request(url, headers))
        return await self.requests[key]

    async def _uncached_request(self, url: str, headers: dict | None = None) -> httpx.Response:
        host = urlparse(url).netloc
        lock = self.locks.setdefault(host, asyncio.Lock())
        for attempt in range(3):
            async with lock:
                delay = max(self.delay, self.host_delays.get(host, 0))
                wait = delay - (time.monotonic() - self.last_request.get(host, 0))
                if wait > 0:
                    await asyncio.sleep(wait)
                self.last_request[host] = time.monotonic()
                try:
                    async with self.semaphore:
                        async with self.client.stream("GET", url, headers=headers) as response:
                            if int(response.headers.get("content-length", "0")) > MAX_BYTES:
                                raise ValueError("来源超过12MB限制，需配置单独处理")
                            body = bytearray()
                            async for chunk in response.aiter_bytes():
                                body.extend(chunk)
                                if len(body) > MAX_BYTES:
                                    raise ValueError("来源超过12MB限制，需配置单独处理")
                            result = httpx.Response(
                                response.status_code,
                                # aiter_bytes 已完成一次解压，重建时不得再次根据旧头部解压。
                                headers=[
                                    (key, value)
                                    for key, value in response.headers.raw
                                    if key.lower() not in {b"content-encoding", b"content-length"}
                                ],
                                content=bytes(body),
                                request=response.request,
                            )
                except (httpx.TimeoutException, httpx.NetworkError):
                    if attempt == 2:
                        raise
                    result = None
            if result is not None and result.status_code not in {429, 500, 502, 503, 504}:
                return result
            if attempt == 2:
                if result is not None:
                    result.raise_for_status()
                raise RuntimeError("重试耗尽")
            retry = result.headers.get("Retry-After", "") if result is not None else ""
            seconds = 2**attempt
            if retry.isdigit():
                seconds = int(retry)
            elif retry:
                try:
                    seconds = max(
                        0,
                        (parsedate_to_datetime(retry) - datetime.now(timezone.utc)).total_seconds(),
                    )
                except (TypeError, ValueError):
                    pass
            if seconds > 60:
                raise ValueError(f"来源要求 Retry-After {seconds:.0f} 秒，留待下次任务")
            await asyncio.sleep(seconds)
        raise RuntimeError("无法完成请求")

    async def _check_robots(self, url: str):
        if not self.respect_robots:
            return
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        async with self.robot_locks.setdefault(origin, asyncio.Lock()):
            if origin not in self.robots:
                response = await self._request(origin + "/robots.txt")
                robot = RobotFileParser(origin + "/robots.txt")
                if response.status_code in {404, 410}:
                    robot.parse([])
                elif response.status_code in {401, 403}:
                    robot.parse(["User-agent: *", "Disallow: /"])
                else:
                    response.raise_for_status()
                    robot.parse(response.text.splitlines())
                self.robots[origin] = robot
        robot = self.robots[origin]
        if not robot.can_fetch(USER_AGENT, url):
            raise ValueError("robots.txt 不允许抓取该来源")
        crawl_delay = robot.crawl_delay(USER_AGENT) or robot.crawl_delay("*")
        if crawl_delay:
            # 各站点独立限速，同一 host 的任何请求均不低于已知 robots 声明。
            host = parsed.netloc
            self.host_delays[host] = max(self.host_delays.get(host, 0), crawl_delay)

    async def fetch(self, source: SourceConfig, cache: dict | None = None) -> Page:
        await self._check_robots(source.url)
        if source.render:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise ValueError(
                    "动态来源需要 uv sync --extra browser 和 playwright install chromium"
                ) from exc
            async with self.semaphore:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=True)
                    try:
                        page = await browser.new_page(user_agent=USER_AGENT)
                        await page.goto(source.url, wait_until="domcontentloaded", timeout=30000)
                        await page.wait_for_timeout(1500)
                        result = extract_page((await page.content()).encode(), "text/html", source)
                    finally:
                        await browser.close()
            result.lastFullAt = now_iso()
            return result
        headers = {}
        force = (
            not cache
            or not cache.get("lastFullAt")
            or (
                datetime.now(timezone.utc) - datetime.fromisoformat(cache["lastFullAt"])
                >= timedelta(days=source.forceAfterDays)
            )
        )
        if not force and cache:
            if cache.get("etag") and cache["etag"].isascii():
                headers["If-None-Match"] = cache["etag"]
            if cache.get("lastModified") and cache["lastModified"].isascii():
                headers["If-Modified-Since"] = cache["lastModified"]
        response = await self._request(source.url, headers=headers)
        if response.status_code == 304:
            if not cache:
                raise ValueError("服务器返回304但没有本地缓存")
            return Page(**cache)
        response.raise_for_status()
        result = extract_page(
            response.content,
            response.headers.get("content-type", ""),
            source,
            response.encoding or "utf-8",
        )
        result.etag = response.headers.get("etag")
        result.lastModified = response.headers.get("last-modified")
        result.lastFullAt = now_iso()
        return result
