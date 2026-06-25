import bpy

from .i18n import _
from .operators import get_all_list_target_indices


def draw_all_shape_key_tools(box, context, obj, mgr):
    box.label(text=_("All Shape Keys"), icon='SHAPEKEY_DATA')
    box.label(text=_("Use the left checkbox to select. Drag over checkboxes for fast multi-select."), icon='INFO')

    search_row = box.row(align=True)
    search_row.prop(mgr, "all_search_text", text="", icon='VIEWZOOM')

    # 使用真正的 UIList 滚动列表。
    # 左侧复选框负责批量选择；单击行本身则作为“单选中的形态键”。
    box.template_list(
        "MESH_UL_all_shapekeys",
        "",
        obj.data,
        "sk_items",
        mgr,
        "active_all_item_index",
        rows=12,
        maxrows=20,
    )

    target_indices, from_selection = get_all_list_target_indices(obj.data, mgr)
    if target_indices:
        if from_selection and len(target_indices) > 1:
            box.label(text=f"{_('Checked All Items:')} {len(target_indices)}", icon='RESTRICT_SELECT_OFF')
        else:
            active_index = target_indices[-1]
            active_item = obj.data.sk_items[active_index]
            status = active_item.category if active_item.category.strip() else _("Unclassified")
            box.label(text=f"{_('All List Target:')} {active_item.name}  |  {status}", icon='RESTRICT_SELECT_OFF')
    else:
        box.label(text=_("No all-list item selected yet"), icon='INFO')

    row = box.row(align=True)
    row.operator("sk_helper.assign_active_all_to_category", text=_("Assign"), icon='ADD')
    row.operator("sk_helper.clear_active_all_category", text=_("Remove Category"), icon='REMOVE')

    row = box.row(align=True)
    row.operator("sk_helper.assign_active_and_above_category", text=_("Assign Active and Above to Category"), icon='TRIA_UP_BAR')

    row = box.row(align=True)
    row.operator("sk_helper.clear_all_list_selection", text=_("Clear All List Selection"), icon='X')


def draw_alias_editor_tools(box, context, obj, mgr):
    box.label(text=_("Alias Editor"), icon='GREASEPENCIL')

    row = box.row(align=True)
    row.prop(mgr, "all_search_text", text="", icon='VIEWZOOM')
    row.operator("sk_helper.reset_all_alias_previews", text="", icon='LOOP_BACK')

    box.template_list(
        "MESH_UL_alias_editor",
        "",
        obj.data,
        "sk_items",
        mgr,
        "active_alias_item_index",
        rows=8,
        maxrows=16,
    )

    mirror_alias_box = box.box()
    mirror_alias_box.label(text=_("Mirror Alias"), icon='MOD_MIRROR')
    row = mirror_alias_box.row(align=True)
    row.prop(mgr, "left_alias_prefix", text=_("Left Prefix"))
    row.prop(mgr, "left_alias_suffix", text=_("Left Suffix"))
    row = mirror_alias_box.row(align=True)
    row.prop(mgr, "right_alias_prefix", text=_("Right Prefix"))
    row.prop(mgr, "right_alias_suffix", text=_("Right Suffix"))
    mirror_alias_box.operator("sk_helper.sync_mirror_aliases", text=_("Sync Mirror Aliases"), icon='FILE_REFRESH')


def draw_frequency_statistics_tools(layout, mgr):
    row = layout.row(align=True)
    row.prop(mgr, "frequency_preset", text=_("Frequency Preset"))
    row.operator("sk_helper.create_frequency_preset", text="", icon='ADD')
    row.operator("sk_helper.delete_frequency_preset", text="", icon='REMOVE')
    row = layout.row(align=True)
    row.operator(
        "sk_helper.sort_by_current_keyframe_frequency",
        text=_("Sort by Current Project Frequency"),
        icon='SORT_DESC',
    )
    row.operator(
        "sk_helper.sort_by_frequency_preset",
        text=_("Sort by Frequency Preset"),
        icon='SORT_DESC',
    )
    row = layout.row(align=True)
    row.operator(
        "sk_helper.add_current_project_frequency",
        text=_("Add Current Project Statistics"),
        icon='ADD',
    )
    row = layout.row(align=True)
    row.prop(mgr, "frequency_project", text=_("Saved Project Statistics"))
    row.operator("sk_helper.delete_frequency_project_statistics", text="", icon='REMOVE')


