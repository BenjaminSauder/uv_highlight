import bpy
import bgl
import bmesh

import math
import mathutils

from mathutils import Matrix, Vector
from collections import defaultdict
import time

red   = (1.0, 0.0, 0.0)
green = (0.0, 1.0, 0.0)
blue  = (0.0, 0.0, 1.0)
cyan  = (0.0, 1.0, 1.0)

handle_view = None
handle_uv = None

bm_render = None

    
def enable():
    global handle_view, handle_uv   
    if handle_view:
        return

    #handle_pixel = SpaceView3D.draw_handler_add(draw_callback_px, (), 'WINDOW', 'POST_PIXEL')
    handle_view = bpy.types.SpaceView3D.draw_handler_add(draw_callback_view3D, (), 'WINDOW', 'POST_VIEW')
    handle_uv = bpy.types.SpaceImageEditor.draw_handler_add(draw_callback_viewUV, (), 'WINDOW', 'POST_PIXEL')
   
    tag_redraw_all_views()


def disable():
    global handle_view, handle_uv
    if not handle_view:
        return

    #SpaceView3D.draw_handler_remove(handle_pixel, 'WINDOW')
    bpy.types.SpaceView3D.draw_handler_remove(handle_view, 'WINDOW')
    bpy.types.SpaceImageEditor.draw_handler_remove(handle_uv, 'WINDOW')

    handle_view = None
    handle_uv = None

    tag_redraw_all_views()


verts = []
hidden_edges = []
edges = []
faces = []
closestVert = None
closestEdge = None
otherEdge = None
closestFace = None


vert_count = 0
selection_count = 0
kdtree = None
bm = None



def update(mode):
    global bm, hidden_edges

    if not MOUSE_UPDATE:
        bpy.ops.wm.mouse_position('INVOKE_DEFAULT')

    bm = bmesh.from_edit_mesh(bpy.context.active_object.data)  
    uv_layer = bm.loops.layers.uv.verify()    
    bm.faces.layers.tex.verify()

    
    update_preselection(uv_layer)

    #test for uv selection change
    total = 0
    for f in bm.faces:
        if f.select:
            for l in f.loops:
                if l[uv_layer].select:
                    total += l.index
        #mhhh this could be chached.        
        else:
            pass
            #for l in f.loops:
            #    hidden_edges.append(l[uv_layer].uv.copy())  
            #    hidden_edges.append(l.link_loop_next[uv_layer].uv.copy())               


    global selection_count
    if selection_count == total:
        return
    selection_count = total
    

    global verts, edges, faces
    verts = set()
    edges = set()
    hidden_edges = []  
    faces = []  

    #collect selected elements
    for f in bm.faces:

        start = f.loops[0]
        current = None
        face_uvs_selected = True      
        f_verts = []

        while start != current:

            if current == None:
                current = start

            uv = current[uv_layer]
            nextuv = current.link_loop_next[uv_layer]

            if not f.select:
                continue

            if uv.select:
                verts.add(current.vert) 
                f_verts.append(current.vert)
            elif face_uvs_selected:
                face_uvs_selected = False

            if uv.select and nextuv.select:
                island_boundary = current.edge.is_boundary
                selection_boundary = False
                
                for link_face in current.edge.link_faces:                    
                    if link_face == f:
                        continue

                    for linkloop in link_face.loops:
                        linkuv = linkloop[uv_layer] 
                        if not linkuv.select:
                            selection_boundary = True                                                       
                            break

                edges.add((current.edge, selection_boundary, island_boundary ))
                    

            current = current.link_loop_next

        if face_uvs_selected:            
            faces.append(f_verts)
     
    #print("..............")
    #print("edges: ", len(edges))
    #print("edges selection boundary: ", len(list(filter(lambda x: x[1], edges))))
    #print("edges island boundary: ", len(list(filter(lambda x: x[2], edges))))


uv_to_loop = {}
faces_to_uvs = defaultdict(set)
uvs_to_faces = defaultdict(set)

def create_chaches():
    global kdtree, uv_to_loop, vert_count

    if kdtree == None or len(bm.verts) != vert_count:
        vert_count = len(bm.verts)
        uv_to_loop.clear()

        faces_to_uvs.clear()
        uvs_to_faces.clear()

        for f in bm.faces:
            if f.select == False:
                continue
            for l in f.loops:
                uv =l[uv_layer].uv.copy()
                uv.resize_3d()
                uv.freeze()                    
                uv_to_loop[uv] = l

                id = uv.to_tuple(5), l.vert.index
                faces_to_uvs[f.index].add(id)
                uvs_to_faces[id].add(f.index)

        kdtree = mathutils.kdtree.KDTree(len(uv_to_loop))
        i=0
        for k,v in uv_to_loop.items():
            kdtree.insert(k, i)
            i+= 1

        kdtree.balance()

