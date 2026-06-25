import bpy

from .i18n import _
from .core import (
    get_shapekey_slider_value,
    set_shapekey_slider_value,
    get_shapekey_preview_value,
    set_shapekey_preview_value,
    on_active_item_index_changed,
    on_active_all_item_index_changed,
    on_all_selected_changed,
    on_auto_keyframe_toggled,
)
from .frequency_presets import frequency_preset_items, frequency_project_items

DEFAULT_AI_ALIAS_PROMPT = """You are helping rename Blender shape keys into readable, clear, concise aliases.

Target language: {target_language}

Task:
- Create one alias for each shape key name listed below.
- Keep aliases short and easy to scan in an animator-facing UI.
- Preserve important side markers such as Left/Right when they affect meaning.
- Do not invent controls that are not implied by the original name.
- Prefer natural words over technical abbreviations when possible.

Output format:
- Return only a JSON object.
- Each key must be the exact original shape key name.
- Each value must be the alias.

Shape key names:
{shape_key_names}"""


def get_addon_preferences(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


class ShapeKeyOrganizerPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    ai_alias_prompt: bpy.props.StringProperty(
        name="AI Alias Prompt",
        description="Prompt template used when copying AI alias generation prompts. Supports {target_language} and {shape_key_names}",
        default=DEFAULT_AI_ALIAS_PROMPT,
        maxlen=8192,
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text=_("AI Alias Prompt"), icon='TEXT')
        layout.prop(self, "ai_alias_prompt", text="")
        layout.operator("sk_helper.reset_ai_alias_prompt", text=_("Use Default AI Alias Prompt"), icon='LOOP_BACK')


class ShapeKeyItem(bpy.types.PropertyGroup):
    """存储在 Mesh 下的形态键元数据"""
    name: bpy.props.StringProperty()
    alias: bpy.props.StringProperty(default="")
    category: bpy.props.StringProperty(default="")
    category_order: bpy.props.IntProperty(default=-1)
    selected: bpy.props.BoolProperty(default=False)
    # “所有形态键”列表专用选择状态，避免影响当前分类里的动画勾选/批量K帧。
    all_selected: bpy.props.BoolProperty(default=False, update=on_all_selected_changed)
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
    alias_preview_value: bpy.props.FloatProperty(
        name="Preview Value",
        description="Preview this shape key value while editing aliases without inserting keyframes",
        min=-100.0,
        max=100.0,
        soft_min=0.0,
        soft_max=1.0,
        precision=3,
        get=get_shapekey_preview_value,
        set=set_shapekey_preview_value
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
    # “所有形态键”列表使用独立活动索引，代表这个列表里的原生单选行。
    active_all_item_index: bpy.props.IntProperty(default=0, update=on_active_all_item_index_changed)
    active_all_item_name: bpy.props.StringProperty(default="")
    active_alias_item_index: bpy.props.IntProperty(default=0)
    ai_alias_target_language: bpy.props.StringProperty(
        name="Target Language",
        description="Target language for AI-generated shape key aliases",
        default="English",
    )
    ai_alias_json_text: bpy.props.StringProperty(
        name="AI Alias JSON",
        description="Paste the JSON object returned by the AI, using exact shape key names as keys and aliases as values",
        default="",
        maxlen=65535,
    )
    # “所有形态键”列表的范围/批量选择锚点；复选框多选与原生单选行分离。
    all_select_anchor_index: bpy.props.IntProperty(default=-1)
    all_select_anchor_name: bpy.props.StringProperty(default="")
    all_search_text: bpy.props.StringProperty(
        name="All List Search",
        description="Filter the All Shape Keys list by name, alias, or category",
        default=""
    )
    show_preset_tools: bpy.props.BoolProperty(
        name="Preset Editor",
        description="Hide Auto Match and All Shape Keys tools after presets are ready",
        default=True
    )
    left_alias_prefix: bpy.props.StringProperty(
        name="Left Alias Prefix",
        description="Text added before aliases of left mirror shape keys",
        default=""
    )
    left_alias_suffix: bpy.props.StringProperty(
        name="Left Alias Suffix",
        description="Text added after aliases of left mirror shape keys",
        default=""
    )
    right_alias_prefix: bpy.props.StringProperty(
        name="Right Alias Prefix",
        description="Text added before aliases of right mirror shape keys",
        default=""
    )
    right_alias_suffix: bpy.props.StringProperty(
        name="Right Alias Suffix",
        description="Text added after aliases of right mirror shape keys",
        default=""
    )
    frequency_preset: bpy.props.EnumProperty(
        name="Frequency Preset",
        description="Frequency statistics preset stored in Blender's user preset directory",
        items=frequency_preset_items
    )
    frequency_project: bpy.props.EnumProperty(
        name="Saved Project Statistics",
        description="Project statistics stored in the selected frequency preset",
        items=frequency_project_items
    )
    auto_keyframe: bpy.props.BoolProperty(
        name="Auto Keyframe",
        description="Enable Blender Auto Key for native shape key value editing",
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
