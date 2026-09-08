"""保守的公告解析：不确定的时间保留待核验，不混用硕博或材料日期。"""

import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from .models import Evidence, Opportunity, SourceConfig, TimePoint, Unit

TZ = ZoneInfo("Asia/Shanghai")
DATE = re.compile(
    r"(?:(?P<year>20\d{2})\s*[年./-]\s*)?"
    r"(?P<month>1[0-2]|0?[1-9])\s*(?P<separator>[月./-])\s*(?P<day>3[01]|[12]\d|0?[1-9])(?!\d)(?!\s+\d)\s*日?"
    r"(?:\s*[（(]\s*(?:周|星期|礼拜)[一二三四五六日天]\s*[）)])?"
    r"(?:\s*(?P<period>上午|下午|晚上|中午)?\s*(?P<hour>2[0-4]|1\d|0?\d)"
    r"\s*(?:[:：]\s*(?P<minute>[0-5]\d)|[时点](?P<zhminute>[0-5]?\d)?分?))?"
)
PRE = re.compile(
    r"预推免|预报名|预接收|预面试|推免.{0,12}预选拔|接收.{0,20}推荐免试.{0,15}(?:预|申请)|推免.{0,8}预申请"
)
APPLY = re.compile(r"报名|预申请|申请(?:时间|起止|截止)|系统.{0,10}(?:开放|关闭|填报)")
END = re.compile(r"截止|截至|至|之前|日前|结束|关闭|延长|延期|调整为")
MATERIAL = re.compile(r"材料|纸质|邮寄|邮件|发送|附件上传")
PHD = re.compile(r"直博|博士|硕博连读")
MASTER = re.compile(r"硕士|学硕|专硕|直硕|推免硕|学术学位|专业学位")
RANGE = r"至|到|—|―|－|~|～|-"
APPLICATION_LABEL = re.compile(
    r"(?:报名|申请)(?:开始|截止|截至|起止)?时间|(?:报名|申请)(?:截止|截至)"
)


def _has_end(line: str) -> bool:
    return bool(END.search(line) or re.search(r"(?:日|[:：]\s*\d{2}|[时点])\s*(?:前|以前)", line))


def _clauses(text: str):
    """日期在逗号前、报名动作在逗号后的句子需一起读，不能跨段借用标签。"""
    for sentence in re.split(r"[\n。；;]+", text):
        parts = re.split(r"[，,]+", sentence)
        i = 0
        while i < len(parts):
            line = parts[i]
            if DATE.search(line) and not (APPLY.search(line) or MATERIAL.search(line)):
                j = i + 1
                while j < len(parts) and not DATE.search(parts[j]):
                    line += "，" + parts[j]
                    j += 1
                i = j
            else:
                i += 1
            yield line


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def stable_id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def notice_identity(url: str) -> str:
    """只规范化已知 CMS 的同文章分类别名，不猜测不同文章属于同一批次。"""
    parts = urlsplit(url)
    article = re.fullmatch(r"/(?:[^/]+/)*c\d+a(\d+)/page\.(?:htm|psp)", parts.path)
    path = f"/article/{article[1]}" if article else parts.path
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def parse_time(raw: str, season: int = 2026, source_id: str | None = None) -> TimePoint:
    normalized = re.sub(r"(?<=\d)[ \t]+(?=\d)", "", raw)
    match = DATE.search(normalized)
    if not match:
        return TimePoint(raw=raw, sourceId=source_id)
    if not match["year"] and match["separator"] != "月":
        # 缺少年份的数字短横线更常见于附件编号和 URL hash，不据此认定日期。
        return TimePoint(raw=raw, sourceId=source_id)
    year = int(match["year"] or season)
    month, day = int(match["month"]), int(match["day"])
    try:
        if match["hour"] is None:
            value = datetime(year, month, day).date().isoformat()
            return TimePoint(value=value, precision="date", raw=raw, sourceId=source_id)
        hour = int(match["hour"])
        minute = int(match["minute"] or match["zhminute"] or "0")
        if match["period"] in {"下午", "晚上", "中午"} and hour < 12:
            hour += 12
        if hour == 24 and minute != 0:
            raise ValueError("24点之后的分钟无效")
        value = datetime(year, month, day, hour % 24, minute, tzinfo=TZ)
        if hour == 24:
            value += timedelta(days=1)
        return TimePoint(value=value.isoformat(), precision="datetime", raw=raw, sourceId=source_id)
    except ValueError:
        return TimePoint(raw=raw, sourceId=source_id)


def _points(line: str, season: int, source_id: str) -> list[TimePoint]:
    # 补全“9月1日至10日”的省略月份，避免将10日丢失。
    line = re.sub(
        r"(\d{1,2})月(\d{1,2})日(\s*(?:至|到|—|－|-)\s*)(\d{1,2})日",
        lambda m: f"{m[1]}月{m[2]}日{m[3]}{m[1]}月{m[4]}日",
        line,
    )
    line = re.sub(r"https?://\S+", "", line)
    # 带时刻的同月区间，例如“9月1日09:00-11日17:00”。
    line = re.sub(
        r"(\d{1,2})月(\d{1,2}日[^\n。；;，,]*?)(\s*(?:至|到|—|―|－|~|～|-)\s*)(\d{1,2})日",
        lambda m: f"{m[1]}月{m[2]}{m[3]}{m[1]}月{m[4]}日",
        line,
    )
    return [
        point
        for match in DATE.finditer(line)
        if (point := parse_time(match[0], season, source_id)).value is not None
    ]


