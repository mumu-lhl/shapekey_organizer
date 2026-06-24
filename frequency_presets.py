import json
import os
import hashlib

import bpy

from .core import check_and_sync_sk_items, reorder_sk_items_by_names


PRESET_RELATIVE_DIR = "presets/shapekey_organizer_frequency"
PRESET_VERSION = "1.0"
EMPTY_ENUM_VALUE = "__NONE__"
_frequency_preset_enum_items = []
_frequency_project_enum_items = []
_enum_item_cache = {}


def _retain_enum_items(items):
    """Keep dynamic enum strings alive for Blender's RNA callbacks."""
    key = tuple(items)
    if key not in _enum_item_cache:
        _enum_item_cache[key] = items
    return _enum_item_cache[key]


def _preset_directory():
    return bpy.utils.user_resource('SCRIPTS', path=PRESET_RELATIVE_DIR, create=True)


def _preset_path(preset_name):
    return os.path.join(_preset_directory(), f"{preset_name}.json")


def _available_preset_names():
    directory = _preset_directory()
    if not directory or not os.path.isdir(directory):
        return []
    return sorted(
        os.path.splitext(filename)[0]
        for filename in os.listdir(directory)
        if filename.lower().endswith(".json") and os.path.isfile(os.path.join(directory, filename))
    )


def _preset_enum_identifier(preset_name):
    digest = hashlib.sha1(preset_name.encode('utf-8')).hexdigest()
    return f"preset_{digest}"


def _selected_preset_name(selection):
    """Resolve a UI enum value back to the JSON filename stem."""
    if not selection or selection == EMPTY_ENUM_VALUE:
        return ""
    for preset_name in _available_preset_names():
        if selection == preset_name or selection == _preset_enum_identifier(preset_name):
            return preset_name
    return ""


def frequency_preset_items(self, context):
    global _frequency_preset_enum_items
    names = _available_preset_names()
    if not names:
        _frequency_preset_enum_items = [
            (EMPTY_ENUM_VALUE, "No Frequency Presets", "Create a frequency statistics preset first")
        ]
    else:
        _frequency_preset_enum_items = [
            (_preset_enum_identifier(name), name, f"Frequency statistics preset: {name}")
            for name in names
        ]
    return _retain_enum_items(_frequency_preset_enum_items)


def _read_preset(preset_name):
    with open(_preset_path(preset_name), 'r', encoding='utf-8') as file:
        data = json.load(file)
    if not isinstance(data, dict) or not isinstance(data.get("projects", {}), dict):
        raise ValueError("Invalid frequency statistics preset")
    return data


