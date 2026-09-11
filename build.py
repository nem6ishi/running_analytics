import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from src.parser import load_activities
from src.analytics import prepare_full_analytics


def build():
    root_dir = Path(__file__).resolve().parent
    data_path = root_dir / "data" / "Activities.csv"
    templates_dir = root_dir / "templates"
    docs_dir = root_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        raise FileNotFoundError(f"データファイルが見つかりません: {data_path}")

    print(f"Loading data from {data_path}...")
    df = load_activities(data_path)
    print(f"Loaded {len(df)} activities.")

    print("Analyzing data & generating insights...")
    analytics_data = prepare_full_analytics(df)

    print("Rendering HTML with Jinja2...")
    env = Environment(loader=FileSystemLoader(templates_dir), autoescape=True)
    template = env.get_template("index.html")

    def json_default(obj):
        if hasattr(obj, "item"):
            return obj.item()
        if hasattr(obj, "tolist"):
            return obj.tolist()
        return str(obj)

    rendered_html = template.render(
        overview=analytics_data["overview"],
        overview_json=json.dumps(analytics_data["overview"], ensure_ascii=False, default=json_default),
        monthly=analytics_data["monthly"],
        reversed_insights=analytics_data["reversed_insights"],
        insights_json=json.dumps(analytics_data["insights"], ensure_ascii=False, default=json_default),
        chart_data_json=json.dumps(analytics_data["chart_data"], ensure_ascii=False, default=json_default),
    )

    output_html_path = docs_dir / "index.html"
    output_html_path.write_text(rendered_html, encoding="utf-8")
    print(f"Successfully generated: {output_html_path}")

    # GitHub Pages用 .nojekyll ファイル作成
    nojekyll_path = docs_dir / ".nojekyll"
    nojekyll_path.touch(exist_ok=True)
    print("Created docs/.nojekyll")


if __name__ == "__main__":
    build()
