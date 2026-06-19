bl_info = {
    "name": "Shape Key Classification",
    "author": "Mumulhl",
    "version": (0, 0, 1),
    "blender": (5, 1, 0),
    "location": "View3D > N-Panel > 形态键分类",
    "description": "形态键分类。采用 WindowManager 承载 UI 开关、分类上下移动、重命名防丢失、镜像K帧、重写的稳定自动K帧、通配符批量匹配以及预设导出/应用",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import bpy
import re
import json
from bpy_extras.io_utils import ExportHelper, ImportHelper

# ==========================================
# 1. 双保险国际化翻译系统 (Translation System)
# ==========================================

_zh_fallback = {
    "Category Name": "分类名称",
    "Match Pattern": "匹配规则",
    "Auto Keyframe": "开启自动K帧",
    "Mirror Mode": "开启镜像同步",
    "Pattern": "规则",
    "Add Category": "添加分类",
    "Remove Category": "移除分类",
    "Move Category": "移动分类",
    "Move Shape Key": "移动形态键",
    "Move Mode": "移动模式",
    "Move Selected Up": "勾选项上移",
    "Move Selected Down": "勾选项下移",
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
    "Active Category:": "活跃目录:",
    "Batch Select:": "全选控制:",
    "Select All": "全选",
    "Deselect All": "清空选择",
    "Invert Selection": "反选",
    "Move Checked Here": "将勾选项归类到当前",
    "Remove Checked": "将勾选项移出当前",
    "Animation Actions": "动画批量处理",
    "Keyframe Selected Checked": "批量K帧勾选项",
    "Reset Selected to 0": "批量重置为 0",
    "Global Option Configuration": "全局配置",
    "Show Only Keyed": "仅显示已打关键帧",
    "Search": "搜索",
    "Please create or select a category": "请在上方选择或创建一个分类",
    "Name": "名称",
    "Insert Shape Key Keyframe": "自动写入关键帧",
}

translations_dict = {
    "zh_CN": {("*", k): v for k, v in _zh_fallback.items()},
    "zh_Hans": {("*", k): v for k, v in _zh_fallback.items()},
    "zh_TW": {("*", k): v for k, v in _zh_fallback.items()}
}

def is_chinese_active():
    """检测当前 Blender 界面语言环境"""
    try:
        locale = bpy.app.translations.locale
        if locale and locale.startswith('zh'):
            return True
    except Exception:
        pass
    try:
        lang = bpy.context.preferences.view.language
        if lang and lang.startswith('zh'):
            return True
    except Exception:
        pass
    try:
        if bpy.app.translations.pgettext("File") == "文件":
            return True
        if bpy.app.translations.pgettext("Render") == "渲染":
            return True
    except Exception:
        pass
    return False

def _(msg):
    """强力双轨制翻译接口"""
    if is_chinese_active():
        try:
            translated = bpy.app.translations.pgettext(msg)
            if translated != msg:
                return translated
        except Exception:
            pass
        return _zh_fallback.get(msg, msg)
    return msg


# ==========================================
# 2. 核心数据、状态标志与工具函数
# ==========================================

_syncing_slider_values = False


def match_pattern(string, pattern):
    """支持通配符匹配（形如 *[Eye] 后缀安全匹配）"""
    if not pattern:
        return False
    escaped = re.escape(pattern)
    regex_str = escaped.replace(r'\*', '.*').replace(r'\?', '.')
    try:
        regex = re.compile('^' + regex_str + '$', re.IGNORECASE)
        return bool(regex.match(string))
    except re.error:
        return pattern.lower() in string.lower()

def mirror_name(name):
    """根据常见前缀/后缀自动推断镜像形态键名称"""
    pairs = [
        ("_L", "_R"), ("_l", "_r"),
        (".L", ".R"), (".l", ".r"),
        ("Left", "Right"), ("left", "right"),
        ("LEFT", "RIGHT"), ("_Left", "_Right"), ("_left", "_right")
    ]
    for left, right in pairs:
        if name.endswith(left):
            return name[:-len(left)] + right
        if name.endswith(right):
            return name[:-len(right)] + left
        if left in name:
            return name.replace(left, right)
        if right in name:
            return name.replace(right, left)
    return None


def get_sk_item(mesh, key_name):
    for item in mesh.sk_items:
        if item.name == key_name:
            return item
    return None


def set_sk_item_slider_value(mesh, key_name, value):
    return None


def sync_sk_item_slider_values(mesh, source_key_blocks=None):
    return None


def cleanup_slider_value_fcurves(mesh):
    if not mesh.animation_data or not mesh.animation_data.action:
        return
    action = mesh.animation_data.action
    for fcurve in list(action.fcurves):
        if fcurve.data_path.startswith("sk_items[") and fcurve.data_path.endswith('].slider_value'):
            action.fcurves.remove(fcurve)


def get_keyframe_value_on_current_frame(key_block_parent, key_name, frame):
    if not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return None
    action = key_block_parent.animation_data.action
    data_path = f'key_blocks["{key_name}"].value'
    for fcurve in action.fcurves:
        if fcurve.data_path != data_path:
            continue
        for kp in fcurve.keyframe_points:
            if abs(kp.co[0] - frame) < 0.01:
                return kp.co[1]
        break
    return None


def has_any_keyframes(key_block_parent, key_name):
    if not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return False
    action = key_block_parent.animation_data.action
    data_path = f'key_blocks["{key_name}"].value'
    return any(fcurve.data_path == data_path and len(fcurve.keyframe_points) > 0 for fcurve in action.fcurves)


def get_visible_category_item_indices(obj, mgr):
    categories = obj.data.sk_categories
    if not categories or mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
        return []

    active_cat = categories[mgr.active_category_index]
    result = []
    for index, item in enumerate(obj.data.sk_items):
        if item.category != active_cat.name:
            continue
        if mgr.show_only_keyed and not has_any_keyframes(obj.data.shape_keys, item.name):
            continue
        result.append(index)
    return result


def get_sk_item_index_by_name(mesh, key_name):
    for index, item in enumerate(mesh.sk_items):
        if item.name == key_name:
            return index
    return -1


def get_current_manager(context=None):
    ctx = context or getattr(bpy, "context", None)
    if not ctx:
        return None
    try:
        return ctx.window_manager.sk_manager
    except Exception:
        return None


def sync_active_item_by_name(mesh, mgr):
    if not mgr or not mesh:
        return

    if mgr.active_item_name:
        name_index = get_sk_item_index_by_name(mesh, mgr.active_item_name)
        if name_index >= 0 and mgr.active_item_index != name_index:
            mgr.active_item_index = name_index
            return

    if 0 <= mgr.active_item_index < len(mesh.sk_items):
        mgr.active_item_name = mesh.sk_items[mgr.active_item_index].name
    elif len(mesh.sk_items) > 0:
        mgr.active_item_index = min(max(0, mgr.active_item_index), len(mesh.sk_items) - 1)
        mgr.active_item_name = mesh.sk_items[mgr.active_item_index].name
    else:
        mgr.active_item_name = ""


def reorder_sk_items_from_preset(mesh, categories_data):
    kb_names = [kb.name for kb in mesh.shape_keys.key_blocks if kb.name != "Basis"] if mesh.shape_keys else []
    if not kb_names:
        return

    cat_cache = {item.name: item.category for item in mesh.sk_items}
    sel_cache = {item.name: item.selected for item in mesh.sk_items}

    ordered_names = []
    for cat_data in categories_data:
        for key_name in cat_data.get("assigned_keys", []):
            if key_name in kb_names and key_name not in ordered_names:
                ordered_names.append(key_name)

    for key_name in kb_names:
        if key_name not in ordered_names:
            ordered_names.append(key_name)

    mesh.sk_items.clear()
    for name in ordered_names:
        item = mesh.sk_items.add()
        item.name = name
        item.category = cat_cache.get(name, "")
        item.selected = sel_cache.get(name, False)


def reorder_sk_items_by_names(mesh, ordered_names):
    cat_cache = {item.name: item.category for item in mesh.sk_items}
    sel_cache = {item.name: item.selected for item in mesh.sk_items}

    mesh.sk_items.clear()
    for name in ordered_names:
        item = mesh.sk_items.add()
        item.name = name
        item.category = cat_cache.get(name, "")
        item.selected = sel_cache.get(name, False)


def get_keyframe_button_icon(key_block_parent, key_name, frame, current_value):
    keyed_value = get_keyframe_value_on_current_frame(key_block_parent, key_name, frame)
    if keyed_value is None:
        if has_any_keyframes(key_block_parent, key_name):
            return 'DECORATE_ANIMATE'
        return 'RADIOBUT_OFF'
    if abs(keyed_value - current_value) <= 0.0001:
        return 'DECORATE_KEYFRAME'
    return 'KEY_DEHLT'

def screen_is_playing():
    """判断当前视口是否处于动画播放状态"""
    try:
        return bpy.context.screen.is_animation_playing
    except:
        return False

def check_and_sync_sk_items(mesh):
    """保持 mesh.sk_items 与 mesh.shape_keys 完美同步"""
    if not mesh.shape_keys:
        if len(mesh.sk_items) > 0:
            mesh.sk_items.clear()
        return
    cleanup_slider_value_fcurves(mesh)
    kb_names = [kb.name for kb in mesh.shape_keys.key_blocks if kb.name != "Basis"]
    item_names = [item.name for item in mesh.sk_items]
    if kb_names != item_names:
        cat_cache = {item.name: item.category for item in mesh.sk_items}
        sel_cache = {item.name: item.selected for item in mesh.sk_items}
        preserved_names = [name for name in item_names if name in kb_names]
        appended_names = [name for name in kb_names if name not in preserved_names]
        final_names = preserved_names + appended_names
        mesh.sk_items.clear()
        for name in final_names:
            item = mesh.sk_items.add()
            item.name = name
            item.category = cat_cache.get(name, "")
            item.selected = sel_cache.get(name, False)
    sync_sk_item_slider_values(mesh)


def apply_value_to_shapekey(mesh, key_blocks, key_name, value, mgr):
    if key_name not in key_blocks:
        return []

    affected_names = []
    key_blocks[key_name].value = value
    set_sk_item_slider_value(mesh, key_name, value)
    affected_names.append(key_name)

    if mgr.mirror_mode:
        mirror_name_value = mirror_name(key_name)
        if mirror_name_value and mirror_name_value in key_blocks:
            key_blocks[mirror_name_value].value = value
            set_sk_item_slider_value(mesh, mirror_name_value, value)
            affected_names.append(mirror_name_value)

    return affected_names


def upsert_shape_key_keyframe(shape_keys, key_name, frame, value):
    data_path = f'key_blocks["{key_name}"].value'
    action = shape_keys.animation_data.action if shape_keys.animation_data else None
    if action:
        for fcurve in action.fcurves:
            if fcurve.data_path != data_path:
                continue
            for kp in fcurve.keyframe_points:
                if abs(kp.co[0] - frame) < 0.01:
                    kp.co[1] = value
                    fcurve.update()
                    return
            break
    shape_keys.keyframe_insert(data_path=data_path, frame=frame)


def get_shapekey_slider_value(self):
    mesh = self.id_data
    if not mesh or not mesh.shape_keys:
        return 0.0

    kb = mesh.shape_keys.key_blocks.get(self.name)
    if not kb:
        return 0.0

    return float(kb.value)


def set_shapekey_slider_value(self, value):
    global _syncing_slider_values

    if _syncing_slider_values:
        return

    mesh = self.id_data
    if not mesh or not mesh.shape_keys:
        return

    key_blocks = mesh.shape_keys.key_blocks
    if self.name not in key_blocks:
        return

    context = bpy.context
    mgr = getattr(context.window_manager, "sk_manager", None) if context else None
    if mgr is None:
        try:
            mgr = bpy.context.window_manager.sk_manager
        except Exception:
            mgr = None
    if mgr is None:
        return

    affected_names = set(apply_value_to_shapekey(mesh, key_blocks, self.name, value, mgr))

    # 勾选多个后，拖动其中一个已勾选项时，其他勾选项同步采用相同数值。
    if self.selected:
        for item in mesh.sk_items:
            if item.name == self.name or not item.selected:
                continue
            for affected_name in apply_value_to_shapekey(mesh, key_blocks, item.name, value, mgr):
                affected_names.add(affected_name)

    if mgr.auto_keyframe:
        scene = context.scene if context and context.scene else getattr(bpy.context, "scene", None)
        if scene:
            for affected_name in affected_names:
                upsert_shape_key_keyframe(mesh.shape_keys, affected_name, scene.frame_current, value)


def on_auto_keyframe_toggled(self, context):
    return None


def on_active_item_index_changed(self, context):
    obj = None
    try:
        obj = context.active_object if context else bpy.context.active_object
    except Exception:
        obj = None

    if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
        return
    if 0 <= self.active_item_index < len(obj.data.sk_items):
        self.active_item_name = obj.data.sk_items[self.active_item_index].name


def tag_redraw_all_areas():
    try:
        wm = bpy.context.window_manager
    except Exception:
        return

    for window in wm.windows:
        screen = window.screen
        if not screen:
            continue
        for area in screen.areas:
            area.tag_redraw()


def sync_shapekey_ui_for_object(obj, depsgraph=None):
    if obj.type != 'MESH' or not obj.data or not obj.data.shape_keys:
        return

    mesh = obj.data
    check_and_sync_sk_items(mesh)
    sync_active_item_by_name(mesh, get_current_manager())

    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None

    source_key_blocks = mesh.shape_keys.key_blocks
    if depsgraph is not None:
        try:
            eval_obj = obj.evaluated_get(depsgraph)
            eval_shape_keys = eval_obj.data.shape_keys if eval_obj and eval_obj.data else None
            if eval_shape_keys:
                source_key_blocks = eval_shape_keys.key_blocks
        except Exception:
            pass

    sync_sk_item_slider_values(mesh, source_key_blocks=source_key_blocks)


def sync_shapekey_ui_for_scene(scene, depsgraph=None):
    for obj in scene.objects:
        try:
            sync_shapekey_ui_for_object(obj, depsgraph=depsgraph)
        except Exception:
            pass

    tag_redraw_all_areas()


@bpy.app.handlers.persistent
def shapekey_monitor_handler(scene, depsgraph):
    """
    Depsgraph 监听器：仅负责同步列表内容和代理滑块值。
    自动 K 帧完全由插件自己的代理滑块回调负责。
    """
    if screen_is_playing():
        return
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph)


