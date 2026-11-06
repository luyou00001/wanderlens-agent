from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from wanderlens import __version__
from wanderlens.catalog import find_model, load_catalog, select_models
from wanderlens.commerce import export_bundle
from wanderlens.config import resolve_settings
from wanderlens.errors import WanderlensError
from wanderlens.monitor import serve_monitor
from wanderlens.paths import repo_root
from wanderlens.pipeline import describe, draft, ingest, iter_assets, set_place, set_publish, set_sale
from wanderlens.publishing import export_posts


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except WanderlensError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", type=Path, help="設定檔路徑。預設使用 config/settings.yaml，若該檔不存在則用內建預設。")
    common.add_argument("--vault", type=Path, help="素材庫目錄，覆蓋設定檔。")
    common.add_argument("--library", type=Path, help="素材索引 JSON 的路徑。")

    parser = argparse.ArgumentParser(
        prog="wanderlens",
        description="把本機的旅行照片與影片整理成待審閱草稿，以及可再經人工確認的數位影像包。",
    )
    parser.add_argument("--version", action="version", version=f"wanderlens {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    models = commands.add_parser("models", help="查看開源模型清單。")
    model_commands = models.add_subparsers(dest="models_command", required=True)
    listing = model_commands.add_parser("list", help="列出模型。")
    listing.add_argument("--role", help="依用途篩選，例如 vision_language。")
    listing.add_argument("--commercial", choices=["allowed", "disallowed", "conditional", "unknown"])
    listing.add_argument("--query", help="搜尋名稱、識別碼或說明。")
    listing.add_argument("--json", action="store_true", dest="as_json")
    listing.set_defaults(handler=handle_models_list)
    showing = model_commands.add_parser("show", help="顯示一個模型的完整條目。")
    showing.add_argument("model_id")
    showing.set_defaults(handler=handle_models_show)

    ingest_parser = commands.add_parser("ingest", parents=[common], help="清點素材庫並更新索引。")
    ingest_parser.add_argument("--input", type=Path, help="要掃描的子目錄，必須位於素材庫內。預設為 inbox。")
    ingest_parser.add_argument("--prune", action="store_true", help="移除這次掃描範圍內已經不存在的索引。")
    ingest_parser.set_defaults(handler=handle_ingest)

    describe_parser = commands.add_parser("describe", parents=[common], help="為尚未描述的素材產生技術預檢或模型描述。")
    describe_parser.add_argument("--force", action="store_true", help="重新描述，並清掉舊草稿與發佈標記。")
    describe_parser.add_argument("--limit", type=int, help="本次最多處理幾筆。")
    describe_parser.set_defaults(handler=handle_describe)

    draft_parser = commands.add_parser("draft", parents=[common], help="由描述產生各平台草稿。")
    draft_parser.set_defaults(handler=handle_draft)

    export_parser = commands.add_parser("export-posts", parents=[common], help="匯出待人工審閱的貼文目錄。")
    export_parser.add_argument("--output", type=Path)
    export_parser.set_defaults(handler=handle_export)

    sale = commands.add_parser("mark-sale", parents=[common], help="標記素材是否可進入販售草稿包。")
    sale.add_argument("--asset-id", action="append", required=True, dest="asset_ids")
    group = sale.add_mutually_exclusive_group(required=True)
    group.add_argument("--yes", action="store_true")
    group.add_argument("--no", action="store_true")
    sale.set_defaults(handler=handle_sale)

    publish = commands.add_parser("mark-publish", parents=[common], help="標記已有畫面描述的草稿可供你自行發佈。")
    publish.add_argument("--asset-id", action="append", required=True, dest="asset_ids")
    publish_group = publish.add_mutually_exclusive_group(required=True)
    publish_group.add_argument("--yes", action="store_true")
    publish_group.add_argument("--no", action="store_true")
    publish.set_defaults(handler=handle_publish)

    place = commands.add_parser("label-place", parents=[common], help="為素材或整段行程加上你自己的地點標記。")
    place.add_argument("--asset-id", action="append", dest="asset_ids")
    place.add_argument("--trip-id")
    place.add_argument("--place", help="地點名稱。與 --clear 擇一。")
    place.add_argument("--clear", action="store_true", help="清除地點標記。")
    place.set_defaults(handler=handle_place)

    bundle = commands.add_parser("bundle", parents=[common], help="組成尚未上架的數位影像草稿包。")
    bundle.add_argument("--output", type=Path)
    bundle.add_argument("--min-long-edge", type=int, default=1600)
    bundle.add_argument("--allow-people", action="store_true")
    bundle.add_argument("--allow-unknown-people", action="store_true")
    bundle.add_argument("--allow-sensitive", action="store_true")
    bundle.set_defaults(handler=handle_bundle)

    listing_assets = commands.add_parser("list", parents=[common], help="列出索引中的素材識別碼。")
    listing_assets.add_argument("--trip-id")
    listing_assets.add_argument("--limit", type=int, default=50)
    listing_assets.add_argument("--all", action="store_true", dest="list_all")
    listing_assets.set_defaults(handler=handle_list)

    ui = commands.add_parser("ui", parents=[common], help="開啟本機監控頁。")
    ui.add_argument("--host", default="127.0.0.1", help="預設只聽 127.0.0.1。")
    ui.add_argument("--port", type=int, default=8765)
    ui.set_defaults(handler=handle_ui)
    return parser


def handle_models_list(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    models = select_models(
        catalog["models"],
        role=args.role,
        commercial=args.commercial,
        query=args.query,
    )
    if args.as_json:
        print(json.dumps(models, ensure_ascii=False, indent=2))
        return 0
    if not models:
        print("沒有符合條件的模型。")
        return 0
    print(f"清單日期：{catalog.get('updated', '未知')}　共 {len(models)} 項")
    for model in models:
        vram = model.get("min_vram_gb_estimate")
        vram_text = "-" if vram is None else str(vram)
        huggingface = model.get("huggingface") or model.get("github") or ""
        print(
            f"{model['status']:<14} {model['commercial_use']:<12} "
            f"vram={vram_text:<4} {model['id']:<28} {huggingface}"
        )
    return 0


def handle_models_show(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    model = find_model(catalog["models"], args.model_id)
    print(yaml.safe_dump(model, allow_unicode=True, sort_keys=False).rstrip())
    return 0


def handle_ingest(args: argparse.Namespace) -> int:
    settings = _settings(args)
    input_dir = _optional_path(args.input)
    report = ingest(settings, input_dir=input_dir, prune=args.prune)
    print(
        f"掃描 {report.scanned_files} 個媒體檔，新增 {report.added}，"
        f"更新 {report.updated}，無法讀取 {report.unreadable}，"
        f"移除 {report.removed}，行程 {report.trips}。"
    )
    print(f"索引：{report.library_path}")
    return 0


def handle_describe(args: argparse.Namespace) -> int:
    if args.limit is not None and args.limit < 1:
        raise WanderlensError("--limit 必須至少為 1。")
    settings = _settings(args)
    report = describe(settings, force=args.force, limit=args.limit)
    print(
        f"已描述 {report.described}，略過 {report.skipped}，失敗 {report.failed}。"
    )
    for relative, reason in report.failures:
        print(f"失敗 {relative}：{reason}", file=sys.stderr)
    print(f"索引：{report.library_path}")
    if report.failed and report.described == 0 and report.skipped == 0:
        return 2
    if report.failed:
        return 1
    return 0


def handle_draft(args: argparse.Namespace) -> int:
    count = draft(_settings(args))
    print(f"已更新 {count} 筆素材的草稿。")
    return 0


def handle_export(args: argparse.Namespace) -> int:
    output = export_posts(_settings(args), _optional_path(args.output))
    print(f"已匯出待審閱草稿：{output}")
    return 0


def handle_sale(args: argparse.Namespace) -> int:
    count = set_sale(_settings(args), args.asset_ids, args.yes)
    print(f"已更新 {count} 筆販售標記。")
    return 0


def handle_publish(args: argparse.Namespace) -> int:
    count = set_publish(_settings(args), args.asset_ids, args.yes)
    print(f"已更新 {count} 筆發佈標記。")
    return 0


def handle_place(args: argparse.Namespace) -> int:
    if bool(args.place) == bool(args.clear):
        raise WanderlensError("請指定 --place，或使用 --clear 清除標記。")
    if bool(args.trip_id) == bool(args.asset_ids):
        raise WanderlensError("請指定 --trip-id 或至少一個 --asset-id，不要同時指定。")
    place = None if args.clear else " ".join(args.place.split())
    if place == "":
        raise WanderlensError("地點標記不可為空白。")
    count = set_place(
        _settings(args),
        asset_ids=args.asset_ids,
        trip_id=args.trip_id,
        place=place,
    )
    print(f"已更新 {count} 筆地點標記。")
    return 0


def handle_bundle(args: argparse.Namespace) -> int:
    output = export_bundle(
        _settings(args),
        _optional_path(args.output),
        min_long_edge=args.min_long_edge,
        allow_people=args.allow_people,
        allow_unknown_people=args.allow_unknown_people,
        allow_sensitive=args.allow_sensitive,
    )
    print(f"已寫出草稿包：{output}")
    return 0


def handle_ui(args: argparse.Namespace) -> int:
    host = (args.host or "").strip()
    if not host:
        raise WanderlensError("請提供 --host。")
    serve_monitor(_settings(args), host=host, port=args.port)
    return 0


def handle_list(args: argparse.Namespace) -> int:
    assets = iter_assets(_settings(args))
    if args.trip_id:
        assets = [asset for asset in assets if asset.trip_id == args.trip_id]
    if not assets:
        print("素材索引是空的。")
        return 0
    visible = assets if args.list_all else assets[: args.limit]
    for asset in visible:
        provider = (asset.analysis or {}).get("provider") or "-"
        sale = "Y" if asset.cleared_for_sale else "-"
        publish = "Y" if asset.approved_for_publish else "-"
        print(f"{asset.id}  sale={sale} publish={publish} {provider:<10} {asset.relative_path}")
    if len(visible) < len(assets):
        print(f"只顯示 {len(visible)} / {len(assets)}。若要全部列出，請加上 --all。")
    return 0


def _settings(args: argparse.Namespace):
    config = args.config
    if config is not None and not config.is_absolute():
        config = (repo_root() / config).resolve()
    overrides = {
        "vault_dir": _optional_path(args.vault),
        "library_path": _optional_path(args.library),
    }
    return resolve_settings(config, overrides)


def _optional_path(value: Path | None) -> Path | None:
    if value is None:
        return None
    if value.is_absolute():
        return value
    return (repo_root() / value).resolve()
