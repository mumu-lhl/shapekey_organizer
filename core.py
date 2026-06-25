import bpy
import re

_syncing_slider_values = False
_syncing_all_selection = False
_syncing_native_value_changes = False
_syncing_mirror_keyframes = False
_syncing_auto_keyframe_state = False
_native_shape_key_value_cache = {}
_native_frame_keyframe_cache = {}

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


def iter_action_fcurve_collections(action):
    if not action:
        return
    fcurves = getattr(action, "fcurves", None)
    if fcurves is not None:
        yield fcurves
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            for channelbag in getattr(strip, "channelbags", []):
                fcurves = getattr(channelbag, "fcurves", None)
                if fcurves is not None:
                    yield fcurves


def iter_action_fcurves(action):
    for fcurves in iter_action_fcurve_collections(action):
        for fcurve in fcurves:
            yield fcurve


def cleanup_slider_value_fcurves(mesh):
    if not mesh.animation_data or not mesh.animation_data.action:
        return
    action = mesh.animation_data.action
    for fcurves in iter_action_fcurve_collections(action):
        for fcurve in list(fcurves):
            if fcurve.data_path.startswith("sk_items[") and fcurve.data_path.endswith('].slider_value'):
                fcurves.remove(fcurve)


_action_keyframes_cache = {}
_frame_keyframe_cache = {}

def clear_keyframe_caches():
    _action_keyframes_cache.clear()
    _frame_keyframe_cache.clear()


def _cache_keyframes_on_frame(shape_keys, frame):
    action = shape_keys.animation_data.action if shape_keys.animation_data else None
    if not action:
        return {}
    return get_frame_keyframe_values(action, frame)


def _store_native_frame_keyframes(mesh, frame):
    if not mesh.shape_keys:
        return {}
    values = dict(_cache_keyframes_on_frame(mesh.shape_keys, frame))
    action = mesh.shape_keys.animation_data.action if mesh.shape_keys.animation_data else None
    cache_key = (mesh.as_pointer(), action.as_pointer() if action else 0, round(frame, 2))
    _native_frame_keyframe_cache[cache_key] = values
    return values

def get_action_keyframes(action):
    if not action:
        return set()
    action_ptr = action.as_pointer()
    if action_ptr in _action_keyframes_cache:
        return _action_keyframes_cache[action_ptr]
        
    any_keyframes = set()
    for fcurve in iter_action_fcurves(action):
        if len(fcurve.keyframe_points) == 0:
            continue
        dp = fcurve.data_path
        if dp.startswith('key_blocks["') and dp.endswith('"].value'):
            parts = dp.split('"')
            if len(parts) >= 2:
                any_keyframes.add(parts[1])
                
    _action_keyframes_cache[action_ptr] = any_keyframes
    return any_keyframes

def get_frame_keyframe_values(action, frame):
    if not action:
        return {}
    action_ptr = action.as_pointer()
    frame_key = round(frame, 2)
    cache_key = (action_ptr, frame_key)
    
    if cache_key in _frame_keyframe_cache:
        return _frame_keyframe_cache[cache_key]
        
    keyed_on_frame = {}
    for fcurve in iter_action_fcurves(action):
        dp = fcurve.data_path
        if dp.startswith('key_blocks["') and dp.endswith('"].value'):
            parts = dp.split('"')
            if len(parts) >= 2:
                name = parts[1]
                for kp in fcurve.keyframe_points:
                    if abs(kp.co[0] - frame) < 0.01:
                        keyed_on_frame[name] = kp.co[1]
                        break
                        
    _frame_keyframe_cache[cache_key] = keyed_on_frame
    return keyed_on_frame

def get_keyed_shape_key_names(key_block_parent):
    if not key_block_parent or not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return set()
    return get_action_keyframes(key_block_parent.animation_data.action)

def get_keyframe_value_on_current_frame(key_block_parent, key_name, frame):
    if not key_block_parent or not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return None
    values = get_frame_keyframe_values(key_block_parent.animation_data.action, frame)
    return values.get(key_name)

def has_any_keyframes(key_block_parent, key_name):
    if not key_block_parent or not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return False
    return key_name in get_action_keyframes(key_block_parent.animation_data.action)

