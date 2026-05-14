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
