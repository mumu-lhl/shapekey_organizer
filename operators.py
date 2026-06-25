import bpy

from . import core as core_module
from .i18n import _
from .core import (
    match_pattern, mirror_name, mirror_side, get_visible_category_item_indices, get_sk_item_index_by_name,
    reorder_sk_items_by_names, check_and_sync_sk_items, set_sk_item_slider_value,
    get_keyframe_value_on_current_frame, get_keyframe_button_icon, has_any_keyframes,
    tag_redraw_all_areas, iter_action_fcurve_collections, is_auto_keyframe_enabled,
)


def _alias_without_side_markers(alias, prefix, suffix):
    """Remove this side's configured markers before applying them again."""
    if prefix and alias.startswith(prefix):
        alias = alias[len(prefix):]
    if suffix and alias.endswith(suffix):
        alias = alias[:-len(suffix)]
    return alias


class SK_OT_sync_mirror_aliases(bpy.types.Operator):
    bl_idname = "sk_helper.sync_mirror_aliases"
    bl_label = "Sync Mirror Aliases"
    bl_description = "Create matching aliases for recognized left/right shape key pairs"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data.shape_keys

    def execute(self, context):
        mesh = context.active_object.data
        mgr = context.window_manager.sk_manager
        items_by_name = {item.name: item for item in mesh.sk_items}
        synced_pairs = 0

        # Only visit left keys. mirror_name() remains the single source of naming recognition.
        for left_item in items_by_name.values():
            if mirror_side(left_item.name) != 'LEFT':
                continue
            right_name = mirror_name(left_item.name)
            right_item = items_by_name.get(right_name)
            if not right_item:
                continue

            # The left alias wins when both exist; otherwise use the populated side.
            if left_item.alias.strip():
                base_alias = _alias_without_side_markers(
                    left_item.alias, mgr.left_alias_prefix, mgr.left_alias_suffix
                )
            elif right_item.alias.strip():
                base_alias = _alias_without_side_markers(
                    right_item.alias, mgr.right_alias_prefix, mgr.right_alias_suffix
                )
            else:
                continue

            left_item.alias = f"{mgr.left_alias_prefix}{base_alias}{mgr.left_alias_suffix}"
            right_item.alias = f"{mgr.right_alias_prefix}{base_alias}{mgr.right_alias_suffix}"
            synced_pairs += 1

        if synced_pairs:
            self.report({'INFO'}, _("Synchronized aliases for {} mirror pair(s)").format(synced_pairs))
        else:
            self.report({'INFO'}, _("No mirrored shape key pairs with aliases found"))
        return {'FINISHED'}

class SK_OT_add_category(bpy.types.Operator):
    bl_idname = "sk_helper.add_category"
    bl_label = "Add Category"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        cat = obj.data.sk_categories.add()
        cat.name = _("New Category {}").format(len(obj.data.sk_categories))
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
            self.report({'WARNING'}, _("No categories defined"))
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
        self.report({'INFO'}, _("Successfully classified {} shape keys.").format(matched_count))
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
        self.report({'INFO'}, _("Moved {} shape keys to category '{}'").format(count, active_cat.name))
        return {'FINISHED'}


def get_active_category(context):
    obj = context.active_object
    mgr = context.window_manager.sk_manager
    categories = obj.data.sk_categories
    if not categories or mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
        return None
    return categories[mgr.active_category_index]


def resolve_all_item_index(mesh, item_name="", fallback_index=-1):
    """用形态键名字定位真实集合行；index 只作为 fallback。"""
    if mesh is None or not hasattr(mesh, "sk_items"):
        return -1
    if item_name:
        index = get_sk_item_index_by_name(mesh, item_name)
        if index >= 0:
            return index
    if 0 <= fallback_index < len(mesh.sk_items):
        return fallback_index
    return -1


def resolve_active_all_single_index(mesh, mgr):
    """返回“所有形态键”列表里原生单选行对应的真实索引。

    这个函数故意优先使用 active_all_item_index，因为用户希望“不点复选框，
    只单击列表行”的单选也能成为归类/移除目标。
    active_all_item_name 只作为 fallback，用于重载文件或索引临时越界时恢复。
    """
    if mesh is None or mgr is None or not hasattr(mesh, "sk_items"):
        return -1
    if 0 <= mgr.active_all_item_index < len(mesh.sk_items):
        return mgr.active_all_item_index
    return resolve_all_item_index(mesh, getattr(mgr, "active_all_item_name", ""), -1)


