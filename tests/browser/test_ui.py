"""验证完整用户流程与时区边界。"""

import copy
import re

from playwright.sync_api import expect


def test_material_only_deadline_in_list_detail_quick_filter_and_calendar(page, catalog):
    data = copy.deepcopy(catalog)
    item = data["opportunities"][0]
    item.update(title="仅材料时限", batch="仅材料时限", availability="announced")
    item["applicationStart"] = {
        "value": None,
        "precision": "unknown",
        "raw": "开放时间未知",
        "sourceId": "fixture-source",
    }
    item["applicationEnd"] = {
        "value": None,
        "precision": "unknown",
        "raw": "未单列网上报名截止",
        "sourceId": "fixture-source",
    }
    item["materialsEnd"] = {
        "value": "2026-09-09T17:00:00+08:00",
        "precision": "datetime",
        "raw": "9月9日17:00前提交材料",
        "sourceId": "fixture-source",
    }
    page.route("**/data/catalog.json", lambda route: route.fulfill(json=data))
    page.reload(wait_until="networkidle")
    page.get_by_test_id("search-input").fill("仅材料时限")
    row = page.get_by_test_id("opportunity-row")
    expect(row).to_contain_text("材料提交截止")
    expect(row).to_contain_text("09/09 17:00")
    expect(row).not_to_contain_text("报名中")
    row.get_by_role("button").first.click()
    expect(page.locator(".deadline-hero")).to_contain_text("材料提交截止")
    page.keyboard.press("Escape")
    page.get_by_test_id("tab-calendar").click()
    expect(page.locator(".calendar-event")).to_contain_text("材料")


def test_search_url_restore_and_favorite(page):
    search = page.get_by_test_id("search-input")
    search.fill("批次1")
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)
    expect(page).to_have_url(re.compile(".*query=.*"))
    page.get_by_test_id("favorite-toggle").click()
    page.reload(wait_until="networkidle")
    expect(search).to_have_value("批次1")
    expect(page.get_by_test_id("favorite-toggle")).to_have_attribute("aria-pressed", "true")
    search.fill("")
    page.get_by_role("button", name=re.compile("只看我的收藏")).click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)
    expect(page.get_by_test_id("opportunity-row")).to_contain_text("批次1")


def test_beijing_dates_and_separate_material_deadline(page):
    page.get_by_test_id("search-input").fill("批次1")
    page.get_by_test_id("opportunity-row").get_by_role("button").first.click()
    detail = page.get_by_test_id("detail-panel")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("09/10 12:00")
    expect(detail).to_contain_text("09/11 12:00")
    expect(detail.locator(".detail-footer").get_by_role("link").first).to_have_attribute(
        "href", "https://www.zju.edu.cn/"
    )
    page.keyboard.press("Escape")
    expect(detail).not_to_be_visible()
    page.get_by_test_id("search-input").fill("仅日期")
    row = page.get_by_test_id("opportunity-row")
    expect(row).to_contain_text("今日截止")
    expect(row).to_contain_text("具体时刻未公布")
    expect(row.locator(".deadline-block")).not_to_contain_text("小时")


def test_calendar_expands_all_projects_and_unknown_deadlines(page):
    page.get_by_test_id("tab-calendar").click()
    expect(page.get_by_test_id("calendar-more")).to_have_count(1)
    page.get_by_test_id("calendar-more").click()
    expect(page.locator(".calendar-day-details").get_by_test_id("opportunity-row")).to_have_count(6)
    page.get_by_role("button", name=re.compile("截止待确认")).click()
    expect(page.locator(".calendar-day-details").get_by_test_id("opportunity-row")).to_have_count(1)
    expect(page.locator(".calendar-day-details")).to_contain_text("未知截止批次")


def test_coverage_contains_all_68_institutions_and_explicit_gaps(page):
    expect(page.get_by_test_id("coverage-progress")).to_contain_text("已发现公告 1 / 68 个机构")
    expect(page.get_by_test_id("coverage-progress")).to_contain_text("公告与学院盘点仍在补充")
    page.get_by_test_id("tab-coverage").click()
    expect(page.locator("details.coverage-school")).to_have_count(68)
    page.get_by_label("筛选覆盖状态").select_option("published")
    expect(page.locator("details.coverage-school")).to_have_count(1)
    summary = page.locator("details.coverage-school summary")
    expect(summary).to_contain_text("已发现公告")
    expect(summary).to_contain_text("盘点待完成")
    expect(summary).to_contain_text("来源访问异常")
    page.get_by_label("筛选覆盖状态").select_option("")
    page.get_by_test_id("search-input").fill("浙江大学")
    expect(page.locator("details.coverage-school")).to_have_count(1)
    page.locator("details.coverage-school summary").click()
    expect(page.locator(".coverage-content")).to_contain_text("不代表")
    expect(page.locator(".coverage-content")).to_contain_text("计算机学院测试培养单位")


