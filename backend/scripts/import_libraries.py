"""一次性把规则书 5 个文本库（事件/陷阱/怪物/奇遇/NPC）解析成结构化 seed。

源文件是团主手写的管道分隔表格，位于仓库外的素材目录；本脚本读取它们，输出
backend/app/data/library_seed.json（已提交进仓库，运行时不再依赖源 txt）。

用法（源文件路径可用环境变量覆盖）：
    python scripts/import_libraries.py
"""
import json
import os
from pathlib import Path

SRC_DIR = Path(os.environ.get(
    "DRAGON_ARENA_LIB_SRC",
    r"D:\Code\AIdemo\AiDome\临时\pvp",
))
OUT = Path(__file__).resolve().parent.parent / "app" / "data" / "library_seed.json"

# 每个库：文件名后缀、category、(名称列, 等级/稀有度列 或 None, 效果列)
LIBS = [
    ("事件库", "event",     "事件名称", None,    "效果"),
    ("陷阱库", "trap",      "陷阱名称", "等级",  "伤害/效果"),
    ("怪物库", "monster",   "怪物名称", "等级",  "特殊能力"),
    ("奇遇库", "adventure", "名称",     "稀有度", "效果描述"),
    ("NPC库",  "npc",       "NPC名称",  "类型",  "功能描述"),
]


def parse_file(path: Path, category: str, name_col: str, tier_col, effect_col: str):
    lines = [l.rstrip("\n") for l in path.read_text(encoding="utf-8").splitlines()]
    # 第一行是 "=== X库 (共N行) ==="，第二行是表头
    header = [c.strip() for c in lines[1].split("|")]
    entries = []
    for i, raw in enumerate(lines[2:]):
        if not raw.strip():
            continue
        cells = [c.strip() for c in raw.split("|")]
        if len(cells) < 2:
            continue
        fields = {header[j]: (cells[j] if j < len(cells) else "")
                  for j in range(len(header))}
        name = fields.get(name_col, "").strip()
        if not name:
            continue
        entries.append({
            "id": f"{category}_{fields.get('序号', i + 1)}",
            "category": category,
            "name": name,
            "tier": (fields.get(tier_col, "") or "").strip() if tier_col else "",
            "effect_text": fields.get(effect_col, "").strip(),
            "note": fields.get("备注", "").strip(),
            "fields": fields,
        })
    return entries


def main():
    all_entries = []
    for suffix, category, name_col, tier_col, effect_col in LIBS:
        path = SRC_DIR / f"_lib_{suffix}.txt"
        if not path.exists():
            print(f"[skip] 源文件不存在: {path}")
            continue
        got = parse_file(path, category, name_col, tier_col, effect_col)
        print(f"[ok] {suffix}: {len(got)} 条")
        all_entries.extend(got)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n共 {len(all_entries)} 条 → {OUT}")


if __name__ == "__main__":
    main()
