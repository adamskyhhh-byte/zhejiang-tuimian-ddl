"""项目持久 ID 与变更归并；解析失败时不丢弃已有有效时间。"""

import json
from urllib.parse import urlparse

from .models import Opportunity, SourceConfig
from .parser import notice_identity, stable_id


def semantic(item: dict) -> dict:
    ignored = {"id", "firstSeenAt", "updatedAt", "sourceIds", "evidence", "reviewRevision"}
    result = {key: value for key, value in item.items() if key not in ignored}
    result.setdefault("assessmentMode", "unknown")
    result.setdefault("programTags", [])
    for key in ("applicationStart", "applicationEnd", "materialsEnd"):
        if result.get(key):
            result[key] = {k: v for k, v in result[key].items() if k not in {"raw", "sourceId"}}
    return result


def resolve_id(state: dict, candidate: Opportunity, source: SourceConfig) -> str:
    def canonical(identity: str) -> str:
        aliases = state.get("opportunityAliases", {})
        while identity in aliases:
            identity = aliases[identity]
        return identity

    key = "|".join(
        [
            candidate.schoolId,
            candidate.unitId,
            str(candidate.year),
            candidate.batch,
            source.identityKey or source.url,
        ]
    )
    if key in state["ids"]:
        return canonical(state["ids"][key])
    for item in state["opportunities"].values():
        # 种子与同网址后续正文改名仍归属原项目。批次变更要建新项目。
        if (
            item["unitId"] == candidate.unitId
            and item["year"] == candidate.year
            and item["batch"] == candidate.batch
            and (
                notice_identity(item["noticeUrl"])
                in {notice_identity(source.url), notice_identity(source.identityKey or source.url)}
                or source.id in item["sourceIds"]
            )
        ):
            state["ids"][key] = canonical(item["id"])
            return state["ids"][key]
    state["ids"][key] = canonical(candidate.id)
    return state["ids"][key]


def timing(item: dict) -> dict:
    value = semantic(item)
    return {
        field: value.get(field)
        for field in ("applicationStart", "applicationEnd", "materialsEnd", "availability")
    }


