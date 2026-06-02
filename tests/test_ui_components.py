from ui.components import (
    action_card,
    action_grid,
    metric_card,
    metric_grid,
    status_card,
    step_guide,
    step_item,
)


def test_metric_card_escapes_text_and_allows_known_tone():
    html = metric_card("<label>", "<7>", caption="cap<script>", icon="<i>", tone="teal")

    assert 'class="metric-card teal"' in html
    assert "&lt;label&gt;" in html
    assert "&lt;7&gt;" in html
    assert "cap&lt;script&gt;" in html
    assert "&lt;i&gt;" in html
    assert "<script>" not in html


def test_unknown_tone_is_not_rendered_as_class():
    html = status_card("Title", "Body", status='bad" onclick="x')

    assert 'onclick' not in html
    assert 'class="status-card"' in html


def test_action_and_metric_grids_wrap_cards():
    cards = [action_card("🔍", "Data", "Collect"), action_card("🤖", "SOLA", "Draft")]
    assert action_grid(cards).startswith('<div class="action-grid">')
    assert action_grid(cards).count('class="action-card"') == 2

    metrics = [metric_card("A", 1), metric_card("B", 2)]
    assert metric_grid(metrics).startswith('<div class="metric-grid">')
    assert metric_grid(metrics).count('class="metric-card"') == 2


def test_step_guide_escapes_and_marks_active_step():
    html = step_guide([step_item(1, "<Pick>", "Body<script>", active=True)])

    assert html.startswith('<div class="step-guide">')
    assert 'class="step-item active"' in html
    assert "&lt;Pick&gt;" in html
    assert "Body&lt;script&gt;" in html
    assert "<script>" not in html


# ── prepare_screen_html: st.html SVG 함정 보정 (전 화면 아이콘/차트) ──

def test_prepare_screen_html_reencodes_broken_data_uri_icon():
    from ui.components import prepare_screen_html
    raw = ('<img src="data:image/svg+xml;utf8,'
           "<svg xmlns='http://x' viewBox='0 0 24 24' fill='#2563EB'></svg>" '" width="11"/>')
    out = prepare_screen_html(raw)
    assert ";utf8," not in out
    assert "data:image/svg+xml," in out
    src = out.split('src="', 1)[1].split('"', 1)[0]
    assert "#" not in src and "<svg" not in src   # '#'(→%23)·'<' 인코딩되어 src 안 잘림
    assert "%23" in src


def test_prepare_screen_html_converts_inline_svg_to_img():
    from ui.components import prepare_screen_html
    raw = ("<div><svg xmlns='http://x' class='db-trend-svg' "
           "style='width:100%;height:60px;'><path d='M0 0'/></svg></div>")
    out = prepare_screen_html(raw)
    assert "<svg" not in out                       # 인라인 svg 제거(st.html sanitize 회피)
    assert '<img src="data:image/svg+xml,' in out
    assert 'class="db-trend-svg"' in out           # class 보존
    assert "height:60px" in out                    # style 보존


def test_prepare_screen_html_noop_without_svg():
    from ui.components import prepare_screen_html
    raw = '<div class="x">hello world</div>'
    assert prepare_screen_html(raw) == raw
