"""状态原子持久化、人工修正叠加和发布前关系校验。"""

import copy
import hashlib
import json
import os
from pathlib import Path

from .models import Catalog, Opportunity, School, Source, SourceConfig, Unit
from .parser import now_iso


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_config(root: Path):
    data = root / "data"
    schools = [School.model_validate(s) for s in read_json(data / "schools.json", [])]
    units = [Unit.model_validate(u) for u in read_json(data / "units.json", [])]
    sources = [SourceConfig.model_validate(s) for s in read_json(data / "sources.json", [])]
    seeds = [Opportunity.model_validate(o) for o in read_json(data / "seeds.json", [])]
    if not schools:
        raise ValueError("data/schools.json 为空或不存在")
    overrides = read_json(data / "overrides.json", {})
    if isinstance(overrides, list):
        overrides = {item["id"]: {k: v for k, v in item.items() if k != "id"} for item in overrides}
    if not isinstance(overrides, dict):
        raise ValueError("overrides 必须为按项目ID索引的对象或数组")
    for identity, override in overrides.items():
        if not isinstance(override, dict) or not override.get("reason"):
            raise ValueError(f"人工修正 {identity} 必须含 reason")
        if set(override) & {"id", "schoolId", "unitId", "year", "season", "stage"}:
            raise ValueError(f"人工修正 {identity} 不能改动项目身份字段")
        reviewed = override.get("reviewedSourceHashes")
        if reviewed is not None and (
            not isinstance(reviewed, dict)
            or not reviewed
            or any(not isinstance(digest, str) or len(digest) != 64 for digest in reviewed.values())
        ):
            raise ValueError(f"人工修正 {identity} 的 reviewedSourceHashes 必须包含来源正文 hash")
        if reviewed and (
            not isinstance(override.get("reviewedAutomaticHash"), str)
            or len(override["reviewedAutomaticHash"]) != 64
        ):
            raise ValueError(f"人工修正 {identity} 缺少采集结果复核指纹 reviewedAutomaticHash")
    return schools, units, sources, seeds, overrides


def empty_state():
    return {
        "version": 1,
        "pages": {},
        "sourceStatus": {},
        "discoveredSources": {},
        "opportunities": {},
        "ids": {},
        "sourceVersions": {},
        "supersededSources": {},
        "correctionAuthorities": {},
        "retiredSources": {},
        "changes": [],
        "reviewQueue": [],
        "run": None,
    }


def load_review_decisions(root: Path) -> dict:
    decisions = read_json(root / "data/review-decisions.json", {})
    excluded = decisions.get("excludedOpportunities", {})
    aliases = decisions.get("opportunityAliases", {})
    if not isinstance(excluded, dict) or not isinstance(aliases, dict):
        raise ValueError("人工排除及项目别名必须为按项目 ID 索引的对象")
    for identity, decision in excluded.items():
        if (
            not isinstance(decision, dict)
            or not decision.get("reason")
            or not decision.get("evidenceUrls")
        ):
            raise ValueError(f"人工排除 {identity} 必须提供 reason 和 evidenceUrls")
    for identity in aliases:
        visited = {identity}
        target = aliases[identity]
        while target in aliases:
            if target in visited:
                raise ValueError(f"项目别名 {identity} 存在循环")
            visited.add(target)
            target = aliases[target]
        if not isinstance(target, str) or target in excluded:
            raise ValueError(f"项目别名 {identity} 的目标无效或已被排除")
    return {"excludedOpportunities": excluded, "opportunityAliases": aliases}


def load_state(root: Path, seeds: list[Opportunity]) -> dict:
    state = read_json(root / "data/state.json", empty_state())
    if state.get("version") != 1:
        raise ValueError("state.json 版本不兼容，不能覆盖历史状态")
    for key, default in empty_state().items():
        state.setdefault(key, default)
    state.update(load_review_decisions(root))
    for seed in seeds:
        if seed.id not in state["opportunities"]:
            pending = seed.model_dump()
            pending["verification"] = "pending"
            state["opportunities"][seed.id] = pending
    return state