def update_preselection(uv_layer):    
    global  closestVert, closestEdge, otherEdge, closestFace, UV_MOUSE 
    closestVert = None
    closestEdge = None
    closestFace = None

    vertDistance = 1000000    
    edgeDistance = 1000000
    faceDistance = 1000000

    mode = bpy.context.scene.tool_settings.uv_select_mode

    #this gets slow, so I bail out :X
    if not UV_MOUSE or len(bm.verts) > 100000:
        return

    create_chaches()

    #collect closest vert
    closestUV = kdtree.find(UV_MOUSE.resized(3))[0]
    closestUV.freeze()        
    closestVert = (uv_to_loop[closestUV].vert, closestUV)         

    '''
    for f in bm.faces:
        if f.select == False:
            continue

        uvs = []
        for l in f.loops:
            uv = l[uv_layer]
            uvs.append(uv.uv)
            d = uv.uv - mathutils.Vector(UV_MOUSE)
            if d.length < vertDistance:
                vertDistance = d.length
                closestVert = (l.vert, uv.uv)

        if point_in_polygon(UV_MOUSE, uvs):
            closestFace = f
            
    #bmesh is invalid in 2d call...
    v, uv = closestVert
    closestVert = (v, uv.copy())
    '''

    #collect closest edge
    for edge in closestVert[0].link_edges:
        if not edge.select:
            continue

        for l in edge.link_loops:
            uv = l[uv_layer]
            nextuv = l.link_loop_next[uv_layer]
            d = distanceToLine(uv.uv, nextuv.uv, UV_MOUSE)                     
            if d < edgeDistance:
                edgeDistance = d
                closestEdge = (edge, uv.uv, nextuv.uv)
    edge, uv, nextuv = closestEdge
    closestEdge = (edge, uv.copy(), nextuv.copy())    

    #search the other uv edge
    otherEdge = None
    for l in edge.link_loops:
        other_uv = l[uv_layer].uv
        other_nextuv = l.link_loop_next[uv_layer].uv

        if (l.edge.select and other_uv != uv and other_nextuv != nextuv and
            other_uv != nextuv and other_nextuv != uv):
            
            otherEdge = (l.edge, other_uv.copy(), other_nextuv.copy())
            break


    #just assuming that the face in question is somewhere around our closest vert 
    potential_faces = set() 
    collect_faces(potential_faces, closestVert[0].link_faces[0].edges, 0, 3)
            
    for f in potential_faces:                
        face_uvs = []
        for l in f.loops:
            face_uvs.append(l[uv_layer].uv)
        
        if point_in_polygon(UV_MOUSE, face_uvs):
            closestFace = f
            break


    if mode  == "ISLAND" and closestFace:
        island = []
        parse_uv_island(bm, closestFace.index, set(faces_to_uvs.keys()), island)
        print(len(island))


            
    if closestFace != None:
        faceverts = []
        faceuvs = []
        for l in closestFace.loops:
            faceverts.append(l.vert)
            faceuvs.append( l[uv_layer].uv.copy() )
        closestFace = (faceverts, faceuvs)



NORMALOFFSET = 0.0001

