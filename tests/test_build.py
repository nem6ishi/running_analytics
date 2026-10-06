import pytest
from pathlib import Path


def test_build_output_verification():
    root_dir = Path(__file__).resolve().parent.parent
    html_path = root_dir / "docs" / "index.html"
    
    assert html_path.exists(), "docs/index.html が生成されている必要があります"
    content = html_path.read_text(encoding="utf-8")

    # 1. cdn.tailwindcss.com が完全に排除されていること
    assert "cdn.tailwindcss.com" not in content, "Play CDN (cdn.tailwindcss.com) が残っています"

    # 2. 主要な 3大ビュー要素が存在すること
    assert 'id="view-cockpit"' in content
    assert 'id="view-activity"' in content
    assert 'id="view-trends"' in content

    # 3. Phase 4 で追加された新機能セクションが存在すること
    assert "trainingLoadChart" in content or "CTL / ATL / TSB" in content
    assert "80/20" in content
    assert "サブ50" in content

    # 4. 固定バージョンの Chart.js CDN が指定されていること
    assert "chart.js@" in content or "chart.umd.min.js" in content
