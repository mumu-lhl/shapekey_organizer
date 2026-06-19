bl_info = {
    "name": "Shape Key Classification",
    "author": "Mumulhl",
    "version": (0, 0, 1),
    "blender": (5, 1, 0),
    "location": "View3D > N-Panel > 形态键分类",
    "description": "形态键分类。采用 WindowManager 承载 UI 开关、分类上下移动、重命名防丢失、镜像K帧、支持强制推栈(Undo Push)的延时防抖自动K帧、通配符批量匹配以及预设导出/应用",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import bpy
import re
import json
import time
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
# 2. 核心数据同步、防抖定时器与工具函数
# ==========================================

_shape_key_cache = {}
_mirror_updating = False

_pending_keyframes = {} 
_timer_running = False

def auto_keyframe_timer_callback():
    """轻量级系统定时器：停止拖动滑块超过 0.3 秒后，调用撤销算子写入关键帧"""
    global _pending_keyframes, _timer_running
    current_time = time.time()
    keys_to_remove = []
    
    try:
        scene = bpy.context.scene
    except AttributeError:
        return 0.05
        
    for (obj_name, kb_name), last_change_time in list(_pending_keyframes.items()):
        if current_time - last_change_time >= 0.3:
            obj = bpy.data.objects.get(obj_name)
            if obj and obj.data and obj.data.shape_keys:
                # 检查是否开启了镜像，若开启则动态获取镜像名，以便在单个 Undo 算子中合并写入
                mgr = bpy.context.window_manager.sk_manager
                mirror_kb_name = ""
                if mgr.mirror_mode:
                    m_name = mirror_name(kb_name)
                    if m_name and m_name in obj.data.shape_keys.key_blocks:
                        mirror_kb_name = m_name
                
                # 调用自定义撤销算子，确保写入动作可被 Ctrl+Z 完美消除
                try:
                    bpy.ops.sk_helper.insert_keyframe(
                        obj_name=obj_name,
                        kb_name=kb_name,
                        frame=scene.frame_current,
                        mirror_kb_name=mirror_kb_name
                    )
                except Exception as e:
                    print(f"Auto-keyframe failed: {e}")
                    
            keys_to_remove.append((obj_name, kb_name))
            
    for k in keys_to_remove:
        _pending_keyframes.pop(k, None)
        
    if _pending_keyframes:
        return 0.05
    else:
        _timer_running = False
        return None

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

def is_keyframed_on_current_frame(key_block_parent, key_name, frame):
    """检测指定形态键在当前帧是否已有关键帧"""
    if not key_block_parent.animation_data or not key_block_parent.animation_data.action:
        return False
    action = key_block_parent.animation_data.action
    data_path = f'key_blocks["{key_name}"].value'
    for fcurve in action.fcurves:
        if fcurve.data_path == data_path:
            for kp in fcurve.keyframe_points:
                if abs(kp.co[0] - frame) < 0.01:
                    return True
    return False

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
        
    kb_names = [kb.name for kb in mesh.shape_keys.key_blocks if kb.name != "Basis"]
    item_names = [item.name for item in mesh.sk_items]
    
    if kb_names != item_names:
        cat_cache = {item.name: item.category for item in mesh.sk_items}
        sel_cache = {item.name: item.selected for item in mesh.sk_items}
        
        mesh.sk_items.clear()
        for name in kb_names:
            item = mesh.sk_items.add()
            item.name = name
            item.category = cat_cache.get(name, "")
            item.selected = sel_cache.get(name, False)


@bpy.app.handlers.persistent
def shapekey_monitor_handler(scene, depsgraph):
    """Depsgraph 监听器：后台高安全级别数据同步、自动防抖K帧与镜像同步"""
    global _mirror_updating, _shape_key_cache, _pending_keyframes, _timer_running
    if _mirror_updating:
        return
        
    if screen_is_playing():
        return

    try:
        context = bpy.context
        obj = context.active_object
        wm = context.window_manager
    except AttributeError:
        return

    if not obj or obj.type != 'MESH' or not obj.data or not obj.data.shape_keys:
        return

    try:
        _mirror_updating = True
        check_and_sync_sk_items(obj.data)
        _mirror_updating = False
    except Exception:
        _mirror_updating = False
        pass

    try:
        mgr = wm.sk_manager
        if not mgr:
            return
        auto_key = mgr.auto_keyframe
        mirror_mode = mgr.mirror_mode
    except AttributeError:
        return

    key = obj.data.shape_keys
    kb_list = key.key_blocks
    mesh_name = obj.data.name

    for kb in kb_list:
        cache_key = (mesh_name, kb.name)
        old_val = _shape_key_cache.get(cache_key, None)
        
        try:
            new_val = kb.value
        except ReferenceError:
            continue

        if old_val is not None and abs(old_val - new_val) > 0.0001:
            # 1. 镜像模式
            if mirror_mode:
                m_name = mirror_name(kb.name)
                if m_name and m_name in kb_list:
                    try:
                        _mirror_updating = True
                        kb_list[m_name].value = new_val
                        _shape_key_cache[(mesh_name, m_name)] = new_val
                        _mirror_updating = False
                    except Exception:
                        _mirror_updating = False
            
            # 2. 自动K帧（防抖队列延迟写入）
            if auto_key:
                _pending_keyframes[(obj.name, kb.name)] = time.time()
                
                if not _timer_running:
                    _timer_running = True
                    bpy.app.timers.register(auto_keyframe_timer_callback)

        _shape_key_cache[cache_key] = new_val


# ==========================================
# 3. 属性组定义 (Property Groups)
# ==========================================

class ShapeKeyItem(bpy.types.PropertyGroup):
    """存储在 Mesh 下的形态键元数据"""
    name: bpy.props.StringProperty()
    category: bpy.props.StringProperty(default="")
    selected: bpy.props.BoolProperty(default=False)

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
    active_item_index: bpy.props.IntProperty(default=0)
    
    auto_keyframe: bpy.props.BoolProperty(
        name="Auto Keyframe",
        description="Automatically insert keyframe when shape key value changes",
        default=False
    )
    mirror_mode: bpy.props.BoolProperty(
        name="Mirror Mode",
        description="Automatically mirror value adjustments and keyframes to opposite side",
        default=False
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
            row.label(text=item.name)
            row.prop(kb, "value", text="", slider=True)
            
            # 检测关键帧状态
            has_key = is_keyframed_on_current_frame(obj.data.shape_keys, item.name, context.scene.frame_current)
            icon_type = 'DECORATE_KEYFRAME' if has_key else 'DECORATE_ANIMATE'
            
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
        
        for i, item in enumerate(items):
            if item.category != cat_name:
                filter_flags[i] &= ~self.bitflag_filter_item
                
        return filter_flags, filter_order


# ==========================================
# 5. 操作算子 (Operators)
# ==========================================

class SK_OT_insert_keyframe(bpy.types.Operator):
    """
    内部撤销算子：
    专为防抖自动K帧编写。通过将 keyframe_insert 包装在带 UNDO 标识的算子中，
    并在末尾显式触发 `undo_push`，强制 Blender 数据库为异步K帧事件追加历史快照，
    从而根治 Ctrl+Z 撤销时遗留关键帧、使其数值变为0的顽固架构问题。
    """
    bl_idname = "sk_helper.insert_keyframe"
    bl_label = "Insert Shape Key Keyframe"
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    
    obj_name: bpy.props.StringProperty()
    kb_name: bpy.props.StringProperty()
    frame: bpy.props.IntProperty()
    mirror_kb_name: bpy.props.StringProperty(default="")
    
    def execute(self, context):
        obj = bpy.data.objects.get(self.obj_name)
        if obj and obj.data and obj.data.shape_keys:
            key = obj.data.shape_keys
            kb_list = key.key_blocks
            
            # 1. 写入主形态键关键帧
            if self.kb_name in kb_list:
                key.keyframe_insert(
                    data_path=f'key_blocks["{self.kb_name}"].value',
                    frame=self.frame
                )
                
            # 2. 如果提供了镜像，合并在同一个撤销步骤中写入镜像关键帧
            if self.mirror_kb_name and self.mirror_kb_name in kb_list:
                key.keyframe_insert(
                    data_path=f'key_blocks["{self.mirror_kb_name}"].value',
                    frame=self.frame
                )
                
            # 3. 强力加固：强制通知 Blender 撤销引擎，立即在历史栈顶建立一个名为 "Auto Keyframe" 的安全还原快照点
            try:
                bpy.ops.ed.undo_push(message="Auto Keyframe")
            except Exception as e:
                print(f"Undo push failed: {e}")
                
        return {'FINISHED'}

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
        items=[
            ('UP', "Up", ""),
            ('DOWN', "Down", "")
        ]
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
        has_key = is_keyframed_on_current_frame(obj.data.shape_keys, self.shapekey_name, frame)
        
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
            
            # 处理镜像侧
            mgr = context.window_manager.sk_manager
            if mgr.mirror_mode:
                m_name = mirror_name(self.shapekey_name)
                if m_name and m_name in key_blocks:
                    key_blocks[m_name].value = kb.value
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
                if mgr.auto_keyframe:
                    obj.data.shape_keys.keyframe_insert(
                        data_path=f'key_blocks["{kb.name}"].value',
                        frame=context.scene.frame_current
                    )
                if mgr.mirror_mode:
                    m_name = mirror_name(kb.name)
                    if m_name and m_name in key_blocks:
                        key_blocks[m_name].value = 0.0
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
            cat_data = {
                "name": cat.name,
                "match_pattern": cat.match_pattern,
                "assigned_keys": keys
            }
            preset_data["categories"].append(cat_data)
            
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
            
            assigned_keys = cat_data.get("assigned_keys", [])
            for key_name in assigned_keys:
                for item in obj.data.sk_items:
                    if item.name == key_name:
                        item.category = cat.name
                        break
                        
            pattern = cat.match_pattern
            if pattern:
                for item in obj.data.sk_items:
                    if item.category == "":
                        if match_pattern(item.name, pattern):
                            item.category = cat.name
                            
        context.window_manager.sk_manager.active_category_index = 0
        self.report({'INFO'}, f"Imported {len(categories_data)} categories successfully.")
        return {'FINISHED'}


# ==========================================
# 7. UI 主面板布局
# ==========================================

class VIEW3D_PT_sk_organizer(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Shape Key Classification' # 通过双保险机制自动翻译
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
        
        # 侧边控制栏（增、删、上移、下移）
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
        
        if len(categories) > 0 and mgr.active_category_index >= 0 and mgr.active_category_index < len(categories):
            active_cat = categories[mgr.active_category_index]
            box.label(text=f"{_('Active Category:')} {active_cat.name}", icon='FOLDER_REDIRECT')
            
            box.template_list("MESH_UL_filtered_shapekeys", "", obj.data, "sk_items", mgr, "active_item_index")
            
            # 批量操作选择
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
            
            # 批量K帧
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
    SK_OT_insert_keyframe,
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
    # 强制进行清理，防止上一次由于错误终止导致的未注销残留
    try:
        unregister()
    except Exception:
        pass

    try:
        # 重载阶段直接显式清除当前模块名的缓存数据，确保 translations.register 绝不报错
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
        # 将配置管理器（Manager）注册在 WindowManager 下，天然免受三维场景撤销（Undo）的回滚影响
        bpy.types.WindowManager.sk_manager = bpy.props.PointerProperty(type=MeshShapeKeyManager)
    except Exception as e:
        print(f"Register properties failed: {e}")
    
    if shapekey_monitor_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(shapekey_monitor_handler)

def unregister():
    try:
        bpy.app.translations.unregister(__name__)
    except Exception:
        pass
    
    if shapekey_monitor_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(shapekey_monitor_handler)
        
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