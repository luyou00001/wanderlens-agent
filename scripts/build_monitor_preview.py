#!/usr/bin/env python3
"""把模型清單與假素材寫成監控頁的預覽資料。"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wanderlens.preview import write_preview  # noqa: E402


def main() -> None:
    target = ROOT / "web" / "preview" / "snapshot.json"
    payload = write_preview(target)
    print(f"已寫出 {target}，模型 {len(payload['models'])} 項。")


if __name__ == "__main__":
    main()
