import time

import bpy
import bgl

import gpu
from gpu_extras.batch import batch_for_shader

from mathutils import Matrix

from . import shader

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
        self.preselection_vertex = None

    def can_draw(self): 
        return (self.batch_vertex and self.batch_edge and self.batch_face)
    
class RenderableViewUV():

    def __init__(self):
        self.batch_hidden_edges = None
        self.preselection_vertex = None

    def can_draw(self): 
        if self.batch_hidden_edges:
            return True
        
        return False

class Renderer():

    def __init__(self):
        self.targets = {}
        self.mode = "VERTEX"
    
    def clean_inactive_targets(self):
        active_objects = set()
        for obj in bpy.context.objects_in_mode_unique_data: # bpy.context.selected_objects:
            if obj.name not in active_objects and obj.mode == 'EDIT':
                active_objects.add(obj.name)

        obsolete = []
        for key in self.targets.keys():
            if key not in active_objects:
                obsolete.append(key)
        
        for key in obsolete:
            del self.targets[key]



class RendererView3d(Renderer):
    '''
    This renderer is responsible to draw the selected uv's, uv edges and uv faces in the scene view.
    '''
    def __init__(self):
        super().__init__()
        self.area_id = 0
        self.View3DEditors = {}
        self.shader = shader.uniform_color_offset()
        #self.shader = gpu.shader.from_builtin('3D_UNIFORM_COLOR')    
        self.enable()
        
    def enable(self):
        self.enabled = True
        self.handle_view3d = bpy.types.SpaceView3D.draw_handler_add(self.draw, (), 'WINDOW', 'POST_VIEW')
        
    def disable(self):        
        self.enabled = False     
        self.targets.clear()

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
        
    def draw(self):
        for renderable in self.targets.values():
            if not renderable.can_draw():
                continue

            with gpu.matrix.push_pop(): 
                #view_distance = bpy.context.region_data.view_distance
            
                viewProjectionMatrix = bpy.context.region_data.perspective_matrix           
                
                #TODO offset to avoid z-fighting 
                
                gpu.matrix.load_matrix(renderable.matrix)
                gpu.matrix.load_projection_matrix(viewProjectionMatrix)

                bgl.glEnable(bgl.GL_DEPTH_TEST)
                self.shader.bind()
                
                if self.mode == "VERTEX":            
                    self.shader.uniform_float("color", (1, 0, 0, 1.0))
                    renderable.batch_vertex.draw(self.shader)

                elif self.mode == "EDGE":
                    bgl.glLineWidth(2.0)
                    self.shader.uniform_float("color", (1, 0, 0, 1.0))
                    renderable.batch_edge.draw(self.shader)
                    bgl.glLineWidth(1.0)
                else:          
                    bgl.glEnable(bgl.GL_BLEND)
                    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
                    
                    self.shader.uniform_float("color", (1, 0, 0, 0.1))
                    renderable.batch_face.draw(self.shader)

                    bgl.glDisable(bgl.GL_BLEND)
                    bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)
                
                #preselection
                if self.mode == "VERTEX" and renderable.preselection_vertex:       

                    self.shader.uniform_float("color", (1, 1, 0, 1.0))
                    renderable.preselection_vertex.draw(self.shader)

                bgl.glDisable(bgl.GL_DEPTH_TEST)


    
            
    def update(self, data):
        #return
       
        if not self.enabled:
            self.enable()
        # else:
        #     self.disable()            
        #     return

        #if not self.handle_view3d:            
        #   self.enable()    
        self.clean_inactive_targets()

        if not data.target:
            return
      
        renderable = RenderableView3d(data.matrix)
       
        renderable.batch_vertex = batch_for_shader(self.shader, 'POINTS', {"pos":data.vert_buffer })
       
        coords, indices = data.edge_buffer
        renderable.batch_edge = batch_for_shader(self.shader, 'LINES', {"pos":coords }, indices=indices)
                  
        coords, indices = data.face_buffer            
        renderable.batch_face = batch_for_shader(self.shader, 'TRIS', {"pos":coords }, indices=indices)

        self.targets[data.target] = renderable

    def preselection(self, data):
        
        if self.mode == 'VERTEX':
            coords = [(data.preselection_verts[0])]
            if len(coords) > 0:
                self.targets[data.target].preselection_vertex = batch_for_shader(self.shader, 'POINTS', {"pos":coords})