def _write_preset(preset_name, data):
    with open(_preset_path(preset_name), 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def _current_project_id():
    if not bpy.data.filepath:
        return ""
    return bpy.path.abspath(bpy.data.filepath)


def _project_enum_identifier(project_id):
    """Enum identifiers must be ASCII; Blender paths may contain Unicode."""
    digest = hashlib.sha1(project_id.encode('utf-8')).hexdigest()
    return f"project_{digest}"


def _selected_project_id(preset_name, selection):
    """Resolve a UI enum value back to the project path stored in the JSON file."""
    if not selection or selection == EMPTY_ENUM_VALUE:
        return ""
    projects = _read_preset(preset_name).get("projects", {})
    if selection in projects:
        return selection  # Supports selections saved by the previous implementation.
    for project_id in projects:
        if _project_enum_identifier(project_id) == selection:
            return project_id
    return ""


def count_mesh_keyframes(mesh):
    """Return non-zero value-keyframe point counts for this mesh's shape keys."""
    if not mesh.shape_keys or not mesh.shape_keys.animation_data:
        return {}
    action = mesh.shape_keys.animation_data.action
    if not action:
        return {}

    counts = {item.name: 0 for item in mesh.sk_items}
    data_path_to_name = {
        f'key_blocks["{key_name}"].value': key_name
        for key_name in counts
    }
    for fcurve in action.fcurves:
        key_name = data_path_to_name.get(fcurve.data_path)
        if key_name:
            counts[key_name] += len(fcurve.keyframe_points)
    return {name: count for name, count in counts.items() if count > 0}


def collect_current_project_statistics():
    """Collect non-zero counts from every plugin-managed mesh in the current file."""
    meshes = {}
    for mesh in bpy.data.meshes:
        if not mesh.shape_keys or not hasattr(mesh, "sk_items"):
            continue
        check_and_sync_sk_items(mesh)
        counts = count_mesh_keyframes(mesh)
        if counts:
            meshes[mesh.name] = {"keyframe_counts": counts}
    return meshes


def aggregate_preset_counts(data):
    """Sum same-named shape keys from every project and mesh in a preset."""
    totals = {}
    for project in data.get("projects", {}).values():
        if not isinstance(project, dict):
            continue
        meshes = project.get("meshes", {})
        if not isinstance(meshes, dict):
            continue
        for mesh in meshes.values():
            if not isinstance(mesh, dict):
                continue
            keyframe_counts = mesh.get("keyframe_counts", {})
            if not isinstance(keyframe_counts, dict):
                continue
            for key_name, count in keyframe_counts.items():
                if isinstance(count, int) and count > 0:
                    totals[key_name] = totals.get(key_name, 0) + count
    return totals


def _categorized_shape_key_indices(mesh):
    """Return every shape key assigned to any category, in current list order."""
    return [
        index for index, item in enumerate(mesh.sk_items)
        if item.category.strip()
    ]


def _sort_mesh_by_counts(mesh, counts):
    check_and_sync_sk_items(mesh)
    target_indices = _categorized_shape_key_indices(mesh)
    original_names = [item.name for item in mesh.sk_items]
    target_names = [original_names[index] for index in target_indices]
    ordered_target_names = sorted(
        target_names,
        key=lambda name: (-counts.get(name, 0), target_names.index(name)),
    )
    ordered_names = list(original_names)
    for index, name in zip(target_indices, ordered_target_names):
        ordered_names[index] = name
    if ordered_names != original_names:
        reorder_sk_items_by_names(mesh, ordered_names)
    return sum(1 for name in target_names if counts.get(name, 0) > 0)


def frequency_project_items(self, context):
    global _frequency_project_enum_items
    preset_name = _selected_preset_name(getattr(self, "frequency_preset", ""))
    if not preset_name:
        _frequency_project_enum_items = [
            (EMPTY_ENUM_VALUE, "No Project Statistics", "Select a frequency statistics preset first")
        ]
        return _retain_enum_items(_frequency_project_enum_items)
    try:
        projects = _read_preset(preset_name).get("projects", {})
    except (OSError, ValueError, json.JSONDecodeError):
        projects = {}
    if not projects:
        _frequency_project_enum_items = [
            (EMPTY_ENUM_VALUE, "No Project Statistics", "This preset does not contain project statistics")
        ]
        return _retain_enum_items(_frequency_project_enum_items)
    _frequency_project_enum_items = [
        (
            _project_enum_identifier(project_id),
            project.get("name", os.path.basename(project_id) or project_id),
            project_id,
        )
        for project_id, project in sorted(projects.items())
        if isinstance(project, dict)
    ]
    if not _frequency_project_enum_items:
        _frequency_project_enum_items = [
            (EMPTY_ENUM_VALUE, "No Project Statistics", "This preset does not contain valid project statistics")
        ]
    return _retain_enum_items(_frequency_project_enum_items)


class SK_OT_sort_by_current_keyframe_frequency(bpy.types.Operator):
    bl_idname = "sk_helper.sort_by_current_keyframe_frequency"
    bl_label = "Sort by Current Project Frequency"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            return False
        return bool(_categorized_shape_key_indices(obj.data))

    def execute(self, context):
        mesh = context.active_object.data
        check_and_sync_sk_items(mesh)
        matched_count = _sort_mesh_by_counts(mesh, count_mesh_keyframes(mesh))
        self.report({'INFO'}, f"Sorted all categorized shape keys using {matched_count} non-zero current-project frequencies")
        return {'FINISHED'}


class SK_OT_create_frequency_preset(bpy.types.Operator):
    bl_idname = "sk_helper.create_frequency_preset"
    bl_label = "Create Frequency Preset"
    bl_options = {'REGISTER'}

    preset_name: bpy.props.StringProperty(name="Preset Name", default="Frequency Statistics")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        preset_name = os.path.splitext(os.path.basename(self.preset_name.strip()))[0]
        if not preset_name or preset_name in {'.', '..', EMPTY_ENUM_VALUE}:
            self.report({'ERROR'}, "Enter a valid preset name")
            return {'CANCELLED'}
        if preset_name in _available_preset_names():
            self.report({'ERROR'}, "A frequency preset with this name already exists")
            return {'CANCELLED'}
        _write_preset(preset_name, {"preset_version": PRESET_VERSION, "projects": {}})
        context.window_manager.sk_manager.frequency_preset = _preset_enum_identifier(preset_name)
        self.report({'INFO'}, f"Created frequency preset '{preset_name}'")
        return {'FINISHED'}


class SK_OT_delete_frequency_preset(bpy.types.Operator):
    bl_idname = "sk_helper.delete_frequency_preset"
    bl_label = "Delete Frequency Preset"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        preset_name = _selected_preset_name(context.window_manager.sk_manager.frequency_preset)
        if preset_name not in _available_preset_names():
            self.report({'ERROR'}, "Select an existing frequency preset")
            return {'CANCELLED'}
        try:
            os.remove(_preset_path(preset_name))
        except OSError as error:
            self.report({'ERROR'}, f"Failed to delete frequency preset: {error}")
            return {'CANCELLED'}
        remaining_names = _available_preset_names()
        context.window_manager.sk_manager.frequency_preset = (
            _preset_enum_identifier(remaining_names[0]) if remaining_names else EMPTY_ENUM_VALUE
        )
        self.report({'INFO'}, f"Deleted frequency preset '{preset_name}'")
        return {'FINISHED'}


class SK_OT_add_current_project_frequency(bpy.types.Operator):
    bl_idname = "sk_helper.add_current_project_frequency"
    bl_label = "Add Current Project Statistics"
    bl_options = {'REGISTER'}

    def execute(self, context):
        preset_name = _selected_preset_name(context.window_manager.sk_manager.frequency_preset)
        if preset_name not in _available_preset_names():
            self.report({'ERROR'}, "Select an existing frequency preset")
            return {'CANCELLED'}
        project_id = _current_project_id()
        if not project_id:
            self.report({'ERROR'}, "Save the Blender file before adding project statistics")
            return {'CANCELLED'}
        try:
            data = _read_preset(preset_name)
            meshes = collect_current_project_statistics()
            if meshes:
                data["projects"][project_id] = {
                    "name": os.path.basename(project_id),
                    "meshes": meshes,
                }
            else:
                data["projects"].pop(project_id, None)
            _write_preset(preset_name, data)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.report({'ERROR'}, f"Failed to save project statistics: {error}")
            return {'CANCELLED'}
        if meshes:
            context.window_manager.sk_manager.frequency_project = _project_enum_identifier(project_id)
            self.report({'INFO'}, f"Added statistics for {len(meshes)} mesh(es) to '{preset_name}'")
        else:
            context.window_manager.sk_manager.frequency_project = next(
                (
                    _project_enum_identifier(project_id)
                    for project_id in _read_preset(preset_name).get("projects", {})
                ),
                EMPTY_ENUM_VALUE,
            )
            self.report({'INFO'}, "No non-zero shape key frequencies were found in this project")
        return {'FINISHED'}


class SK_OT_sort_by_frequency_preset(bpy.types.Operator):
    bl_idname = "sk_helper.sort_by_frequency_preset"
    bl_label = "Sort by Frequency Preset"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj or obj.type != 'MESH' or not obj.data.shape_keys:
            return False
        return bool(_categorized_shape_key_indices(obj.data))

    def execute(self, context):
        preset_name = _selected_preset_name(context.window_manager.sk_manager.frequency_preset)
        if preset_name not in _available_preset_names():
            self.report({'ERROR'}, "Select an existing frequency preset")
            return {'CANCELLED'}
        try:
            counts = aggregate_preset_counts(_read_preset(preset_name))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.report({'ERROR'}, f"Failed to load frequency preset: {error}")
            return {'CANCELLED'}
        matched_count = _sort_mesh_by_counts(context.active_object.data, counts)
        self.report({'INFO'}, f"Sorted all categorized shape keys using {matched_count} saved frequencies")
        return {'FINISHED'}


class SK_OT_delete_frequency_project_statistics(bpy.types.Operator):
    bl_idname = "sk_helper.delete_frequency_project_statistics"
    bl_label = "Delete Project Statistics"
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        manager = context.window_manager.sk_manager
        preset_name = _selected_preset_name(manager.frequency_preset)
        if preset_name not in _available_preset_names():
            self.report({'ERROR'}, "Select saved project statistics")
            return {'CANCELLED'}
        try:
            data = _read_preset(preset_name)
            project_id = _selected_project_id(preset_name, manager.frequency_project)
            if not project_id:
                self.report({'ERROR'}, "Select saved project statistics")
                return {'CANCELLED'}
            if project_id not in data["projects"]:
                self.report({'ERROR'}, "Selected project statistics no longer exist")
                return {'CANCELLED'}
            del data["projects"][project_id]
            _write_preset(preset_name, data)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.report({'ERROR'}, f"Failed to delete project statistics: {error}")
            return {'CANCELLED'}
        remaining_projects = _read_preset(preset_name).get("projects", {})
        manager.frequency_project = next(
            (_project_enum_identifier(project_id) for project_id in remaining_projects),
            EMPTY_ENUM_VALUE,
        )
        self.report({'INFO'}, "Deleted saved project statistics")
        return {'FINISHED'}
