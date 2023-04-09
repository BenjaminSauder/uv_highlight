import time
from enum import Enum

import bpy
import bgl

import gpu
from gpu_extras.batch import batch_for_shader

from mathutils import Matrix

from . import shader

FADE = 0.2

class Update(Enum):
    FULL = 1
    SELECTION = 2


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


class RenderableView3d():

    def __init__(self, matrix):
        self.matrix = matrix
        self.batch_vertex = None
        self.batch_edge = None
        self.batch_face = None
        self.batch_uv_seam = None

        self.show_preselection = True
        self.preselection_vertex = None
        self.preselection_edge = None
        self.preselection_face = None

    def can_draw(self):
        return (self.batch_vertex and
                self.batch_edge and
                self.batch_face and 
                self.batch_uv_seam)

    def reset_preselection(self):
        self.preselection_vertex = None
        self.preselection_edge = None


class RenderableViewUV():

    def __init__(self):       
        self.batch_uv_edges = None
        self.batch_uv_verts = None
        self.batch_uv_seam = None

        self.show_preselection = True
        self.preselection_vertex = None
        self.preselection_other_vertices = None
        self.preselection_edge = None
        self.preselection_other_edge = None
        self.preselection_face = None

    def can_draw(self):
        if self.batch_uv_edges or self.batch_uv_verts or self.batch_uv_seam:
            return True

        return False


class Renderer():

    def __init__(self):
        self.targets = {}
        self.mode = "VERTEX"
        self.settings = None
        self.prefs = None
        self.timer = 0

    def load_prefs(self):
        if not self.prefs:
            self.prefs = bpy.context.preferences.addons[__package__].preferences

    def clean_inactive_targets(self):
        active_objects = set()
        for obj in bpy.context.objects_in_mode_unique_data:  # bpy.context.selected_objects:
            if obj.name not in active_objects and obj.mode == 'EDIT':
                active_objects.add(obj.name)

        obsolete = []
        for key in self.targets.keys():
            if key not in active_objects:
                obsolete.append(key)

        for key in obsolete:
            del self.targets[key]

    def focus_preselection(self, active_obj):
        for name, renderable in self.targets.items():
            if name != active_obj:
                renderable.show_preselection = False

        if active_obj in self.targets:
            self.targets[active_obj].show_preselection = True

    def hide_preselection(self):
        for renderable in self.targets.values():
            renderable.show_preselection = False

    def mute_color(self, color):
        return color[0] * 0.5, color[1] * 0.5, color[2] * 0.5, color[3]

    def update_timer(self): 
        delta = 1.0
        if time.time() < self.timer:
            delta = 1.0 - ((self.timer - time.time()) / FADE)
        
        return delta