def draw_callback_view3D():
    obj = bpy.context.active_object

    if obj == None or obj.mode != "EDIT" or not isEditingUVs():     
        return

    t1 = time.perf_counter()

    mode = bpy.context.scene.tool_settings.uv_select_mode 
    matrix =  obj.matrix_world
          
    update(mode)
        
    t2 = time.perf_counter()   

    bgl.glColor3f(*cyan)  
    #draw selected
    if mode == "VERTEX":
        bgl.glPointSize(6.0)
        bgl.glBegin(bgl.GL_POINTS)
      
        for vert in verts:
                bgl.glVertex3f(*(matrix * (vert.co + vert.normal * NORMALOFFSET)))        
        bgl.glEnd()
        bgl.glPointSize(1.0)
    elif mode == "EDGE":
        bgl.glLineWidth(5.0)
        
        for edge in edges:           
            bgl.glBegin(bgl.GL_LINE_STRIP)
            bgl.glVertex3f(*(matrix * edge[0].verts[0].co))
            bgl.glVertex3f(*(matrix * edge[0].verts[1].co))
            bgl.glEnd()
    else:
        bgl.glEnable(bgl.GL_CULL_FACE)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(3.0)
        bgl.glColor4f(*cyan, 0.4)        
        for f in faces:
            bgl.glBegin(bgl.GL_POLYGON)         
            for v in f:
                bgl.glVertex3f(*(matrix * (v.co + v.normal * NORMALOFFSET)))
            bgl.glEnd()
        
        ''' 
        #draw outline
        bgl.glDisable(bgl.GL_BLEND)
        bgl.glColor4f(*cyan, 1.0)      
        for edge in edges: 
            if edge[1] or edge[2]:          
                bgl.glBegin(bgl.GL_LINE_STRIP)
                bgl.glVertex3f(*(matrix * edge[0].verts[0].co + edge[0].verts[0].normal * 0.005))
                bgl.glVertex3f(*(matrix * edge[0].verts[1].co + edge[0].verts[1].normal * 0.005))
                bgl.glEnd()
        '''
    
    #PRE HIGHLIGHT VERTS
    if UV_MOUSE:
        if mode == 'VERTEX' and closestVert and closestVert[0]:
            #print(UV_MOUSE)
            bgl.glPointSize(6.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor3f(*red)
            bgl.glVertex3f(*(matrix * closestVert[0].co + closestVert[0].normal * NORMALOFFSET))
            bgl.glEnd()
            bgl.glPointSize(1.0)    
        if mode == 'EDGE' and closestEdge and closestEdge[0]:
            bgl.glLineWidth(5.0)
            bgl.glColor3f(*red)
            bgl.glBegin(bgl.GL_LINE_STRIP)      
            bgl.glVertex3f(*(matrix * closestEdge[0].verts[0].co))
            bgl.glVertex3f(*(matrix * closestEdge[0].verts[1].co))
            bgl.glEnd()
        if mode == 'FACE' and closestFace and closestFace[0]:
            bgl.glEnable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glLineWidth(3.0)
            bgl.glColor4f(*red, 0.4)
            bgl.glBegin(bgl.GL_POLYGON)         
            for v in closestFace[0]:
                bgl.glVertex3f(*(matrix * (v.co + v.normal * NORMALOFFSET)))
            bgl.glEnd()

    restore_opengl_defaults()
    
    t3 = time.perf_counter()
    #print( "fps: %.1f total: %.3f - update: %.3f - render: %.3f" % ( 1.0/(t3-t1), t3-t1, t2-t1, t3 - t2 ))


def draw_callback_viewUV():   
    obj = bpy.context.active_object
    if obj == None or obj.mode != "EDIT" or not isEditingUVs():
        return

    mode = bpy.context.scene.tool_settings.uv_select_mode

    bgl.glLineWidth(0.5)       
    bgl.glEnable(bgl.GL_LINE_SMOOTH );
    bgl.glEnable(bgl.GL_BLEND);
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);     
    bgl.glBegin(bgl.GL_LINES) 
    
    for vert in hidden_edges:       
        bgl.glColor3f(0.4,0.4,0.4,)
        bgl.glVertex2i(*(UV_TO_VIEW(*vert, False)))
    bgl.glEnd()

    #PRE HIGHLIGHT VERTS
    if UV_MOUSE and UV_TO_VIEW:
        if mode == 'VERTEX' and closestVert and closestVert[1]:
            bgl.glPointSize(3.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor3f(*red)

            view = UV_TO_VIEW(*closestVert[1])
            bgl.glVertex2i(*view)
            bgl.glPointSize(1.0)   
            bgl.glEnd()

            #print("MOUSE: %s, ClosestVert: %s - %s" % (UV_MOUSE, closestVert[1], view)) 
        elif mode == 'EDGE':
            bgl.glLineWidth(3.5)       
            bgl.glEnable(bgl.GL_LINE_SMOOTH );
            bgl.glEnable(bgl.GL_BLEND);
            bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);     
            bgl.glBegin(bgl.GL_LINES)  
            #edge
            if closestEdge and closestEdge[1] and closestEdge[2]:    
                bgl.glColor3f(0,0,0)
                bgl.glVertex2i(*(UV_TO_VIEW(*closestEdge[1], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*closestEdge[2], False)))
            #matching edge
            if otherEdge and otherEdge[1] and otherEdge[2]:
                bgl.glColor3f(0,0,0)
                bgl.glVertex2i(*(UV_TO_VIEW(*otherEdge[1], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*otherEdge[2], False)))
            bgl.glEnd()

            bgl.glLineWidth(2)
            bgl.glBegin(bgl.GL_LINES)  
            #edge
            if closestEdge and closestEdge[1] and closestEdge[2]:    
                bgl.glColor3f(*red)
                bgl.glVertex2i(*(UV_TO_VIEW(*closestEdge[1], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*closestEdge[2], False)))
            #matching edge
            if otherEdge and otherEdge[1] and otherEdge[2]:
                bgl.glColor3f(0.6, 0, 0)
                bgl.glVertex2i(*(UV_TO_VIEW(*otherEdge[1], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*otherEdge[2], False)))
            bgl.glEnd()
        elif mode == "FACE" and closestFace:
            bgl.glDisable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glLineWidth(1.5)
            bgl.glColor4f(*red, 0.4)
            bgl.glBegin(bgl.GL_POLYGON)         
            for v in closestFace[1]:
                bgl.glVertex2i(*(UV_TO_VIEW(*v, False)))
            bgl.glEnd()

    restore_opengl_defaults()