def review_signature(item: dict) -> str:
    """同时锁定已检查的采集值和来源集合，不能让旧正文复核吞掉新来源更正。"""
    values = {key: item.get(key) for key in ("availability", "verification")}
    values["reviewRevision"] = item.get("reviewRevision", 0)
    values["sourceIds"] = sorted(item.get("sourceIds", []))
    for key in ("applicationStart", "applicationEnd", "materialsEnd"):
        point = item.get(key) or {}
        values[key] = {field: point.get(field) for field in ("value", "precision")}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def override_opportunity(item: dict, overrides: dict, pages: dict | None = None) -> dict:
    result = copy.deepcopy(item)
    override = overrides.get(item["id"], {})
    if not override:
        return result
    changed = False
    for key, value in override.items():
        if key in {"reason", "verification", "reviewedSourceHashes", "reviewedAutomaticHash"}:
            continue
        if key not in Opportunity.model_fields:
            raise ValueError(f"人工修正不支持字段 {key}")
        old = result.get(key)
        if isinstance(old, dict) and isinstance(value, dict):
            value = old | value
        if key in {"applicationStart", "applicationEnd", "materialsEnd", "availability"}:
            if isinstance(value, dict) and isinstance(old, dict):
                changed |= value.get("value") != old.get("value")
            else:
                changed |= value != old
        result[key] = value
    # 人工复核可明确接受当前正文的解析缺口；官方正文一旦改变，必须重新核验。
    reviewed = override.get("reviewedSourceHashes", {})
    matches_review = (
        bool(reviewed)
        and override.get("reviewedAutomaticHash") == review_signature(item)
        and all(
            (pages or {}).get(source_id, {}).get("hash") == digest
            for source_id, digest in reviewed.items()
        )
    )
    needs_review = (bool(reviewed) and not matches_review) or (changed and not matches_review)
    result["verification"] = (
        "conflict" if needs_review else override.get("verification", result["verification"])
    )
    result["notes"] = result.get("notes", "") + " 人工修正：" + override["reason"]
    if needs_review:
        result["notes"] += "；官方正文已变动或采集来源与人工值不同，请复核。"
    return result


def build_catalog(root: Path, state: dict | None = None) -> Catalog:
    schools, units, source_configs, seeds, overrides = load_config(root)
    state = state if state is not None else load_state(root, seeds)
    sources = {s.id: s for s in source_configs}
    for source_id, source in state["discoveredSources"].items():
        sources.setdefault(source_id, SourceConfig.model_validate(source))
    public_sources = []
    for source in sources.values():
        value = source.model_dump() | state["sourceStatus"].get(source.id, {})
        public_sources.append(Source.model_validate(value))
    decisions = load_review_decisions(root)
    excluded, aliases = decisions["excludedOpportunities"], decisions["opportunityAliases"]
    opportunities = [
        Opportunity.model_validate(override_opportunity(item, overrides, state["pages"]))
        for item in state["opportunities"].values()
        if item["id"] not in excluded and item["id"] not in aliases
    ]
    published_ids = {item.id for item in opportunities}
    changes = []
    for change in state["changes"]:
        identity = change["opportunityId"]
        if identity in excluded:
            continue
        while identity in aliases:
            identity = aliases[identity]
        if identity not in published_ids:
            raise ValueError(f"变更 {change['id']} 的项目别名目标不存在")
        changes.append(change | {"opportunityId": identity})
    for unit in units:
        unit_sources = [s for s in public_sources if s.unitId == unit.id]
        if any(o.unitId == unit.id for o in opportunities):
            unit.coverage = "published"
        elif unit_sources and all(s.error for s in unit_sources):
            unit.coverage = "error"
        # 未执行全量人工盘点不能把自动搜不到升级为 not_found。
    timestamp = now_iso()
    run = state["run"] or {"startedAt": timestamp, "finishedAt": timestamp, "status": "not_run"}
    settings = read_json(root / "data/settings.json", {})
    return Catalog(
        generatedAt=timestamp,
        schools=schools,
        units=units,
        sources=public_sources,
        opportunities=opportunities,
        changes=changes,
        run=run,
        rosterYear=settings.get("rosterYear", 2026),
        admissionYear=settings.get("admissionYear", 2027),
        season=settings.get("season", 2026),
    )


def export_catalog(root: Path, state: dict | None = None) -> Catalog:
    catalog = build_catalog(root, state)
    write_json(root / "public/data/catalog.json", catalog.model_dump())
    return catalog


def load_catalog(root: Path) -> Catalog:
    return Catalog.model_validate(read_json(root / "public/data/catalog.json", {}))
