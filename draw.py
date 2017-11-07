import bpy
import bgl
import bmesh

import math
import mathutils

from mathutils import Matrix, Vector
from collections import defaultdict
import time

NORMALOFFSET = 0.0001

COLOR_RED   = (1.0, 0.0, 0.0)
COLOR_GREEN = (0.0, 1.0, 0.0)
COLOR_BLUE  = (0.0, 0.0, 1.0)
COLOR_CYAN  = (0.0, 1.0, 1.0)

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


selected_verts = []
hidden_edges = []
selected_edges = []
selected_faces = []

closest_vert = None
closest_edge = None
other_edge = None
closest_face = None

vert_count = 0
vert_select_count = 0
uv_select_count = 0

bm_instance = None

def update():
    global hidden_edges, vert_count, vert_select_count, uv_select_count, bm_instance

    obj = bpy.context.active_object
    if obj == None or obj.mode != "EDIT" or not isEditingUVs():
        vert_count = 0
        vert_select_count = 0
        uv_select_count = 0
        bm_instance = None
        return False

    if not MOUSE_UPDATE:
        bpy.ops.wm.mouse_position('INVOKE_DEFAULT')

    mesh = bpy.context.active_object.data
    if not bm_instance:
        bm_instance = bmesh.from_edit_mesh(mesh)

    uv_layer = bm_instance.loops.layers.uv.verify()
    bm_instance.faces.layers.tex.verify()

    verts_updated, verts_selection_changed, uv_selection_changed = detect_mesh_changes(bm_instance, uv_layer)
    #print(verts_updated, verts_selection_changed, uv_selection_changed)

    # this gets slow, so I bail out :X
    if len(bm_instance.verts) < 100000:
        if verts_selection_changed or verts_updated:
            #print("UPDATE CACHES!")
            create_chaches(bm_instance, uv_layer)
        if UV_MOUSE:
            update_preselection(bm_instance, uv_layer)

    if uv_selection_changed:
        collect_selected_elements(bm_instance, uv_layer)

    #print("..............")
    #print("edges: ", len(edges))
    #print("edges selection boundary: ", len(list(filter(lambda x: x[1], edges))))
    #print("edges island boundary: ", len(list(filter(lambda x: x[2], edges))))
    return True

#caches
kdtree = None
uv_to_loop = {}
faces_to_uvs = defaultdict(set)
uvs_to_faces = defaultdict(set)

def create_chaches(bm, uv_layer):
    global kdtree, uv_to_loop

    uv_to_loop.clear()
    faces_to_uvs.clear()
    uvs_to_faces.clear()

    for f in bm.faces:
        if not f.select:
            continue
        for l in f.loops:
            uv = l[uv_layer].uv.copy()
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
        i += 1

    kdtree.balance()

def update_preselection(bm, uv_layer):    
    global  closest_vert, closest_edge, other_edge, closest_face, UV_MOUSE

    closest_vert = None
    closest_edge = None
    closest_face = None

    edgeDistance = 1000000

    mode = bpy.context.scene.tool_settings.uv_select_mode

    #collect closest vert
    closestUV = kdtree.find(UV_MOUSE.resized(3))[0]
    if closestUV:
        closestUV.freeze()
        closest_loop = uv_to_loop[closestUV]
        closest_vert = ((closest_loop.vert.co.copy(), closest_loop.vert.normal.copy()), closestUV)
    else:
        #if there is no closest vert, then there are just no elements at all
        return

    #find closet edge
    for edge in closest_loop.vert.link_edges:
        if not edge.select:
            continue

        for l in edge.link_loops:
            uv = l[uv_layer]
            next_uv = l.link_loop_next[uv_layer]
            d = distanceToLine(uv.uv, next_uv.uv, UV_MOUSE)
            if d < edgeDistance:
                edgeDistance = d
                closest_edge = (edge, uv.uv, next_uv.uv)
    edge, uv, next_uv = closest_edge
    edge_coord = ((edge.verts[0].co.copy(), edge.verts[0].normal.copy()), (edge.verts[1].co.copy(), edge.verts[1].normal.copy() ))
    closest_edge = (edge_coord , (uv.copy(), next_uv.copy()))

    #search the other uv edge
    other_edge = None
    for l in edge.link_loops:
        other_uv = l[uv_layer].uv
        other_nextuv = l.link_loop_next[uv_layer].uv

        if (l.edge.select and other_uv != uv and other_nextuv != next_uv and
            other_uv != next_uv and other_nextuv != uv):
            other_edge_coord = ((l.edge.verts[0].co.copy(), l.edge.verts[0].normal.copy()),
                    (l.edge.verts[1].co.copy(), l.edge.verts[1].normal.copy()))
            other_edge = (other_edge_coord, (other_uv.copy(), other_nextuv.copy()))
            break


    #just assuming that the face in question is somewhere around our closest vert 
    potential_faces = set() 
    collect_faces(potential_faces, closest_loop.vert.link_faces[0].edges, 0, 3)
            
    for f in potential_faces:                
        face_uvs = []
        for l in f.loops:
            face_uvs.append(l[uv_layer].uv)
        
        if point_in_polygon(UV_MOUSE, face_uvs):
            closest_face = [f]
            break

    if mode == "ISLAND" and closest_face:
        island = []
        faces_left = set(faces_to_uvs.keys())       
        if len(faces_left) > 0:
            parse_uv_island(bm, closest_face[0].index, faces_left, island)
            closest_face = island
            #print(len(closestFace))

    if closest_face != None and len(closest_face) > 0:
        polys = []
        uvs = []
        for f in closest_face:
            faceverts = []
            faceuvs = []
            for l in f.loops:
                faceverts.append((l.vert.co.copy(), l.vert.normal.copy()))
                faceuvs.append(l[uv_layer].uv.to_tuple(5))
            polys.append(faceverts)
            uvs.append(faceuvs)

        closest_face = (polys, uvs)
        #print(closestFace)