def set_active_all_item_safely(mgr, mesh, item_index):
    """只同步“所有形态键”列表自己的活动项，绝不影响当前分类列表。"""
    if not mgr or mesh is None or not (0 <= item_index < len(mesh.sk_items)):
        return
    item_name = mesh.sk_items[item_index].name
    mgr.active_all_item_index = item_index
    mgr.active_all_item_name = item_name


def set_all_selection_indices(items, selected_indices):
    selected_indices = set(selected_indices)
    old_guard = getattr(core_module, "_syncing_all_selection", False)
    core_module._syncing_all_selection = True
    try:
        for index, item in enumerate(items):
            value = index in selected_indices
            if item.all_selected != value:
                item.all_selected = value
    finally:
        core_module._syncing_all_selection = old_guard


def get_all_selected_indices(items):
    return [index for index, item in enumerate(items) if item.all_selected]


def get_all_list_target_indices(mesh, mgr):
    """优先返回 all-list 勾选项；没有勾选时返回当前高亮单项。"""
    if mesh is None or not hasattr(mesh, "sk_items"):
        return [], False

    selected_indices = get_all_selected_indices(mesh.sk_items)
    if selected_indices:
        return selected_indices, True

    active_index = resolve_active_all_single_index(mesh, mgr)
    if active_index >= 0:
        return [active_index], False
    return [], False


def assign_item_to_category_safely(item, category_name):
    """只给未分类项归类；已有分类绝不覆盖。"""
    if item.category.strip():
        return False
    item.category = category_name
    return True


class SK_OT_assign_active_all_to_category(bpy.types.Operator):
    bl_idname = "sk_helper.assign_active_all_to_category"
    bl_label = "Assign"
    bl_description = "Assign checked shape keys in All Shape Keys to the active category. If nothing is checked, assign the active row without overwriting existing categories"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        active_cat = get_active_category(context)
        mgr = context.window_manager.sk_manager
        targets, _ = get_all_list_target_indices(obj.data, mgr)
        return active_cat is not None and bool(targets)

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        active_cat = get_active_category(context)
        if active_cat is None:
            return {'CANCELLED'}

        target_indices, from_selection = get_all_list_target_indices(obj.data, mgr)
        if not target_indices:
            return {'CANCELLED'}

        moved = 0
        skipped = 0
        last_target_index = target_indices[-1]
        target_names = []
        for item_index in target_indices:
            if item_index < 0 or item_index >= len(obj.data.sk_items):
                continue
            item = obj.data.sk_items[item_index]
            target_names.append(item.name)
            if assign_item_to_category_safely(item, active_cat.name):
                moved += 1
            else:
                skipped += 1

        if from_selection:
            set_all_selection_indices(obj.data.sk_items, set())

        if 0 <= last_target_index < len(obj.data.sk_items):
            item = obj.data.sk_items[last_target_index]
            set_active_all_item_safely(mgr, obj.data, last_target_index)
            mgr.all_select_anchor_index = last_target_index
            mgr.all_select_anchor_name = item.name

        if moved == 0:
            if target_names:
                self.report({'INFO'}, _("No changes. Shape key '{}' is already classified as '{}'.").format(
                    target_names[-1], obj.data.sk_items[last_target_index].category
                ))
            else:
                self.report({'INFO'}, _("No valid shape keys selected."))
        elif len(target_names) == 1:
            self.report({'INFO'}, _("Moved shape key '{}' to category '{}'.").format(target_names[0], active_cat.name))
        else:
            self.report({'INFO'}, _("Moved {} shape keys to category '{}'. Skipped {} already-classified shape keys.").format(
                moved, active_cat.name, skipped
            ))
        return {'FINISHED'}


class SK_OT_clear_active_all_category(bpy.types.Operator):
    bl_idname = "sk_helper.clear_active_all_category"
    bl_label = "Remove Category"
    bl_description = "Remove checked shape keys in All Shape Keys from their current categories. If nothing is checked, remove the active row from its current category"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        mgr = context.window_manager.sk_manager
        targets, _ = get_all_list_target_indices(obj.data, mgr)
        return bool(targets)

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        target_indices, from_selection = get_all_list_target_indices(obj.data, mgr)
        if not target_indices:
            return {'CANCELLED'}

        removed = 0
        skipped = 0
        last_target_index = target_indices[-1]
        target_names = []
        for item_index in target_indices:
            if item_index < 0 or item_index >= len(obj.data.sk_items):
                continue
            item = obj.data.sk_items[item_index]
            target_names.append(item.name)
            old_category = item.category
            if not old_category.strip():
                skipped += 1
                continue
            item.category = ""
            removed += 1

        if from_selection:
            set_all_selection_indices(obj.data.sk_items, set())

        if 0 <= last_target_index < len(obj.data.sk_items):
            item = obj.data.sk_items[last_target_index]
            set_active_all_item_safely(mgr, obj.data, last_target_index)
            mgr.all_select_anchor_index = last_target_index
            mgr.all_select_anchor_name = item.name

        if removed == 0:
            if target_names:
                self.report({'INFO'}, _("No changes. Shape key '{}' is already unclassified.").format(target_names[-1]))
            else:
                self.report({'INFO'}, _("No valid shape keys selected."))
        elif len(target_names) == 1:
            self.report({'INFO'}, _("Removed shape key '{}' from its category.").format(target_names[0]))
        else:
            self.report({'INFO'}, _("Removed {} shape keys from their categories. Skipped {} already-unclassified shape keys.").format(
                removed, skipped
            ))
        return {'FINISHED'}


