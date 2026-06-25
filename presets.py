import bpy
import json
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .core import match_pattern, check_and_sync_sk_items, reorder_sk_items_from_preset
from .i18n import _

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
            "preset_version": "1.0",
            "mesh_name": obj.data.name,
            "categories": [],
            "key_aliases": {
                item.name: item.alias
                for item in obj.data.sk_items
                if item.alias.strip()
            }
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
            self.report({'INFO'}, _("Preset successfully exported to {}").format(self.filepath))
        except Exception as e:
            self.report({'ERROR'}, _("Failed to export preset: {}").format(e))
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
            self.report({'ERROR'}, _("Failed to read preset file: {}").format(e))
            return {'CANCELLED'}
        obj.data.sk_categories.clear()
        check_and_sync_sk_items(obj.data)
        for item in obj.data.sk_items:
            item.category = ""
        categories_data = preset_data.get("categories", [])
        key_aliases = preset_data.get("key_aliases", {})
        for cat_data in categories_data:
            cat = obj.data.sk_categories.add()
            cat.name = cat_data.get("name", _("New Category"))
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
        for item in obj.data.sk_items:
            item.alias = key_aliases.get(item.name, "")
        context.window_manager.sk_manager.active_category_index = 0
        self.report({'INFO'}, _("Imported {} categories successfully.").format(len(categories_data)))
        return {'FINISHED'}
