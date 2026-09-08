"""列表发现、当季详情与附件复查、失败保留及原子导出。"""

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import urlparse

from .fetch import Fetcher, Page
from .models import Run, SourceConfig
from .parser import PRE, notice_identity, now_iso, parse_notice, stable_id
from .reconcile import merge_candidate
from .storage import build_catalog, load_config, load_state, read_json, write_json

logger = logging.getLogger(__name__)


def _source_key(source: SourceConfig) -> tuple:
    targets = sorted(set(([source.unitId] if source.unitId else []) + source.unitIds))
    return notice_identity(source.url), source.schoolId, tuple(targets), str(source.scope)


def _apply_source_scope(sources: dict[str, SourceConfig]) -> None:
    """共享学校栏目的 unitId 仅是检索目标，不是通知适用范围证据。"""
    targets: dict[tuple[str, str], set[str]] = {}
    for source in sources.values():
        key = source.schoolId, notice_identity(source.url)
        targets.setdefault(key, set()).update(
            ([source.unitId] if source.unitId else []) + source.unitIds
        )
    for source in sources.values():
        if source.noticeScope == "auto" and (
            not source.unitId or len(targets[source.schoolId, notice_identity(source.url)]) > 1
        ):
            source.noticeScope = "school"
    for source in sources.values():
        parent = sources.get(source.parentId)
        if parent:
            if not parent.enabled:
                source.enabled = False
            if source.noticeScope == "auto" and parent.noticeScope == "school":
                source.noticeScope = "school"


def _review(state: dict, source: SourceConfig, message: str, timestamp: str):
    # 同一原因只留一个待核验项，重跑不膨胀队列。
    state["reviewQueue"] = [
        item
        for item in state["reviewQueue"]
        if not (item["sourceId"] == source.id and item["reason"] == message)
    ]
    state["reviewQueue"].append(
        {"sourceId": source.id, "url": source.url, "reason": message, "detectedAt": timestamp}
    )


def _discovered_source(
    parent: SourceConfig, url: str, title: str, *, kind: str, identity: str | None = None
) -> SourceConfig:
    value = parent.model_dump()
    value.update(
        id="source-"
        + stable_id(
            parent.schoolId, parent.unitId or "", url, json.dumps(parent.unitIds), str(parent.scope)
        ),
        url=url,
        title=title or parent.title,
        kind=kind,
        parentId=parent.parentId or parent.id,
        identityKey=identity,
        lastAttemptAt=None,
        lastSuccessAt=None,
        lastParsedAt=None,
        error=None,
    )
    if parent.kind == "listing" and kind != "listing":
        # 列表布局选择器不应套在详情正文。
        value["contentSelector"] = None
    return SourceConfig.model_validate(value)


def discover(source: SourceConfig, page: Page, *, page_count: dict[str, int]) -> list[SourceConfig]:
    result = []
    for link in page.links:
        url, title = link["url"], link["title"]
        if url == source.url:
            continue
        text = title + " " + url
        if any(re.search(pattern, text, re.I) for pattern in source.excludePatterns):
            continue
        pdf = urlparse(url).path.lower().endswith(".pdf") or title.lower().endswith(".pdf")
        if source.kind != "listing":
            if pdf:
                result.append(
                    _discovered_source(
                        source,
                        url,
                        source.title,
                        kind="pdf",
                        identity=source.identityKey or source.url,
                    )
                )
            continue
        root_id = source.parentId or source.id
        if re.search(r"^(?:下一页|下页|next|下一頁|>)$", title, re.I):
            if page_count.get(root_id, 1) < source.maxPages:
                page_count[root_id] = page_count.get(root_id, 1) + 1
                result.append(_discovered_source(source, url, source.title, kind="listing"))
            continue
        included = any(re.search(pattern, text, re.I) for pattern in source.includePatterns)
        if source.includePatterns and not included:
            continue
        if not source.includePatterns and not (
            PRE.search(title) or re.search(r"推免.{0,15}(?:延期|更正|调整|补充)", title)
        ):
            continue
        if "夏令营" in title and not PRE.search(title):
            continue
        result.append(_discovered_source(source, url, title, kind="pdf" if pdf else "notice"))
    return result


