"""分析视角工具函数测试"""

from tradingagents.agents.utils.perspective_utils import (
    normalize_analysis_perspective,
    get_perspective_label,
    build_perspective_guidance,
)


def test_normalize_aliases():
    assert normalize_analysis_perspective("value") == "value"
    assert normalize_analysis_perspective("trend") == "trend"
    assert normalize_analysis_perspective("价值分析") == "value"
    assert normalize_analysis_perspective("趋势分析") == "trend"
    assert normalize_analysis_perspective("invalid") == "value"
    assert normalize_analysis_perspective(None) == "value"


def test_labels():
    assert get_perspective_label("value") == "价值分析"
    assert get_perspective_label("trend") == "趋势分析"


def test_guidance_differs():
    from tradingagents.agents import Toolkit

    Toolkit.update_config({"analysis_perspective": "value"})
    value_text = build_perspective_guidance()
    Toolkit.update_config({"analysis_perspective": "trend"})
    trend_text = build_perspective_guidance()
    assert "价值分析决策宪法" in value_text
    assert "趋势分析决策宪法" in trend_text
    assert value_text != trend_text