def draw_callback_view3D():

    t1 = time.perf_counter()
    if not update():
        return
    t2 = time.perf_counter()

    obj = bpy.context.active_object
    mode = bpy.context.scene.tool_settings.uv_select_mode
    matrix = obj.matrix_world

    #draw selected
    bgl.glColor3f(*COLOR_CYAN)
    if mode == "VERTEX":
        bgl.glPointSize(6.0)
        bgl.glBegin(bgl.GL_POINTS)
      
        for co, normal in selected_verts:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
        bgl.glEnd()
        bgl.glPointSize(1.0)
    elif mode == "EDGE":
        bgl.glLineWidth(5.0)

        bgl.glBegin(bgl.GL_LINE_STRIP)
        for edge in selected_edges:
            for co, normal in edge[0]:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))

        bgl.glEnd()
    else:
        bgl.glEnable(bgl.GL_CULL_FACE)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(3.0)
        bgl.glColor4f(*COLOR_CYAN, 0.4)
        for f in selected_faces:
            bgl.glBegin(bgl.GL_POLYGON)         
            for co, normal in f:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
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
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

        bgl.glColor4f(*COLOR_RED, 0.45)

        if mode == 'VERTEX' and closest_vert and closest_vert[0]:
            bgl.glPointSize(6.0)
            bgl.glBegin(bgl.GL_POINTS)
            #bgl.glColor3f(*red)
            co, normal = closest_vert[0]
            bgl.glVertex3f(*(matrix * co + normal * NORMALOFFSET))
            bgl.glEnd()

        if mode == 'EDGE' and closest_edge and closest_edge[0]:
            bgl.glLineWidth(5.0)
            bgl.glColor4f(*COLOR_RED, 1.0)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for co, normal in closest_edge[0]:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
            bgl.glEnd()
        #draw FACE and ISLAND
        elif closest_face and closest_face[0]:
            bgl.glEnable(bgl.GL_CULL_FACE)
            #bgl.glEnable(bgl.GL_BLEND)
            #bgl.glLineWidth(3.0)
            #bgl.glColor4f(*red, 0.4)
            
            for p in closest_face[0]:
                bgl.glBegin(bgl.GL_POLYGON)
                for co, normal in p:                     
                    bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
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
    
    for uv in hidden_edges:
        bgl.glColor3f(0.4,0.4,0.4,)
        bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
    bgl.glEnd()

    #PRE HIGHLIGHT VERTS
    if UV_MOUSE and UV_TO_VIEW:
        if mode == 'VERTEX' and closest_vert and closest_vert[1]:
            bgl.glPointSize(3.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor3f(*COLOR_RED)

            view = UV_TO_VIEW(*closest_vert[1])
            bgl.glVertex2i(*view)
            bgl.glPointSize(1.0)   
            bgl.glEnd()

            #print("MOUSE: %s, ClosestVert: %s - %s" % (UV_MOUSE, closestVert[1], view)) 
        elif mode == 'EDGE':
            #draw dark first, then overpaint with brighter colour
            bgl.glLineWidth(3.5)       
            bgl.glEnable(bgl.GL_LINE_SMOOTH);
            bgl.glEnable(bgl.GL_BLEND);
            bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
            bgl.glBegin(bgl.GL_LINES)  
            #edge
            if closest_edge and closest_edge[1][0] and closest_edge[1][1]:
                bgl.glColor3f(0,0,0)
                bgl.glVertex2i(*(UV_TO_VIEW(*closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*closest_edge[1][1], False)))
            #matching edge
            if other_edge and other_edge[1][0] and other_edge[1][1]:
                bgl.glColor3f(0,0,0)
                bgl.glVertex2i(*(UV_TO_VIEW(*other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*other_edge[1][1], False)))
            bgl.glEnd()

            bgl.glLineWidth(2)
            bgl.glBegin(bgl.GL_LINES)  
            #edge
            if closest_edge and closest_edge[1][0] and closest_edge[1][1]:
                bgl.glColor3f(*COLOR_RED)
                bgl.glVertex2i(*(UV_TO_VIEW(*closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*closest_edge[1][1], False)))
            #matching edge
            if other_edge and other_edge[1][0] and other_edge[1][1]:
                bgl.glColor3f(0.6, 0, 0)
                bgl.glVertex2i(*(UV_TO_VIEW(*other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*other_edge[1][1], False)))
            bgl.glEnd()
        elif closest_face and closest_face[1]:
            bgl.glDisable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glLineWidth(1.5)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE);
            scale = 0.25
            if mode == "ISLAND":
                scale = 0.1
            bgl.glColor4f(COLOR_RED[0] * scale, 0, 0, 1.0)
            for p in closest_face[1]:
                bgl.glBegin(bgl.GL_POLYGON)         
                for uv in p:
                    bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
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