def test_school_without_announcement_explains_inventory_and_opens_coverage(page):
    page.locator(".desktop-sidebar").get_by_label("学校").select_option("nudt")
    empty = page.get_by_test_id("list-empty-state")
    expect(empty).to_contain_text("国防科技大学已在学校目录中")
    expect(empty).to_contain_text("已记录 0 个培养单位")
    expect(empty).to_contain_text("尚未配置可检查的官方来源，待补充")
    expect(empty).to_contain_text("这不代表报名未开始，也不代表没有相关招生")
    page.get_by_test_id("search-input").fill("另一个筛选条件")
    empty.get_by_role("button", name="查看该校覆盖情况").click()
    expect(page.locator("details.coverage-school")).to_have_count(1)
    expect(page.locator("details.coverage-school")).to_contain_text("国防科技大学")
    expect(page.get_by_test_id("search-input")).to_have_value("")
    page.get_by_test_id("coverage-progress").get_by_role("button").click()
    expect(page.locator("details.coverage-school")).to_have_count(68)


def test_filtered_empty_state_does_not_claim_school_has_no_announcement(page):
    page.locator(".desktop-sidebar").get_by_label("学校").select_option("zju")
    page.get_by_test_id("search-input").fill("不存在的批次")
    empty = page.get_by_test_id("list-empty-state")
    expect(empty).to_contain_text("没有符合条件的报名信息")
    expect(empty).not_to_contain_text("尚未收录该校")


def test_single_failed_source_stays_stale_when_other_source_succeeds(page):
    page.get_by_test_id("search-input").fill("单源失效")
    expect(page.get_by_test_id("opportunity-row")).to_contain_text("来源待更新")
    page.get_by_test_id("search-input").fill("批次1")
    expect(page.get_by_test_id("opportunity-row")).not_to_contain_text("来源待更新")


def test_mobile_filter_drawer_and_no_horizontal_overflow(page):
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_test_id("mobile-filter-toggle").click()
    drawer = page.get_by_role("dialog", name="筛选条件")
    expect(drawer).to_be_visible()
    drawer.get_by_test_id("filter-status").select_option("closed")
    drawer.get_by_role("button", name="查看筛选结果").click()
    expect(drawer).not_to_be_visible()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)
    expect(page.get_by_test_id("opportunity-row")).to_contain_text("历史批次")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        "手机页面横向溢出"
    )


def test_broken_local_storage_does_not_break_rendering(page):
    page.evaluate("localStorage.setItem('zj-ddl-favorites', '{invalid json')")
    page.reload(wait_until="networkidle")
    expect(page.get_by_test_id("tab-list")).to_be_visible()
    expect(page.get_by_test_id("opportunity-row").first).to_be_visible()


def test_multiselect_tags_formats_counts_and_url_restore(page):
    panel = page.locator(".desktop-sidebar")
    tags = panel.get_by_test_id("tag-filter")
    formats = panel.get_by_test_id("format-filter")
    expect(tags.locator(".filter-chips button")).to_have_count(10)
    expect(tags.get_by_role("button", name="港三，0 个项目")).to_be_disabled()
    tags.get_by_role("button", name="985，9 个项目").click()
    tags.get_by_role("button", name="联培，1 个项目").click()
    formats.get_by_role("button", name="线上，1 个项目").click()
    formats.get_by_role("button", name="混合，1 个项目").click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(2)
    expect(tags.get_by_role("button", name="985，9 个项目")).to_be_visible()
    tags.get_by_role("button", name="985，9 个项目").click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(0)
    formats.get_by_role("button", name="线下，1 个项目").click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)
    expect(page.get_by_test_id("opportunity-row")).to_contain_text("线下考核")
    page.reload(wait_until="networkidle")
    expect(tags.get_by_role("button", name="联培，1 个项目")).to_have_attribute(
        "aria-pressed", "true"
    )
    for label in ["线上", "线下", "混合"]:
        expect(formats.get_by_role("button", name=f"{label}，1 个项目")).to_have_attribute(
            "aria-pressed", "true"
        )
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)
    panel.get_by_test_id("status-chip-filter").get_by_role(
        "button", name="已结束，1 个项目"
    ).click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(0)
    panel.get_by_test_id("status-chip-filter").get_by_role(
        "button", name="已结束，1 个项目"
    ).click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(1)


def test_mobile_format_unknown_and_selected_zero_tag_can_be_cleared(page):
    page.goto(page.url.split("?")[0] + "?tags=港三", wait_until="networkidle")
    page.set_viewport_size({"width": 390, "height": 844})
    page.get_by_test_id("mobile-filter-toggle").click()
    drawer = page.get_by_role("dialog", name="筛选条件")
    zero_tag = drawer.get_by_role("button", name="港三，0 个项目")
    expect(zero_tag).to_be_enabled()
    expect(zero_tag).to_have_attribute("aria-pressed", "true")
    zero_tag.click()
    expect(zero_tag).to_be_disabled()
    drawer.get_by_role("button", name="未核验，6 个项目").click()
    drawer.get_by_role("button", name="查看筛选结果").click()
    expect(page.get_by_test_id("opportunity-row")).to_have_count(5)
    expect(page.get_by_test_id("opportunity-row").first).to_contain_text("形式未核验")
    page.reload(wait_until="networkidle")
    page.get_by_test_id("mobile-filter-toggle").click()
    expect(drawer.get_by_role("button", name="未核验，6 个项目")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
        "手机页面横向溢出"
    )