def merge_candidate(
    state: dict,
    candidate: Opportunity,
    source: SourceConfig,
    timestamp: str,
    *,
    correction: bool = False,
) -> bool:
    identity = resolve_id(state, candidate, source)
    if identity in state.get("excludedOpportunities", {}):
        return False
    if source.id in state.get("retiredSources", {}).get(identity, {}):
        # 父通知已移除此附件；旧文件仍可访问不代表它仍是有效招生依据。
        return False
    candidate.id = identity
    incoming = candidate.model_dump()
    previous = state["opportunities"].get(identity)
    if previous:
        incoming["reviewRevision"] = previous.get("reviewRevision", 0)
    if previous and any(
        previous[field] != incoming[field]
        for field in ("schoolId", "unitId", "year", "season", "batch")
    ):
        # 人工将误配学院的旧记录归并后，其旧来源不能覆盖正确培养单位的身份与时间。
        return False
    if previous and notice_identity(previous["noticeUrl"]) == notice_identity(source.url):
        incoming["noticeUrl"] = previous["noticeUrl"]
    versions = state.setdefault("sourceVersions", {}).setdefault(identity, {})
    superseded = state.setdefault("supersededSources", {}).setdefault(identity, {})
    authorities = state.setdefault("correctionAuthorities", {})
    authority = authorities.get(identity)
    raw_semantic = semantic(incoming)
    if versions.get(source.id) == raw_semantic:
        # 同一原文反复复查不能重新参与覆盖，避免原公告和延期公告轮流产生虚假变更。
        return False
    first_visit = source.id not in versions
    versions[source.id] = raw_semantic
    if (
        previous
        and authority
        and first_visit
        and source.url == authority["originalUrl"]
        and source.id != authority["sourceId"]
    ):
        # 首次先发现延期通知时，随后读取其明确链接的原公告只补证据，不回退延期。
        superseded[source.id] = timing(incoming)
        previous["sourceIds"] = list(dict.fromkeys(previous["sourceIds"] + incoming["sourceIds"]))
        previous["evidence"] = [
            e for e in previous["evidence"] if e["sourceId"] != source.id
        ] + incoming["evidence"]
        for field in ("applicationStart", "materialsEnd"):
            old, new = previous.get(field), incoming.get(field)
            if new and new.get("value") and (not old or not old.get("value")):
                previous[field] = new
        if not previous["degrees"]:
            previous["degrees"] = incoming["degrees"]
        return False
    if (
        correction
        and source.identityKey
        and source.identityKey != source.url
        and urlparse(source.identityKey).scheme in {"https", "http"}
    ):
        authorities[identity] = {"sourceId": source.id, "originalUrl": source.identityKey}
    if previous and source.id in superseded:
        if timing(incoming) in [superseded[source.id], timing(previous)]:
            return False
        # 旧来源被明确更正取代后又修改了时间，保留较新的结果并要求人工消歧。
        incoming = previous | {
            "verification": "conflict",
            "notes": "已被后续公告替代的来源时间出现实质变化，保留现有时间并待核验。",
            "evidence": [e for e in previous["evidence"] if e["sourceId"] != source.id]
            + candidate.model_dump()["evidence"],
        }
        correction = False
    elif previous and correction:
        previous_source = previous["applicationEnd"].get("sourceId")
        if previous_source and previous_source != source.id:
            superseded[previous_source] = timing(previous)
    kind = "new"
    before = None
    if previous:
        incoming["firstSeenAt"] = previous["firstSeenAt"]
        incoming["sourceIds"] = list(dict.fromkeys(previous["sourceIds"] + incoming["sourceIds"]))
        incoming["evidence"] = [
            e for e in previous["evidence"] if e["sourceId"] != source.id
        ] + incoming["evidence"]
        # 对已知来源的暂时解析失败只降低核验，不清空先前已知时间。
        for field in ("applicationStart", "applicationEnd", "materialsEnd"):
            old, new = previous.get(field), incoming.get(field)
            if old and old.get("value") and (not new or not new.get("value")):
                incoming[field] = old
                if not correction:
                    incoming["verification"] = "pending"
                    incoming["notes"] += " 新正文未能确认全部既有时间，暂保留上次值。"
        for field in ("degrees", "applicationUrl", "assessment"):
            if not incoming.get(field) and previous.get(field):
                incoming[field] = previous[field]
        old_end = previous["applicationEnd"].get("value")
        new_end = incoming["applicationEnd"].get("value")
        old_source = previous["applicationEnd"].get("sourceId")
        old_urls = {
            notice_identity(e["url"]) for e in previous["evidence"] if e["sourceId"] == old_source
        }
        different_source = (
            old_source not in {None, source.id} and notice_identity(source.url) not in old_urls
        )
        if old_end and new_end and old_end != new_end and different_source and not correction:
            incoming["applicationEnd"] = previous["applicationEnd"]
            incoming["verification"] = "conflict"
            incoming["notes"] += f" 来源冲突：新来源给出 {new_end}，保留已有 {old_end}，待核验。"
            new_end = old_end
        elif previous["verification"] == "conflict" and not correction:
            # 另一来源再次成功访问不构成冲突已解决的证据。
            incoming["verification"] = "conflict"
            incoming["notes"] = previous["notes"]
        if semantic(previous) == semantic(incoming):
            incoming["updatedAt"] = previous["updatedAt"]
            state["opportunities"][identity] = incoming
            return False
        kind = "corrected"
        if incoming["availability"] == "cancelled" and previous["availability"] != "cancelled":
            kind = "cancelled"
        elif previous["availability"] == "cancelled" and incoming["availability"] == "open":
            kind = "reopened"
        elif old_end and new_end and old_end != new_end:
            # ISO8601 字符串在日期部分即按北京时间排序；同一天精度变化算更正。
            if previous["applicationEnd"]["precision"] == incoming["applicationEnd"]["precision"]:
                kind = "extended" if new_end > old_end else "shortened"
        before = json.dumps(semantic(previous), ensure_ascii=False, sort_keys=True)
    incoming["updatedAt"] = timestamp
    Opportunity.model_validate(incoming)
    state["opportunities"][identity] = incoming
    after = json.dumps(semantic(incoming), ensure_ascii=False, sort_keys=True)
    labels = {
        "new": "新增招生通知",
        "extended": "报名截止延期",
        "shortened": "报名截止提前",
        "corrected": "公告内容更正",
        "cancelled": "报名取消",
        "reopened": "报名重新开放",
    }
    state["changes"].append(
        {
            "id": "change-" + stable_id(identity, timestamp, before or "", after),
            "opportunityId": identity,
            "detectedAt": timestamp,
            "kind": kind,
            "summary": labels[kind],
            "before": before,
            "after": after,
            "sourceId": source.id,
        }
    )
    return True
