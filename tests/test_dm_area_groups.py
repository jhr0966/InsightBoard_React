"""데이터 관리 area 2 그룹 segmented 재편 (PR-A)."""
from __future__ import annotations

import pytest

from ui import data_management_v2 as dm


# ── 상수/라우팅 ──────────────────────────────────────────

def test_groups_constants():
    assert dm._DM_GROUPS == ("news", "tasks")
    assert "news" in dm._DM_GROUP_TABS and "tasks" in dm._DM_GROUP_TABS
    # 모든 sub-탭이 한 그룹에 정확히 한 번씩
    all_tabs = sum(dm._DM_GROUP_TABS.values(), ())
    assert sorted(all_tabs) == sorted(dm._DM_TABS)


def test_dm_group_of_classifies_tabs():
    assert dm._dm_group_of("jobs") == "news"
    assert dm._dm_group_of("kw") == "news"
    assert dm._dm_group_of("src") == "news"
    assert dm._dm_group_of("task") == "tasks"
    assert dm._dm_group_of("unknown") == "news"


# ── _dm_resolve_group_and_tab — URL 호환 ───────────────

def test_resolve_legacy_url_with_only_dm_tab():
    """기존 ?dm_tab=task 만 있는 URL → tasks 그룹으로 자동 추론."""
    assert dm._dm_resolve_group_and_tab(None, "task") == ("tasks", "task")
    assert dm._dm_resolve_group_and_tab(None, "kw") == ("news", "kw")
    assert dm._dm_resolve_group_and_tab(None, "jobs") == ("news", "jobs")
    assert dm._dm_resolve_group_and_tab(None, "src") == ("news", "src")


def test_resolve_defaults_when_both_missing():
    assert dm._dm_resolve_group_and_tab(None, None) == ("news", "jobs")
    assert dm._dm_resolve_group_and_tab("", "") == ("news", "jobs")


def test_resolve_grp_only_uses_group_default_tab():
    assert dm._dm_resolve_group_and_tab("tasks", None) == ("tasks", "task")
    assert dm._dm_resolve_group_and_tab("news", None) == ("news", "jobs")


def test_resolve_invalid_grp_or_tab_is_ignored():
    # 잘못된 grp → 무시
    assert dm._dm_resolve_group_and_tab("nope", "kw") == ("news", "kw")
    # 잘못된 tab → 빈 취급
    assert dm._dm_resolve_group_and_tab("tasks", "nope") == ("tasks", "task")


def test_resolve_grp_corrected_to_match_tab():
    """grp 과 tab 이 어긋나면 tab 의 그룹이 진실."""
    assert dm._dm_resolve_group_and_tab("news", "task") == ("tasks", "task")
    assert dm._dm_resolve_group_and_tab("tasks", "kw") == ("news", "kw")


# ── _dm_tab_href — 그룹 정보 자동 포함 ─────────────────

def test_dm_tab_href_jobs_default_is_clean():
    """news 그룹 + jobs 탭은 둘 다 생략 (가장 깔끔한 URL)."""
    href = dm._dm_tab_href("jobs")
    assert "dm_tab=" not in href
    assert "dm_grp=" not in href


def test_dm_tab_href_includes_dm_grp_for_non_default():
    """jobs 가 아닌 탭은 dm_grp 와 dm_tab 둘 다 명시."""
    href_kw = dm._dm_tab_href("kw")
    assert "dm_grp=news" in href_kw
    assert "dm_tab=kw" in href_kw

    href_task = dm._dm_tab_href("task")
    assert "dm_grp=tasks" in href_task
    # task 는 tasks 그룹의 기본 탭이므로 dm_tab 생략
    assert "dm_tab=" not in href_task

    href_src = dm._dm_tab_href("src")
    assert "dm_grp=news" in href_src
    assert "dm_tab=src" in href_src


# ── _dm_group_href / _dm_groups_html ───────────────────

def test_dm_group_href_points_to_group_default_tab():
    assert dm._dm_group_href("news") == dm._dm_tab_href("jobs")
    assert dm._dm_group_href("tasks") == dm._dm_tab_href("task")


def test_dm_groups_html_renders_both_groups_and_marks_active():
    html_news = dm._dm_groups_html("news")
    assert "dm-groups" in html_news
    assert "📰 뉴스 데이터" in html_news
    assert "📋 작업 데이터" in html_news
    # news 가 active
    assert 'class="dm-group dm-group-active"' in html_news
    assert html_news.count("dm-group-active") == 1

    html_tasks = dm._dm_groups_html("tasks")
    assert html_tasks.count("dm-group-active") == 1
    # tasks 위치는 두 번째 그룹 — active 가 거기에
    idx_active = html_tasks.find("dm-group-active")
    idx_news_label = html_tasks.find("📰")
    idx_tasks_label = html_tasks.find("📋")
    assert idx_news_label < idx_active < idx_tasks_label or idx_active > idx_tasks_label


def test_dm_groups_html_anchors_have_href_and_role():
    html = dm._dm_groups_html("news")
    # role=tablist + role=tab
    assert 'role="tablist"' in html
    assert html.count('role="tab"') == 2
    # aria-selected 정확
    assert 'aria-selected="true"' in html
    assert 'aria-selected="false"' in html


# ── _dm_tabs_html — 그룹별 sub-탭만 표시 ──────────────

def test_dm_tabs_html_news_group_shows_only_news_tabs():
    """news 그룹에서는 jobs/kw/src 만, task 는 표시하지 않음."""
    html = dm._dm_tabs_html("jobs", {"active_sources": 1, "today_count": 1})
    assert "수집잡 · 뉴스 라이브러리" in html
    assert "키워드" in html
    assert "출처 설정" in html
    assert "작업 정의" not in html


def test_dm_tabs_html_tasks_group_shows_only_task_tab():
    """tasks 그룹에서는 task 만."""
    html = dm._dm_tabs_html("task", {"active_sources": 0, "today_count": 0})
    assert "작업 정의" in html
    assert "수집잡 · 뉴스 라이브러리" not in html
    assert "키워드" not in html
    assert "출처 설정" not in html


def test_dm_tabs_html_marks_active_within_group():
    html = dm._dm_tabs_html("kw", {"active_sources": 1, "today_count": 1})
    # 한 탭만 dm-tab-active
    assert html.count("dm-tab-active") == 1
    # kw 가 활성
    assert 'aria-current="true"' in html


def test_dm_tabs_html_invalid_tab_falls_back_to_jobs():
    html = dm._dm_tabs_html("nuke", {"active_sources": 0, "today_count": 0})
    # jobs 가 active (news 그룹 기본)
    assert "수집잡 · 뉴스 라이브러리" in html
    assert "작업 정의" not in html  # tasks 그룹 탭 노출 X