def get_visible_category_item_indices(obj, mgr):
    categories = obj.data.sk_categories
    if not categories or mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
        return []

    active_cat = categories[mgr.active_category_index]
    result = []
    keyed_names = get_keyed_shape_key_names(obj.data.shape_keys) if mgr.show_only_keyed else None
    for index, item in enumerate(obj.data.sk_items):
        if item.category != active_cat.name:
            continue
        if mgr.show_only_keyed and (not keyed_names or item.name not in keyed_names):
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
            return True
        return False
    kb_names = [kb.name for kb in mesh.shape_keys.key_blocks if kb.name != "Basis"]
    item_names = [item.name for item in mesh.sk_items]
    if kb_names != item_names:
        cleanup_slider_value_fcurves(mesh)
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
        return True
    return False


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
        for fcurve in iter_action_fcurves(action):
            if fcurve.data_path != data_path:
                continue
            for kp in fcurve.keyframe_points:
                if abs(kp.co[0] - frame) < 0.01:
                    kp.co[1] = value
                    fcurve.update()
                    return
            break
    shape_keys.keyframe_insert(data_path=data_path, frame=frame)


def sync_native_shape_key_keyframe_insertions(obj, mgr, scene):
    """Mirror keyframes inserted through Blender's native ShapeKey.value UI.

    Pressing I on the native value property bypasses the plugin operators. The
    depsgraph handler sees the resulting action change and mirrors only newly
    inserted or updated keyframes on the current frame.
    """
    global _syncing_mirror_keyframes

    if _syncing_mirror_keyframes or not mgr:
        return False
    if not mgr.mirror_mode:
        _store_native_frame_keyframes(obj.data, scene.frame_current)
        return False

    mesh = obj.data
    shape_keys = mesh.shape_keys
    if not shape_keys or not shape_keys.animation_data or not shape_keys.animation_data.action:
        if shape_keys:
            _store_native_frame_keyframes(mesh, scene.frame_current)
        return False

    action = shape_keys.animation_data.action
    frame = scene.frame_current
    cache_key = (mesh.as_pointer(), action.as_pointer(), round(frame, 2))
    empty_action_cache_key = (mesh.as_pointer(), 0, round(frame, 2))
    current_values = dict(get_frame_keyframe_values(action, frame))
    previous_values = _native_frame_keyframe_cache.get(cache_key)
    if previous_values is None and empty_action_cache_key in _native_frame_keyframe_cache:
        previous_values = _native_frame_keyframe_cache.pop(empty_action_cache_key)
    _native_frame_keyframe_cache[cache_key] = current_values

    if previous_values is None or bpy.context.active_object != obj:
        return False

    changed_names = [
        name for name, value in current_values.items()
        if (
            name not in previous_values
            or abs(previous_values.get(name, value) - value) > 0.000001
        )
    ]
    if not changed_names:
        return False

    key_blocks = shape_keys.key_blocks
    mirrored = False
    _syncing_mirror_keyframes = True
    try:
        for key_name in changed_names:
            mirrored_name = mirror_name(key_name)
            if not mirrored_name or mirrored_name not in key_blocks:
                continue
            source_value = float(key_blocks[key_name].value)
            key_blocks[mirrored_name].value = source_value
            set_sk_item_slider_value(mesh, mirrored_name, source_value)
            upsert_shape_key_keyframe(shape_keys, mirrored_name, frame, source_value)
            mirrored = True
    finally:
        _syncing_mirror_keyframes = False

    if mirrored:
        clear_keyframe_caches()
        _native_frame_keyframe_cache[cache_key] = dict(get_frame_keyframe_values(action, frame))
        _cache_native_shape_key_values(mesh)
    return mirrored


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
        return False

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
        return False

    changed_names = [
        name for name, value in current_values.items()
        if name in previous_values and abs(value - previous_values[name]) > 0.000001
    ]
    if not changed_names:
        return False

    key_blocks = mesh.shape_keys.key_blocks
    _syncing_native_value_changes = True
    synced = False
    try:
        for key_name in changed_names:
            item = get_sk_item(mesh, key_name)
            if not item:
                continue
            value = current_values[key_name]
            apply_value_to_shapekey(mesh, key_blocks, key_name, value, mgr)
            synced = True

            if item.selected:
                for selected_item in mesh.sk_items:
                    if selected_item.name == key_name or not selected_item.selected:
                        continue
                    apply_value_to_shapekey(mesh, key_blocks, selected_item.name, value, mgr)
                    synced = True

        # Do not keyframe from this depsgraph callback. It would become a
        # separate undo step from the native ShapeKey.value drag. Blender's
        # native Auto Key handles the directly edited value in the same undo
        # operation; this callback is limited to value synchronization.
    finally:
        _syncing_native_value_changes = False
        _cache_native_shape_key_values(mesh)
    return synced


