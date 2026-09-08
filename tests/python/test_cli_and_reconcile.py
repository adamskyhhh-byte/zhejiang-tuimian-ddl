import asyncio
import json
import sys

from test_crawler import setup_root
from test_parser import unit

from tuimian.__main__ import main
from tuimian.crawler import _invalidate_source, crawl
from tuimian.models import SourceConfig
from tuimian.parser import parse_notice
from tuimian.reconcile import merge_candidate
from tuimian.storage import (
    empty_state,
    load_catalog,
    override_opportunity,
    read_json,
    review_signature,
)


def test_manual_deadline_review_accepts_only_the_reviewed_official_content():
    source = SourceConfig(
        id="n",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/n",
        title="2027年硕士预推免",
    )
    item = parse_notice(source.title, "硕士预推免申请时间见正文图片。", source, unit()).model_dump()
    override = {
        item["id"]: {
            "reason": "人工核对官方正文图片：9月13日17:00前提交申请材料。",
            "materialsEnd": {
                "value": "2026-09-13T17:00:00+08:00",
                "precision": "datetime",
                "raw": "9月13日17:00前",
                "sourceId": "n",
            },
            "verification": "verified",
            "reviewedSourceHashes": {"n": "a" * 64},
            "reviewedAutomaticHash": review_signature(item),
        }
    }
    reviewed = override_opportunity(item, override, {"n": {"hash": "a" * 64}})
    assert reviewed["verification"] == "verified"
    assert reviewed["applicationEnd"]["value"] is None
    for pages in [{}, {"n": {"hash": "b" * 64}}]:
        changed = override_opportunity(item, override, pages)
        assert changed["verification"] == "conflict"
        assert changed["materialsEnd"]["value"] == reviewed["materialsEnd"]["value"]
    incoming = item | {"sourceIds": ["n", "new-official-correction"]}
    assert (
        override_opportunity(incoming, override, {"n": {"hash": "a" * 64}})["verification"]
        == "conflict"
    )


def test_replaced_attachment_invalidates_review_even_when_pending_and_old_pdf_reappears():
    source = SourceConfig(
        id="old-pdf",
        schoolId="s",
        unitId="s-ai",
        kind="pdf",
        url="https://s.edu.cn/a.pdf",
        title="2027年硕士预推免",
    )
    candidate = parse_notice(source.title, "硕士预推免申请时间见正文图片。", source, unit())
    state = empty_state()
    state["opportunities"][candidate.id] = candidate.model_dump()
    original = state["opportunities"][candidate.id]
    override = {
        candidate.id: {
            "reason": "人工核验原附件",
            "verification": "verified",
            "reviewedSourceHashes": {source.id: "a" * 64},
            "reviewedAutomaticHash": review_signature(original),
        }
    }
    parent = source.model_copy(
        update={"id": "parent", "kind": "notice", "url": "https://s.edu.cn/n"}
    )
    _invalidate_source(state, parent, {source.url})
    assert state["opportunities"][candidate.id]["verification"] == "pending"
    merge_candidate(state, candidate, source, "2026-09-09T02:00:00+08:00")
    retained = state["opportunities"][candidate.id]
    assert retained["reviewRevision"] == 1
    assert (
        override_opportunity(retained, override, {source.id: {"hash": "a" * 64}})["verification"]
        == "conflict"
    )


def test_readable_retired_pdf_cannot_restore_automatic_verification():
    source = SourceConfig(
        id="old",
        schoolId="s",
        unitId="s-ai",
        kind="pdf",
        url="https://s.edu.cn/a.pdf",
        title="2027年硕士预推免",
    )
    candidate = parse_notice(source.title, "硕士预报名截止9月10日。", source, unit())
    state = empty_state()
    state["opportunities"][candidate.id] = candidate.model_dump()
    assert candidate.verification == "verified"
    parent = source.model_copy(update={"id": "parent", "url": "https://s.edu.cn/n"})
    _invalidate_source(state, parent, {source.url})
    assert not merge_candidate(state, candidate, source, "2026-09-09T02:00:00+08:00")
    assert state["opportunities"][candidate.id]["verification"] == "pending"
    assert state["opportunities"][candidate.id]["applicationEnd"]["value"] == "2026-09-10"


