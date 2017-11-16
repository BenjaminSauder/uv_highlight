import bpy
import bmesh

import math
import mathutils

from mathutils import Matrix, Vector
from collections import defaultdict
import time

from .render import create_vao

UV_MOUSE = None

last_update = 0
updating = False


def handle_scene_update(context):
    global updating, last_update

    # avoid recursive calls
    if updating:
        return

    # cap the update rate
    if time.perf_counter() - last_update < 1.0 / 30.0:
        return

    try:
        edit_obj = bpy.context.edit_object
        if edit_obj is not None and edit_obj.is_updated_data is True:
            updating = True
            update()
            last_update = time.perf_counter()
            updating = False
    except AttributeError as e:
        pass


selected_verts = []
hidden_edges = []
selected_edges = []
selected_faces = []

closest_vert = None
other_vert = None
closest_edge = None
other_edge = None
closest_face = None

vert_count = 0
vert_select_count = 0
uv_select_count = 0

bm_instance = None


def reset():
    global hidden_edges, vert_count, vert_select_count, uv_select_count, bm_instance, hidden_edges
    vert_count = 0
    vert_select_count = 0
    uv_select_count = 0
    bm_instance = None
    selected_verts.clear()
    selected_faces.clear()
    selected_edges.clear()
    hidden_edges.clear()


def update(do_update_preselection=False):
    t1 = time.perf_counter()
    global hidden_edges, vert_count, vert_select_count, uv_select_count, bm_instance, hidden_edges

    # print("update")

    if not isEditingUVs():
        reset()
        return False

    settings = bpy.context.scene.uv_highlight
    prefs = bpy.context.user_preferences.addons[__package__].preferences

    from . import operators
    if not operators.MOUSE_UPDATE:
        # pass
        bpy.ops.wm.uv_mouse_position('INVOKE_DEFAULT')

    mesh = bpy.context.active_object.data
    force_cache_rebuild = False
    if not bm_instance or not bm_instance.is_valid:
        force_cache_rebuild = True
        bm_instance = bmesh.from_edit_mesh(mesh)

    # this gets slow, so I bail out :X
    if len(bm_instance.verts) > prefs.max_verts:
        return

    uv_layer = bm_instance.loops.layers.uv.verify()
    bm_instance.faces.layers.tex.verify()

    verts_updated, verts_selection_changed, uv_selection_changed = detect_mesh_changes(bm_instance, uv_layer)
    # print(verts_updated, verts_selection_changed, uv_selection_changed)

    if force_cache_rebuild or verts_selection_changed or not do_update_preselection:
        # print("--uv highlight rebuild cache--")
        create_chaches(bm_instance, uv_layer)

        tag_redraw_all_views()

    if UV_MOUSE and settings.show_preselection:
        try:
            update_preselection(bm_instance, uv_layer)
        except ReferenceError as e:
            print("--uv highlight rebuild cache--")
            bm_instance = None
            update()

    t_uv_selection_changed_start = time.perf_counter()
    if uv_selection_changed:
        collect_selected_elements(bm_instance, uv_layer)

    t_uv_selection_changed_end = time.perf_counter()

    # print("..............")
    # print("edges: ", len(edges))
    # print("edges selection boundary: ", len(list(filter(lambda x: x[1], edges))))
    # print("edges island boundary: ", len(list(filter(lambda x: x[2], edges))))

    t2 = time.perf_counter()
    # print("update cost: %.3f - selection change: %.3f" % (
    # t2 - t1, t_uv_selection_changed_end - t_uv_selection_changed_start))

    return True


# caches
kdtree = None
uv_to_loop = {}
faces_to_uvs = defaultdict(set)
uvs_to_faces = defaultdict(set)