class SK_OT_set_all_list_anchor_to_active(bpy.types.Operator):
    bl_idname = "sk_helper.set_all_list_anchor_to_active"
    bl_label = "Set Range Anchor"
    bl_description = "Use the active row in All Shape Keys as the range selection anchor"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        mgr = context.window_manager.sk_manager
        return resolve_active_all_single_index(obj.data, mgr) >= 0

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        item_index = resolve_all_item_index(obj.data, mgr.active_all_item_name, mgr.active_all_item_index)
        if item_index < 0 or item_index >= len(obj.data.sk_items):
            return {'CANCELLED'}
        set_active_all_item_safely(mgr, obj.data, item_index)
        mgr.all_select_anchor_index = item_index
        mgr.all_select_anchor_name = obj.data.sk_items[item_index].name
        self.report({'INFO'}, _("Range anchor set to '{}'.").format(obj.data.sk_items[item_index].name))
        return {'FINISHED'}


class SK_OT_select_all_range_to_active(bpy.types.Operator):
    bl_idname = "sk_helper.select_all_range_to_active"
    bl_label = "Select Range to Active"
    bl_description = "Select shape keys between the range anchor and the active row in All Shape Keys"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        mgr = context.window_manager.sk_manager
        active_index = resolve_all_item_index(obj.data, mgr.active_all_item_name, mgr.active_all_item_index)
        anchor_index = resolve_all_item_index(obj.data, mgr.all_select_anchor_name, mgr.all_select_anchor_index)
        return active_index >= 0 and anchor_index >= 0

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        items = obj.data.sk_items
        active_index = resolve_all_item_index(obj.data, mgr.active_all_item_name, mgr.active_all_item_index)
        anchor_index = resolve_all_item_index(obj.data, mgr.all_select_anchor_name, mgr.all_select_anchor_index)
        if active_index < 0 or anchor_index < 0:
            return {'CANCELLED'}

        start = min(anchor_index, active_index)
        end = max(anchor_index, active_index)
        selected = set(range(start, end + 1))
        if mgr.all_range_append:
            selected.update(get_all_selected_indices(items))
        set_all_selection_indices(items, selected)
        set_active_all_item_safely(mgr, obj.data, active_index)
        self.report({'INFO'}, _("Selected {} shape keys from range anchor to active row.").format(end - start + 1))
        return {'FINISHED'}


class SK_OT_select_active_all_item_only(bpy.types.Operator):
    bl_idname = "sk_helper.select_active_all_item_only"
    bl_label = "Select Active Only"
    bl_description = "Clear All Shape Keys selection and check only the active row"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        mgr = context.window_manager.sk_manager
        return resolve_active_all_single_index(obj.data, mgr) >= 0

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        item_index = resolve_all_item_index(obj.data, mgr.active_all_item_name, mgr.active_all_item_index)
        if item_index < 0 or item_index >= len(obj.data.sk_items):
            return {'CANCELLED'}
        set_all_selection_indices(obj.data.sk_items, {item_index})
        set_active_all_item_safely(mgr, obj.data, item_index)
        mgr.all_select_anchor_index = item_index
        mgr.all_select_anchor_name = obj.data.sk_items[item_index].name
        return {'FINISHED'}



class SK_OT_clear_all_list_selection(bpy.types.Operator):
    bl_idname = "sk_helper.clear_all_list_selection"
    bl_label = "Clear All List Selection"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and hasattr(obj.data, "sk_items")

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        set_all_selection_indices(obj.data.sk_items, set())
        mgr.all_select_anchor_index = -1
        mgr.all_select_anchor_name = ""
        self.report({'INFO'}, _("Cleared All Shape Keys selection."))
        return {'FINISHED'}


