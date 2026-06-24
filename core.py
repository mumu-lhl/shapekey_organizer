import bpy
import re

_syncing_slider_values = False
_syncing_all_selection = False
_syncing_native_value_changes = False
_native_shape_key_value_cache = {}

MIRROR_NAME_PAIRS = (
    ("_L", "_R"), ("_l", "_r"),
    (".L", ".R"), (".l", ".r"),
    ("Left", "Right"), ("left", "right"),
    ("LEFT", "RIGHT"), ("_Left", "_Right"), ("_left", "_right"),
)

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
    for left, right in MIRROR_NAME_PAIRS:
        if name.endswith(left):
            return name[:-len(left)] + right
        if name.endswith(right):
            return name[:-len(right)] + left
        if left in name:
            return name.replace(left, right)
        if right in name:
            return name.replace(right, left)
    return None


def mirror_side(name):
    """Return the side recognized by :func:`mirror_name` for a shape key."""
    for left, right in MIRROR_NAME_PAIRS:
        if name.endswith(left) or left in name:
            return 'LEFT'
        if name.endswith(right) or right in name:
            return 'RIGHT'
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

    alias_cache = {item.name: item.alias for item in mesh.sk_items}
    cat_cache = {item.name: item.category for item in mesh.sk_items}
    sel_cache = {item.name: item.selected for item in mesh.sk_items}
    all_sel_cache = {item.name: item.all_selected for item in mesh.sk_items}

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
        item.alias = alias_cache.get(name, "")
        item.category = cat_cache.get(name, "")
        item.selected = sel_cache.get(name, False)
        item.all_selected = all_sel_cache.get(name, False)


def reorder_sk_items_by_names(mesh, ordered_names):
    alias_cache = {item.name: item.alias for item in mesh.sk_items}
    cat_cache = {item.name: item.category for item in mesh.sk_items}
    sel_cache = {item.name: item.selected for item in mesh.sk_items}
    all_sel_cache = {item.name: item.all_selected for item in mesh.sk_items}

    mesh.sk_items.clear()
    for name in ordered_names:
        item = mesh.sk_items.add()
        item.name = name
        item.alias = alias_cache.get(name, "")
        item.category = cat_cache.get(name, "")
        item.selected = sel_cache.get(name, False)
        item.all_selected = all_sel_cache.get(name, False)


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
        alias_cache = {item.name: item.alias for item in mesh.sk_items}
        cat_cache = {item.name: item.category for item in mesh.sk_items}
        sel_cache = {item.name: item.selected for item in mesh.sk_items}
        all_sel_cache = {item.name: item.all_selected for item in mesh.sk_items}
        preserved_names = [name for name in item_names if name in kb_names]
        appended_names = [name for name in kb_names if name not in preserved_names]
        final_names = preserved_names + appended_names
        mesh.sk_items.clear()
        for name in final_names:
            item = mesh.sk_items.add()
            item.name = name
            item.alias = alias_cache.get(name, "")
            item.category = cat_cache.get(name, "")
            item.selected = sel_cache.get(name, False)
            item.all_selected = all_sel_cache.get(name, False)
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


def _cache_native_shape_key_values(mesh):
    if not mesh.shape_keys:
        return {}
    values = {
        key_block.name: float(key_block.value)
        for key_block in mesh.shape_keys.key_blocks
        if key_block.name != "Basis"
    }
    _native_shape_key_value_cache[mesh.as_pointer()] = values
    return values


def sync_native_shape_key_value_changes(obj, mgr):
    """Apply plugin value-sync options after a native ShapeKey.value edit.

    The UI now draws the native property so Blender can display its keyed state.
    This handler restores the plugin's multi-select and mirror behavior without
    animating a proxy property. Native Auto Key handles the edited value itself.
    """
    global _syncing_native_value_changes

    mesh = obj.data
    if not mesh.shape_keys:
        return

    cache_key = mesh.as_pointer()
    current_values = {
        key_block.name: float(key_block.value)
        for key_block in mesh.shape_keys.key_blocks
        if key_block.name != "Basis"
    }
    previous_values = _native_shape_key_value_cache.get(cache_key)
    _native_shape_key_value_cache[cache_key] = current_values

    # The first observation establishes a baseline. Only direct changes on the
    # active mesh are treated as UI edits; other meshes may update via evaluation.
    if _syncing_native_value_changes or previous_values is None or bpy.context.active_object != obj:
        return

    changed_names = [
        name for name, value in current_values.items()
        if name in previous_values and abs(value - previous_values[name]) > 0.000001
    ]
    if not changed_names:
        return

    key_blocks = mesh.shape_keys.key_blocks
    _syncing_native_value_changes = True
    try:
        for key_name in changed_names:
            item = get_sk_item(mesh, key_name)
            if not item:
                continue
            value = current_values[key_name]
            apply_value_to_shapekey(mesh, key_blocks, key_name, value, mgr)

            if item.selected:
                for selected_item in mesh.sk_items:
                    if selected_item.name == key_name or not selected_item.selected:
                        continue
                    apply_value_to_shapekey(mesh, key_blocks, selected_item.name, value, mgr)

        # Do not keyframe from this depsgraph callback. It would become a
        # separate undo step from the native ShapeKey.value drag. Blender's
        # native Auto Key handles the directly edited value in the same undo
        # operation; this callback is limited to value synchronization.
    finally:
        _syncing_native_value_changes = False
        _cache_native_shape_key_values(mesh)


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



