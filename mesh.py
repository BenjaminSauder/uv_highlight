
import math
import time
from collections import defaultdict

import bpy
import bmesh
import numpy as np

import mathutils

from . import util


class StoredSelections():
    pass

PRINT_PERF_TIME = False

class Data():
    '''
    This class fetches all the necessary data from a mesh, to be able to render it's selected uv's, uv edges uv faces etc.

    To update this is pretty expensive on high density meshes, as there are sadly no foreach_get methods on bmesh,
    and to my knowledge its also not possible to get the loop data from the mesh.foreach calls in edit mode. So for
    now I just keep using bmesh, and try not to do unnecessary things.

    Adding Preselection makes this also a whole lot slower.
    '''

    def __init__(self, settings):        
        self.is_updating = False
        self.settings = settings

        self.reset()

        prefs = bpy.context.preferences.addons[__package__].preferences
        self.max_verts = prefs.max_verts

    def reset(self, buffer_only=False):

        if not buffer_only:
            self.target = None
            self.matrix = None

        # geometry buffers
        self.uv_vertex_selected = np.empty(0)
        self.uv_coords = np.empty(0)
        self.uv_face_selected = np.empty(0)
        self.uv_edge_selected = np.empty(0)
        self.vert_selected = np.empty(0)

        # checks
        self.face_count = -1
        self.vert_count = -1

        # lookups
        self.face_to_vert = None
        self.faces_to_uvs = defaultdict(list)
        self.uvs_to_faces = defaultdict(set)
        self.uv_to_vert = {}
        self.looptris = []

        # preselection
        self._calculate_preselection = True
        self.closest_island = None

        # render buffers
        self.vert_buffer = []
        self.edge_buffer = (), ()
        self.uv_edge_buffer = (), ()
        self.face_buffer = (), ()

        self.preselection_verts = (), ()
        self.preselection_edges = [], ()

    def calculate_preselection(self, state):
        self._calculate_preselection = state

        if self._calculate_preselection:
            if self.bm:
                self.fetch_mesh_data(self.bm, self.uv_layer)

    def update(self, obj, update_selection_only):
        if self.is_updating:
            return False

        if not obj:
            return False

        mesh = obj.data
        if not mesh.is_editmode:
            self.reset()
            return True

        self.target = obj.name
        self.matrix = obj.matrix_world.copy()

        if len(mesh.vertices) > self.max_verts:
            return False

        self.bm = bmesh.from_edit_mesh(mesh)
        self.uv_layer = self.bm.loops.layers.uv.verify()

        # update geometry buffers
        t = time.perf_counter()
        selection_updated = False
        if update_selection_only:
            data = self.fetch_selection_data(self.bm, self.uv_layer)
            if self.has_selection_changed(data):
                self.update_stored_selections(data)
                selection_updated = True
            else:
                return False

        self.is_updating = True

        if not selection_updated:
            result = self.fetch_selection_data(self.bm, self.uv_layer)
            self.update_stored_selections(result)
        if PRINT_PERF_TIME: print("update selection", time.perf_counter() - t)

        if not update_selection_only or not self.has_fetched_mesh_data():
            t = time.perf_counter()
            self.fetch_mesh_data(self.bm, self.uv_layer)
            if PRINT_PERF_TIME: print("fetch_mesh_data", time.perf_counter() - t)

        # update render buffers
        t = time.perf_counter()
        self.create_vert_buffer(self.bm)
        if PRINT_PERF_TIME: print("create_vert_buffer", time.perf_counter() - t)
        
        t = time.perf_counter()
        self.create_edge_buffer(self.bm)
        if PRINT_PERF_TIME: print("create_edge_buffer", time.perf_counter() - t)
        
        t = time.perf_counter()
        self.create_uv_edge_buffer(self.bm)
        if PRINT_PERF_TIME: print("create_uv_edge_buffer", time.perf_counter() - t)

        t = time.perf_counter()
        self.create_face_buffer(self.bm)
        if PRINT_PERF_TIME: print("create_face_buffer", time.perf_counter() - t)
        
        
        self.is_updating = False
        if PRINT_PERF_TIME: print("-" * 66)
        return True

    def has_fetched_mesh_data(self):
        if self.face_to_vert:
            return True
        return False

    def fetch_selection_data(self, bm, uv_layer):
        vert_selected = []
        uv_vertex_selected = []
        uv_face_selected = []
        uv_edge_selected = []
        uv_edge_selected_coords = []

        all_verts_selected = True

        # only used for uv kd tree building
        uv_coords = []

        for f in bm.faces:
            face_selected = True
            for l in f.loops:
                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                if uv.select and l.vert.select:
                    uv_vertex_selected.append(l.vert.index)

                if l.vert.select:
                    vert_selected.append(l.vert.index)

                    if self.calculate_preselection:
                        uv_coords.append(uv.uv)
                elif all_verts_selected:
                    all_verts_selected = False

                if uv.select and uv_next.select and l.edge.select:
                    uv_edge_selected.append(l.edge.index)
                    coords = uv.uv, uv_next.uv
                    uv_edge_selected_coords.append(coords)

                if face_selected and not uv.select:
                    face_selected = False

            if face_selected and l.face.select:
                uv_face_selected.append(l.face.index)

        result = StoredSelections()
        result.vert_selected = np.array(vert_selected)
        result.uv_vertex_selected = np.array(uv_vertex_selected)
        result.uv_edge_selected = np.array(uv_edge_selected)
        result.uv_face_selected = np.array(uv_face_selected)
        result.uv_edge_selected_coords = uv_edge_selected_coords
        result.uv_coords = uv_coords
        result.all_verts_selected = all_verts_selected

        return result

    def update_stored_selections(self, stored_selections):
        self.vert_selected = stored_selections.vert_selected
        self.uv_vertex_selected = stored_selections.uv_vertex_selected
        self.uv_edge_selected = stored_selections.uv_edge_selected
        self.uv_face_selected = stored_selections.uv_face_selected
        self.uv_edge_selected_coords = stored_selections.uv_edge_selected_coords
        self.all_verts_selected = stored_selections.all_verts_selected

        if self.calculate_preselection:
            self.create_kd_tree(stored_selections.uv_coords)

    def has_selection_changed(self, new_selections):
        if (np.array_equal(self.vert_selected, new_selections.vert_selected) and
                np.array_equal(self.uv_vertex_selected, new_selections.uv_vertex_selected)):
            return False

        return True

    def update_loop_tris(self, bm):
        t = time.perf_counter()
        self.looptris = bm.calc_loop_triangles()
        
        if PRINT_PERF_TIME: print("looptris", time.perf_counter() - t)

        t = time.perf_counter()
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        # only needed for preselection
        if self.calculate_preselection:
            bm.faces.ensure_lookup_table()
        if PRINT_PERF_TIME: print("lookup tables", time.perf_counter() - t)


    def fetch_mesh_data(self, bm, uv_layer):
        # print("fetch_mesh_data")
        vert_count = len(bm.verts)
        face_count = len(bm.faces)
        looptris_valid = len(self.looptris) > 0 and self.looptris[0][0].is_valid

        if (face_count != self.face_count or vert_count != self.vert_count or not looptris_valid):
            self.face_count = face_count
            self.vert_count = vert_count
            self.update_loop_tris(bm)

        if len(self.looptris) == 0:
            self.reset(buffer_only=True)
            return

        faces_to_uvs = defaultdict(list)
        uvs_to_faces = defaultdict(set)
        uv_to_vert = {}

        current = self.looptris[0][0].face.index
        face_to_vert = {}
        face_to_vert[current] = []

        uv_coords = []

        for loops in self.looptris:
            for l in loops:
                index = l.face.index
                if index != current:
                    current = index
                    face_to_vert[current] = []

                face_to_vert[current].append(l.vert.index)

                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                uv_co = uv.uv.to_tuple(5)
                uv_coords.extend(uv_co)

                if l.face.select:
                    if self.calculate_preselection:
                        id = uv_co, l.vert.index
                        faces_to_uvs[l.face.index].append(id)
                        uvs_to_faces[id].add(l.face.index)
                        uv_to_vert[uv_co] = l.vert.index
               

        self.uv_coords = np.array(uv_coords)
        self.face_to_vert = face_to_vert

        if self.calculate_preselection:
            self.faces_to_uvs = faces_to_uvs
            self.uvs_to_faces = uvs_to_faces
            self.uv_to_vert = uv_to_vert
            self.face_to_island = self.find_uv_islands(bm)
            self.closest_island = None

    ############################################################################
    # PRESELECTION
    ############################################################################

    def get_closest_uv_distance(self, mouse_pos):

        if self.vert_selected.size < 4:
            return math.inf, None

        closest_uv, index, distance = self.kd_tree.find(mouse_pos)

        return distance, closest_uv

    # make sure that get_closest_uv_distance is called before
    def update_preselection(self, mode, uv, mouse_position):

        mouse_pos = mouse_position.copy()
        mouse_pos.resize_2d()

        closest_uv = uv.copy()
        closest_uv.resize_2d()
        closest_uv = closest_uv.to_tuple(5)

        if closest_uv in self.uv_to_vert:
            index = self.uv_to_vert[closest_uv]
            closest_vert = self.bm.verts[index]
        else:
            return False

        if mode == 'VERTEX':
            uvs = [closest_uv]
            for loop in closest_vert.link_loops:
                loop_uv = loop[self.uv_layer]
                uvs.append(loop_uv.uv.to_tuple())

            self.preselection_verts = (
                closest_vert.co.to_tuple()), (uvs)
            return True

        elif mode == 'EDGE':
            self.preselection_edges = self.preselect_edges(
                closest_vert, mouse_pos)
            if self.preselection_edges:
                return True
        elif mode == 'FACE':
            self.preselection_faces = self.preselect_face(
                closest_vert, mouse_pos)
            return True

        elif mode == 'ISLAND':
            self.preselection_faces = self.preselect_island(
                closest_vert, mouse_pos)
            return True

        return False

    def create_kd_tree(self, uv_coords):

        size = len(uv_coords)
        kd = mathutils.kdtree.KDTree(size)
        insert = kd.insert

        for index, co in enumerate(uv_coords):
            insert((co[0], co[1], 0), index)

        kd.balance()

        self.kd_tree = kd

    def get_connected_uv_edge(self, edge, edge_uv, uv_layer):
        for l in edge.link_loops:
            if not l.edge.select or not l.face.select:
                continue

            other_uv = l[uv_layer].uv
            other_next_uv = l.link_loop_next[uv_layer].uv

            uv, next_uv = edge_uv

            a = uv == other_uv
            b = uv == other_next_uv
            c = next_uv == other_next_uv
            d = next_uv == other_uv

            # this little funky term makes sure to only count for split uv edges
            if not ((a or b) and (c or d)):
                return other_uv, other_next_uv

        return ()

    def preselect_edges(self, closest_vert, mouse_pos):
        uv_layer = self.uv_layer

        closest_edge = None
        closest_edge_uv = ()

        other_edge_uv = ()
        edge_distance = math.inf

        # find closest edge
        for edge in closest_vert.link_edges:
            if not edge.select:
                continue

            for l in edge.link_loops:
                if not l.face.select:
                    continue

                # uv = l[uv_layer].uv.copy()
                # next_uv = l.link_loop_next[uv_layer].uv.copy()

                uv = l[uv_layer].uv
                next_uv = l.link_loop_next[uv_layer].uv

                d = util.distance_line_point(uv, next_uv, mouse_pos)

                if d < edge_distance:
                    edge_distance = d
                    closest_edge = edge
                    closest_edge_uv = uv, next_uv

                # happens when the closest vert is at a corner, and both edges share that corner vert
                elif d == edge_distance:
                    min_uv, min_next_uv = closest_edge_uv

                    if (min_uv - mouse_pos).length == d:
                        current = (min_next_uv - mouse_pos).to_tuple()
                    else:
                        current = (min_uv - mouse_pos).to_tuple()

                    if (uv - mouse_pos).length == d:
                        candiate = (next_uv - mouse_pos).to_tuple()
                    else:
                        candiate = (uv - mouse_pos).to_tuple()

                    candiate_min = min(candiate)
                    current_min = min(current)

                    if candiate_min < current_min:
                        closest_edge = edge
                        closest_edge_uv = uv, next_uv

        if not closest_edge:
            return False

        other_edge_uv = self.get_connected_uv_edge(
            closest_edge, closest_edge_uv, uv_layer)

        # create render buffers
        verts = []
        verts.append(closest_edge.verts[0].co)
        verts.append(closest_edge.verts[1].co)

        uvs = closest_edge_uv
        uvs_other = ()
        if len(other_edge_uv) > 0:
            uvs_other = other_edge_uv

        return verts, (uvs, uvs_other)

    def find_closest_face(self, closest_vert, mouse_pos):

        for f in closest_vert.link_faces:
            if not f.select:
                continue

            face_uvs = [l[self.uv_layer].uv for l in f.loops]

            if util.point_in_polygon(mouse_pos, face_uvs):
                closest_face = f.index
                closest_face_loops = [l for l in f.loops]
                return closest_face, closest_face_loops

        return None, None

    def preselect_face(self, closest_vert, mouse_pos):

        closest_face, closest_face_loops = self.find_closest_face(
            closest_vert, mouse_pos)

        if closest_face == None:
            return ((), ()), ((), ())

        return self.vert_uv_buffers_for_faces(self.bm, [closest_face])

    def preselect_island(self, closest_vert, mouse_pos):

        closest_face, closest_face_loops = self.find_closest_face(
            closest_vert, mouse_pos)
        if closest_face == None:
            return ((), ()), ((), ())

        closest_island = self.face_to_island[closest_face]

        if len(closest_island) == 0:
            return ((), ()), ((), ())

        # creating the render buffer is pretty slow..
        if not self.closest_island or closest_island != self.closest_island[0]:
            buffers = self.vert_uv_buffers_for_faces(self.bm, closest_island)
            self.closest_island = closest_island, buffers
            return buffers
        else:
            return self.closest_island[1]

    def find_uv_islands(self, bm):
        islands = []

        faces_left = set(self.faces_to_uvs.keys())
        while faces_left:
            face_index = list(faces_left)[0]
            island, faces_left = self.parse_uv_island(
                self.bm, face_index, faces_left)
            islands.append(island)

        face_to_island = {}
        for island in islands:
            for face in island:
                face_to_island[face] = island

        return face_to_island

    # a non recursive rewrite of:
    # https://blender.stackexchange.com/questions/48827/how-to-get-lists-of-uv-island-from-python-script

    def parse_uv_island(self, bm, face_index, faces_left):
        island = []
        candidates = set([face_index])
        next_candidates = []

        while len(candidates) > 0:
            for current in candidates:
                if current in faces_left:
                    faces_left.remove(current)
                    island.append(bm.faces[current].index)

                    uvs = self.faces_to_uvs[current]
                    for uv in uvs:
                        connected_faces = self.uvs_to_faces[uv]
                        if connected_faces:
                            for face in connected_faces:
                                next_candidates.append(face)
            candidates.clear()
            candidates.update(next_candidates)
            next_candidates.clear()

        return island, faces_left

    ############################################################################
    # RENDER BUFFERS
    #
    # this just converts the mesh data into vbo/ibo compatible formats
    ############################################################################

    def create_vert_buffer(self, bm):
        verts = np.unique(self.uv_vertex_selected)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        self.vert_buffer = coords

    def create_edge_buffer(self, bm):
        unique_edges = np.unique(self.uv_edge_selected)
        vert_indices = [(bm.edges[index].verts[0].index,
                         bm.edges[index].verts[1].index) for index in unique_edges]
        vert_indices = np.array(vert_indices)

        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.edge_buffer = coords, indices

    def create_uv_edge_buffer(self, bm):
        uv_edges = []
        for index, edge in enumerate(self.uv_edge_selected):
            edge_coords = self.uv_edge_selected_coords[index]

            other = self.get_connected_uv_edge(
                bm.edges[edge], edge_coords, self.uv_layer)
            if other and other not in self.uv_edge_selected_coords:
                uv_edges.extend(other)

        if len(uv_edges) == 0:
            self.uv_edge_buffer = (), ()
            return

        edges = np.array(uv_edges)
        uv, indices = np.unique(edges, return_inverse=True, axis=0)
        uv = uv.tolist()

        indices = indices.reshape(-1, 2)
        indices = indices.astype(int).tolist()

        self.uv_edge_buffer = uv, indices

    def create_face_buffer(self, bm):
        loop_tris = []
        for f in self.uv_face_selected:
            loop_tris.extend(self.face_to_vert[f])

        vert_indices = np.array(loop_tris).reshape(-1, 3)
        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.face_buffer = (coords, indices)

    def vert_uv_buffers_for_faces(self, bm, faces):
        loop_tris = []
        loop_tris_extend = loop_tris.extend
        uvs = []
        uvs_extend = uvs.extend

        for f in faces:
            loop_tris_extend(self.face_to_vert[f])

            uv = self.faces_to_uvs[f]
            uv = [item[0] for item in uv]
            uvs_extend(uv)

        vert_indices = np.array(loop_tris).reshape(-1, 3)
        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        uv_verts, uv_indices = np.unique(uvs, return_inverse=True, axis=0)
        uv_verts = uv_verts.tolist()
        uv_indices = uv_indices.astype(int)

        return (coords, indices), (uv_verts, uv_indices)