def test_offline_export_validate_and_unknown_source(tmp_path, monkeypatch):
    root = setup_root(tmp_path)
    monkeypatch.setattr(sys, "argv", ["tuimian", "crawl", "--root", str(root), "--no-network"])
    assert main() == 0
    assert load_catalog(root).run.status == "not_run"
    monkeypatch.setattr(sys, "argv", ["tuimian", "export", "--root", str(root)])
    assert main() == 0
    monkeypatch.setattr(
        sys, "argv", ["tuimian", "validate", "--root", str(root), "--expect-schools", "1"]
    )
    assert main() == 0
    monkeypatch.setattr(
        sys, "argv", ["tuimian", "validate", "--root", str(root), "--expect-schools", "68"]
    )
    assert main() == 2
    monkeypatch.setattr(
        sys, "argv", ["tuimian", "crawl", "--root", str(root), "--source", "missing"]
    )
    assert main() == 2


def test_seed_pending_without_network_and_identity_survives_new_notice(tmp_path):
    root = setup_root(tmp_path)
    source = SourceConfig(
        id="n",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/n",
        title="2027年硕士预推免",
    )
    first = parse_notice(source.title, "硕士预推免报名截止9月10日。", source, unit())
    assert first.verification == "verified"
    data = root / "data"
    sources = json.loads((data / "sources.json").read_text(encoding="utf-8"))
    sources.append(source.model_dump())
    (data / "sources.json").write_text(json.dumps(sources), encoding="utf-8")
    (data / "seeds.json").write_text(json.dumps([first.model_dump()]), encoding="utf-8")
    asyncio.run(crawl(root, no_network=True))
    assert load_catalog(root).opportunities[0].verification == "pending"
    state = empty_state()
    state["opportunities"][first.id] = first.model_dump()
    later = source.model_copy(
        update={"id": "new", "url": "https://s.edu.cn/new", "identityKey": source.url}
    )
    candidate = parse_notice("2027年硕士预推免延期", "硕士预推免报名延期至9月12日。", later, unit())
    merge_candidate(state, candidate, later, "2026-09-08T12:00:00+08:00", correction=True)
    assert len(state["opportunities"]) == 1
    assert state["opportunities"][first.id]["applicationEnd"]["value"] == "2026-09-12"
    assert state["changes"][-1]["kind"] == "extended"


def test_independent_source_conflict_and_cancel_reopen():
    state = empty_state()
    source = SourceConfig(
        id="a",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/a",
        title="2027年硕士预推免",
        identityKey="program",
    )
    first = parse_notice(source.title, "硕士预推免报名截止9月10日。", source, unit())
    merge_candidate(state, first, source, "2026-09-08T12:00:00+08:00")
    other = source.model_copy(update={"id": "b", "url": "https://s.edu.cn/b"})
    different = parse_notice(source.title, "硕士预推免报名截止9月11日。", other, unit())
    merge_candidate(state, different, other, "2026-09-08T13:00:00+08:00")
    result = state["opportunities"][first.id]
    assert result["applicationEnd"]["value"] == "2026-09-10"
    assert result["verification"] == "conflict"
    merge_candidate(state, different, other, "2026-09-08T13:10:00+08:00")
    merge_candidate(state, first, source, "2026-09-08T13:20:00+08:00")
    assert state["opportunities"][first.id]["verification"] == "conflict"
    assert state["opportunities"][first.id]["applicationEnd"]["value"] == "2026-09-10"
    cancelled = parse_notice(
        source.title, "硕士预推免报名截止9月10日，本次预推免报名取消。", source, unit()
    )
    merge_candidate(state, cancelled, source, "2026-09-08T14:00:00+08:00", correction=True)
    assert state["changes"][-1]["kind"] == "cancelled"
    reopened = parse_notice(source.title, "硕士预推免即日起报名，报名截止9月10日。", source, unit())
    merge_candidate(state, reopened, source, "2026-09-08T15:00:00+08:00", correction=True)
    assert state["changes"][-1]["kind"] == "reopened"