def detect_mesh_changes(bm, uv_layer):
    global vert_count, uv_select_count, vert_select_count

    verts_updated = False
    verts_selection_changed = False
    uv_selection_changed = False

    if vert_count != len(bm.verts):
        vert_count = len(bm.verts)
        verts_updated = True


    verts_selected = sum([v.index for v in bm.verts if v.select])
    if verts_selected != vert_select_count:
        vert_select_count = verts_selected
        verts_selection_changed = True


    uv_count = 0
    for f in bm.faces:
        if f.select:
            for l in f.loops:
                if l[uv_layer].select:
                    uv_count += l.index
        # mhhh this could be chached.
        else:
            pass
            # for l in f.loops:
            #    hidden_edges.append(l[uv_layer].uv.copy())
            #    hidden_edges.append(l.link_loop_next[uv_layer].uv.copy())

    if uv_select_count != uv_count:
        uv_select_count = uv_count
        uv_selection_changed = True

    return (verts_updated, verts_selection_changed, uv_selection_changed)

def collect_selected_elements(bm, uv_layer):
    global selected_verts, selected_edges, selected_faces
    selected_verts = set()
    selected_edges = set()
    hidden_edges = []
    selected_faces = []

    # collect selected elements
    for f in bm.faces:

        start = f.loops[0]
        current = None
        face_uvs_selected = True
        f_verts = []

        while start != current:

            if current == None:
                current = start

            uv = current[uv_layer]
            next_uv = current.link_loop_next[uv_layer]

            if not f.select:
                continue

            if uv.select:
                v = (current.vert.co.copy().freeze(), current.vert.normal.copy().freeze())
                selected_verts.add(v)
                f_verts.append(v)
            elif face_uvs_selected:
                face_uvs_selected = False

            if uv.select and next_uv.select:
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

                v1 = (current.edge.verts[0].co.copy().freeze(), current.edge.verts[0].normal.copy().freeze())
                v2 = (current.edge.verts[1].co.copy().freeze(), current.edge.verts[1].normal.copy().freeze())
                selected_edges.add(((v1, v2), selection_boundary, island_boundary))

            current = current.link_loop_next

        if face_uvs_selected:
                selected_faces.append(f_verts)


#https://github.com/nutti/Magic-UV/blob/develop/uv_magic_uv/muv_packuv_ops.py
def parse_uv_island(bm, face_idx, faces_left, island):
    if face_idx in faces_left:
        faces_left.remove(face_idx)
        island.append(bm.faces[face_idx])
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
        print("UV Highlight: running")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}