def create_chaches(bm, uv_layer):
    global kdtree, uv_to_loop, hidden_edges

    hidden_edges.clear()
    uv_to_loop.clear()
    faces_to_uvs.clear()
    uvs_to_faces.clear()

    for f in bm.faces:
        if not f.select:
            for edge in f.edges:
                for el in edge.link_loops:
                    uv = el[uv_layer].uv.copy().freeze()
                    nextuv = el.link_loop_next[uv_layer].uv.copy().freeze()

                    hidden_edges.append(uv.x)
                    hidden_edges.append(uv.y)

                    hidden_edges.append(nextuv.x)
                    hidden_edges.append(nextuv.y)

        else:
            for l in f.loops:
                uv = l[uv_layer].uv.copy()
                uv.resize_3d()
                uv.freeze()
                uv_to_loop[uv] = l

                id = uv.to_tuple(8), l.vert.index
                faces_to_uvs[f.index].add(id)
                uvs_to_faces[id].add(f.index)

    kdtree = mathutils.kdtree.KDTree(len(uv_to_loop))
    i = 0
    for k, v in uv_to_loop.items():
        kdtree.insert(k, i)
        i += 1

    kdtree.balance()

    create_vao("hidden_edges", hidden_edges)


def update_preselection(bm, uv_layer):
    global closest_vert, other_vert, closest_edge, other_edge, closest_face, UV_MOUSE

    closest_vert = None
    other_vert = None
    closest_edge = None
    closest_face = None

    edgeDistance = 1000000

    mode = bpy.context.scene.tool_settings.uv_select_mode

    # collect closest vert
    closestUV = kdtree.find(UV_MOUSE.resized(3))[0]
    if closestUV:
        closestUV.freeze()
        closest_loop = uv_to_loop[closestUV]
        closest_vert = (closest_loop.vert.co.copy(), closest_loop.vert.normal.copy()), closestUV

        for l in closest_loop.vert.link_loops:
            if l == closest_loop:
                continue

            uv = l[uv_layer]
            if uv.uv != closest_loop[uv_layer].uv:
                other_vert = uv.uv.copy().freeze()
    else:
        # if there is no closest vert, then there are just no elements at all
        create_vao("closest_faces", [])
        create_vao("closest_face_uvs", [])
        return

    # find closet edge
    for edge in closest_loop.vert.link_edges:
        if not edge.select:
            continue

        for l in edge.link_loops:
            uv = l[uv_layer]
            next_uv = l.link_loop_next[uv_layer]
            d = distanceToLine(uv.uv, next_uv.uv, UV_MOUSE)
            if d < edgeDistance:
                edgeDistance = d
                closest_edge = edge, uv.uv, next_uv.uv

    if closest_edge:
        edge, uv, next_uv = closest_edge
        edge_coord = (
            (edge.verts[0].co.copy(), edge.verts[0].normal.copy()),
            (edge.verts[1].co.copy(), edge.verts[1].normal.copy()))
        closest_edge = (edge_coord, (uv.copy(), next_uv.copy()))

        # search the other uv edge
        other_edge = None
        for l in edge.link_loops:
            other_uv = l[uv_layer].uv
            other_nextuv = l.link_loop_next[uv_layer].uv

            if (l.edge.select and other_uv != uv and other_nextuv != next_uv):  # and
                # other_uv != next_uv and other_nextuv != uv):
                other_edge_coord = ((l.edge.verts[0].co.copy(), l.edge.verts[0].normal.copy()),
                                    (l.edge.verts[1].co.copy(), l.edge.verts[1].normal.copy()))
                other_edge = (other_edge_coord, (other_uv.copy(), other_nextuv.copy()))
                break

    for f in closest_loop.vert.link_faces:  # potential_faces:
        if not f.select:
            continue

        face_uvs = []
        for l in f.loops:
            face_uvs.append(l[uv_layer].uv)

        if point_in_polygon(UV_MOUSE, face_uvs):
            closest_face = [f]
            break

    if mode == "ISLAND" and closest_face:

        faces_left = set(faces_to_uvs.keys())
        if len(faces_left) > 0:
            closest_face = parse_uv_island(bm, closest_face[0].index)
            # print(len(closestFace))

    if closest_face != None and len(closest_face) > 0:
        faces = []
        for f in closest_face:
            faces.append(f.index)

        verts, uvs = get_triangulated_faces(bm, faces, collect_uvs=True)
        create_vao("closest_faces", verts)
        create_vao("closest_face_uvs", uvs)


def isEditingUVs():
    context = bpy.context
    obj = context.active_object

    if obj == None or obj.mode != "EDIT":
        return False

    '''
    # if context.active_object.data.total_vert_sel == 0:
    #    return False
    
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'IMAGE_EDITOR':
                if (area.spaces.active.mode == 'VIEW'
                    and context.scene.tool_settings.use_uv_select_sync == False):
                    return True
    '''

    #if not context.scene.tool_settings.use_uv_select_sync:
    #    return True

    return True


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

    if uv_select_count != uv_count:
        uv_select_count = uv_count
        uv_selection_changed = True

    return (verts_updated, verts_selection_changed, uv_selection_changed)


