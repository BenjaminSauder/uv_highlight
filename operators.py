import bpy
import mathutils

from . import main
from . import render
from .prefs import debug


class UV_OT_Timer(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = "uv.timer"
    bl_label = "UV Timer"

    _timer = None

    def modal(self, context, event):
        if event.type == 'TIMER':
            main.updater.heartbeat()

        if not main.updater.timer_running:
            self.cancel(context)

        return {'PASS_THROUGH'}

    def execute(self, context):
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


class UV_OT_mouseposition(bpy.types.Operator):
    """ This operator grabs the mouse location """
    bl_idname = "uv.mouseposition"
    bl_label = "UV Mouse location"
    # bl_options = {"REGISTER"}#, "INTERNAL"}

    def invoke(self, context, event):
        #print( event.type )
        if event.type == 'MOUSEMOVE':
            main.UV_MOUSE = None

        # print(event.type, time.time())
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR" and area.ui_type == "UV":
                for region in area.regions:
                    if region.type == "WINDOW":
                        width = region.width
                        height = region.height
                        region_x = region.x
                        region_y = region.y

                        region_to_view = region.view2d.region_to_view
                        uv_to_view_func = region.view2d.view_to_region

                mouse_region_x = event.mouse_x - region_x
                mouse_region_y = event.mouse_y - region_y

                self.mousepos = (mouse_region_x, mouse_region_y)

                # clamp to area
                if (mouse_region_x > 0 and mouse_region_y > 0 and
                    mouse_region_x < region_x + width and
                        mouse_region_y < region_y + height):
                    p = mathutils.Vector(region_to_view(
                        mouse_region_x, mouse_region_y))
                    main.updater.mouse_position = p

                    # print(p)

                # register draw handler
                main.updater.renderer_uv.handle_image_editor(
                    area, uv_to_view_func)

        return {'FINISHED'}

    # def invoke(self, context, event):
    #     self.mousepos = (0, 0)
    #     context.window_manager.modal_handler_add(self)
    #     return {'RUNNING_MODAL'}