def on_all_selected_changed(self, context):
    """
    “所有形态键”列表的原生复选框变化回调。

    只维护 all-list 自己的 active/anchor 状态；不触碰 item.selected，
    因此不会影响当前分类列表里的动画K帧勾选。
    程序批量改 all_selected 时会用 _syncing_all_selection 跳过这里，
    避免一口气设置很多项时 anchor 被最后一个变化项污染。
    """
    global _syncing_all_selection
    if _syncing_all_selection:
        return

    mesh = self.id_data
    if not mesh or not hasattr(mesh, "sk_items"):
        return

    mgr = get_current_manager(context)
    if not mgr:
        return

    index = get_sk_item_index_by_name(mesh, self.name)
    if index < 0:
        return

    mgr.active_all_item_index = index
    mgr.active_all_item_name = self.name
    mgr.all_select_anchor_index = index
    mgr.all_select_anchor_name = self.name


def on_auto_keyframe_toggled(self, context):
    """Use Blender's native Auto Key for direct ShapeKey.value editing."""
    scene = context.scene if context else getattr(bpy.context, "scene", None)
    if scene and scene.tool_settings:
        scene.tool_settings.use_keyframe_insert_auto = self.auto_keyframe


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


def on_active_all_item_index_changed(self, context):
    """“所有形态键”列表的原生单选行变化回调。

    现在允许“只单击列表行、不点复选框”也作为插件的当前目标。
    注意：这个值来自 Blender UIList 的 active 行。用户已确认暂时接受滚动后
    active 行偶发滞后的问题，所以这里恢复同步 active_all_item_name，
    让“智能归类 / 智能移除分类”等按钮可用。

    复选框多选仍然只写 item.all_selected，不会同步到当前分类/K帧列表的 item.selected。
    """
    obj = None
    try:
        obj = context.active_object if context else bpy.context.active_object
    except Exception:
        obj = None

    if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
        return

    if 0 <= self.active_all_item_index < len(obj.data.sk_items):
        item = obj.data.sk_items[self.active_all_item_index]
        self.active_all_item_name = item.name
        self.all_select_anchor_index = self.active_all_item_index
        self.all_select_anchor_name = item.name


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


def sync_shapekey_ui_for_object(obj, depsgraph=None, process_native_value_changes=True):
    if obj.type != 'MESH' or not obj.data or not obj.data.shape_keys:
        return

    mesh = obj.data
    check_and_sync_sk_items(mesh)
    mgr = get_current_manager()
    sync_active_item_by_name(mesh, mgr)

    if process_native_value_changes and mgr:
        sync_native_shape_key_value_changes(obj, mgr)
    else:
        _cache_native_shape_key_values(mesh)

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


def sync_shapekey_ui_for_scene(scene, depsgraph=None, process_native_value_changes=True):
    for obj in scene.objects:
        try:
            sync_shapekey_ui_for_object(
                obj,
                depsgraph=depsgraph,
                process_native_value_changes=process_native_value_changes,
            )
        except Exception:
            pass

    tag_redraw_all_areas()


@bpy.app.handlers.persistent
def shapekey_monitor_handler(scene, depsgraph):
    """
    Depsgraph 监听器：同步列表，并处理原生形态键值的直接编辑。
    """
    if screen_is_playing():
        return
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph)


@bpy.app.handlers.persistent
def shapekey_frame_change_handler(scene, depsgraph=None):
    if screen_is_playing():
        return
    # Frame evaluation changes values without user edits; refresh the baseline
    # instead of treating those changes as a request to mirror or keyframe.
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph, process_native_value_changes=False)
