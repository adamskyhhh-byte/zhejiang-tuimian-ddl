"""使用招生通知的表达方式验证时间和招生范围边界。"""

from tuimian.models import SourceConfig, Unit
from tuimian.parser import parse_notice, parse_time


def unit():
    return Unit(
        id="s-ai",
        schoolId="s",
        name="人工智能学院",
        disciplines=["AI"],
        relevance="core",
        directoryUrl="https://s.edu.cn",
        admissionUrl="https://s.edu.cn",
    )


def source():
    return SourceConfig(
        id="n",
        schoolId="s",
        unitId="s-ai",
        kind="notice",
        url="https://s.edu.cn/notice/1",
        title="2027年硕士预推免报名通知",
    )


def test_date_precision_and_midnight():
    assert parse_time("9月7日24:00", 2026, "n").value == "2026-09-08T00:00:00+08:00"
    result = parse_time("9月9日", 2026, "n")
    assert result.value == "2026-09-09"
    assert result.precision == "date"
    assert parse_time("9月31日", 2026, "n").precision == "unknown"


def test_application_and_materials_are_separate():
    result = parse_notice(
        "2027年硕士预推免报名通知",
        "硕士研究生预推免。\n报名时间：2026年9月1日9:00至9月10日17:00。\n材料提交截止时间：9月12日。",
        source(),
        unit(),
    )
    assert result is not None
    assert result.applicationStart.value == "2026-09-01T09:00:00+08:00"
    assert result.applicationEnd.value == "2026-09-10T17:00:00+08:00"
    assert result.materialsEnd.value == "2026-09-12"


def test_mixed_master_doctorate_never_borrows_doctorate_deadline():
    result = parse_notice(
        "2027年硕士、直博预推免报名",
        "硕士研究生预推免报名安排另行通知。\n直博生报名截止时间：2026年9月8日。",
        source(),
        unit(),
    )
    assert result is not None
    assert result.applicationEnd.value is None
    assert result.verification == "pending"
    assert result.availability == "announced"


def test_excludes_camp_formal_and_doctorate_only():
    for title in ["2027年直博生预报名通知", "2026年优秀大学生夏令营", "2027年全国正式推免系统报名"]:
        assert parse_notice(title, "报名截止9月10日", source(), unit()) is None


def test_unrelated_year_and_ambiguous_deadlines_are_not_verified():
    assert parse_notice("2026年硕士预推免通知", "2025年9月报名", source(), unit()) is None
    result = parse_notice(
        "2027年硕士预推免",
        "硕士预推免报名截止9月8日。\n硕士预推免报名截止9月10日。",
        source(),
        unit(),
    )
    assert result is not None
    assert result.applicationEnd.value is None
    assert result.verification == "pending"


def test_no_inference_of_open_from_missing_start():
    result = parse_notice("2027年硕士预推免", "硕士预推免报名截止9月9日。", source(), unit())
    assert result.availability == "announced"
    assert result.applicationStart.precision == "unknown"