def restore_opengl_defaults():
    bgl.glPointSize(1)
    bgl.glLineWidth(1)   
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


def isEditingUVs():
    context = bpy.context

    if context.active_object.data.total_vert_sel == 0:
        return False

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                if (area.spaces.active.mode == 'VIEW'
                    and context.scene.tool_settings.use_uv_select_sync == False):                   
                    return True

    return False

#https://github.com/nutti/Magic-UV/blob/develop/uv_magic_uv/muv_packuv_ops.py
def parse_uv_island(bm, face_idx, faces_left, island):
    if face_idx in faces_left:
        faces_left.remove(face_idx)
        island.append({'face': bm.faces[face_idx]})
        for v in faces_to_uvs[face_idx]:
            connected_faces = uvs_to_faces[v]
            if connected_faces:
                for cf in connected_faces:
                    parse_uv_island(bm, cf, faces_left, island)


def collect_faces(faces, bmedges, depth, max_depth):
    for e in bmedges:
        for f in e.link_faces:
            if not f.select:
                continue
            faces.add(f)

            depth += 1  
            if depth <= max_depth:
                collect_faces(faces, f.edges, depth, max_depth)


def distanceToLine(start, end, point):
    line_vec = start - end
    point_vec = start - point
    line_unitvec = line_vec.normalized()
    point_vec_scaled = point_vec * (1.0/line_vec.length)

    t = line_unitvec.dot(point_vec_scaled)    
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    nearest = line_vec * t
    dist = (nearest - point_vec).length
    return dist

def point_in_polygon(p, polygon):
    x, y = p[0], p[1]

    inside = False
    j = len(polygon) - 1

    for i in range(len(polygon)):
        
        xi = polygon[i][0]
        yi = polygon[i][1]
        xj = polygon[j][0]
        yj = polygon[j][1]
        
        intersect = (((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi))        
        if (intersect):
            inside = not inside

        j = i    
    return inside;

#some code here is from space_view3d_math_vis
def tag_redraw_all_views():
    all_views( lambda region: region.tag_redraw() )


def all_views(func):
    context = bpy.context
    # Py cant access notifers
    for window in context.window_manager.windows:
        for area in window.screen.areas:         
            if area.type == 'VIEW_3D' or area.type == 'IMAGE_EDITOR':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        func(region)


UV_MOUSE = None
UV_TO_VIEW = None
MOUSE_UPDATE = False

class SimpleMouseOperator(bpy.types.Operator):
    """ This operator grabs the mouse location
    """
    bl_idname = "wm.mouse_position"
    bl_label = "Mouse location"

    def modal(self, context, event):
        global UV_MOUSE, UV_TO_VIEW

        #UV_MOUSE = None
        #UV_TO_VIEW = None

        if event.type == 'MOUSEMOVE':
            for area in context.screen.areas:
                if area.type == "IMAGE_EDITOR":
                    #area is somehow wrong, as it includes the header
                    for region in area.regions:
                        if region.type == "WINDOW":
                                width = region.width
                                height = region.height
                                region_x = region.x
                                region_y = region.y

                                region_to_view = region.view2d.region_to_view                                
                                UV_TO_VIEW = region.view2d.view_to_region

                    mouse_region_x = event.mouse_x - region_x
                    mouse_region_y = event.mouse_y - region_y

                    self.mousepos = (mouse_region_x, mouse_region_y)
                    #print(self.mousepos)

                    #clamp to area
                    if (mouse_region_x > 0 and mouse_region_y > 0 and
                        mouse_region_x < region_x + width and
                        mouse_region_y < region_y + height):
                            UV_MOUSE = mathutils.Vector(region_to_view(mouse_region_x, mouse_region_y))
                            #print(UV_MOUSE)
                    else:
                        UV_MOUSE = None

                    tag_redraw_all_views()

        return {'PASS_THROUGH'}


    def invoke(self, context, event):
        global MOUSE_UPDATE
        if MOUSE_UPDATE:
            return {"FINISHED"}
        MOUSE_UPDATE = True

        self.mousepos = (0,0)
        print("running")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
