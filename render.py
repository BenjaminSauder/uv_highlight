import time

import bpy
import bgl

import gpu
from gpu_extras.batch import batch_for_shader

from mathutils import Matrix

# some code here is from space_view3d_math_vis
def tag_redraw_all_views():
    # print("redraw")
    all_views(lambda region: region.tag_redraw())


def all_views(func):
    context = bpy.context
    # Py cant access notifers
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D' or area.type == 'IMAGE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        func(region)


class RendererView3d():
    def __init__(self):
        self.area_id = 0
        self.View3DEditors = {}
        self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        self.batch = None
        self.enable()

    def enable(self):
        self.enabled = True
        self.handle_view3d = bpy.types.SpaceView3D.draw_handler_add(self.draw_callback, (), 'WINDOW', 'POST_VIEW')

    def disable(self):        
        self.enabled = False

        if self.handle_view3d:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle_view3d, 'WINDOW')
            self.handle_view3d = None

        for area, handle in self.View3DEditors.items():
            bpy.types.SpaceImageEditor.draw_handler_remove(handle, 'WINDOW')
        self.View3DEditors.clear()

    def handle_view3d_editor(self):
        pass

    def clean_handlers(self):
        pass
        
    def draw_callback(self):
        if self.batch:
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
            bgl.glEnable(bgl.GL_DEPTH_TEST)

            self.shader.bind()
            self.shader.uniform_float("color", (1, 0, 0, 0.5))
            self.batch.draw(self.shader)

            bgl.glDisable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)
            bgl.glDisable(bgl.GL_DEPTH_TEST)


    def update(self, data):

        if not self.handle_view3d:            
            self.enable()

        perf_time = time.perf_counter()
        if data.buffer_faces:      
            coords, indices = data.buffer_faces
            self.batch = batch_for_shader(self.shader, 'TRIS', {"pos":coords }, indices=indices)
            tag_redraw_all_views()

            print( "update renderer: %s"  % (time.perf_counter() - perf_time))
      


class RendererUV():
      
    def __init__(self):
        self.area_id = 0
        self.ImageEditors = {}
        self.enabled = True

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

        for area, handle in self.ImageEditors.items():
            bpy.types.SpaceImageEditor.draw_handler_remove(handle, 'WINDOW')
        self.ImageEditors.clear()


    def handle_image_editor(self, area, uv_to_view):
        if not self.enabled:
            return 
        
        if area not in self.ImageEditors.keys():
            self.area_id += 1
            print(f"new draw area - adding handler: {self.area_id}")

            args = (self.draw_callback,
                    (area, uv_to_view, self.area_id), 'WINDOW', 'POST_PIXEL')
            handle = area.spaces[0].draw_handler_add(*args)
           
            self.ImageEditors[area] = handle

    def clean_handlers(self, area):
        if len(area.regions) == 0 or area.type != "IMAGE_EDITOR":
            bpy.types.SpaceImageEditor.draw_handler_remove(self.ImageEditors[area], 'WINDOW')
            self.ImageEditors.pop(area, None)
            # print("removing Image_Editor from drawing: %s" % id)
            return True

        return False

    def draw_callback(self, area, uv_to_view, id):
        if self.clean_handlers(area):
            return

    def update(self, selections):
        pass