class RendererView3d(Renderer):
    '''
    This renderer is responsible to draw the selected uv's, uv edges and uv faces in the scene view.
    '''

    def __init__(self):
        super().__init__()
                
        self.shader = shader.uniform_color_offset()
        #self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')
        self.enabled = False


    def enable(self):
        if self.enabled:
            return

        self.enabled = True
        self.visible = True
        self.handle_view3d = bpy.types.SpaceView3D.draw_handler_add(
            self.draw, (), 'WINDOW', 'POST_VIEW')
        # print('added draw view3d')

    def disable(self):
        if not self.enabled:
            return

        self.enabled = False
        self.targets.clear()
        self.visible = False
                    
        bpy.types.SpaceView3D.draw_handler_remove(
            self.handle_view3d, 'WINDOW')
        self.handle_view3d = None
        # print('removed draw view3d')
    
    def draw(self):
        
        if self.settings and not self.settings.show_in_viewport:
            return

        self.load_prefs()

        delta = self.update_timer()

        for renderable in self.targets.values():
            if not renderable.can_draw():
                continue

            with gpu.matrix.push_pop():
                gpu.matrix.load_matrix(renderable.matrix)
                with gpu.matrix.push_pop_projection():
                    # maybe do a correct z depth offset one day..
                    # view_distance = bpy.context.region_data.view_distance
                    viewProjectionMatrix = bpy.context.region_data.perspective_matrix
                    gpu.matrix.load_projection_matrix(viewProjectionMatrix)

                    bgl.glEnable(bgl.GL_DEPTH_TEST)
                    self.shader.bind()

                    if self.visible:
                        
                        if self.settings.show_uv_seams:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)
                         
                            bgl.glLineWidth(2.0)

                            c = self.prefs.uv_seams
                            self.shader.uniform_float("color", (c[0], c[1], c[2], c[3]  * delta))
                            renderable.batch_uv_seam.draw(self.shader)
                            
                            bgl.glLineWidth(1.0)
                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                        if self.mode == "VERTEX":
                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_selection_verts_edges))
                            renderable.batch_vertex.draw(self.shader)

                        elif self.mode == "EDGE":
                            bgl.glLineWidth(2.0)
                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_selection_verts_edges))
                            renderable.batch_edge.draw(self.shader)
                            bgl.glLineWidth(1.0)
                        else:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)

                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_selection_faces))
                            renderable.batch_face.draw(self.shader)

                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                    # preselection
                    if self.settings.show_preselection and renderable.show_preselection:
                        if self.mode == "VERTEX" and renderable.preselection_vertex:
                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_preselection_verts_edges))
                            renderable.preselection_vertex.draw(self.shader)
                        elif self.mode == "EDGE" and renderable.preselection_edge:
                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_preselection_verts_edges))
                            bgl.glLineWidth(2.0)
                            renderable.preselection_edge.draw(self.shader)
                            bgl.glLineWidth(1.0)
                        elif (self.mode == 'FACE' or self.mode == 'ISLAND') and renderable.preselection_face:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)

                            self.shader.uniform_float(
                                "color", (self.prefs.view3d_preselection_faces))
                            renderable.preselection_face.draw(self.shader)

                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                    bgl.glDisable(bgl.GL_DEPTH_TEST)

            # gpu.matrix.reset()

    def update(self, data,  update):
            
        if not self.enabled:
            self.enable()
        # else:
        #     self.disable()
        #     return

        self.settings = bpy.context.scene.uv_highlight

        # if not self.handle_view3d:
        #   self.enable()
        self.clean_inactive_targets()

        if not data.target:
            return

        renderable = RenderableView3d(data.matrix)

        renderable.batch_vertex = batch_for_shader(
            self.shader, 'POINTS', {"pos": data.vert_buffer})

        coords, indices = data.edge_buffer
        renderable.batch_edge = batch_for_shader(
            self.shader, 'LINES', {"pos": coords}, indices=indices)

        coords, indices = data.face_buffer
        renderable.batch_face = batch_for_shader(
            self.shader, 'TRIS', {"pos": coords}, indices=indices)

        if update == Update.FULL:
            coords, indices = data.uv_seam_buffer[0]

            h_current = hash(str(coords))
            # print(h_current)
            h_last = None
            if data.target in self.targets and  hasattr( self.targets[data.target], 'batch_uv_seam_hash'):
                h_last = self.targets[data.target].batch_uv_seam_hash

            if h_current != h_last:
                renderable.batch_uv_seam_hash = h_current
                renderable.batch_uv_seam = batch_for_shader(
                    self.shader, 'LINES', {"pos": coords}, indices=indices)
                self.timer = time.time() + FADE
            else:
                renderable.batch_uv_seam = self.targets[data.target].batch_uv_seam
                renderable.batch_uv_seam_hash = self.targets[data.target].batch_uv_seam_hash
        else:
            renderable.batch_uv_seam = self.targets[data.target].batch_uv_seam
            renderable.batch_uv_seam_hash = self.targets[data.target].batch_uv_seam_hash

        self.targets[data.target] = renderable

    def preselection(self, data):

        self.focus_preselection(data.target)

        if data.target not in self.targets:
            return

        renderable = self.targets[data.target]

        if self.mode == 'VERTEX':
            coords = data.preselection_verts[0]
            if len(coords) > 0:
                coords = [coords]

            renderable.preselection_vertex = batch_for_shader(
                self.shader, 'POINTS', {"pos": coords})

        elif self.mode == 'EDGE':
            coords = data.preselection_edges[0]

            renderable.preselection_edge = batch_for_shader(
                self.shader, 'LINES', {"pos": coords})

        elif self.mode == 'FACE' or self.mode == 'ISLAND':
            coords, indices = data.preselection_faces[0]
            renderable.preselection_face = batch_for_shader(
                self.shader, 'TRIS', {"pos": coords}, indices=indices)


