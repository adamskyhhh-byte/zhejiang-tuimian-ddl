"""命令行入口：uv run python -m tuimian。"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .crawler import crawl
from .models import Catalog
from .storage import export_catalog, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="浙江选调院校预推免官方公告增量采集")
    commands = parser.add_subparsers(dest="command", required=True)
    crawl_parser = commands.add_parser("crawl", help="发现新公告、复查已知公告和附件并导出")
    crawl_parser.add_argument(
        "--source", action="append", default=[], help="只检查所选来源及其子来源"
    )
    crawl_parser.add_argument("--limit", type=int, help="限制本次请求的来源数（包括发现的来源）")
    crawl_parser.add_argument(
        "--no-network", action="store_true", help="仅导入种子并导出，不声称联网核验"
    )
    export_parser = commands.add_parser("export", help="由已持久化状态与人工修正生成静态数据")
    validate_parser = commands.add_parser("validate", help="校验静态数据模型与引用关系")
    validate_parser.add_argument("--catalog", type=Path, help="指定待校验 JSON 文件")
    validate_parser.add_argument("--expect-schools", type=int, help="额外校验学校数量")
    for command in (crawl_parser, export_parser, validate_parser):
        command.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)
    try:
        root = args.root.resolve()
        if args.command == "crawl":
            if args.limit is not None and args.limit < 1:
                parser.error("--limit 必须大于0")
            result = asyncio.run(
                crawl(root, source_ids=args.source, limit=args.limit, no_network=args.no_network)
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["status"] == "failed" else 0
        if args.command == "export":
            result = export_catalog(root)
        else:
            path = args.catalog or root / "public/data/catalog.json"
            result = Catalog.model_validate(read_json(path, {}))
            if args.expect_schools is not None and len(result.schools) != args.expect_schools:
                raise ValueError(f"院校数量为 {len(result.schools)}，预期 {args.expect_schools}")
        print(
            f"校验通过：{len(result.schools)} 所机构，{len(result.units)} 个培养单位，"
            f"{len(result.opportunities)} 个项目"
        )
        return 0
    except (ValueError, OSError) as exc:
        print(f"失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
