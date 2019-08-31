import math
import time

import bpy
import bmesh
from bpy.app.handlers import persistent

import mathutils
from mathutils import Matrix, Vector

from . import render
from . import mesh
from . import props

class Updater():
    '''
    This is the main updater, it hooks up the depsgraph handler (which in turn starts
    a never ending modal timer) and handles the required updates whenever something changed via the depsgraph.

    The heartbeat does the decicion making when to update what, and then calls all the necessary refreshes of the data,
    and finally updates the renderers.
    '''

    def __init__(self):
        self.renderer_view3d = render.RendererView3d()
        self.renderer_uv = render.RendererUV()
        self.settings = None
        self.mouse_update = False
        self.mouse_position = Vector((0, 0, 0))
        self.timer_running = False
        self.visible = False
        self.uv_select_mode = "VERTEX"                  
        self.uv_select_sync_mode = False
        self.mesh_data = {}
        self.last_update = {}
        self.op = None
        self.uv_editor_visible = False

    def unsubscribe_from_depsgraph_update(self):
        try:
            bpy.app.handlers.depsgraph_update_post.remove(
                self.depsgraph_handler)
        except Exception as e:
            pass

    def start(self):
        # print("Start UV Highlight")
        self.__init__()
        self.unsubscribe_from_depsgraph_update()
        bpy.app.handlers.depsgraph_update_post.append(self.depsgraph_handler)

    def stop(self):
        # print("Stop UV Highlight")
        self.renderer_uv.disable()
        self.renderer_view3d.disable()
        self.timer_running = False

        self.unsubscribe_from_depsgraph_update()

    # this queries all the objects in edit mode, to find the object closest to the cursor
    def update_preselection(self, active_objects, uv_select_mode):
        if not self.mouse_position:
            return

        min_dist = math.inf
        target_mesh_data = None
        min_closest_uv = None

        for id in active_objects.keys():
            mesh_data = self.mesh_data[id]
            distance, closest_uv = mesh_data.get_closest_uv_distance(self.mouse_position)

            if distance < min_dist:                
                min_dist = distance
                min_closest_uv = closest_uv
                target_mesh_data = mesh_data

        if target_mesh_data:
            if target_mesh_data.update_preselection(uv_select_mode, min_closest_uv, self.mouse_position):
                self.renderer_view3d.preselection(target_mesh_data)
                self.renderer_uv.preselection(target_mesh_data)
                render.tag_redraw_all_views()
    
    def hide_preselection(self):
        self.renderer_view3d.hide_preselection()
        self.renderer_uv.hide_preselection()
        render.tag_redraw_all_views()

    def handle_update_rendering(self):
        if self.pending_updates():
            # self.renderer_view3d.visible = False
            self.renderer_uv.visible = False
            render.tag_redraw_all_views()
        else:            
            self.renderer_view3d.visible = True
            self.renderer_uv.visible = True
            render.tag_redraw_all_views()

    def get_active_objects(self, depsgraph=None):
        active_objects = {}
        objects = bpy.context.selected_objects
        for obj in objects:
            if obj.type != 'MESH':
                continue

            target = obj
            if depsgraph:
                target = obj.evaluated_get(depsgraph)
                target = obj.original

            active_objects[obj.name] = target
        return active_objects

    def all_modes_disabled(self):
        return (
            not self.settings.show_in_viewport and
            not self.settings.show_preselection
            )

    def set_visibility(self, visible):

        if self.visible == visible:
            return

        self.visible = visible

        # print(f"SET VISIBILITY:{visible}")

        if visible:
            self.renderer_uv.enable()
            self.renderer_view3d.enable()
        else:
            self.renderer_uv.disable()
            self.renderer_view3d.disable()
            self.last_update.clear()
            self.mesh_data.clear()

        render.tag_redraw_all_views()
             
    def fetch_mesh_data(self, active_objects, force_fetch_mesh_data):

        t = -1
        if force_fetch_mesh_data:
            t = 0.1

        for id in active_objects.keys():
            if id not in self.mesh_data.keys():
                self.mesh_data[id] = mesh.Data(self.settings)
                self.last_update[id] = t

    def heartbeat(self):

        obj = bpy.context.active_object
        if not obj or obj.type != 'MESH':
            return

        self.free()

        force_fetch_mesh_data = False

        if self.all_modes_disabled() or obj.mode != 'EDIT':
            self.set_visibility(False)
            return
        else:
            self.set_visibility(True)
            force_fetch_mesh_data = True

        uv_select_sync_mode = bpy.context.scene.tool_settings.use_uv_select_sync        
        if uv_select_sync_mode != self.uv_select_sync_mode:
            self.uv_select_sync_mode = uv_select_sync_mode
            self.set_visibility(not uv_select_sync_mode)
            if uv_select_sync_mode:
                return
            else:
                force_fetch_mesh_data = True
            
        self.handle_uv_selection_mode_changed()

        depsgraph = bpy.context.evaluated_depsgraph_get()
        active_objects = self.get_active_objects(depsgraph)
        
        self.fetch_mesh_data(active_objects, force_fetch_mesh_data)
       
        if self.handle_uv_edtitor_visibility_changed(active_objects):            
            return

        if self.handle_id_updates(active_objects):            
            return

        if self.handle_operators(active_objects):
            return

        self.handle_update_rendering()
       
        if self.settings.show_preselection:
            if self.pending_updates():
                self.hide_preselection()
            else:
                self.update_preselection(active_objects, self.uv_select_mode)

    def handle_uv_selection_mode_changed(self):
        uv_select_mode = bpy.context.scene.tool_settings.uv_select_mode
        if uv_select_mode != self.uv_select_mode:
            self.uv_select_mode = uv_select_mode
            self.renderer_view3d.mode = uv_select_mode
            self.renderer_uv.mode = uv_select_mode
            render.tag_redraw_all_views()

    def handle_id_updates(self, active_objects):
        result = False
        t = time.time()
        for id, last_update in self.last_update.items():
            if  0 < last_update and last_update < t:               
                self.last_update[id] = -1

                if self.mesh_data[id].update(active_objects[id], False):
                    self.renderer_view3d.update(self.mesh_data[id])
                    self.renderer_uv.update(self.mesh_data[id])
                    render.tag_redraw_all_views()                  

                result = True

        return result

    def pending_updates(self):
        for update in self.last_update.values():
            if update > 0:
                return True
        return False

    def handle_operators(self, active_objects):
        if len(bpy.context.window_manager.operators) == 0:
            return False

        op = bpy.context.window_manager.operators[-1]
        if op != self.op:
            self.op = op
        else:
            return False

        op_name = op.bl_idname 
        if not op_name.startswith("UV_OT"):
            return False

        if op.bl_idname.startswith("UV_OT_select"):
            for id, mesh_data in self.mesh_data.items():
                if mesh_data.update(active_objects[id], True):
                    self.renderer_view3d.update(mesh_data)
                    self.renderer_uv.update(mesh_data)
                    render.tag_redraw_all_views()

        return True

    def handle_uv_edtitor_visibility_changed(self, active_objects):
        visibility = self.uv_editor_visibility()
        if self.uv_editor_visible == visibility:
            if not self.uv_editor_visible:
                if self.renderer_view3d.enabled:
                    self.renderer_view3d.disable()
                    render.tag_redraw_all_views()
            return False

        self.uv_editor_visible = visibility

        if self.uv_editor_visible:
            for id, obj in active_objects.items():
                mesh_data = self.mesh_data[id]
                if mesh_data.update(obj, False):
                    self.renderer_view3d.update(mesh_data)
                    self.renderer_uv.update(mesh_data)
                    render.tag_redraw_all_views()
        else:
            self.renderer_view3d.disable()
            render.tag_redraw_all_views()

        return True

    def handle_toggle_preselection_state(self):
        state = self.settings.show_preselection
        active_objects = self.get_active_objects()
        for id in active_objects.keys():
            mesh_data = self.mesh_data[id]
            mesh_data.calculate_preselection(state)

    def free(self):
        active_objects = self.get_active_objects()

        obsolete = []
        for id in self.mesh_data.keys():
            if id not in active_objects.keys():
                obsolete.append(id)

        for id in obsolete:
            del self.last_update[id]
            del self.mesh_data[id]

    def uv_editor_visibility(self):
        for area in bpy.context.screen.areas:
            if area.type == "IMAGE_EDITOR" and area.ui_type == "UV":
                return True
        return False

    def can_skip_depsgraph(self, update):

        if not update.id or not update.is_updated_geometry:
            return True

        if not hasattr(update.id, 'type'):
            return True

        if update.id.type != 'MESH':
            return True

        active_objects = self.get_active_objects()
        for name in active_objects.keys():
            if name == update.id.name:
                return False

        return True

    @persistent
    def depsgraph_handler(self, dummy):
        # start modal timer
        if not self.timer_running:
            self.timer_running = True
            bpy.ops.uv.timer()
            return

        # cant do this in _restrictedContext ...
        # so set this up once the callback fires.
        if not self.settings:
            self.settings = bpy.context.scene.uv_highlight
            self.renderer_uv.settings = self.settings
            self.renderer_view3d.settings = self.settings

        depsgraph = bpy.context.evaluated_depsgraph_get()
        for update in depsgraph.updates:
            # print(f"{update.id.name}")
            if self.can_skip_depsgraph(update):
                continue

            if not update.id.name in self.last_update:
                self.last_update[update.id.name] = -1

            # print(update.id.mode)

            if update.id.mode != 'EDIT':
                self.heartbeat()
                return

            # I do not handle depsgraph updates directly, this gets deffered to be handled in a heartbeat update.
            t = time.time()
            last_update = self.last_update[update.id.name]           
            if t < last_update and last_update > 0:
                self.last_update[update.id.name] = t + 0.5
                # print("update")
            else:
                # print("start")
                self.last_update[update.id.name] = t + 0.25


updater = Updater()