class SK_OT_assign_active_and_above_category(bpy.types.Operator):
    bl_idname = "sk_helper.assign_active_and_above_category"
    bl_label = "Assign Active and Above to Category"
    bl_description = "Assign only the continuous unclassified range from the active shape key upward. Stop at the first already-classified shape key, and never overwrite existing categories."
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not hasattr(obj.data, "sk_items"):
            return False
        mgr = context.window_manager.sk_manager
        categories = obj.data.sk_categories
        return bool(categories) and 0 <= mgr.active_category_index < len(categories) and resolve_active_all_single_index(obj.data, mgr) >= 0

    def execute(self, context):
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        categories = obj.data.sk_categories
        if not categories or mgr.active_category_index < 0 or mgr.active_category_index >= len(categories):
            return {'CANCELLED'}
        target_index = resolve_active_all_single_index(obj.data, mgr)
        if target_index < 0 or target_index >= len(obj.data.sk_items):
            return {'CANCELLED'}

        active_cat = categories[mgr.active_category_index]
        assigned_count = 0
        boundary_name = ""

        # 关键修复：从当前项向上寻找“连续未分类区间”。
        # 一旦遇到任何已经归类的形态键，立刻停止。
        # 这样后续在更下面归类时，不会穿过旧分类边界，也绝不会覆盖已有分类。
        for index in range(target_index, -1, -1):
            item = obj.data.sk_items[index]
            if item.category.strip():
                boundary_name = item.name
                break
            item.category = active_cat.name
            assigned_count += 1

        set_active_all_item_safely(mgr, obj.data, target_index)

        if assigned_count == 0:
            if boundary_name:
                self.report({'INFO'}, _("No changes. Active or upper boundary shape key '{}' is already classified.").format(boundary_name))
            else:
                self.report({'INFO'}, _("No unclassified shape keys found."))
        else:
            if boundary_name:
                message = _("Moved {} continuous unclassified shape keys to category '{}'; stopped before already-classified shape key '{}'").format(
                    assigned_count, active_cat.name, boundary_name
                )
            else:
                message = _("Moved {} continuous unclassified shape keys to category '{}'").format(
                    assigned_count, active_cat.name
                )
            self.report({'INFO'}, message)
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
        self.report({'INFO'}, _("Removed {} shape keys from category.").format(count))
        return {'FINISHED'}


class SK_OT_reset_alias_preview(bpy.types.Operator):
    bl_idname = "sk_helper.reset_alias_preview"
    bl_label = "Reset Preview Value"
    bl_description = "Reset this shape key preview value to 0 without inserting keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    shapekey_name: bpy.props.StringProperty()

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            return {'CANCELLED'}
        key_blocks = obj.data.shape_keys.key_blocks
        if self.shapekey_name not in key_blocks:
            return {'CANCELLED'}
        key_blocks[self.shapekey_name].value = 0.0
        set_sk_item_slider_value(obj.data, self.shapekey_name, 0.0)
        tag_redraw_all_areas()
        return {'FINISHED'}


class SK_OT_reset_all_alias_previews(bpy.types.Operator):
    bl_idname = "sk_helper.reset_all_alias_previews"
    bl_label = "Reset All Preview Values"
    bl_description = "Reset all shape key preview values to 0 without inserting keyframes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = context.active_object
        if not obj or not obj.data.shape_keys:
            return {'CANCELLED'}
        key_blocks = obj.data.shape_keys.key_blocks
        for item in obj.data.sk_items:
            if item.name in key_blocks:
                key_blocks[item.name].value = 0.0
                set_sk_item_slider_value(obj.data, item.name, 0.0)
        tag_redraw_all_areas()
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
                for fcurves in iter_action_fcurve_collections(action):
                    for fcurve in list(fcurves):
                        if fcurve.data_path == data_path:
                            for kp in list(fcurve.keyframe_points):
                                if abs(kp.co[0] - frame) < 0.01:
                                    fcurve.keyframe_points.remove(kp)
                            if len(fcurve.keyframe_points) == 0:
                                fcurves.remove(fcurve)
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
        tag_redraw_all_areas()
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
        self.report({'INFO'}, _("Keyframed {} shape keys.").format(count))
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
                if is_auto_keyframe_enabled(mgr, context):
                    obj.data.shape_keys.keyframe_insert(
                        data_path=f'key_blocks["{kb.name}"].value',
                        frame=context.scene.frame_current
                    )
                if mgr.mirror_mode:
                    m_name = mirror_name(kb.name)
                    if m_name and m_name in key_blocks:
                        key_blocks[m_name].value = 0.0
                        set_sk_item_slider_value(obj.data, m_name, 0.0)
                        if is_auto_keyframe_enabled(mgr, context):
                            obj.data.shape_keys.keyframe_insert(
                                data_path=f'key_blocks["{m_name}"].value',
                                frame=context.scene.frame_current
                            )
        return {'FINISHED'}
