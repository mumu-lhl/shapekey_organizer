import bpy

ADDON_NAME = "Shape Key Classification"
ADDON_NAME_ZH = "形态键分类"

_zh_fallback = {
    "Category Name": "分类名称",
    "Match Pattern": "匹配规则",
    "Auto Keyframe": "开启自动K帧",
    "Mirror Mode": "开启镜像同步",
    "Pattern": "匹配规则",
    "Add Category": "添加分类",
    "Remove Category": "移除分类",
    "Move Category": "移动分类",
    "Move Shape Key": "移动形态键",
    "Move Mode": "移动模式",
    "Auto Match Category": "自动规则分类",
    "Move Selected to Active Category": "将选定移至当前分类",
    "Remove Selected from Category": "从当前分类移除选定",
    "Keyframe Selected": "批量K帧选中",
    "Reset Selected": "重置选定值为 0",
    ADDON_NAME: ADDON_NAME_ZH,
    "Please select a Mesh object": "请先选择网格物体 (Mesh)",
    "Selected mesh has no Shape Keys": "所选网格不包含形态键",
    "Presets Manager": "配置预设 (JSON)",
    "Import Preset": "导入配置",
    "Export Preset": "导出当前",
    "Frequency Statistics Preset": "频次统计预设",
    "Frequency Preset": "频次预设",
    "Saved Project Statistics": "已保存工程统计",
    "Sort by Current Project Frequency": "按当前工程频次排序",
    "Sort by Frequency Preset": "按频次预设排序",
    "Add Current Project Statistics": "加入当前工程统计",
    "Preset Name": "预设名称",
    "Create Frequency Preset": "新建频次预设",
    "Delete Frequency Preset": "删除频次预设",
    "Delete Project Statistics": "删除工程统计",
    "Categories Manager": "分类管理器",
    "Categories": "分类",
    "Auto Match Active": "一键分类当前组",
    "Auto Match All": "一键分类全部组",
    "Shape Keys in Category": "当前选定分类的内容",
    "All Shape Keys": "所有形态键",
    "Preset Editor": "预设编辑器",
    "Show Preset Editor": "显示预设编辑器",
    "Hide Auto Match and All Shape Keys tools after presets are ready": "预设制作完成后可关闭，用于隐藏一键分类和所有形态键列表",
    "Assign Active and Above to Category": "将上方连续未分类项归类",
    "Assign this shape key and all shape keys above it to the active category": "将当前选中的形态键及其上方尚未归类的形态键归类到当前分类，已归类的形态键会被跳过",
    "Assign checked shape keys in All Shape Keys to the active category. If nothing is checked, assign the active row without overwriting existing categories": "将“所有形态键”列表中勾选的形态键归类到当前分类；如果没有勾选，则归类当前高亮项，不覆盖已有分类",
    "Remove checked shape keys in All Shape Keys from their current categories. If nothing is checked, remove the active row from its current category": "将“所有形态键”列表中勾选的形态键移除其现有分类；如果没有勾选，则移除当前高亮项的分类",
    "Clear All List Selection": "清空所有列表选择",
    "All List Search": "所有列表搜索",
    "Filter the All Shape Keys list by name, alias, or category": "按名称、别名或分类过滤所有形态键列表",
    "No all-list item selected yet": "尚未选择所有列表中的项目",
    "Remove One Shape Key from Category": "从分类移除单个形态键",
    "Remove this shape key from its current category": "将这个形态键从当前已有分类中移除",
    "Unclassified": "未分类",
    "Click row to single select | Checkbox: Ctrl toggle, Shift range": "点击名称单选｜左侧选择按钮支持 Ctrl 增减、Shift 范围选择",
    "Selection: Ctrl toggle, Shift range, Ctrl+Shift append range": "选择：普通点击单选，Ctrl 单个增减，Shift 范围选择，Ctrl+Shift 追加范围",

    "Use the left checkbox to select. Drag over checkboxes for fast multi-select.": "使用左侧复选框选择；按住并拖过复选框可快速多选。",
    "All List Target:": "所有列表目标:",
    "Checked All Items:": "已勾选项目数:",
    "Range Anchor:": "范围锚点:",
    "Select Active Only": "只选当前项",
    "Set Range Anchor": "设为范围起点",
    "Append Range": "追加范围",
    "When selecting a range in All Shape Keys, keep the existing checked items": "在所有形态键里选择范围时保留已有勾选项",
    "Select Range to Active": "选择到当前项的范围",
    "Active Category:": "活跃目录:",
    "Batch Select:": "全选控制:",
    "Select All": "全选",
    "Deselect All": "清空选择",
    "Invert Selection": "反选",
    "Assign": "归类",
    "Remove Category": "移除分类",
    "Animation Actions": "动画批量处理",
    "Keyframe Selected Checked": "批量K帧勾选项",
    "Reset Selected to 0": "批量重置为 0",
    "Global Option Configuration": "全局配置",
    "Show Only Keyed": "仅显示已打关键帧",
    "Search": "搜索",
    "Alias": "别名",
    "Alias Editor": "别名编辑器",
    "Preview Value": "预览值",
    "Preview this shape key value while editing aliases without inserting keyframes": "编辑别名时预览此形态键数值，且不插入关键帧",
    "Original Name": "原始名称",
    "Mirror Alias": "镜像别名",
    "Left Prefix": "左侧前缀",
    "Left Suffix": "左侧后缀",
    "Right Prefix": "右侧前缀",
    "Right Suffix": "右侧后缀",
    "Sync Mirror Aliases": "同步镜像别名",
    "Please create or select a category": "请在上方选择或创建一个分类",
    "Open Preset Editor to create or select a category": "打开预设编辑器以创建或选择分类",
    "Name": "名称",
    "Insert Shape Key Keyframe": "自动写入关键帧",
    "Reset Preview Value": "重置预览值",
    "Reset All Preview Values": "重置全部预览值",
    "Reset this shape key preview value to 0 without inserting keyframes": "将此形态键预览值重置为 0，且不插入关键帧",
    "Reset all shape key preview values to 0 without inserting keyframes": "将所有形态键预览值重置为 0，且不插入关键帧",

    "Export current mesh categories and assignments to a JSON file": "将当前的网格分类和分配导出为 JSON 文件",
    "Import categories and assignments from a JSON file": "从 JSON 文件导入分类和分配",
    "Preset successfully exported to {}": "预设成功导出至 {}",
    "Failed to export preset: {}": "导出预设失败: {}",
    "Failed to read preset file: {}": "读取预设文件失败: {}",
    "Imported {} categories successfully.": "成功导入了 {} 个分类。",
    "Create matching aliases for recognized left/right shape key pairs": "为识别的左/右镜像形态键对创建匹配的别名",
    "Synchronized aliases for {} mirror pair(s)": "已成功同步 {} 对镜像别名",
    "No mirrored shape key pairs with aliases found": "未发现带有别名的镜像形态键对",
    "New Category {}": "新分类 {}",
    "New Category": "新分类",
    "Up": "向上",
    "Down": "向下",
    "Before": "在此之前",
    "After": "在此之后",
    "Automatically assign shape keys to categories based on patterns": "根据匹配规则自动将形态键分配到分类",
    "No categories defined": "未定义任何分类",
    "Successfully classified {} shape keys.": "成功自动分类了 {} 个形态键。",
    "Moved {} shape keys to category '{}'": "已将 {} 个形态键移至分类 '{}'",
    "No changes. Shape key '{}' is already classified as '{}'.": "无变更。形态键 '{}' 已经归类为 '{}'。",
    "No valid shape keys selected.": "未选择有效的形态键。",
    "Moved shape key '{}' to category '{}'.": "已将形态键 '{}' 移至分类 '{}'。",
    "Moved {} shape keys to category '{}'. Skipped {} already-classified shape keys.": "已将 {} 个形态键移至分类 '{}'。跳过了 {} 个已分类的形态键。",
    "No changes. Shape key '{}' is already unclassified.": "无变更。形态键 '{}' 已经是未分类状态。",
    "Removed shape key '{}' from its category.": "已将形态键 '{}' 从其分类中移除。",
    "Removed {} shape keys from their categories. Skipped {} already-unclassified shape keys.": "已从分类中移除 {} 个形态键。跳过了 {} 个本就未分类的形态键。",
    "Use the active row in All Shape Keys as the range selection anchor": "将所有形态键列表中的当前高亮行用作范围选择起点",
    "Range anchor set to '{}'.": "范围起点已设置为 '{}'。",
    "Select shape keys between the range anchor and the active row in All Shape Keys": "选择所有形态键列表中范围起点与当前高亮行之间的形态键",
    "Selected {} shape keys from range anchor to active row.": "已选择从范围起点到当前项的 {} 个形态键。",
    "Clear All Shape Keys selection and check only the active row": "清空所有形态键选择并仅勾选当前高亮行",
    "Cleared All Shape Keys selection.": "已清空所有形态键的选择。",
    "Assign only the continuous unclassified range from the active shape key upward. Stop at the first already-classified shape key, and never overwrite existing categories.": "仅将当前选中的形态键及其上方连续的未分类形态键归类到当前分类。在遇到第一个已分类的形态键时停止，且绝不覆盖已有分类。",
    "No changes. Active or upper boundary shape key '{}' is already classified.": "无变更。当前项或上边界形态键 '{}' 已经归类。",
    "No unclassified shape keys found.": "未发现未分类的形态键。",
    "Moved {} continuous unclassified shape keys to category '{}'; stopped before already-classified shape key '{}'": "已将连续的 {} 个未分类形态键移至分类 '{}'；已在已分类形态键 '{}' 前停止",
    "Moved {} continuous unclassified shape keys to category '{}'": "已将连续的 {} 个未分类形态键移至分类 '{}'",
    "Removed {} shape keys from category.": "已从分类中移除 {} 个形态键。",
    "Keyframe Single": "单键K帧",
    "Keyframed {} shape keys.": "已为 {} 个形态键打上关键帧。",
    "No Frequency Presets": "无频次预设",
    "Create a frequency statistics preset first": "请先创建一个频次统计预设",
    "Frequency statistics preset: {}": "频次统计预设: {}",
    "Invalid frequency statistics preset": "无效的频次统计预设",
    "No Project Statistics": "无工程统计",
    "Select a frequency statistics preset first": "请先选择一个频次统计预设",
    "This preset does not contain project statistics": "该预设不包含工程统计",
    "This preset does not contain valid project statistics": "该预设不包含有效的工程统计",
    "Sorted all categorized shape keys using {} non-zero current-project frequencies": "已使用 {} 个非零当前工程频次对所有已分类的形态键排序",
    "Frequency Statistics": "频次统计",
    "Enter a valid preset name": "请输入有效的预设名称",
    "A frequency preset with this name already exists": "同名的频次预设已存在",
    "Created frequency preset '{}'": "已创建频次预设 '{}'",
    "Select an existing frequency preset": "选择一个已有的频次预设",
    "Failed to delete frequency preset: {}": "删除频次预设失败: {}",
    "Deleted frequency preset '{}'": "已删除频次预设 '{}'",
    "Save the Blender file before adding project statistics": "在添加工程统计前请先保存 Blender 文件",
    "Failed to save project statistics: {}": "保存工程统计失败: {}",
    "Added statistics for {} mesh(es) to '{}'": "已将 {} 个网格的统计信息添加至 '{}'",
    "No non-zero shape key frequencies were found in this project": "在此工程中未发现非零的形态键频次",
    "Failed to load frequency preset: {}": "加载频次预设失败: {}",
    "Sorted all categorized shape keys using {} saved frequencies": "已使用 {} 个保存的频次对所有已分类的形态键排序",
    "Select saved project statistics": "选择保存的工程统计",
    "Selected project statistics no longer exist": "选择的工程统计已不存在",
    "Failed to delete project statistics: {}": "删除工程统计失败: {}",
    "Deleted saved project statistics": "已删除保存 of 工程统计",
    "Supports wildcard patterns (e.g. *[Eye] or *Mouth*)": "支持通配符规则（例如 *[Eye] 或 *Mouth*）",
    "Left Alias Prefix": "左侧别名前缀",
    "Text added before aliases of left mirror shape keys": "添加到左侧镜像形态键别名前面的文本",
    "Left Alias Suffix": "左侧别名后缀",
    "Text added after aliases of left mirror shape keys": "添加到左侧镜像形态键别名后面的文本",
    "Right Alias Prefix": "右侧别名前缀",
    "Text added before aliases of right mirror shape keys": "添加到右侧镜像形态键别名前面的文本",
    "Right Alias Suffix": "右侧别名后缀",
    "Text added after aliases of right mirror shape keys": "添加到右侧镜像形态键别名后面的文本",
    "Frequency statistics preset stored in Blender's user preset directory": "存储在 Blender 用户预设目录中的频次统计预设",
    "Project statistics stored in the selected frequency preset": "存储在选定频次预设中的工程统计",
    "Enable Blender Auto Key for native shape key value editing": "启用 Blender 自动插帧以进行原生形态键数值编辑",
    "Automatically mirror value adjustments and keyframes to opposite side": "自动将数值调整和关键帧镜像到另一侧",
    "Only show shape keys that have at least one keyframe": "仅显示至少包含一个关键帧的形态键",
    "Enable fast reposition mode for shape keys": "启用形态键的快速重新定位模式",
    "Filter shape keys by name": "按名称过滤形态键",
}