@bpy.app.handlers.persistent
def shapekey_frame_change_handler(scene, depsgraph=None):
    if screen_is_playing():
        return
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph)


# ==========================================
# 3. 属性组定义 (Property Groups)
# ==========================================

class ShapeKeyItem(bpy.types.PropertyGroup):
    """存储在 Mesh 下的形态键元数据"""
    name: bpy.props.StringProperty()
    category: bpy.props.StringProperty(default="")
    selected: bpy.props.BoolProperty(default=False)
    slider_value: bpy.props.FloatProperty(
        name="Value",
        min=-100.0,
        max=100.0,
        soft_min=0.0,
        soft_max=1.0,
        precision=3,
        get=get_shapekey_slider_value,
        set=set_shapekey_slider_value
    )

def on_category_name_changed(self, context):
    """更新监听器：重命名分类时自动重映射形态键归属名"""
    mesh = self.id_data
    if not mesh or not hasattr(mesh, "sk_items"):
        return
    old_name = self.last_name
    new_name = self.name
    if old_name == "":
        self.last_name = new_name
        return
    if old_name != new_name:
        for item in mesh.sk_items:
            if item.category == old_name:
                item.category = new_name
        self.last_name = new_name

class ShapeKeyCategoryItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Category Name",
        default="New Category",
        update=on_category_name_changed
    )
    last_name: bpy.props.StringProperty(default="")
    match_pattern: bpy.props.StringProperty(
        name="Match Pattern",
        default="*",
        description="Supports wildcard patterns (e.g. *[Eye] or *Mouth*)"
    )