class RendererUV(Renderer):
    '''
    This renderer is responsible to draw the hidden edges, preselection of uv's, uv edges, uv faces and islands etc. in the uv editor.
    '''
    def __init__(self):
        super().__init__()
        self.area_id = 0
        self.editors = {}
        self.enabled = True
        self.shader = gpu.shader.from_builtin('2D_UNIFORM_COLOR')        


    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False     
        self.targets.clear()

        for area, handle in self.editors.items():
            bpy.types.SpaceImageEditor.draw_handler_remove(handle, 'WINDOW')
        self.editors.clear()


    def handle_editor(self, area):
        if not self.enabled:
            return 
        
        if area not in self.editors.keys():
            self.area_id += 1
            print(f"new draw area - adding handler: {self.area_id}")

            args = (self.draw,
                    (area, self.area_id),
                    'WINDOW', 'POST_VIEW')
            handle = area.spaces[0].draw_handler_add(*args)
           
            self.editors[area] = handle

    def area_valid(self, area):
        if len(area.regions) == 0 or area.type != "IMAGE_EDITOR":
            bpy.types.SpaceImageEditor.draw_handler_remove(self.editors[area], 'WINDOW')
            self.editors.pop(area, None)
            # print("removing Image_Editor from drawing: %s" % id)
            return False

        return True

    def get_line_width(self, width, height, axis_x, axis_y):
        ratio_x = width / axis_x
        ratio_y = height / axis_y
        ratio = min(ratio_x, ratio_y)

        line_width = 1.0
        if ratio < 0.35:
            line_width = 3.0
        elif ratio < 1.0:
            line_width = 2.0
        elif ratio > 2.0:
            line_width = 1.0
        elif ratio > 8.0:
            line_width = 0.5

        return line_width

    def draw(self, area, id):
        if not self.area_valid(area):
            return

        for region in area.regions:
            if region.type == "WINDOW":
                width = region.width
                height = region.height
                region_x = region.x
                region_y = region.y

                uv_to_view = region.view2d.view_to_region
                break
        
        bgl.glEnable(bgl.GL_DEPTH_TEST)
        viewport_info = bgl.Buffer(bgl.GL_INT, 4)
        bgl.glGetIntegerv(bgl.GL_VIEWPORT, viewport_info)
        bgl.glViewport(region_x, region_y, width, height)
               
        origin_x, origin_y = uv_to_view(0, 0, clip=False)
        top_x, top_y = uv_to_view(1.0, 1.0, clip=False) 
        axis_x = top_x - origin_x
        axis_y = top_y - origin_y
   
        matrix = Matrix((
            [axis_x / width * 2, 0, 0,  2.0 * -((width - origin_x  - 0.5 * width)  + region_x) / width],
            [0, axis_y / height * 2, 0, 2.0 * -((height - origin_y - 0.5 * height) + region_y) / height],
            [0, 0, 1.0, 0],
            [0, 0, 0, 1.0]))

        identiy = Matrix.Identity(4)

        line_width = self.get_line_width(width, height, axis_x, axis_y)

        with gpu.matrix.push_pop():               
            gpu.matrix.load_matrix(matrix)
            gpu.matrix.load_projection_matrix(identiy)

            for renderable in self.targets.values():
                if not renderable.can_draw():
                    continue                    

                self.shader.bind()

                #draw hidden edges         
                bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)
                bgl.glLineWidth(line_width)
                self.shader.uniform_float("color", (0.5, 0.5, 0.5, 1.0))
                renderable.batch_hidden_edges.draw(self.shader)
                bgl.glLineWidth(1.0)

                #preselection
                if self.mode == "VERTEX" and renderable.preselection_vertex:
                    self.shader.uniform_float("color", (1, 1, 0, 1.0))
                    renderable.preselection_vertex.draw(self.shader)

        bgl.glViewport(*tuple(viewport_info))
        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)
        bgl.glDisable(bgl.GL_DEPTH_TEST)

    def update(self, data):
        #return

        if not self.enabled:
            self.enable()

        self.clean_inactive_targets()   
    
        if not data.target:
            return

        renderable = RenderableViewUV()

        coords, indices = data.hidden_edge_buffer
        renderable.batch_hidden_edges = batch_for_shader(self.shader, 'LINES', {"pos":coords }, indices=indices)

        self.targets[data.target] = renderable

    def preselection(self, data):
        
        if self.mode == 'VERTEX':
            coords = [(data.preselection_verts[1])]
            if len(coords) > 0:
                self.targets[data.target].preselection_vertex = batch_for_shader(self.shader, 'POINTS', {"pos":coords})