def draw_category_work_selector(layout, obj, mgr):
    box = layout.box()
    box.label(text=_("Categories"), icon='FILE_FOLDER')
    box.template_list(
        "MESH_UL_sk_category_selector",
        "",
        obj.data,
        "sk_categories",
        mgr,
        "active_category_index",
        rows=4,
        maxrows=8,
    )


def draw_work_options(layout, mgr):
    box = layout.box()
    row = box.row(align=True)
    row.prop(bpy.context.scene.tool_settings, "use_keyframe_insert_auto", text=_("Auto Keyframe"), icon='REC', toggle=True)
    row.prop(mgr, "mirror_mode", text=_("Mirror Mode"), icon='MOD_MIRROR', toggle=True)
    row = box.row(align=True)
    row.prop(mgr, "show_only_keyed", text=_("Show Only Keyed"), toggle=True, icon='DECORATE_KEYFRAME')
    row.prop(mgr, "reorder_mode", text=_("Move Mode"), toggle=True, icon='ARROW_LEFTRIGHT')


def draw_current_category_shape_keys(layout, context, obj, mgr, categories):
    box = layout.box()
    box.label(text=_("Shape Keys in Category"), icon='SHAPEKEY_DATA')
    if len(categories) > 0 and 0 <= mgr.active_category_index < len(categories):
        row = box.row(align=True)
        row.prop(mgr, "search_text", text="", icon='VIEWZOOM')
        box.template_list("MESH_UL_filtered_shapekeys", "", obj.data, "sk_items", mgr, "active_item_index")
        row = box.row(align=True)
        row.label(text=_("Batch Select:"))
        op_sel = row.operator("sk_helper.select_all", text=_("Select All"))
        op_sel.action = 'SELECT'
        op_desel = row.operator("sk_helper.select_all", text=_("Deselect All"))
        op_desel.action = 'DESELECT'
        op_inv = row.operator("sk_helper.select_all", text=_("Invert Selection"))
        op_inv.action = 'INVERT'
        box_anim = box.box()
        box_anim.label(text=_("Animation Actions"), icon='ACTION')
        row = box_anim.row(align=True)
        row.operator("sk_helper.keyframe_batch", text=_("Keyframe Selected Checked"), icon='DECORATE_KEYFRAME')
        row.operator("sk_helper.reset_selected", text=_("Reset Selected to 0"), icon='LOOP_BACK')
    else:
        box.label(text=_("Open Preset Editor to create or select a category"), icon='INFO')


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

        draw_category_work_selector(layout, obj, mgr)
        draw_work_options(layout, mgr)
        draw_current_category_shape_keys(layout, context, obj, mgr, categories)


class VIEW3D_PT_sk_preset_editor(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shape Key Classification'
    bl_label = 'Preset Editor'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data.shape_keys

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        mgr = context.window_manager.sk_manager
        categories = obj.data.sk_categories

        box = layout.box()
        box.label(text=_("Presets Manager"), icon='PRESET')
        row = box.row(align=True)
        row.operator("sk_helper.import_preset", text=_("Import Preset"), icon='IMPORT')
        row.operator("sk_helper.export_preset", text=_("Export Preset"), icon='EXPORT')

        box = layout.box()
        box.label(text=_("Categories Manager"), icon='FILE_FOLDER')
        row = box.row()
        row.template_list("MESH_UL_sk_categories", "", obj.data, "sk_categories", mgr, "active_category_index")
        col = row.column(align=True)
        col.operator("sk_helper.add_category", text="", icon='ADD')
        col.operator("sk_helper.remove_category", text="", icon='REMOVE')
        col.operator("sk_helper.reorder_category", text="", icon='TRIA_UP').direction = 'UP'
        col.operator("sk_helper.reorder_category", text="", icon='TRIA_DOWN').direction = 'DOWN'

        row = layout.row(align=True)
        row.operator("sk_helper.auto_match", text=_("Auto Match Active"), icon='FILE_REFRESH').target_all = False
        row.operator("sk_helper.auto_match", text=_("Auto Match All"), icon='FILE_REFRESH').target_all = True

        if len(categories) > 0 and 0 <= mgr.active_category_index < len(categories):
            box_all = layout.box()
            draw_all_shape_key_tools(box_all, context, obj, mgr)

            alias_box = layout.box()
            draw_alias_editor_tools(alias_box, context, obj, mgr)
        else:
            layout.label(text=_("Please create or select a category"), icon='INFO')


class VIEW3D_PT_sk_frequency_statistics(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shape Key Classification'
    bl_label = 'Frequency Statistics Preset'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.data.shape_keys

    def draw(self, context):
        draw_frequency_statistics_tools(self.layout, context.window_manager.sk_manager)