def _unique(points: list[TimePoint], source_id: str) -> tuple[TimePoint, bool]:
    valid = {p.value: p for p in points if p.value is not None}
    if len(valid) == 1:
        return next(iter(valid.values())), False
    return TimePoint(sourceId=source_id), len(valid) > 1


def _scope_text(title: str, text: str, source: SourceConfig, unit: Unit) -> str | None:
    scope = source.scope.get(unit.id) if isinstance(source.scope, dict) else source.scope
    if scope:
        match = re.search(scope, text, flags=re.S)
        return (match[1] if match.lastindex else match[0]) if match else None
    if source.noticeScope == "unit" or (source.noticeScope == "auto" and source.unitId == unit.id):
        return text
    # 校级栏目可以转载学院专属通知；必须由通知标题明确对应培养单位。
    compact_name = re.sub(r"\s+", "", unit.name)
    if compact_name in re.sub(r"\s+", "", title):
        return text
    # 名录/联系方式里出现学院不能证明整校报名时间适用于学院。
    paragraphs = [
        line
        for line in re.split(r"[\n。；;]+", text)
        if compact_name in re.sub(r"\s+", "", line)
        and (APPLY.search(line) or MATERIAL.search(line))
        and (DATE.search(line) or _availability(line) == "open")
    ]
    return "\n".join(paragraphs) or None


def _availability(text: str) -> str:
    for sentence in re.split(r"[\n。；;]+", text):
        # 取消某申请人的资格不是取消该批项目；条件句也不能作为既成事实。
        if re.search(r"逾期|未提交|未完成|不符合|不满足|若|如果|否则|取消.{0,12}资格", sentence):
            continue
        if re.search(
            r"取消.{0,15}(?:报名|预推免)|停止.{0,8}报名|(?:报名|预推免).{0,8}取消", sentence
        ):
            return "cancelled"
    for sentence in re.split(r"[\n。；;]+", text):
        if MATERIAL.search(sentence) or re.search(r"咨询|另行通知", sentence):
            continue
        if re.search(
            r"即日起.{0,20}(?:报名|预申请)|(?:报名|预申请)(?:时间)?[:：\s]*(?:自)?即日起|(?:报名|预申请).{0,8}(?:现已(?:开放|开启)|已开始)|现已(?:开放|开启).{0,8}(?:报名|预申请)|开始接受.{0,8}(?:报名|预申请)",
            sentence,
        ):
            return "open"
    return "announced"