def collect_selected_elements(bm, uv_layer):
    # global selected_verts, selected_edges  # , selected_faces
    selected_verts = []
    selected_edges = []
    selected_faces = set()

    # collect selected elements
    for f in bm.faces:

        if not f.select:
            continue

        start = f.loops[0]
        current = None
        face_uvs_selected = True
        f_verts = []

        while start != current:

            if current == None:
                current = start

            uv = current[uv_layer]
            next_uv = current.link_loop_next[uv_layer]

            if uv.select:
                v = (current.vert.co.copy().freeze(), current.vert.normal.copy().freeze())
                # selected_verts.add(v)
                selected_verts.append(current.vert.co.x)
                selected_verts.append(current.vert.co.y)
                selected_verts.append(current.vert.co.z)

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

                # v1 = (current.edge.verts[0].co.copy().freeze(), current.edge.verts[0].normal.copy().freeze())
                # v2 = (current.edge.verts[1].co.copy().freeze(), current.edge.verts[1].normal.copy().freeze())
                # selected_edges.add(((v1, v2), selection_boundary, island_boundary))

                selected_edges.append(current.edge.verts[0].co.x)
                selected_edges.append(current.edge.verts[0].co.y)
                selected_edges.append(current.edge.verts[0].co.z)
                selected_edges.append(current.edge.verts[1].co.x)
                selected_edges.append(current.edge.verts[1].co.y)
                selected_edges.append(current.edge.verts[1].co.z)

            current = current.link_loop_next

        if face_uvs_selected and f.select:
            selected_faces.add(f.index)

    create_vao("selected_verts", selected_verts)
    create_vao("selected_edges", selected_edges)

    # create a triangulated vertex array of the selected faces
    if len(selected_faces) > 0:
        triangulated_verts = get_triangulated_faces(bm, selected_faces)
        create_vao("selected_faces", triangulated_verts)
    else:
        create_vao("selected_faces", [])


def get_triangulated_faces(bm, face_selection, collect_uvs=False):
    clone = bm.copy()

    unselected = []
    for f in clone.faces:
        if f.index not in face_selection:
            unselected.append(f)

    bmesh.ops.delete(clone, geom=unselected, context=5)

    triangulated = clone.calc_tessface()

    if collect_uvs:
        uv_layer = clone.loops.layers.uv.verify()
        clone.faces.layers.tex.verify()

    matrix = bpy.context.active_object.matrix_world
    triangulated_verts = []
    triangulated_uvs = []
    for triangle in triangulated:
        for loop in triangle:
            pos = matrix * loop.vert.co
            triangulated_verts.append(pos.x)
            triangulated_verts.append(pos.y)
            triangulated_verts.append(pos.z)
            if collect_uvs:
                triangulated_uvs.append(loop[uv_layer].uv.x)
                triangulated_uvs.append(loop[uv_layer].uv.y)

    del clone

    if collect_uvs:
        return triangulated_verts, triangulated_uvs

    return triangulated_verts


# a non recursive rewrite of https://github.com/nutti/Magic-UV/blob/develop/uv_magic_uv/muv_packuv_ops.py
def parse_uv_island(bm, face_idx):

    print(len(faces_to_uvs), len(uvs_to_faces))

    faces_left = set(faces_to_uvs.keys())  # all faces
    island = []

    candidates = set([face_idx])
    next_candidates = set()

    bm.faces.ensure_lookup_table()

    while len(candidates) > 0:
        for current in candidates:
            if current in faces_left:
                faces_left.remove(current)
                island.append(bm.faces[current])

                for uv in faces_to_uvs[current]:
                    connected_faces = uvs_to_faces[uv]
                    if connected_faces:
                        for cf in connected_faces:
                            next_candidates.add(cf)
        candidates.clear()
        candidates.update(next_candidates)
        next_candidates.clear()

    return island


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
    point_vec_scaled = point_vec * (1.0 / line_vec.length)

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


# some code here is from space_view3d_math_vis
def tag_redraw_all_views():
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
