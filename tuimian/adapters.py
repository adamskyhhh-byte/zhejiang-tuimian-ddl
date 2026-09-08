"""已对照官方字段核验的公开 JSON 接口适配。"""

import json
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .models import SourceConfig


def nudt_admissions(soup: BeautifulSoup, source: SourceConfig) -> tuple:
    """国防科大列表含 JS 翻页，详情正文只取 articleContent，避免导航与登录框。"""
    if urlparse(source.url).hostname != "yjszs.nudt.edu.cn":
        raise ValueError("nudt_admissions 只适用于国防科技大学官方研究生招生网站")
    links = []
    if source.kind == "listing":
        body = soup.select_one(".article_list")
        if body is None:
            raise ValueError("国防科大公告列表 .article_list 未找到，请使用学院发文列表入口")
        title = source.title
        for anchor in body.select("a[href]"):
            raw_url = anchor.get("href", "").strip()
            url = urljoin(source.url, raw_url).replace("/newDetailed.view?", "/detailed.view?")
            if urlparse(url).hostname != "yjszs.nudt.edu.cn":
                continue
            heading = anchor.select_one(".news_bt, .info .bt, h3, h4")
            label = (heading or anchor).get_text(" ", strip=True)
            links.append({"url": url, "title": label})
        page_no, page_size, total = (
            soup.select_one(f"input[name='{name}']")
            for name in ("pageNo", "pageSize", "totalPages")
        )
        if page_no and total and int(page_no.get("value", "1")) < int(total.get("value", "1")):
            parsed = urlparse(source.url)
            query = dict(parse_qsl(parsed.query))
            query.update(
                pageNo=str(int(page_no["value"]) + 1),
                pageSize=page_size.get("value", "10") if page_size else "10",
                state="F",
            )
            links.append(
                {"url": urlunparse(parsed._replace(query=urlencode(query))), "title": "下一页"}
            )
    else:
        body = soup.select_one(
            "#articleContent, .news-view > .content > .font, .v_news_content, .article .entry"
        )
        heading = soup.select_one("h1.arti_title, h1")
        if body is None or heading is None:
            raise ValueError("国防科大详情正文或标题未找到，保留旧公告")
        title = heading.get_text(" ", strip=True)
        for anchor in body.select("a[href]"):
            url = urljoin(source.url, anchor.get("href", "").strip())
            if urlparse(url).hostname == "yjszs.nudt.edu.cn":
                links.append({"url": url, "title": anchor.get_text(" ", strip=True)})
    return title, body, links


def zju_admissions(content: bytes, source: SourceConfig) -> tuple[str, str, list[dict[str, str]]]:
    if urlparse(source.url).hostname != "yjsy.zju.edu.cn":
        raise ValueError("zju_admissions 只适用于浙江大学研究生院官方公开接口")
    payload = json.loads(content)
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("records"), list):
        raise ValueError("浙大接口结构变化，缺少 result.records")
    rows = result["records"]
    if not rows:
        raise ValueError("浙大接口无招生记录，保留已有时间并待核验")
    paragraphs, years = [], set()
    for row in rows:
        if str(row.get("bksmlx")) != "2" or row.get("bksmlx_dictText") != "免试生":
            continue
        if str(row.get("fbzt")) != "1" or str(row.get("qrzt")) != "1":
            continue
        year = str(row.get("nf", ""))
        name, timing = row.get("sysOrgCode_dictText"), row.get("jzrq")
        if not name or not timing or not year.isdigit():
            continue
        # jzrq 是该学院一行对应的报名时间，不从邻行或院系说明借用时间。
        timing = BeautifulSoup(timing, "html.parser").get_text(" ", strip=True)
        paragraphs.append(f"{name} 报名时间：{timing}")
        years.add(year)
    if not paragraphs or len(years) != 1:
        raise ValueError("浙大接口没有可明确归属同一招生年的已发布免试生报名记录")
    # 预报名阶段由已配置官方接口限定；保留官网报考类型原文，不推断学位类型。
    title = f"浙江大学{next(iter(years))}年推荐免试研究生预报名时间"
    return title, "\n".join(paragraphs), []
