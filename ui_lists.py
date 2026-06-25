import bpy

from .i18n import _
from .core import (
    get_visible_category_item_indices, has_any_keyframes, get_keyframe_button_icon,
    get_keyed_shape_key_names, get_category_order_sort_key,
)

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


class MESH_UL_sk_category_selector(bpy.types.UIList):
    """Compact category selector for animation work."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.label(text=item.name, icon='FILE_FOLDER')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon='FILE_FOLDER')


class MESH_UL_all_shapekeys(bpy.types.UIList):
    """所有形态键滚动列表。

    关键原则：行内不放自定义 Operator，也不让“名称文字”参与选择。
    Blender UIList 在滚轮向下滚动后，鼠标悬停高亮行有时会停留在旧行；
    如果把名称做成可点击控件，第一次点击可能会落到旧高亮行。

    因此这里把选择入口收束到左侧原生 BoolProperty 小复选框：
    - 复选框负责 item.all_selected，支持按住拖过复选框快速多选；
    - 名称只是 label，只负责显示，不改变选择；
    - 插件的归类目标仍由 on_all_selected_changed() 记录的 item.name 决定。
    """

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type not in {'DEFAULT', 'COMPACT'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon='SHAPEKEY_DATA')
            return

        mgr = context.window_manager.sk_manager
        display_name = item.alias.strip() if item.alias.strip() else item.name
        active_icon = 'RESTRICT_SELECT_OFF' if item.name == mgr.active_all_item_name else 'BLANK1'

        split = layout.split(factor=0.72, align=True)
        left = split.row(align=True)
        right = split.row(align=True)

        # 只让左侧小复选框可点击。不要把 display_name 放到 prop 的 text 里，
        # 否则点击文字区域时会重新触发 UIList 的旧 hover/active 行问题。
        left.prop(item, "all_selected", text="")
        left.label(text=display_name, icon=active_icon)

        if item.category.strip():
            right.label(text=item.category, icon='FILE_FOLDER')
        else:
            right.label(text=_("Unclassified"), icon='BLANK1')

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        filter_order = []

        mgr = getattr(context.window_manager, "sk_manager", None) if context else None
        search_text = getattr(mgr, "all_search_text", "").strip().lower() if mgr else ""
        if not search_text:
            return filter_flags, filter_order

        for i, item in enumerate(items):
            alias_text = item.alias.strip().lower()
            category_text = item.category.strip().lower()
            name_text = item.name.lower()
            if (
                search_text not in name_text
                and search_text not in alias_text
                and search_text not in category_text
            ):
                filter_flags[i] &= ~self.bitflag_filter_item

        return filter_flags, filter_order


class MESH_UL_alias_editor(bpy.types.UIList):
    """Preset-time alias editor with value preview controls."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = context.active_object
        if not obj or not obj.data or not obj.data.shape_keys:
            return

        if self.layout_type not in {'DEFAULT', 'COMPACT'}:
            layout.alignment = 'CENTER'
            layout.label(text=item.alias.strip() or item.name, icon='SHAPEKEY_DATA')
            return

        split = layout.split(factor=0.32, align=True)
        name_row = split.row(align=True)
        edit_row = split.row(align=True)

        name_row.label(text=item.name, icon='SHAPEKEY_DATA')
        edit_row.prop(item, "alias", text="")
        edit_row.prop(item, "alias_preview_value", text="", slider=True)
        op = edit_row.operator("sk_helper.reset_alias_preview", text="", icon='LOOP_BACK')
        op.shapekey_name = item.name

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        filter_flags = [self.bitflag_filter_item] * len(items)
        filter_order = []

        mgr = getattr(context.window_manager, "sk_manager", None) if context else None
        search_text = getattr(mgr, "all_search_text", "").strip().lower() if mgr else ""
        if not search_text:
            return filter_flags, filter_order

        for i, item in enumerate(items):
            alias_text = item.alias.strip().lower()
            name_text = item.name.lower()
            if search_text not in name_text and search_text not in alias_text:
                filter_flags[i] &= ~self.bitflag_filter_item

        return filter_flags, filter_order


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
            display_name = item.alias.strip() if item.alias.strip() else item.name
            row.label(text=display_name, icon='RESTRICT_SELECT_OFF' if index == mgr.active_item_index else 'BLANK1')
            # Draw the real ShapeKey value so Blender can show its native
            # keyed/animated state colors and make I-key insertion identical.
            row.prop(kb, "value", text="", slider=True)
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
        keyed_names = get_keyed_shape_key_names(obj.data.shape_keys) if mgr.show_only_keyed else None
        for i, item in enumerate(items):
            if item.category != cat_name:
                filter_flags[i] &= ~self.bitflag_filter_item
                continue
            alias_text = item.alias.strip().lower()
            if search_text and search_text not in item.name.lower() and search_text not in alias_text:
                filter_flags[i] &= ~self.bitflag_filter_item
                continue
            if mgr.show_only_keyed and (not keyed_names or item.name not in keyed_names):
                filter_flags[i] &= ~self.bitflag_filter_item
        filter_order = sorted(
            range(len(items)),
            key=lambda index: get_category_order_sort_key(items[index], index),
        )
        return filter_flags, filter_order