def test_formal_admission_dates_are_excluded_and_pdf_wrapping_is_joined():
    result = parse_notice(
        "2027年硕士预推免",
        "硕士预推免报名截止9月\n9日\n17:00。\n全国推免服务系统报名截止9月28日。",
        source(),
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-09T17:00:00+08:00"


def test_attachment_numbers_urls_and_post_deadline_results_are_not_deadlines():
    for text in [
        "硕士预推免报名申请材料1-5应在截止前提交。",
        "硕士预推免报名截止详见附件https://school.edu.cn/5-09/list.htm",
        "硕士预推免报名截止后复试名单于9月4日前公布。",
    ]:
        result = parse_notice("2027年硕士预推免", text, source(), unit())
        assert result.applicationEnd.value is None
        assert result.verification == "pending"
    assert parse_time("2026-09-10", 2026, "n").value == "2026-09-10"
    assert parse_time("1-5", 2026, "n").value is None


def test_conditional_disqualification_does_not_cancel_the_opportunity():
    result = parse_notice(
        "2027年硕士预推免",
        "硕士学术学位预推免。报名时间2026年9月1日至9月10日。逾期未提交材料者取消报名资格。",
        source(),
        unit(),
    )
    assert result.availability != "cancelled"
    assert result.verification == "verified"


def test_doctorate_section_scope_survives_newlines():
    result = parse_notice(
        "2027年硕士、直博预推免",
        "硕士学术学位预推免。硕士报名安排另行通知。\n（二）直博生报名\n报名截止时间：2026年9月10日。",
        source(),
        unit(),
    )
    assert result.applicationEnd.value is None
    assert result.verification == "pending"
    result = parse_notice(
        "2027年硕士、直博预推免",
        "（一）直博生报名\n报名截止时间：2026年9月10日。\n（二）硕士研究生报名\n报名截止时间：2026年9月12日。",
        source(),
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-12"


def test_consultation_and_material_collection_do_not_imply_registration_is_open():
    for action in ["即日起接受政策咨询", "即日起提交报名材料"]:
        result = parse_notice(
            "2027年硕士预推免",
            f"硕士学术学位预推免。报名截止9月10日。报名开始时间另行通知。{action}。",
            source(),
            unit(),
        )
        assert result.availability == "announced"


def test_formal_stage_scope_is_not_borrowed_by_separate_application_sentence():
    result = parse_notice(
        "2027年接收推荐免试硕士研究生申请通知",
        "本通知为全国正式推免阶段报名安排。硕士学术学位申请时间：2026年9月28日至9月30日。",
        source(),
        unit(),
    )
    assert result is None or result.applicationEnd.value is None
    result = parse_notice(
        "2027年硕士预推免通知",
        "硕士预推免报名截止9月10日。全国正式推免阶段报名安排。申请时间：9月28日至9月30日。",
        source(),
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-10"


def test_bit_real_notice_has_no_master_pre_registration_deadline():
    text = """北京理工大学人工智能学院2027年推免招生办法
三、申请流程
1. 完成学院内预报名
即日起有意愿申请者联系相关导师，向导师提交申请材料。
2. 提交材料
身份证复印件
英语成绩单
3. 发送复试通知
具体时间地点以导师邮件通知为准。
4. 学生参加复试
通过初审的同学将在 9 月 2 0 日前完成复试。
5. 推免服务系统报名
系统开放时间为 9 月 2 1 日 -10 月 20 日。
"""
    result = parse_notice("2027年接收推荐免试硕士研究生申请通知", text, source(), unit())
    assert result.applicationEnd.value is None
    assert result.materialsEnd is None
    assert "20" in result.assessment
    assert result.verification == "pending"
    assert parse_time("9 月 2 0 日").value == "2026-09-20"
    assert parse_time("9月32日").value is None


def test_school_system_date_and_unit_directory_do_not_prove_unit_deadline():
    config = source().model_copy(update={"noticeScope": "school"})
    result = parse_notice(
        "2027年硕士预推免通知",
        "硕士预报名时间9月4日至9月20日，具体时间以各学院公布为准。\n"
        "招生单位及联系方式\n人工智能学院\n085410人工智能\n电话12345678",
        config,
        unit(),
    )
    assert result is None
    result = parse_notice(
        "2027年硕士预推免通知",
        "硕士预报名系统截止9月20日。\n人工智能学院硕士预报名截止9月15日。",
        config,
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-15"


def test_weekday_parentheses_and_spaced_minutes_preserve_exact_time():
    assert parse_time("9月15日（周二）12时").value == "2026-09-15T12:00:00+08:00"
    assert parse_time("9月10日 09 ： 00").value == "2026-09-10T09:00:00+08:00"
    result = parse_notice(
        "2027年硕士预推免报名通知",
        "硕士预报名时间2026年9月9日（周三）12时至9月15日（周二）12时。",
        source(),
        unit(),
    )
    assert result.applicationStart.value == "2026-09-09T12:00:00+08:00"
    assert result.applicationEnd.value == "2026-09-15T12:00:00+08:00"
    result = parse_notice(
        "人工智能学院2027年硕士预推免通知",
        "硕士预报名截止9月15日。",
        source().model_copy(update={"noticeScope": "school"}),
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-15"


def test_science_camp_and_master_to_doctor_transition_are_not_masters_pre_admission():
    for title in ["2027年暑期科学营报名通知", "2027年秋季批次硕博连读报名通知"]:
        assert (
            parse_notice(title, "硕士预推免相关通知。报名截止9月10日。", source(), unit()) is None
        )
    result = parse_notice(
        "2027年硕士预推免及硕博连读通知",
        "硕士预报名截止9月10日。\n（二）硕博连读申请\n报名截止9月20日。",
        source(),
        unit(),
    )
    assert result.applicationEnd.value == "2026-09-10"
    assert (
        parse_notice(
            "2027年硕士预推免补充报名通知", "硕士预报名截止9月6日。", source(), unit()
        ).batch
        == "补充报名"
    )


def test_school_link_directory_is_discovery_evidence_without_a_unit_opportunity():
    result = parse_notice(
        "2027年各院系硕士预推免报名通知（陆续更新）",
        "欢迎查看各院系报名通知。\n人工智能学院硕士预报名通知 点击查看\n法学院硕士预报名通知",
        source().model_copy(update={"noticeScope": "school"}),
        unit(),
    )
    assert result is None
