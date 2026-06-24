# Shape Key Classification

Blender 5.1 形态键分类与 K 帧辅助插件。

## 文件结构

```text
shape_key_classification/
├── __init__.py          # 注册、卸载、类列表
├── i18n.py             # 插件内翻译，避免 Pattern 被 Blender 内置词义翻译成“图案”
├── core.py             # 形态键同步、K 帧、镜像、handler、选择回调
├── properties.py       # PropertyGroup 定义
├── ui_lists.py         # 分类列表、所有形态键列表、当前分类形态键列表
├── operators.py        # 分类、归类、范围选择、K 帧等操作
├── presets.py          # JSON 导入导出，preset_version = 1.0
├── panel.py            # N 面板 UI 布局
└── README.md
```

## 重要设计说明

“所有形态键”区域使用真正的 `UIList` 滚动列表，但行内不再放自定义 Operator。
之前为了在行内支持 Ctrl / Shift 点击，自定义 Operator 会受到 UIList 滚动后的可视行缓存、active 行更新顺序影响，导致第一次点击无效、错选、Ctrl/Shift 范围错乱等问题。

现在行内只保留 Blender 原生控件：

- 原生 `BoolProperty` 复选框：写入 `ShapeKeyItem.all_selected`
- 原生 active 行：写入 `MeshShapeKeyManager.active_all_item_index`，用于“智能归类 / 智能移除分类”
- 文本标签：显示名称和已有分类

这样“所有形态键”的整理选择不会同步到“当前分类内容”的动画 K 帧选择：

- 所有形态键列表：`all_selected`
- 当前分类/K帧列表：`selected`

## 所有形态键列表操作

- 点击行：设为当前项。
- 勾选复选框：加入/移出所有列表选择。
- “只选当前项”：清空所有列表选择，只勾选当前行。
- “设为范围起点”：把当前行作为范围选择锚点。
- “选择到当前项的范围”：选择锚点到当前行之间的形态键。
- “追加范围”开启时，范围选择会保留已有勾选项。
- “智能归类”：如果有勾选则归类勾选项；如果没有勾选，则归类当前高亮项，不覆盖已有分类。
- “智能移除分类”：如果有勾选则移除勾选项的分类；如果没有勾选，则移除当前高亮项的分类。

## 安装

把整个 `shape_key_classification` 文件夹放入 Blender 插件目录，或直接安装 zip。


## 2026-06 native checkbox list update

- All Shape Keys list remains a real scrollable UIList.
- Row labels are display-only for checkbox selection. Clicking a row still updates the UIList single-selected active item, which is used by the single-item assign/remove buttons.
- The plugin uses the last changed checkbox item as the stable target for single-item actions and active-and-above assignment.
- `item.all_selected` remains separate from category animation selection `item.selected`.
- All-list search filters by shape key name, alias, or category.
- Explicit range-selection buttons were removed because native checkbox drag selection covers that workflow.


## 2026-06 hover-safe checkbox update

- The All Shape Keys list remains a real scrollable UIList.
- Shape key names are labels only; they no longer toggle selection. This avoids a Blender UIList hover/highlight timing issue after scrolling downward.
- Selection is done only through the small left native checkbox, which preserves checkbox drag multi-select.
- All-list selection still uses `item.all_selected` and remains separate from category/K-frame selection `item.selected`.