def parse_notice(
    title: str,
    text: str,
    source: SourceConfig,
    unit: Unit,
    *,
    season: int = 2026,
    year: int = 2027,
    timestamp: str | None = None,
) -> Opportunity | None:
    combined = title + "\n" + text
    if re.search(r"夏令营|科学营|硕博连读", title) and not (
        PRE.search(title) and MASTER.search(title)
    ):
        return None
    explicit_pre = bool(
        source.preAdmissionEvidence and re.search(source.preAdmissionEvidence, combined)
    )
    if not PRE.search(title) and not PRE.search(text[:1000]) and not explicit_pre:
        return None
    if re.search(r"仅.{0,6}(?:直博|博士)|只.{0,6}(?:直博|博士)", combined):
        return None
    if PHD.search(title) and not MASTER.search(title) and not MASTER.search(text):
        return None
    title_year = re.search(r"(20\d{2})\s*(?:年|级)", title)
    if title_year and int(title_year[1]) not in {season, year}:
        return None
    # “2026年硕士招生”指入学年；2026年秋季开展2027级报名则必须有当季证据。
    if str(year) not in combined and str(season) not in text:
        return None
    if re.search(rf"{season - 1}年\s*\d{{1,2}}月", text) and str(year) not in combined:
        return None
    scoped = _scope_text(title, text, source, unit)
    if not scoped:
        return None
    scoped = re.sub(r"(?<=\d)\s*\n\s*(?=[年月日:：\d])", "", scoped)
    scoped = re.sub(r"(?<=[年月日时:：])\s*\n\s*(?=\d)", "", scoped)
    scoped = re.sub(r"(?<=\d)[ \t]+(?=\d)", "", scoped)
    scoped = re.sub(r"(?<=[\u4e00-\u9fff])[ \t]+(?=[\u4e00-\u9fff])", "", scoped)
    starts, ends, materials = [], [], []
    evidence_lines: list[str] = []
    assessment: list[str] = []
    mixed = False
    previous_label = ""
    degree_scope: str | None = None
    stage_scope = "pre_admission"
    master_lines: list[str] = []
    for line in _clauses(scoped):
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[一二三四五六七八九十]+[、．.]", line):
            degree_scope = None
            previous_label = ""
        elif re.match(r"^\d+[.．、]\s*[^\d]", line):
            previous_label = ""
        if re.search(r"报名截止(?:后|之后)|申请截止(?:后|之后)|复试名单|资格名单|名单公布", line):
            continue
        if (
            re.search(
                r"正式推免|全国.{0,15}(?:系统|平台)|教育部.{0,15}系统|研招网|推免服务系统", line
            )
            and not PRE.search(line)
            and not (
                re.search(r"资格.*备案|备案.*资格|获得.*资格", line)
                and not DATE.search(line)
                and not re.search(r"报名|填报|填志愿|录取|确认", line)
            )
        ):
            stage_scope = "formal"
            previous_label = ""
            continue
        if re.search(r"预推免|预报名|预接收|预选拔|预申请", line):
            stage_scope = "pre_admission"
        if stage_scope == "formal":
            continue
        if PHD.search(line):
            if MASTER.search(line) and DATE.search(line):
                mixed = True
            if not MASTER.search(line) and len(line) < 80:
                degree_scope = "doctorate"
            previous_label = ""
            # 只要一句同时出现硕博和时间，宁可待人工分段，不猜测时间的归属。
            continue
        if MASTER.search(line):
            degree_scope = "master"
            previous_label = ""
        if degree_scope == "doctorate":
            continue
        master_lines.append(line)
        dates = _points(line, season, source.id)
        if dates and re.search(r"建议|最好|尽量", line):
            # 建议提前报名不等于系统硬截止，保留原句供人工查看。
            evidence_lines.append(line)
            previous_label = ""
            continue
        if not dates:
            if len(line) < 70 and (APPLY.search(line) or MATERIAL.search(line)):
                previous_label = line
            else:
                previous_label = ""
            continue
        context = ("" if APPLICATION_LABEL.search(line) else previous_label) + " " + line
        previous_label = ""
        application_action = bool(
            APPLY.search(context)
            and (
                APPLICATION_LABEL.search(context)
                or re.search(
                    r"(?:登录|填报|完成|提交).{0,35}(?:报名|申请)|报名.{0,4}(?:及|和|与).*材料",
                    context,
                )
            )
        )
        if MATERIAL.search(context) and not application_action:
            if _has_end(context):
                materials.append(dates[-1])
                evidence_lines.append(line)
            continue
        if re.search(r"考核|复试|面试", context) and not APPLY.search(context):
            assessment.append(line)
            continue
        if not APPLY.search(context):
            continue
        if len(dates) >= 2 and re.search(RANGE, line):
            starts.append(dates[0])
            ends.append(dates[-1])
        elif _has_end(context) or re.search(r"即日起\s*(?:至|到|—|―|－|-)", context):
            ends.append(dates[-1])
        elif re.search(r"开始|开放|启动|起", context):
            starts.append(dates[0])
        evidence_lines.append(line)
    start, start_conflict = _unique(starts, source.id)
    end, end_conflict = _unique(ends, source.id)
    material, material_conflict = _unique(materials, source.id)
    if any(
        point.value and not point.value.startswith(str(season)) for point in (start, end, material)
    ):
        return None
    batch_match = re.search(
        r"第[一二三四五六七八九十\d]+(?:批|轮)(?:次)?|补充批次|补充报名|补报名", title
    )
    batch = source.batch or (batch_match[0] if batch_match else "首批")
    degrees = []
    master_text = "\n".join(master_lines)
    if re.search(r"学术(?:型|学位)|学硕", master_text):
        degrees.append("academic")
    if re.search(r"专业(?:型|学位)|专硕", master_text):
        degrees.append("professional")
    verified = bool(
        (end.value or material.value)
        and not (start_conflict or end_conflict or material_conflict or mixed)
    )
    timestamp = timestamp or now_iso()
    excerpt = "；".join(evidence_lines)[:1800] or scoped[:700]
    notes = []
    if mixed:
        notes.append("硕博时间混合表述，需人工核验硕士适用范围。")
    if start_conflict or end_conflict or material_conflict:
        notes.append("发现多个不同时间，需核验是否属于不同项目或批次。")
    if not degrees:
        notes.append("公告未明确学硕／专硕类型。")
    return Opportunity(
        id="opp-"
        + stable_id(source.schoolId, unit.id, str(year), batch, source.identityKey or source.url),
        schoolId=source.schoolId,
        unitId=unit.id,
        title=title,
        year=year,
        season=season,
        batch=batch,
        degrees=degrees,
        disciplines=unit.disciplines,
        relevance=unit.relevance,
        applicationStart=start,
        applicationEnd=end,
        materialsEnd=material if materials else None,
        assessment="；".join(assessment),
        noticeUrl=source.url,
        sourceIds=[source.id],
        evidence=[Evidence(sourceId=source.id, url=source.url, title=title, excerpt=excerpt)],
        verification="verified" if verified else "pending",
        availability=_availability(master_text),
        firstSeenAt=timestamp,
        updatedAt=timestamp,
        notes="".join(notes),
    )
