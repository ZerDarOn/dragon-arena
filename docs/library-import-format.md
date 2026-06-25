# 内容库导入格式规范

供团主 / AI 批量导入「内容库」（事件 / 陷阱 / 怪物 / 奇遇 / NPC）。
**导出的 JSON 就是本格式**——拿一份导出当模板照着填即可，round-trip 一致。

## 怎么导入

- UI：资源库 →「内容库」Tab → 「⬆ 导入」（仅管理员），选 JSON 文件。
- API：`POST /api/library/import`（需管理员 token）
  ```json
  { "entries": [ /* 见下 */ ], "mode": "upsert" }
  ```
  - `mode: "upsert"`（默认）：按 `id` 合并，已存在覆盖、不存在新增。
  - `mode: "replace"`：整库替换为本次内容。
  - 返回：`{added, updated, total}` 或 `{mode:"replace", total, removed}`。

## 条目格式（LibraryEntry）

```jsonc
{
  "id": "monster_101",        // 可省略；省略时自动生成 "{category}_{8位}"
  "category": "monster",      // 必填：event | trap | monster | adventure | npc
  "name": "暗影狼",            // 必填：条目名
  "tier": "C",                // 可选：等级 / 稀有度 / 类型（视库而定）
  "effect_text": "潜行；背刺+8", // 可选：主效果/描述（团主读它手动判定，系统不解析）
  "note": "刺客怪",            // 可选：备注
  "fields": {                 // 可选：原始表格的全部列，保真展示用，键名随意
    "生命": "40", "护甲": "2", "攻击力": "12", "掉落": "暗影精华×1"
  }
}
```

整个导入文件是一个**条目数组** `[ {…}, {…} ]`（也接受 `{ "entries": [...] }`）。

## 给 AI 的提示

读 Excel 后，把每一行映射成上面的对象：
- 表名 → `category`（怪物表→`monster`，事件表→`event`，依此类推）。
- "名称"列 → `name`；"等级/稀有度/类型"列 → `tier`；"效果/描述/特殊能力"列 → `effect_text`；"备注"→`note`。
- 其余所有列原样塞进 `fields`（键用原表头），不丢信息。
- `id` 留空让系统生成，或用稳定规则（如 `monster_<序号>`）以便后续 upsert 更新同一条。

---

## 道具库导入（同一套思路）

资源库 →「道具库」Tab →「⬆ 导入」；或 `POST /api/items/import`（管理员，body `{entries, mode}`）。
**按 `name` upsert**（货架按 name 引用道具，所以 name 是键，重名即更新）。

```jsonc
{
  "name": "回血药水",        // 必填，作为去重键
  "category": "consumable", // weapon | armor | consumable | skill | misc
  "price": 40,              // 0 = 不可购买（仅战场获得/团主发放）
  "description": "恢复 20 HP",
  "effect_text": "团主参考，系统不解析",
  "icon_url": ""            // 可选
}
```

整个文件是道具对象数组。AI 读兑换表 Excel：一行一个对象，名称列→`name`，价格列→`price`，
品类→`category`，效果/描述→`effect_text`/`description`。
