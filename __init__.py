bl_info = {
    "name": "Shape Key Classification",
    "author": "Mumulhl",
    "version": (1, 0, 0),
    "blender": (5, 1, 0),
    "location": "View3D > N-Panel > 形态键分类",
    "description": "形态键分类、滚动式预设编辑、复选框多选归类、镜像K帧、自动K帧、通配符批量匹配以及预设导出/应用",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import importlib
import bpy

from . import i18n, core, frequency_presets, properties, ui_lists, operators, presets, panel

# 方便开发时在 Blender 内重新加载模块。
for _mod in (i18n, core, frequency_presets, properties, ui_lists, operators, presets, panel):
    importlib.reload(_mod)

classes = [
    properties.ShapeKeyItem,
    properties.MeshShapeKeyManager,
    properties.ShapeKeyCategoryItem,
    frequency_presets.SK_OT_sort_by_current_keyframe_frequency,
    frequency_presets.SK_OT_create_frequency_preset,
    frequency_presets.SK_OT_delete_frequency_preset,
    frequency_presets.SK_OT_add_current_project_frequency,
    frequency_presets.SK_OT_sort_by_frequency_preset,
    frequency_presets.SK_OT_delete_frequency_project_statistics,
    ui_lists.MESH_UL_sk_categories,
    ui_lists.MESH_UL_all_shapekeys,
    ui_lists.MESH_UL_filtered_shapekeys,
    operators.SK_OT_add_category,
    operators.SK_OT_remove_category,
    operators.SK_OT_reorder_category,
    operators.SK_OT_reorder_shapekey,
    operators.SK_OT_sync_mirror_aliases,
    operators.SK_OT_move_active_shapekey_to,
    operators.SK_OT_auto_match,
    operators.SK_OT_assign_category,
    operators.SK_OT_assign_active_all_to_category,
    operators.SK_OT_clear_active_all_category,
    operators.SK_OT_clear_all_list_selection,
    operators.SK_OT_assign_active_and_above_category,
    operators.SK_OT_clear_category,
    operators.SK_OT_keyframe_single,
    operators.SK_OT_keyframe_batch,
    operators.SK_OT_select_all,
    operators.SK_OT_reset_selected,
    presets.SK_OT_export_preset,
    presets.SK_OT_import_preset,
    panel.VIEW3D_PT_sk_organizer,
    panel.VIEW3D_PT_sk_frequency_statistics,
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
        bpy.app.translations.register(__name__, i18n.translations_dict)
    except Exception as e:
        print(f"Translations register error: {e}")

    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except Exception as e:
            print(f"Register failed: {cls} - {e}")

    try:
        bpy.types.Mesh.sk_items = bpy.props.CollectionProperty(type=properties.ShapeKeyItem)
        bpy.types.Mesh.sk_categories = bpy.props.CollectionProperty(type=properties.ShapeKeyCategoryItem)
        bpy.types.WindowManager.sk_manager = bpy.props.PointerProperty(type=properties.MeshShapeKeyManager)
    except Exception as e:
        print(f"Register properties failed: {e}")

    if core.shapekey_monitor_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(core.shapekey_monitor_handler)
    if core.shapekey_frame_change_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(core.shapekey_frame_change_handler)


def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass

    if core.shapekey_monitor_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(core.shapekey_monitor_handler)
    if core.shapekey_frame_change_handler in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(core.shapekey_frame_change_handler)

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