def test_extension_supersedes_original_and_daily_rechecks_are_order_independent():
    state = empty_state()
    source = SourceConfig(
        id="original",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/original",
        title="2027年硕士预推免",
    )
    original = parse_notice(source.title, "硕士预推免报名截止9月10日。", source, unit())
    merge_candidate(state, original, source, "2026-09-07T12:00:00+08:00")
    correction = source.model_copy(
        update={"id": "extension", "url": "https://s.edu.cn/extension", "identityKey": source.url}
    )
    extended = parse_notice(
        "2027年硕士预推免延期", "硕士预推免报名延期至9月12日。", correction, unit()
    )
    merge_candidate(state, extended, correction, "2026-09-08T12:00:00+08:00", correction=True)
    for day, ordered in [
        (9, [(original, source, False), (extended, correction, True)]),
        (10, [(extended, correction, True), (original, source, False)]),
    ]:
        for candidate, config, is_correction in ordered:
            merge_candidate(
                state,
                candidate,
                config,
                f"2026-09-{day:02d}T12:00:00+08:00",
                correction=is_correction,
            )
        current = state["opportunities"][original.id]
        assert current["applicationEnd"]["value"] == "2026-09-12"
        assert current["verification"] == "verified"
        assert len(state["changes"]) == 2


def test_superseded_source_new_date_conflict_is_not_cleared_by_old_correction():
    state = empty_state()
    original_source = SourceConfig(
        id="original",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/original",
        title="2027年硕士预推免",
    )
    original = parse_notice(
        original_source.title, "硕士预推免报名截止9月10日。", original_source, unit()
    )
    merge_candidate(state, original, original_source, "2026-09-07T12:00:00+08:00")
    correction_source = original_source.model_copy(
        update={
            "id": "extension",
            "url": "https://s.edu.cn/extension",
            "identityKey": original_source.url,
        }
    )
    correction = parse_notice(
        "2027年硕士预推免延期", "硕士预推免报名延期至9月12日。", correction_source, unit()
    )
    merge_candidate(
        state, correction, correction_source, "2026-09-08T12:00:00+08:00", correction=True
    )
    changed_original = parse_notice(
        original_source.title, "硕士预推免报名截止9月13日。", original_source, unit()
    )
    merge_candidate(state, changed_original, original_source, "2026-09-09T12:00:00+08:00")
    merge_candidate(
        state, correction, correction_source, "2026-09-09T13:00:00+08:00", correction=True
    )
    assert state["opportunities"][original.id]["verification"] == "conflict"
    assert state["opportunities"][original.id]["applicationEnd"]["value"] == "2026-09-12"
    assert len(state["changes"]) == 3


def test_online_registration_does_not_infer_assessment_mode_and_overrides_survive():
    config = SourceConfig(
        id="s",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        title="2027年硕士预推免",
        url="https://s.edu.cn/n",
    )
    candidate = parse_notice(
        config.title, "硕士预推免网上报名截止9月10日，考核安排另行通知。", config, unit()
    )
    assert candidate.assessmentMode == "unknown"
    assert candidate.programTags == []
    result = override_opportunity(
        candidate.model_dump(),
        {
            candidate.id: {
                "reason": "招生学院另行发布的考核安排已人工核验",
                "assessmentMode": "offline",
                "programTags": ["卓越工程师"],
            }
        },
    )
    assert result["assessmentMode"] == "offline"
    assert result["programTags"] == ["卓越工程师"]