def get_shapekey_slider_value(self):
    mesh = self.id_data
    if not mesh or not mesh.shape_keys:
        return 0.0

    kb = mesh.shape_keys.key_blocks.get(self.name)
    if not kb:
        return 0.0

    return float(kb.value)


def get_shapekey_preview_value(self):
    return get_shapekey_slider_value(self)


def set_shapekey_preview_value(self, value):
    mesh = self.id_data
    if not mesh or not mesh.shape_keys:
        return

    kb = mesh.shape_keys.key_blocks.get(self.name)
    if not kb:
        return

    kb.value = value
    _cache_native_shape_key_values(mesh)
    tag_redraw_all_areas()


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

    if is_auto_keyframe_enabled(mgr, context):
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
    global _syncing_auto_keyframe_state
    if _syncing_auto_keyframe_state:
        return
    scene = context.scene if context else getattr(bpy.context, "scene", None)
    if scene and scene.tool_settings:
        scene.tool_settings.use_keyframe_insert_auto = self.auto_keyframe


def is_auto_keyframe_enabled(mgr=None, context=None):
    ctx = context or getattr(bpy, "context", None)
    scene = getattr(ctx, "scene", None) if ctx else None
    tool_settings = getattr(scene, "tool_settings", None) if scene else None
    if tool_settings is not None:
        return bool(tool_settings.use_keyframe_insert_auto)
    return bool(getattr(mgr, "auto_keyframe", False))


def sync_auto_keyframe_state(scene=None, mgr=None):
    """Reflect Blender's timeline Auto Key state back into the add-on property."""
    global _syncing_auto_keyframe_state

    if mgr is None:
        mgr = get_current_manager()
    if mgr is None:
        return False

    scene = scene or getattr(bpy.context, "scene", None)
    tool_settings = getattr(scene, "tool_settings", None) if scene else None
    if tool_settings is None:
        return False

    value = bool(tool_settings.use_keyframe_insert_auto)
    if bool(mgr.auto_keyframe) == value:
        return False

    _syncing_auto_keyframe_state = True
    try:
        mgr.auto_keyframe = value
    finally:
        _syncing_auto_keyframe_state = False
    return True


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
        return False

    mesh = obj.data
    items_changed = check_and_sync_sk_items(mesh)
    mgr = get_current_manager()
    if not mgr:
        return items_changed

    old_active_item_index = mgr.active_item_index
    sync_active_item_by_name(mesh, mgr)
    active_changed = (mgr.active_item_index != old_active_item_index)

    values_changed = False
    keyframes_changed = False
    if process_native_value_changes:
        values_changed = sync_native_shape_key_value_changes(obj, mgr)
        scene = getattr(bpy.context, "scene", None)
        if scene:
            keyframes_changed = sync_native_shape_key_keyframe_insertions(obj, mgr, scene)
    else:
        _cache_native_shape_key_values(mesh)
        scene = getattr(bpy.context, "scene", None)
        if scene:
            _store_native_frame_keyframes(mesh, scene.frame_current)

    return items_changed or active_changed or values_changed or keyframes_changed


def sync_shapekey_ui_for_scene(scene, depsgraph=None, process_native_value_changes=True):
    context = bpy.context
    auto_key_changed = sync_auto_keyframe_state(scene)
    obj = context.active_object
    if not obj or obj.type != 'MESH' or not obj.data or not obj.data.shape_keys:
        if auto_key_changed:
            tag_redraw_all_areas()
        return

    try:
        changed = sync_shapekey_ui_for_object(
            obj,
            depsgraph=depsgraph,
            process_native_value_changes=process_native_value_changes,
        )
        if changed or auto_key_changed:
            tag_redraw_all_areas()
    except Exception:
        pass


@bpy.app.handlers.persistent
def shapekey_monitor_handler(scene, depsgraph):
    """
    Depsgraph 监听器：同步列表，并处理原生形态键值的直接编辑。
    """
    if screen_is_playing():
        return
    clear_keyframe_caches()
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph)


@bpy.app.handlers.persistent
def shapekey_frame_change_handler(scene, depsgraph=None):
    if screen_is_playing():
        return
    clear_keyframe_caches()
    # Frame evaluation changes values without user edits; refresh the baseline
    # instead of treating those changes as a request to mirror or keyframe.
    sync_shapekey_ui_for_scene(scene, depsgraph=depsgraph, process_native_value_changes=False)
