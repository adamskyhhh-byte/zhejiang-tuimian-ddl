"""国防科技大学2027计算机第二轮真实页面结构和公开时间片段回归。"""

from tuimian.crawler import discover
from tuimian.fetch import extract_page
from tuimian.models import SourceConfig, Unit
from tuimian.parser import parse_notice


def nudt_source(kind="listing"):
    return SourceConfig(
        id="nudt-cs",
        schoolId="nudt",
        unitId="nudt-cs",
        url="https://yjszs.nudt.edu.cn/pubweb/homePageList/newRecruitStudents.view?keyId=23",
        title="计算机学院公告",
        kind=kind,
        adapter="nudt_admissions",
        includePatterns=["(?=.*计算机学院)(?=.*2027)(?=.*(?:推荐免试|推免))"],
    )


def test_nudt_js_pagination_and_old_new_detail_urls_are_canonical():
    html = """<html><ul class="article_list"><li><a href=" /pubweb/homePageList/newDetailed.view?keyId=14937 "><div class="info"><div class="bt">公布计算机学院接收第二轮2027级地方院校推荐免试硕士研究生（含直博生）工作方案</div></div></a></li><li><a href="/pubweb/homePageList/newDetailed.view?keyId=14942"><div class="info"><div class="bt">智能科学学院2027直博生</div></div></a></li></ul><input name="pageNo" value="1"><input name="pageSize" value="10"><input name="totalPages" value="59"><a href="JavaScript:paging('X');">下一页</a></html>"""
    source = nudt_source()
    page = extract_page(html.encode(), "text/html", source)
    discovered = discover(source, page, page_count={})
    assert len(discovered) == 2
    assert discovered[0].url.endswith("/detailed.view?keyId=14937")
    assert "pageNo=2" in discovered[1].url and "state=F" in discovered[1].url
    config = SourceConfig.model_validate(
        source.model_dump()
        | {"url": "https://yjszs.nudt.edu.cn/pubweb/homePageList/newDetailed.view?keyId=14937"}
    )
    assert config.url.endswith("/detailed.view?keyId=14937")


def test_nudt_attachment_page_excludes_related_notices_and_login_captcha():
    source = nudt_source("notice")
    html = """<h1 class="arti_title">计算机学院第二轮2027硕士研究生工作方案</h1><div id="articleContent"><p><a href=" /attached/file/20260904/20260904185822_736.pdf ">计算机学院接收第二轮2027级地方院校推荐免试硕士研究生（含直博生）工作方案</a></p></div><div>验证码 登录</div><a href="/pubweb/homePageList/newDetailed.view?keyId=14942">相关文章：智能科学学院2027直博</a>"""
    page = extract_page(html.encode(), "text/html", source)
    assert len(page.links) == 1
    assert page.links[0]["url"].endswith("20260904185822_736.pdf")
    assert "验证码" not in page.text
    assert "智能科学" not in page.text


def test_nudt_old_detail_selector_excludes_previous_next_and_login():
    source = nudt_source("notice")
    html = """<div class="news-view"><div class="content"><h1>公布计算机学院第二轮2027级硕士研究生工作方案</h1><div class="font"><a href="/attached/file/20260904/20260904185822_736.pdf">第二轮招生工作方案</a></div></div><div class="Previous-page"><div class="font">智能科学学院直博生相关文章</div></div></div><h1>用户登录</h1><div>验证码</div>"""
    page = extract_page(html.encode(), "text/html", source)
    assert len(page.links) == 1
    assert "验证码" not in page.text
    assert "智能科学" not in page.text
    assert "计算机学院" in page.title


def test_nudt_shared_workflow_after_master_doctorate_table_has_master_deadline():
    source = nudt_source("pdf")
    title = "计算机学院接收第二轮2027级地方院校推荐免试硕士研究生（含直博生）工作方案"
    text = """可接收2027级推荐免试硕士研究生、直博生专业如下：
地方
硕士研究生
地方
直博生
一、推免专业及申请条件
地方直博生
申请条件详见学校硕士研究生（含直博生）工作方案。
二、工作流程
（一）推免复试时间
9月15日—17日
（二）推免预报名
报名时间：即日起至9月10日12:00。
（三）推免申请材料提交
在推免预报名同时上传报名系统。
"""
    unit = Unit(
        id="nudt-cs",
        schoolId="nudt",
        name="计算机学院",
        disciplines=["计算机"],
        relevance="core",
        directoryUrl=source.url,
        admissionUrl=source.url,
    )
    parsed = parse_notice(title, text, source, unit)
    assert parsed.batch == "第二轮"
    assert parsed.applicationEnd.value == "2026-09-10T12:00:00+08:00"
    assert parsed.verification == "verified"
    assert parsed.availability == "open"