def test_same_cms_article_alias_keeps_id_and_same_url_update_is_not_source_conflict():
    state = empty_state()
    config = SourceConfig(
        id="old",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/c6/2d/c52126a771629/page.htm",
        title="2027年硕士预推免",
    )
    first = parse_notice(config.title, "硕士预报名截止9月10日。", config, unit())
    merge_candidate(state, first, config, "2026-09-08T12:00:00+08:00")
    alias = config.model_copy(
        update={"id": "discovered", "url": "https://s.edu.cn/c6/2d/c52124a771629/page.htm"}
    )
    repeated = parse_notice(config.title, "硕士预报名截止9月10日。", alias, unit())
    merge_candidate(state, repeated, alias, "2026-09-08T13:00:00+08:00")
    assert len(state["opportunities"]) == 1
    assert len(state["changes"]) == 1
    updated = parse_notice(config.title, "硕士预报名截止9月12日。", alias, unit())
    merge_candidate(state, updated, alias, "2026-09-08T14:00:00+08:00")
    assert state["opportunities"][first.id]["verification"] == "verified"
    assert state["changes"][-1]["kind"] == "extended"


def test_review_exclusion_and_alias_hide_only_public_records_and_prevent_recreation(tmp_path):
    root = setup_root(tmp_path)
    configs, seeds = [], []
    for identity in ["canonical", "alias", "excluded"]:
        config = SourceConfig(
            id=identity,
            schoolId="s",
            unitId="s-ai",
            kind="notice",
            url=f"https://s.edu.cn/{identity}",
            title="2027年硕士预推免",
        )
        configs.append(config.model_dump())
        seeds.append(
            parse_notice(config.title, "硕士预报名截止9月10日。", config, unit()).model_dump()
        )
    for name, value in [("sources", configs), ("seeds", seeds)]:
        (root / f"data/{name}.json").write_text(json.dumps(value), encoding="utf-8")
    canonical, alias, excluded = [item["id"] for item in seeds]
    decisions = {
        "opportunityAliases": {alias: canonical},
        "excludedOpportunities": {
            excluded: {"reason": "公告不属于本单位", "evidenceUrls": ["https://s.edu.cn/excluded"]}
        },
    }
    (root / "data/review-decisions.json").write_text(json.dumps(decisions), encoding="utf-8")
    asyncio.run(crawl(root, no_network=True))
    assert [item.id for item in load_catalog(root).opportunities] == [canonical]
    state = read_json(root / "data/state.json", {})
    assert len(state["opportunities"]) == 3
    for config in configs[1:]:
        source = SourceConfig.model_validate(config)
        incoming = parse_notice(source.title, "硕士预报名截止9月12日。", source, unit())
        merge_candidate(state, incoming, source, "2026-09-08T14:00:00+08:00")
    assert len(state["opportunities"]) == 3
    assert state["opportunities"][excluded]["applicationEnd"]["value"] == "2026-09-10"
    assert state["changes"][0]["opportunityId"] == canonical


def test_wrong_unit_alias_cannot_overwrite_canonical_unit_or_deadline():
    state = empty_state()
    config = SourceConfig(
        id="correct",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/notice",
        title="2027年硕士预推免",
    )
    correct = parse_notice(config.title, "硕士预报名截止9月10日。", config, unit())
    merge_candidate(state, correct, config, "2026-09-08T12:00:00+08:00")
    wrong_unit = unit().model_copy(update={"id": "s-law", "name": "法学院"})
    wrong_source = config.model_copy(update={"id": "wrong", "unitId": "s-law"})
    wrong = parse_notice(config.title, "硕士预报名截止9月20日。", wrong_source, wrong_unit)
    state["opportunityAliases"] = {wrong.id: correct.id}
    assert not merge_candidate(state, wrong, wrong_source, "2026-09-08T14:00:00+08:00")
    assert state["opportunities"][correct.id]["unitId"] == "s-ai"
    assert state["opportunities"][correct.id]["applicationEnd"]["value"] == "2026-09-10"