class MeshShapeKeyManager(bpy.types.PropertyGroup):
    """存储在 WindowManager 级别的 UI 控制器数据。"""
    active_category_index: bpy.props.IntProperty(default=0)
    active_item_index: bpy.props.IntProperty(default=0, update=on_active_item_index_changed)
    active_item_name: bpy.props.StringProperty(default="")
    auto_keyframe: bpy.props.BoolProperty(
        name="Auto Keyframe",
        description="Automatically insert keyframe when shape key value changes",
        default=False,
        update=on_auto_keyframe_toggled
    )
    mirror_mode: bpy.props.BoolProperty(
        name="Mirror Mode",
        description="Automatically mirror value adjustments and keyframes to opposite side",
        default=False
    )
    show_only_keyed: bpy.props.BoolProperty(
        name="Show Only Keyed",
        description="Only show shape keys that have at least one keyframe",
        default=False
    )
    reorder_mode: bpy.props.BoolProperty(
        name="Move Mode",
        description="Enable fast reposition mode for shape keys",
        default=False
    )
    search_text: bpy.props.StringProperty(
        name="Search",
        description="Filter shape keys by name",
        default=""
    )


# ==========================================
# 4. 自定义 UI 列表 (UI Lists)
# ==========================================

class MESH_UL_sk_categories(bpy.types.UIList):
    """分类管理列表"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon='FILE_FOLDER')
            row.prop(item, "match_pattern", text=_("Pattern"))
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon='FILE_FOLDER')

class MESH_UL_filtered_shapekeys(bpy.types.UIList):
    """过滤后的形态键渲染控制列表"""
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = context.active_object
        if not obj or not obj.data or not obj.data.shape_keys:
            return
        kb = obj.data.shape_keys.key_blocks.get(item.name)
        if not kb:
            return
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "selected", text="")
            mgr = context.window_manager.sk_manager
            if mgr.reorder_mode:
                before = row.operator("sk_helper.move_active_shapekey_to", text="", icon='TRIA_UP_BAR', emboss=True)
                before.target_name = item.name
                before.position = 'BEFORE'
            row.label(text=item.name, icon='RESTRICT_SELECT_OFF' if index == mgr.active_item_index else 'BLANK1')
            row.prop(item, "slider_value", text="", slider=True)
            if mgr.reorder_mode:
                after = row.operator("sk_helper.move_active_shapekey_to", text="", icon='TRIA_DOWN_BAR', emboss=True)
                after.target_name = item.name
                after.position = 'AFTER'
            icon_type = get_keyframe_button_icon(
                obj.data.shape_keys,
                item.name,
                context.scene.frame_current,
                kb.value,
            )
            op = row.operator("sk_helper.keyframe_single", text="", icon=icon_type, emboss=False)
            op.shapekey_name = item.name

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        filter_order = []
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return filter_flags, filter_order
        mgr = context.window_manager.sk_manager
        categories = obj.data.sk_categories
        if not categories or mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
            return filter_flags, filter_order
        active_cat = categories[mgr.active_category_index]
        cat_name = active_cat.name
        search_text = mgr.search_text.strip().lower()
        for i, item in enumerate(items):
            if item.category != cat_name:
                filter_flags[i] &= ~self.bitflag_filter_item
                continue
            if search_text and search_text not in item.name.lower():
                filter_flags[i] &= ~self.bitflag_filter_item
                continue
            if mgr.show_only_keyed and not has_any_keyframes(obj.data.shape_keys, item.name):
                filter_flags[i] &= ~self.bitflag_filter_item
        return filter_flags, filter_order


# ==========================================
# 5. 操作算子 (Operators)
# ==========================================

class SK_OT_add_category(bpy.types.Operator):
    bl_idname = "sk_helper.add_category"
    bl_label = "Add Category"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        cat = obj.data.sk_categories.add()
        cat.name = f"New Category {len(obj.data.sk_categories)}"
        context.window_manager.sk_manager.active_category_index = len(obj.data.sk_categories) - 1
        return {'FINISHED'}

class SK_OT_remove_category(bpy.types.Operator):
    bl_idname = "sk_helper.remove_category"
    bl_label = "Remove Category"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        categories = obj.data.sk_categories
        mgr = context.window_manager.sk_manager
        if not categories:
            return {'CANCELLED'}
        idx = mgr.active_category_index
        cat_name = categories[idx].name
        for item in obj.data.sk_items:
            if item.category == cat_name:
                item.category = ""
        categories.remove(idx)
        mgr.active_category_index = min(max(0, idx - 1), len(categories) - 1)
        return {'FINISHED'}

class SK_OT_reorder_category(bpy.types.Operator):
    """排序算子：向上/向下移动分类顺序"""
    bl_idname = "sk_helper.reorder_category"
    bl_label = "Move Category"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")]
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and len(obj.data.sk_categories) > 1

    def execute(self, context):
        obj = context.active_object
        categories = obj.data.sk_categories
        mgr = context.window_manager.sk_manager
        idx = mgr.active_category_index
        if idx < 0 or idx >= len(categories):
            return {'CANCELLED'}
        if self.direction == 'UP':
            if idx == 0:
                return {'CANCELLED'}
            categories.move(idx, idx - 1)
            mgr.active_category_index = idx - 1
        elif self.direction == 'DOWN':
            if idx == len(categories) - 1:
                return {'CANCELLED'}
            categories.move(idx, idx + 1)
            mgr.active_category_index = idx + 1
        return {'FINISHED'}

class SK_OT_reorder_shapekey(bpy.types.Operator):
    """在当前分类的可见列表中调整形态键顺序。"""
    bl_idname = "sk_helper.reorder_shapekey"
    bl_label = "Move Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")]
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            return False
        mgr = context.window_manager.sk_manager
        return len(get_visible_category_item_indices(obj, mgr)) > 1

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        visible_indices = get_visible_category_item_indices(obj, mgr)
        active_index = mgr.active_item_index
        if active_index not in visible_indices:
            return {'CANCELLED'}

        pos = visible_indices.index(active_index)
        if self.direction == 'UP':
            if pos == 0:
                return {'CANCELLED'}
            target_index = visible_indices[pos - 1]
        else:
            if pos >= len(visible_indices) - 1:
                return {'CANCELLED'}
            target_index = visible_indices[pos + 1]

        obj.data.sk_items.move(active_index, target_index)
        mgr.active_item_index = target_index
        if 0 <= target_index < len(obj.data.sk_items):
            mgr.active_item_name = obj.data.sk_items[target_index].name
        return {'FINISHED'}

class SK_OT_move_active_shapekey_to(bpy.types.Operator):
    """将当前活动项，或当前勾选组，直接移动到目标项前后。"""
    bl_idname = "sk_helper.move_active_shapekey_to"
    bl_label = "Move Shape Key"
    bl_options = {'REGISTER', 'UNDO'}

    target_name: bpy.props.StringProperty()
    position: bpy.props.EnumProperty(
        items=[('BEFORE', "Before", ""), ('AFTER', "After", "")]
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            return False
        mgr = context.window_manager.sk_manager
        return 0 <= mgr.active_item_index < len(obj.data.sk_items)

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        visible_indices = get_visible_category_item_indices(obj, mgr)
        if not visible_indices:
            return {'CANCELLED'}

        all_names = [item.name for item in obj.data.sk_items]
        visible_names = [obj.data.sk_items[i].name for i in visible_indices]
        active_name = obj.data.sk_items[mgr.active_item_index].name if 0 <= mgr.active_item_index < len(obj.data.sk_items) else None
        selected_names = [obj.data.sk_items[i].name for i in visible_indices if obj.data.sk_items[i].selected]

        moving_names = selected_names if selected_names else ([active_name] if active_name else [])
        if not moving_names:
            return {'CANCELLED'}
        if self.target_name in moving_names:
            return {'CANCELLED'}
        if self.target_name not in visible_names:
            return {'CANCELLED'}

        visible_remaining = [name for name in visible_names if name not in moving_names]
        target_pos = visible_remaining.index(self.target_name)
        insert_pos = target_pos if self.position == 'BEFORE' else target_pos + 1
        reordered_visible_names = visible_remaining[:insert_pos] + moving_names + visible_remaining[insert_pos:]

        for collection_index, name in zip(visible_indices, reordered_visible_names):
            all_names[collection_index] = name

        reorder_sk_items_by_names(obj.data, all_names)
        if active_name:
            mgr.active_item_name = active_name
            mgr.active_item_index = get_sk_item_index_by_name(obj.data, active_name)
        return {'FINISHED'}

class SK_OT_move_selected_shapekeys(bpy.types.Operator):
    """将当前可见列表中的多个勾选项整体移动一个位置。"""
    bl_idname = "sk_helper.move_selected_shapekeys"
    bl_label = "Move Selected Shape Keys"
    bl_options = {'REGISTER', 'UNDO'}

    direction: bpy.props.EnumProperty(
        items=[('UP', "Up", ""), ('DOWN', "Down", "")]
    )

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            return False
        mgr = context.window_manager.sk_manager
        visible_indices = get_visible_category_item_indices(obj, mgr)
        return any(obj.data.sk_items[i].selected for i in visible_indices)

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        visible_indices = get_visible_category_item_indices(obj, mgr)
        if not visible_indices:
            return {'CANCELLED'}

        all_names = [item.name for item in obj.data.sk_items]
        active_name = obj.data.sk_items[mgr.active_item_index].name if 0 <= mgr.active_item_index < len(obj.data.sk_items) else None
        visible_names = [obj.data.sk_items[i].name for i in visible_indices]
        selected_names = {obj.data.sk_items[i].name for i in visible_indices if obj.data.sk_items[i].selected}
        if not selected_names:
            return {'CANCELLED'}

        reordered_visible_names = visible_names[:]
        moved = False

        if self.direction == 'UP':
            for i in range(1, len(reordered_visible_names)):
                if reordered_visible_names[i] in selected_names and reordered_visible_names[i - 1] not in selected_names:
                    reordered_visible_names[i - 1], reordered_visible_names[i] = reordered_visible_names[i], reordered_visible_names[i - 1]
                    moved = True
        else:
            for i in range(len(reordered_visible_names) - 2, -1, -1):
                if reordered_visible_names[i] in selected_names and reordered_visible_names[i + 1] not in selected_names:
                    reordered_visible_names[i], reordered_visible_names[i + 1] = reordered_visible_names[i + 1], reordered_visible_names[i]
                    moved = True

        if not moved:
            return {'CANCELLED'}

        for collection_index, name in zip(visible_indices, reordered_visible_names):
            all_names[collection_index] = name

        reorder_sk_items_by_names(obj.data, all_names)

        if active_name:
            mgr.active_item_name = active_name
            mgr.active_item_index = get_sk_item_index_by_name(obj.data, active_name)

        return {'FINISHED'}

class SK_OT_auto_match(bpy.types.Operator):
    bl_idname = "sk_helper.auto_match"
    bl_label = "Auto Match Category"
    bl_description = "Automatically assign shape keys to categories based on patterns"
    bl_options = {'REGISTER', 'UNDO'}

    target_all: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            self.report({'WARNING'}, _("Selected mesh has no Shape Keys"))
            return {'CANCELLED'}
        check_and_sync_sk_items(obj.data)
        categories = obj.data.sk_categories
        if not categories:
            self.report({'WARNING'}, "No categories defined")
            return {'CANCELLED'}
        sk_items = obj.data.sk_items
        mgr = context.window_manager.sk_manager
        if not self.target_all:
            if mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
                return {'CANCELLED'}
            cats_to_match = [categories[mgr.active_category_index]]
        else:
            cats_to_match = list(categories)
        matched_count = 0
        for cat in cats_to_match:
            pattern = cat.match_pattern
            if not pattern:
                continue
            for item in sk_items:
                if match_pattern(item.name, pattern):
                    item.category = cat.name
                    matched_count += 1
        self.report({'INFO'}, f"Successfully classified {matched_count} shape keys.")
        return {'FINISHED'}

class SK_OT_assign_category(bpy.types.Operator):
    bl_idname = "sk_helper.assign_category"
    bl_label = "Move Selected to Active Category"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        categories = obj.data.sk_categories
        mgr = context.window_manager.sk_manager
        if not categories or mgr.active_category_index < 0:
            return {'CANCELLED'}
        active_cat = categories[mgr.active_category_index]
        count = 0
        for item in obj.data.sk_items:
            if item.selected:
                item.category = active_cat.name
                item.selected = False
                count += 1
        self.report({'INFO'}, f"Moved {count} shape keys to category '{active_cat.name}'")
        return {'FINISHED'}

class SK_OT_clear_category(bpy.types.Operator):
    bl_idname = "sk_helper.clear_category"
    bl_label = "Remove Selected from Category"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        count = 0
        for item in obj.data.sk_items:
            if item.selected:
                item.category = ""
                item.selected = False
                count += 1
        self.report({'INFO'}, f"Removed {count} shape keys from category.")
        return {'FINISHED'}

class SK_OT_keyframe_single(bpy.types.Operator):
    bl_idname = "sk_helper.keyframe_single"
    bl_label = "Keyframe Single"
    bl_options = {'REGISTER', 'UNDO'}

    shapekey_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            return {'CANCELLED'}
        key_blocks = obj.data.shape_keys.key_blocks
        if self.shapekey_name not in key_blocks:
            return {'CANCELLED'}
        kb = key_blocks[self.shapekey_name]
        frame = context.scene.frame_current
        has_key = get_keyframe_value_on_current_frame(obj.data.shape_keys, self.shapekey_name, frame) is not None
        if has_key:
            action = obj.data.shape_keys.animation_data.action if obj.data.shape_keys.animation_data else None
            if action:
                data_path = f'key_blocks["{self.shapekey_name}"].value'
                for fcurve in action.fcurves:
                    if fcurve.data_path == data_path:
                        for kp in list(fcurve.keyframe_points):
                            if abs(kp.co[0] - frame) < 0.01:
                                fcurve.keyframe_points.remove(kp)
                        if len(fcurve.keyframe_points) == 0:
                            action.fcurves.remove(fcurve)
                        break
        else:
            obj.data.shape_keys.keyframe_insert(
                data_path=f'key_blocks["{self.shapekey_name}"].value',
                frame=frame
            )
            mgr = context.window_manager.sk_manager
            if mgr.mirror_mode:
                m_name = mirror_name(self.shapekey_name)
                if m_name and m_name in key_blocks:
                    key_blocks[m_name].value = kb.value
                    set_sk_item_slider_value(obj.data, m_name, kb.value)
                    obj.data.shape_keys.keyframe_insert(
                        data_path=f'key_blocks["{m_name}"].value',
                        frame=frame
                    )
        context.area.tag_redraw()
        return {'FINISHED'}

class SK_OT_keyframe_batch(bpy.types.Operator):
    bl_idname = "sk_helper.keyframe_batch"
    bl_label = "Keyframe Selected Checked"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            return {'CANCELLED'}
        key_blocks = obj.data.shape_keys.key_blocks
        frame = context.scene.frame_current
        mgr = context.window_manager.sk_manager
        count = 0
        for item in obj.data.sk_items:
            if item.selected and item.name in key_blocks:
                kb = key_blocks[item.name]
                obj.data.shape_keys.keyframe_insert(
                    data_path=f'key_blocks["{kb.name}"].value',
                    frame=frame
                )
                count += 1
                if mgr.mirror_mode:
                    m_name = mirror_name(kb.name)
                    if m_name and m_name in key_blocks:
                        key_blocks[m_name].value = kb.value
                        set_sk_item_slider_value(obj.data, m_name, kb.value)
                        obj.data.shape_keys.keyframe_insert(
                            data_path=f'key_blocks["{m_name}"].value',
                            frame=frame
                        )
        self.report({'INFO'}, f"Keyframed {count} shape keys.")
        return {'FINISHED'}

class SK_OT_select_all(bpy.types.Operator):
    bl_idname = "sk_helper.select_all"
    bl_label = "Select All"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(
        items=[
            ('SELECT', "Select All", ""),
            ('DESELECT', "Deselect All", ""),
            ('INVERT', "Invert Selection", "")
        ]
    )

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        categories = obj.data.sk_categories
        mgr = context.window_manager.sk_manager
        if not categories or mgr.active_category_index < 0:
            return {'CANCELLED'}
        active_cat = categories[mgr.active_category_index]
        for item in obj.data.sk_items:
            if item.category == active_cat.name:
                if self.action == 'SELECT':
                    item.selected = True
                elif self.action == 'DESELECT':
                    item.selected = False
                elif self.action == 'INVERT':
                    item.selected = not item.selected
        return {'FINISHED'}

class SK_OT_reset_selected(bpy.types.Operator):
    bl_idname = "sk_helper.reset_selected"
    bl_label = "Reset Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            return {'CANCELLED'}
        key_blocks = obj.data.shape_keys.key_blocks
        mgr = context.window_manager.sk_manager
        for item in obj.data.sk_items:
            if item.selected and item.name in key_blocks:
                kb = key_blocks[item.name]
                kb.value = 0.0
                set_sk_item_slider_value(obj.data, kb.name, 0.0)
                if mgr.auto_keyframe:
                    obj.data.shape_keys.keyframe_insert(
                        data_path=f'key_blocks["{kb.name}"].value',
                        frame=context.scene.frame_current
                    )
                if mgr.mirror_mode:
                    m_name = mirror_name(kb.name)
                    if m_name and m_name in key_blocks:
                        key_blocks[m_name].value = 0.0
                        set_sk_item_slider_value(obj.data, m_name, 0.0)
                        if mgr.auto_keyframe:
                            obj.data.shape_keys.keyframe_insert(
                                data_path=f'key_blocks["{m_name}"].value',
                                frame=context.scene.frame_current
                            )
        return {'FINISHED'}

# ==========================================
# 6. 预设导入导出 (JSON Presets)
# ==========================================

class SK_OT_export_preset(bpy.types.Operator, ExportHelper):
    bl_idname = "sk_helper.export_preset"
    bl_label = "Export Preset"
    bl_description = "Export current mesh categories and assignments to a JSON file"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}
        categories = obj.data.sk_categories
        preset_data = {
            "preset_version": "1.8",
            "mesh_name": obj.data.name,
            "categories": []
        }
        for cat in categories:
            keys = [item.name for item in obj.data.sk_items if item.category == cat.name]
            preset_data["categories"].append({
                "name": cat.name,
                "match_pattern": cat.match_pattern,
                "assigned_keys": keys
            })
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=4, ensure_ascii=False)
            self.report({'INFO'}, f"Preset successfully exported to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export preset: {str(e)}")
            return {'CANCELLED'}
        return {'FINISHED'}

class SK_OT_import_preset(bpy.types.Operator, ImportHelper):
    bl_idname = "sk_helper.import_preset"
    bl_label = "Import Preset"
    bl_description = "Import categories and assignments from a JSON file"

    filename_ext = ".json"
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH':
            return {'CANCELLED'}
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to read preset file: {str(e)}")
            return {'CANCELLED'}
        obj.data.sk_categories.clear()
        check_and_sync_sk_items(obj.data)
        for item in obj.data.sk_items:
            item.category = ""
        categories_data = preset_data.get("categories", [])
        for cat_data in categories_data:
            cat = obj.data.sk_categories.add()
            cat.name = cat_data.get("name", "New Category")
            cat.match_pattern = cat_data.get("match_pattern", "")
            for key_name in cat_data.get("assigned_keys", []):
                for item in obj.data.sk_items:
                    if item.name == key_name:
                        item.category = cat.name
                        break
            pattern = cat.match_pattern
            if pattern:
                for item in obj.data.sk_items:
                    if item.category == "" and match_pattern(item.name, pattern):
                        item.category = cat.name
        reorder_sk_items_from_preset(obj.data, categories_data)
        context.window_manager.sk_manager.active_category_index = 0
        self.report({'INFO'}, f"Imported {len(categories_data)} categories successfully.")
        return {'FINISHED'}


# ==========================================
# 7. UI 主面板布局
# ==========================================

class VIEW3D_PT_sk_organizer(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shape Key Classification'
    bl_label = 'Shape Key Classification'

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        if not obj or obj.type != 'MESH':
            layout.label(text=_("Please select a Mesh object"), icon='INFO')
            return
        if not obj.data.shape_keys:
            layout.label(text=_("Selected mesh has no Shape Keys"), icon='INFO')
            return

        mgr = context.window_manager.sk_manager
        categories = obj.data.sk_categories

        # 1. 预设
        box = layout.box()
        box.label(text=_("Presets Manager"), icon='PRESET')
        row = box.row(align=True)
        row.operator("sk_helper.import_preset", text=_("Import Preset"), icon='IMPORT')
        row.operator("sk_helper.export_preset", text=_("Export Preset"), icon='EXPORT')

        # 2. 分类
        box = layout.box()
        box.label(text=_("Categories Manager"), icon='FILE_FOLDER')
        row = box.row()
        row.template_list("MESH_UL_sk_categories", "", obj.data, "sk_categories", mgr, "active_category_index")
        col = row.column(align=True)
        col.operator("sk_helper.add_category", text="", icon='ADD')
        col.operator("sk_helper.remove_category", text="", icon='REMOVE')
        col.operator("sk_helper.reorder_category", text="", icon='TRIA_UP').direction = 'UP'
        col.operator("sk_helper.reorder_category", text="", icon='TRIA_DOWN').direction = 'DOWN'
        row = box.row(align=True)
        row.operator("sk_helper.auto_match", text=_("Auto Match Active"), icon='FILE_REFRESH').target_all = False
        row.operator("sk_helper.auto_match", text=_("Auto Match All"), icon='FILE_REFRESH').target_all = True

        # 3. 过滤器控制面板
        box = layout.box()
        box.label(text=_("Shape Keys in Category"), icon='SHAPEKEY_DATA')
        if len(categories) > 0 and 0 <= mgr.active_category_index < len(categories):
            active_cat = categories[mgr.active_category_index]
            box.label(text=f"{_('Active Category:')} {active_cat.name}", icon='FOLDER_REDIRECT')
            row = box.row(align=True)
            row.prop(mgr, "search_text", text="", icon='VIEWZOOM')
            row = box.row(align=True)
            row.prop(mgr, "show_only_keyed", text=_("Show Only Keyed"), toggle=True, icon='DECORATE_KEYFRAME')
            row.prop(mgr, "reorder_mode", text=_("Move Mode"), toggle=True, icon='ARROW_LEFTRIGHT')
            if mgr.reorder_mode:
                row = box.row(align=True)
                row.operator("sk_helper.move_selected_shapekeys", text=_("Move Selected Up"), icon='TRIA_UP').direction = 'UP'
                row.operator("sk_helper.move_selected_shapekeys", text=_("Move Selected Down"), icon='TRIA_DOWN').direction = 'DOWN'
            box.template_list("MESH_UL_filtered_shapekeys", "", obj.data, "sk_items", mgr, "active_item_index")
            row = box.row(align=True)
            row.label(text=_("Batch Select:"))
            op_sel = row.operator("sk_helper.select_all", text=_("Select All"))
            op_sel.action = 'SELECT'
            op_desel = row.operator("sk_helper.select_all", text=_("Deselect All"))
            op_desel.action = 'DESELECT'
            op_inv = row.operator("sk_helper.select_all", text=_("Invert Selection"))
            op_inv.action = 'INVERT'
            row = box.row(align=True)
            row.operator("sk_helper.assign_category", text=_("Move Checked Here"), icon='ADD')
            row.operator("sk_helper.clear_category", text=_("Remove Checked"), icon='REMOVE')
            box_anim = box.box()
            box_anim.label(text=_("Animation Actions"), icon='ACTION')
            row = box_anim.row(align=True)
            row.operator("sk_helper.keyframe_batch", text=_("Keyframe Selected Checked"), icon='DECORATE_KEYFRAME')
            row.operator("sk_helper.reset_selected", text=_("Reset Selected to 0"), icon='LOOP_BACK')
        else:
            box.label(text=_("Please create or select a category"), icon='INFO')

        # 4. 开关
        box = layout.box()
        box.label(text=_("Global Option Configuration"), icon='PREFERENCES')
        col = box.column(align=True)
        col.prop(mgr, "auto_keyframe", text=_("Auto Keyframe"), icon='REC', toggle=True)
        col.prop(mgr, "mirror_mode", text=_("Mirror Mode"), icon='MOD_MIRROR', toggle=True)


# ==========================================
# 8. 注册与销毁 (Register/Unregister)
# ==========================================

classes = [
    ShapeKeyItem,
    MeshShapeKeyManager,
    ShapeKeyCategoryItem,
    MESH_UL_sk_categories,
    MESH_UL_filtered_shapekeys,
    SK_OT_add_category,
    SK_OT_remove_category,
    SK_OT_reorder_category,
    SK_OT_reorder_shapekey,
    SK_OT_move_active_shapekey_to,
    SK_OT_move_selected_shapekeys,
    SK_OT_auto_match,
    SK_OT_assign_category,
    SK_OT_clear_category,
    SK_OT_keyframe_single,
    SK_OT_keyframe_batch,
    SK_OT_select_all,
    SK_OT_reset_selected,
    SK_OT_export_preset,
    SK_OT_import_preset,
    VIEW3D_PT_sk_organizer,
]

def register():
    try:
        unregister()
    except Exception:
        pass
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    try:
        bpy.app.translations.register(__name__, translations_dict)
    except Exception as e:
        print(f"Translations register error: {e}")
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"Register failed: {cls} - {e}")
    try:
        bpy.types.Mesh.sk_items = bpy.props.CollectionProperty(type=ShapeKeyItem)
        bpy.types.Mesh.sk_categories = bpy.props.CollectionProperty(type=ShapeKeyCategoryItem)
        bpy.types.WindowManager.sk_manager = bpy.props.PointerProperty(type=MeshShapeKeyManager)
    except Exception as e:
        print(f"Register properties failed: {e}")
    if shapekey_monitor_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(shapekey_monitor_handler)
    if shapekey_frame_change_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(shapekey_frame_change_handler)

def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    if shapekey_monitor_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(shapekey_monitor_handler)
    if shapekey_frame_change_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(shapekey_frame_change_handler)
    try:
        if hasattr(bpy.types.Mesh, "sk_items"):
            del bpy.types.Mesh.sk_items
        if hasattr(bpy.types.Mesh, "sk_categories"):
            del bpy.types.Mesh.sk_categories
        if hasattr(bpy.types.WindowManager, "sk_manager"):
            del bpy.types.WindowManager.sk_manager
    except Exception:
        pass
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass

if __name__ == "__main__":
    register()