class RendererUV(Renderer):
    '''
    This renderer is responsible to draw preselection of uv's, uv edges, uv faces and islands etc. in the uv editor.
    '''

    def __init__(self):
        super().__init__()
              
        self.enabled = False
        self.shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')
        self.handle_view2d = None
        # self.enable()
        self.visible = False

    def enable(self):
        if self.enabled:
            return

        self.enabled = True
        self.visible = True
        self.handle_view2d = bpy.types.SpaceImageEditor.draw_handler_add(self.draw, (), 'WINDOW', 'POST_VIEW')

    def disable(self):
        if not self.enabled:
            return

        self.enabled = False
        self.targets.clear()
        self.visible = False
        if self.handle_view2d:
            bpy.types.SpaceImageEditor.draw_handler_remove(
                self.handle_view2d, 'WINDOW')
            self.handle_view2d = None

    #not the nicest solution, but I guess its okay for now.
    #I dont expect users to have tons of uv editors open at the same time anyways..
    def find_region(self, width, height):
        context = bpy.context
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'IMAGE_EDITOR' and area.ui_type == "UV":
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            if (width == region.width and
                                    height == region.height):
                                return region, area
        return None, None

    def draw(self):
        self.load_prefs()

        viewport_info = bgl.Buffer(bgl.GL_INT, 4)
        bgl.glGetIntegerv(bgl.GL_VIEWPORT, viewport_info)

        width = viewport_info[2]
        height = viewport_info[3]
        region, area = self.find_region(width, height)
        if not region:
            return

        show_modified_edges = area.spaces.active.uv_editor.show_modified_edges

        uv_to_view = region.view2d.view_to_region
        
        origin_x, origin_y = uv_to_view(0, 0, clip=False)
        top_x, top_y = uv_to_view(1.0, 1.0, clip=False)
        axis_x = top_x - origin_x
        axis_y = top_y - origin_y

        matrix = Matrix((
            [axis_x / width * 2, 0, 0,  2.0 * -
                ((width - origin_x - 0.5 * width)) / width],
            [0, axis_y / height * 2, 0, 2.0 * -
                ((height - origin_y - 0.5 * height)) / height],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1.0]))

        identiy = Matrix.Identity(4)
        
        delta = self.update_timer()

        with gpu.matrix.push_pop():
            gpu.matrix.load_matrix(matrix)
            
            with gpu.matrix.push_pop_projection():
                gpu.matrix.load_projection_matrix(identiy)

                for renderable in self.targets.values():
                    if not renderable.can_draw():
                        continue

                    self.shader.bind()
                                   
                    # draw mesh-connected uv edges
                    if self.visible:
                        if self.settings.show_uv_seams:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)
                            bgl.glLineWidth(1.5)
                            
                            c = self.prefs.uv_seams
                            self.shader.uniform_float("color", (c[0], c[1], c[2], c[3]  * delta))

                            if show_modified_edges:
                                if renderable.batch_uv_seam[0]:
                                    renderable.batch_uv_seam[0].draw(self.shader)
                            else:
                                if renderable.batch_uv_seam[1]:
                                    renderable.batch_uv_seam[1].draw(self.shader)

                            bgl.glLineWidth(1.0)
                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                        if self.mode == "VERTEX" and renderable.batch_uv_verts:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)
                            bgl.glPointSize(5.0)
                            
                            self.shader.uniform_float(
                                "color", self.prefs.uv_matching_edges)
                            renderable.batch_uv_verts.draw(self.shader)

                            bgl.glPointSize(1.0)
                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                        if self.mode == "EDGE" and renderable.batch_uv_edges:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)

                            if self.settings.show_uv_seams: 
                                bgl.glLineWidth(4.0)
                            else:
                                bgl.glLineWidth(2.0)

                            self.shader.uniform_float(
                                "color", self.prefs.uv_matching_edges)
                            renderable.batch_uv_edges.draw(self.shader)

                            bgl.glLineWidth(1.0)
                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

                    # preselection
                    if self.settings.show_preselection and renderable.show_preselection:
                        if self.mode == "VERTEX" and renderable.preselection_vertex:
                            bgl.glPointSize(4.0)
                            color = self.prefs.uv_preselection_verts_edges

                            self.shader.uniform_float(
                                "color", self.mute_color(color))
                            renderable.preselection_other_vertices.draw(
                                self.shader)

                            self.shader.uniform_float("color", color)
                            renderable.preselection_vertex.draw(self.shader)

                            bgl.glPointSize(1.0)

                        elif self.mode == "EDGE" and renderable.preselection_edge:
                            color = self.prefs.uv_preselection_verts_edges
                            bgl.glLineWidth(2.0)
                            self.shader.uniform_float("color", color)
                            renderable.preselection_edge.draw(self.shader)
                            self.shader.uniform_float(
                                "color", self.mute_color(color))
                            renderable.preselection_other_edge.draw(self.shader)
                            bgl.glLineWidth(1.0)
                        elif (self.mode == 'FACE' or self.mode == 'ISLAND') and renderable.preselection_face:
                            bgl.glEnable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_SRC_ALPHA,
                                            bgl.GL_ONE_MINUS_SRC_ALPHA)

                            self.shader.uniform_float(
                                "color", (self.prefs.uv_preselection_faces))
                            renderable.preselection_face.draw(self.shader)

                            bgl.glDisable(bgl.GL_BLEND)
                            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)

        bgl.glViewport(*tuple(viewport_info))




    def update(self, data, update):

        if not self.enabled:
            self.enable()

        self.settings = bpy.context.scene.uv_highlight
        self.clean_inactive_targets()

        if not data.target:
            return

        renderable = RenderableViewUV()

        coords, indices = data.uv_edge_buffer
        renderable.batch_uv_edges = batch_for_shader(
            self.shader, 'LINES', {"pos": coords}, indices=indices)

        coords = data.uv_vert_buffer
        renderable.batch_uv_verts = batch_for_shader(
            self.shader, 'POINTS', {"pos": coords})

        if update == Update.FULL:
            coords, indices = data.uv_seam_buffer[1][0]
            batch_uv_seam_all = batch_for_shader(
                self.shader, 'LINES', {"pos": coords}, indices=indices)

            coords, indices = data.uv_seam_buffer[1][1]
            batch_uv_seam_selected = batch_for_shader(
                self.shader, 'LINES', {"pos": coords}, indices=indices)

            renderable.batch_uv_seam = batch_uv_seam_all, batch_uv_seam_selected
            self.timer = time.time() + FADE
        else:
            # if data.target in self.targets:
            renderable.batch_uv_seam = self.targets[data.target].batch_uv_seam

        self.targets[data.target] = renderable
       


    def preselection(self, data):

        self.focus_preselection(data.target)

        if data == None:
            return

        renderable = self.targets[data.target]

        if self.mode == 'VERTEX':
            coords = data.preselection_verts[1]
            closest = coords[0:1]
            matching = coords[1:]

            renderable.preselection_vertex = batch_for_shader(
                self.shader, 'POINTS', {"pos": closest})

            renderable.preselection_other_vertices = batch_for_shader(
                self.shader, 'POINTS', {"pos": matching})

        elif self.mode == 'EDGE':
            coord_edge, coord_other_edge = data.preselection_edges[1]

            renderable.preselection_edge = batch_for_shader(
                self.shader, 'LINES', {"pos": coord_edge})
            renderable.preselection_other_edge = batch_for_shader(
                self.shader, 'LINES', {"pos": coord_other_edge})

        elif self.mode == 'FACE' or self.mode == 'ISLAND':
            coords, indices = data.preselection_faces[1]
            renderable.preselection_face = batch_for_shader(
                self.shader, 'TRIS', {"pos": coords}, indices=indices)
