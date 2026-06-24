import bpy

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
    "Shape Key Classification": "形态键分类",
    "Please select a Mesh object": "请先选择网格物体 (Mesh)",
    "Selected mesh has no Shape Keys": "所选网格不包含形态键",
    "Presets Manager": "配置预设 (JSON)",
    "Import Preset": "导入配置",
    "Export Preset": "导出当前",
    "Categories Manager": "分类管理器",
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
    "Original Name": "原始名称",
    "Please create or select a category": "请在上方选择或创建一个分类",
    "Name": "名称",
    "Insert Shape Key Keyframe": "自动写入关键帧",
}

ADDON_I18N_CONTEXT = "Shape Key Classification"

translations_dict = {
    "zh_CN": {
        **{(ADDON_I18N_CONTEXT, k): v for k, v in _zh_fallback.items()},
        **{("*", k): v for k, v in _zh_fallback.items()},
    },
    "zh_Hans": {
        **{(ADDON_I18N_CONTEXT, k): v for k, v in _zh_fallback.items()},
        **{("*", k): v for k, v in _zh_fallback.items()},
    },
    "zh_TW": {
        **{(ADDON_I18N_CONTEXT, k): v for k, v in _zh_fallback.items()},
        **{("*", k): v for k, v in _zh_fallback.items()},
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