def _correction_link(page: Page) -> dict[str, str] | None:
    if not re.search(r"延期|延长|提前|更正|调整|取消|重新开放", page.title):
        return None
    explicit = [
        link for link in page.links if re.search(r"原公告|原通知|此前公告|此前通知", link["title"])
    ]
    candidates = explicit or [
        link
        for link in page.links
        if re.search(r"20\d{2}", link["title"])
        and PRE.search(link["title"])
        and not re.search(r"延期|延长|更正|调整", link["title"])
    ]
    unique = {link["url"]: link for link in candidates}
    return next(iter(unique.values())) if len(unique) == 1 else None


async def crawl(
    root: Path,
    *,
    source_ids: list[str] | None = None,
    limit: int | None = None,
    no_network: bool = False,
    fetcher: Fetcher | None = None,
) -> dict:
    root = Path(root).resolve()
    schools, units, configured, seeds, _ = load_config(root)
    state = load_state(root, seeds)
    # 开始联网前先验证所有静态配置与种子关系，失败不污染状态。
    build_catalog(root, state)
    if no_network:
        catalog = build_catalog(root, state)
        write_json(root / "data/state.json", state)
        write_json(root / "public/data/catalog.json", catalog.model_dump())
        return catalog.run.model_dump()
    settings = read_json(root / "data/settings.json", {})
    season, year = settings.get("season", 2026), settings.get("admissionYear", 2027)
    unit_map = {u.id: u for u in units}
    sources = {s.id: s for s in configured}
    for identity, source in state["discoveredSources"].items():
        sources.setdefault(identity, SourceConfig.model_validate(source))
    _apply_source_scope(sources)
    unknown = set(source_ids or []) - sources.keys()
    if unknown:
        raise ValueError(f"来源ID不存在: {', '.join(sorted(unknown))}")
    selected = set(source_ids or sources.keys())
    configured_ids = {source.id for source in configured}
    queue = [
        s
        for s in sources.values()
        if s.enabled
        and (s.id in selected or s.parentId in selected)
        and (s.kind != "listing" or s.id in configured_ids or s.id in (source_ids or []))
    ]
    queue.sort(key=lambda source: (source.kind != "listing", source.id))
    visited: set[str] = set()
    seen_urls = {}
    for source in sources.values():
        seen_urls.setdefault(_source_key(source), []).append(source.id)
    page_count: dict[str, int] = {}
    timestamp = now_iso()
    run = Run(startedAt=timestamp, finishedAt=timestamp)
    owned_fetcher = fetcher is None
    fetcher = fetcher or Fetcher()
    try:
        while queue and (limit is None or run.checked < limit):
            size = min(6, limit - run.checked) if limit is not None else 6
            batch, queue = queue[:size], queue[size:]
            batch = [s for s in batch if s.id not in visited]
            if not batch:
                continue
            for source in batch:
                visited.add(source.id)
                status = state["sourceStatus"].setdefault(source.id, {})
                status["lastAttemptAt"] = now_iso()
            pages = await asyncio.gather(
                *(fetcher.fetch(s, state["pages"].get(s.id)) for s in batch), return_exceptions=True
            )
            for source, result in zip(batch, pages):
                run.checked += 1
                status = state["sourceStatus"].setdefault(source.id, {})
                timestamp = now_iso()
                if isinstance(result, BaseException):
                    run.failed += 1
                    status["error"] = f"{type(result).__name__}: {result}"[:600]
                    _review(state, source, status["error"], timestamp)
                    logger.warning("来源失败 %s: %s", source.id, status["error"])
                    continue
                page = result
                prior_page = state["pages"].get(source.id)
                state["pages"][source.id] = page.to_dict()
                try:
                    discoveries = discover(source, page, page_count=page_count)
                    correction_link = _correction_link(page)
                    if source.kind != "listing" and correction_link:
                        if not source.identityKey:
                            source.identityKey = correction_link["url"]
                        discoveries.append(
                            _discovered_source(
                                source,
                                correction_link["url"],
                                correction_link["title"],
                                kind="notice",
                            )
                        )
                except (ValueError, re.error) as exc:
                    run.failed += 1
                    status["error"] = f"列表解析失败: {exc}"
                    _review(state, source, status["error"], timestamp)
                    continue
                for discovered in discoveries:
                    key = _source_key(discovered)
                    existing_ids = seen_urls.get(key)
                    if existing_ids:
                        # 同一公告人工配置了多个批次时，发现链接应复查全部已知批次。
                        for existing_id in existing_ids:
                            if (
                                sources[existing_id].enabled
                                and existing_id not in visited
                                and existing_id not in {s.id for s in queue}
                            ):
                                queue.append(sources[existing_id])
                        continue
                    sources[discovered.id] = discovered
                    seen_urls[key] = [discovered.id]
                    state["discoveredSources"][discovered.id] = discovered.model_dump()
                    queue.append(discovered)
                    run.discovered += 1
                if source.kind == "listing":
                    run.succeeded += 1
                    status.update(lastSuccessAt=timestamp, lastParsedAt=timestamp, error=None)
                    continue
                unit_ids = list(
                    dict.fromkeys(([source.unitId] if source.unitId else []) + source.unitIds)
                )
                if not unit_ids:
                    unit_ids = [u.id for u in units if u.schoolId == source.schoolId]
                parsed_any = False
                parse_errors = []
                for unit_id in unit_ids:
                    unit = unit_map.get(unit_id)
                    if unit is None:
                        parse_errors.append(f"引用未知培养单位 {unit_id}")
                        continue
                    try:
                        candidate = parse_notice(
                            page.title,
                            page.text,
                            source,
                            unit,
                            season=season,
                            year=year,
                            timestamp=timestamp,
                        )
                    except (ValueError, re.error) as exc:
                        parse_errors.append(f"解析失败: {exc}")
                        continue
                    if candidate is None:
                        continue
                    parsed_any = True
                    # 仅在明确链接原公告时跨 URL 归并更正，否则交给人工 identityKey。
                    correction = bool(
                        re.search(r"延期|延长|提前|更正|调整|取消|重新开放", page.title)
                    )
                    if correction and not source.identityKey:
                        linked = {link["url"] for link in page.links}
                        matches = [
                            item
                            for item in state["opportunities"].values()
                            if item["noticeUrl"] in linked
                            and item["unitId"] == unit_id
                            and item["batch"] == candidate.batch
                        ]
                        if len(matches) == 1:
                            source.identityKey = matches[0]["noticeUrl"]
                    if merge_candidate(state, candidate, source, timestamp, correction=correction):
                        run.changed += 1
                    if candidate.verification != "verified":
                        _review(state, source, candidate.notes or "硕士报名时间待核验", timestamp)
                unconfirmed = [
                    item
                    for item in state["opportunities"].values()
                    if source.id in item["sourceIds"]
                    and not any(
                        evidence["sourceId"] != source.id
                        and evidence["url"] in {link["url"] for link in page.links}
                        for evidence in item["evidence"]
                    )
                ]
                if not parsed_any and unconfirmed:
                    parse_errors.append("当前正文未能确认既有项目，保留旧记录并待核验")
                    _review(
                        state, source, "当前正文未能确认既有项目，保留旧记录并待核验", timestamp
                    )
                    if not prior_page or prior_page["hash"] != page.hash:
                        for item in unconfirmed:
                            if source.id in item["sourceIds"]:
                                if source.id in state["supersededSources"].get(item["id"], {}):
                                    continue
                                state["sourceVersions"].get(item["id"], {}).pop(source.id, None)
                                if item["verification"] != "conflict":
                                    item["verification"] = "pending"
                if parse_errors:
                    run.failed += 1
                    status["error"] = "；".join(parse_errors)[:600]
                    _review(state, source, status["error"], timestamp)
                else:
                    run.succeeded += 1
                    status.update(lastSuccessAt=timestamp, lastParsedAt=timestamp, error=None)
                logger.info("已检查 %s (%s)", source.id, source.kind)
    finally:
        if owned_fetcher:
            await fetcher.close()
    run.finishedAt = now_iso()
    run.status = (
        "failed"
        if run.failed and not run.succeeded
        else "partial"
        if run.failed or queue
        else "success"
        if run.checked
        else "not_run"
    )
    state["run"] = run.model_dump()
    catalog = build_catalog(root, state)
    # 先验证，再原子替换文件；中途异常时旧网页和旧状态仍然可用。
    write_json(root / "data/state.json", state)
    write_json(root / "public/data/catalog.json", catalog.model_dump())
    return run.model_dump()
