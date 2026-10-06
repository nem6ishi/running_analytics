import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import pytailwindcss
from src.parser import load_activities
from src.analytics import prepare_full_analytics
from src.fit_parser import load_all_fit_series


def compile_css(root_dir: Path) -> str:
    input_css = root_dir / "templates" / "assets" / "tailwind.in.css"
    if not input_css.exists():
        raise FileNotFoundError(f"Tailwind input CSS not found: {input_css}")

    print("Compiling Tailwind CSS with pytailwindcss...")
    compiled = pytailwindcss.run(
        ["-i", str(input_css), "--minify"],
        version="v3.4.17",
        auto_install=True,
        cwd=root_dir,
    )
    print(f"Tailwind CSS compiled ({len(compiled)} bytes).")
    return compiled


def build():
    root_dir = Path(__file__).resolve().parent
    data_dir = root_dir / "data"
    data_path = data_dir / "Activities.csv"
    templates_dir = root_dir / "templates"
    docs_dir = root_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    if not data_path.exists():
        raise FileNotFoundError(f"データファイルが見つかりません: {data_path}")

    # CSS コンパイル
    app_css = compile_css(root_dir)

    # JavaScript 読み込み
    app_js_path = templates_dir / "assets" / "app.js"
    if not app_js_path.exists():
        raise FileNotFoundError(f"app.js が見つかりません: {app_js_path}")
    app_js = app_js_path.read_text(encoding="utf-8")

    print(f"Loading data from {data_path}...")
    df = load_activities(data_path)
    print(f"Loaded {len(df)} activities.")

    print(f"Loading FIT files from {data_dir}...")
    fit_dict = load_all_fit_series(data_dir)
    print(f"Loaded {len(fit_dict)} FIT activity entries.")

    print("Analyzing data & generating insights...")
    analytics_data = prepare_full_analytics(df, fit_dict, data_dir=data_dir)

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
        app_css=app_css,
        app_js=app_js,
        overview=analytics_data["overview"],
        overview_json=json.dumps(analytics_data["overview"], ensure_ascii=False, default=json_default),
        monthly=analytics_data["monthly"],
        monthly_json=json.dumps(analytics_data["monthly"], ensure_ascii=False, default=json_default),
        reversed_insights=analytics_data["reversed_insights"],
        insights_json=json.dumps(analytics_data["insights"], ensure_ascii=False, default=json_default),
        chart_data_json=json.dumps(analytics_data["chart_data"], ensure_ascii=False, default=json_default),
        personal_records=analytics_data["personal_records"],
        race_predictions=analytics_data["race_predictions"],
        vdot_data=analytics_data["vdot_data"],
        vdot_data_json=json.dumps(analytics_data["vdot_data"], ensure_ascii=False, default=json_default),
        sub50_progress=analytics_data["sub50_progress"],
        sub50_progress_json=json.dumps(analytics_data["sub50_progress"], ensure_ascii=False, default=json_default),
        calendar_heatmap=analytics_data["calendar_heatmap"],
        calendar_heatmap_json=json.dumps(analytics_data["calendar_heatmap"], ensure_ascii=False, default=json_default),
        rolling_volume=analytics_data["rolling_volume"],
        rolling_volume_json=json.dumps(analytics_data["rolling_volume"], ensure_ascii=False, default=json_default),
        weekly_workload=analytics_data["weekly_workload"],
        weekly_workload_json=json.dumps(analytics_data["weekly_workload"], ensure_ascii=False, default=json_default),
        form_evolution=analytics_data["form_evolution"],
        form_evolution_json=json.dumps(analytics_data["form_evolution"], ensure_ascii=False, default=json_default),
        hr_params=analytics_data["hr_params"],
        hr_params_json=json.dumps(analytics_data["hr_params"], ensure_ascii=False, default=json_default),
        training_load=analytics_data["training_load"],
        training_load_json=json.dumps(analytics_data["training_load"], ensure_ascii=False, default=json_default),
        zone_distribution=analytics_data["zone_distribution"],
        zone_distribution_json=json.dumps(analytics_data["zone_distribution"], ensure_ascii=False, default=json_default),
        sub50_forecast=analytics_data["sub50_forecast"],
        sub50_forecast_json=json.dumps(analytics_data["sub50_forecast"], ensure_ascii=False, default=json_default),
        gear_stats=analytics_data["gear_stats"],
        gear_stats_json=json.dumps(analytics_data["gear_stats"], ensure_ascii=False, default=json_default),
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
