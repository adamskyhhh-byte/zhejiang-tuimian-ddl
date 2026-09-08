"""输出本次来源检查摘要，工作流成功不能掩盖单源失败。"""

import json
import os
from collections import Counter
from pathlib import Path


def summary_lines(catalog: dict) -> list[str]:
    """只使用公开结构化字段，避免将外部页面内容作为指令执行。"""
    run = catalog["run"]
    coverage = Counter(unit["coverage"] for unit in catalog["units"])
    lines = [
        "## 官方公告检查结果",
        "",
        f"快照：{catalog['generatedAt']}",
        f"状态：{run['status']}；检查 {run['checked']}，成功 {run['succeeded']}，失败 {run['failed']}。",
        f"学校／机构 {len(catalog['schools'])}，招生单位 {len(catalog['units'])}，项目 {len(catalog['opportunities'])}。",
        f"单位覆盖：{dict(coverage)}",
        "",
        "失败来源（保留上次信息，不视为本次已核验）：",
    ]
    failed = [source for source in catalog["sources"] if source.get("error")]
    if not failed:
        lines.append("本次没有记录来源错误。请结合网页中各来源的最后成功检查时间判断新鲜度。")
    for source in failed:
        source_id = str(source["id"]).replace("`", "")
        last_success = source.get("lastSuccessAt") or "从未成功"
        error = " ".join(str(source["error"]).split()).replace("<", "&lt;").replace("]", "\\]")
        lines.append(f"- `{source_id}`：{error[:240]}；上次成功：{last_success}")
    return lines


def main() -> None:
    path = Path("public/data/catalog.json")
    if not path.exists():
        text = "尚无有效快照；请检查前序步骤的错误。\n"
    else:
        text = "\n".join(summary_lines(json.loads(path.read_text(encoding="utf-8")))) + "\n"
    print(text)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as summary:
            summary.write(text)


if __name__ == "__main__":
    main()
