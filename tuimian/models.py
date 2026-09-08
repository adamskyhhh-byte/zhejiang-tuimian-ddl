"""与前端共享的 v1 数据模型；日期精度与核验状态独立存储。"""

from datetime import date, datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="ignore", validate_assignment=True)


class TimePoint(Model):
    value: str | None = None
    precision: Literal["datetime", "date", "unknown"] = "unknown"
    raw: str = ""
    sourceId: str | None = None

    @model_validator(mode="after")
    def valid_precision(self):
        if self.precision == "unknown":
            if self.value is not None:
                raise ValueError("未知精度不得带有日期值")
        elif self.precision == "date":
            if not self.value or len(self.value) != 10:
                raise ValueError("日期精度必须为 YYYY-MM-DD")
            date.fromisoformat(self.value)
        else:
            if not self.value or datetime.fromisoformat(self.value).utcoffset() is None:
                raise ValueError("精确时间必须包含时区")
        return self


class Evidence(Model):
    sourceId: str
    url: str
    title: str
    excerpt: str


class School(Model):
    id: str
    name: str
    province: str
    groups: list[str]
    rosterYear: int = 2026
    rosterSources: list[str]
    eligibilityNote: str = ""
    disciplineRestrictions: list[str] = Field(default_factory=list)
    homepage: str
    inventoryStatus: Literal["reviewed", "pending"] = "pending"
    inventoryNote: str = ""


class Unit(Model):
    id: str
    schoolId: str
    name: str
    campus: str = ""
    disciplines: list[str]
    relevance: Literal["core", "related"]
    directoryUrl: str
    admissionUrl: str
    coverage: Literal["published", "not_found", "no_related", "pending", "error"] = "pending"
    note: str = ""


class Source(Model):
    id: str
    schoolId: str
    unitId: str | None = None
    url: str
    title: str
    kind: Literal["listing", "notice", "pdf"]
    lastAttemptAt: str | None = None
    lastSuccessAt: str | None = None
    lastParsedAt: str | None = None
    error: str | None = None

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str):
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ValueError("来源必须为 HTTP(S) URL")
        if parsed.hostname == "yjszs.nudt.edu.cn":
            value = value.replace("/newDetailed.view?", "/detailed.view?")
        return value


class SourceConfig(Source):
    adapter: Literal["html", "zju_admissions", "nudt_admissions"] = "html"
    noticeScope: Literal["auto", "school", "unit"] = "auto"
    unitIds: list[str] = Field(default_factory=list)
    includePatterns: list[str] = Field(default_factory=list)
    excludePatterns: list[str] = Field(default_factory=list)
    contentSelector: str | None = None
    linkSelector: str = "a[href]"
    render: bool = False
    enabled: bool = True
    scope: str | dict[str, str] | None = None
    allowedHosts: list[str] = Field(default_factory=list)
    identityKey: str | None = None
    batch: str | None = None
    forceAfterDays: int = Field(default=7, ge=1)
    maxPages: int = Field(default=3, ge=1, le=30)
    parentId: str | None = None


class Opportunity(Model):
    id: str
    schoolId: str
    unitId: str
    title: str
    year: int = 2027
    season: int = 2026
    batch: str = "首批"
    degrees: list[Literal["academic", "professional"]] = Field(default_factory=list)
    disciplines: list[str]
    relevance: Literal["core", "related"]
    stage: Literal["pre_admission"] = "pre_admission"
    applicationStart: TimePoint = Field(default_factory=TimePoint)
    applicationEnd: TimePoint = Field(default_factory=TimePoint)
    materialsEnd: TimePoint | None = None
    assessment: str = ""
    assessmentMode: Literal["online", "offline", "hybrid", "unknown"] = "unknown"
    programTags: list[str] = Field(default_factory=list)
    applicationUrl: str | None = None
    noticeUrl: str
    sourceIds: list[str]
    evidence: list[Evidence]
    verification: Literal["verified", "pending", "conflict"] = "pending"
    availability: Literal["announced", "open", "cancelled"] = "announced"
    firstSeenAt: str
    updatedAt: str
    notes: str = ""


class Change(Model):
    id: str
    opportunityId: str
    detectedAt: str
    kind: Literal["new", "extended", "shortened", "corrected", "cancelled", "reopened"]
    summary: str
    before: str | None = None
    after: str | None = None
    sourceId: str


class Run(Model):
    startedAt: str
    finishedAt: str
    status: Literal["success", "partial", "failed", "not_run"] = "not_run"
    checked: int = 0
    succeeded: int = 0
    failed: int = 0
    discovered: int = 0
    changed: int = 0


class Catalog(Model):
    schemaVersion: Literal[1] = 1
    generatedAt: str
    rosterYear: int = 2026
    admissionYear: int = 2027
    season: int = 2026
    schools: list[School]
    units: list[Unit]
    sources: list[Source]
    opportunities: list[Opportunity]
    changes: list[Change]
    run: Run

    @model_validator(mode="after")
    def references(self):
        for field in ("schools", "units", "sources", "opportunities", "changes"):
            ids = [item.id for item in getattr(self, field)]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{field} 存在重复 ID")
        schools = {s.id for s in self.schools}
        units = {u.id: u for u in self.units}
        sources = {s.id for s in self.sources}
        opportunities = {o.id for o in self.opportunities}
        for unit in self.units:
            if unit.schoolId not in schools:
                raise ValueError(f"培养单位 {unit.id} 学校不存在")
        for source in self.sources:
            if source.schoolId not in schools:
                raise ValueError(f"来源 {source.id} 学校不存在")
            if source.unitId and (
                source.unitId not in units or units[source.unitId].schoolId != source.schoolId
            ):
                raise ValueError(f"来源 {source.id} 培养单位不匹配")
        for item in self.opportunities:
            if item.unitId not in units or units[item.unitId].schoolId != item.schoolId:
                raise ValueError(f"项目 {item.id} 培养单位不匹配")
            if item.year != self.admissionYear or item.season != self.season:
                raise ValueError(f"项目 {item.id} 招生季不匹配")
            referenced = set(item.sourceIds) | {e.sourceId for e in item.evidence}
            referenced |= {
                p.sourceId
                for p in [item.applicationStart, item.applicationEnd, item.materialsEnd]
                if p and p.sourceId
            }
            if referenced - sources:
                raise ValueError(f"项目 {item.id} 来源不存在: {referenced - sources}")
            if item.verification == "verified" and not item.evidence:
                raise ValueError(f"项目 {item.id} 核验通过但无官方证据")
        for change in self.changes:
            if change.opportunityId not in opportunities or change.sourceId not in sources:
                raise ValueError(f"变更 {change.id} 关联不存在")
        return self