ADDON_I18N_CONTEXT = ADDON_NAME
contexts_to_register = ["*", "UI", "Operator", "Property", "Default", ADDON_I18N_CONTEXT]

translations_dict = {
    "zh_CN": {
        (ctx, k): v
        for ctx in contexts_to_register
        for k, v in _zh_fallback.items()
    },
    "zh_Hans": {
        (ctx, k): v
        for ctx in contexts_to_register
        for k, v in _zh_fallback.items()
    },
    "zh_TW": {
        (ctx, k): v
        for ctx in contexts_to_register
        for k, v in _zh_fallback.items()
    },
}


def get_blender_ui_language():
    """返回 Blender 当前界面语言；不通过翻译结果猜语言。"""
    try:
        view = bpy.context.preferences.view
        if hasattr(view, "use_translate_interface") and not view.use_translate_interface:
            return "en_US"
        language = getattr(view, "language", "")
        if language and language not in {"DEFAULT", ""}:
            return language
    except Exception:
        pass
    try:
        return bpy.app.translations.locale or ""
    except Exception:
        return ""


def is_chinese_active():
    lang = get_blender_ui_language()
    return bool(lang) and lang.lower().replace('-', '_').startswith('zh')


def _(msg):
    """插件自己的轻量翻译入口，避免 Blender 内置泛用词污染。"""
    if is_chinese_active():
        return _zh_fallback.get(msg, msg)
    return msg


def localize_addon_info(bl_info):
    """Keep Blender's add-on list name aligned with the current UI language."""
    bl_info["name"] = _(ADDON_NAME)
    bl_info["location"] = f"View3D > N-Panel > {_(ADDON_NAME)}"


def localize_class_attributes(classes):
    """Localize static RNA strings before Blender registers each class.

    Panel categories, panel titles, operator labels, and operator tooltips are
    class attributes, so they do not pass through the draw-time translation
    helper used by normal layout labels.
    """
    for cls in classes:
        original = getattr(cls, "_sk_original_i18n_attrs", None)
        if original is None:
            original = {}
            for attr in ("bl_label", "bl_category", "bl_description"):
                if hasattr(cls, attr):
                    original[attr] = getattr(cls, attr)
            cls._sk_original_i18n_attrs = original

        for attr, text in original.items():
            if isinstance(text, str):
                setattr(cls, attr, _(text))
