import bpy
import bmesh
import numpy as np
import time


class Storage():

    def __init__(self):
        self.uv_vertex_selected = None
        self.uv_coords = None
        self.uv_face_selected = None
        self.uv_edge_selected = None
        self.vert_selected = None
        self.uv_hidden_edges = None


class Data():
    '''
    This class fetches all the necessary data from one mesh to render it's selected uv's, uv edges uv faces etc.
    To update this is pretty expensive on high density meshes, as there are sadly no foreach_get methods on bmesh,
    and to my knowledge its also not possible to get the loop data from the mesh.foreach calls in edit mode. So for 
    now I just keep using bmesh, and try not to do unnecessary things.
    '''

    def __init__(self):
        self.last_update = 0
        self.is_updating = False
        self.reset()

    def reset(self):
        self.target = None
        self.matrix = None

        # geometry buffers
        self.uv_vertex_selected = np.empty(0)
        self.uv_coords = np.empty(0)
        self.uv_face_selected = np.empty(0)
        self.uv_edge_selected = np.empty(0)
        self.vert_selected = np.empty(0)
        self.uv_hidden_edges = np.empty(0)
        self.faceindex_to_loop = None

        # render buffers
        self.vert_buffer = []
        self.edge_buffer = ((), ())
        self.hidden_edge_buffer = ((), ())
        self.face_buffer = ((), ())

    def update(self, obj, update_selection_only):

        if self.is_updating:
            return False

        if not obj:
            return False

        mesh = obj.data
        if not mesh.is_editmode:
            self.reset()
            return True

        self.target = obj
        self.matrix = obj.matrix_world

        if len(mesh.vertices) > 50000:
            print("skip")
            return False

        do_perf_prints = False
        perf_time = time.perf_counter()
        if do_perf_prints:
            print("-" * 66)

        bm = bmesh.from_edit_mesh(mesh)

        # update geometry buffers
        selection_updated = False
        if update_selection_only:
            result = self.fetch_uv(bm)
            if self.has_selection_changed(result.vert_selected, result.uv_vertex_selected):
                self.apply_storage(result)
                selection_updated = True
                if do_perf_prints:
                    print("update uv selection: %s" %
                          (time.perf_counter() - perf_time))
                    perf_time = time.perf_counter()
            else:
                return False

        self.is_updating = True

        if not selection_updated:
            result = self.fetch_uv(bm)
            self.apply_storage(result)
            if do_perf_prints:
                print("update uv selection: %s" %
                      (time.perf_counter() - perf_time))
                perf_time = time.perf_counter()

        if not update_selection_only or not self.faceindex_to_loop:
            self.fetchData(bm)
            if do_perf_prints:
                print("fetch data: %s" % (time.perf_counter() - perf_time))
                perf_time = time.perf_counter()

        # update render buffers
        bm.verts.ensure_lookup_table()
        self.create_vert_buffer(bm)
        bm.edges.ensure_lookup_table()
        self.create_edge_buffer(bm)
        self.create_hidden_edge_buffer(bm)
        self.create_face_buffer(bm)

        if do_perf_prints:
            print("update buffers: %s" % (time.perf_counter() - perf_time))
            perf_time = time.perf_counter()


        self.last_update = time.perf_counter()
        self.is_updating = False

        return True

    def fetch_uv(self, bm):
        uv_layer = bm.loops.layers.uv.verify()

        uv_coords = []
        uv_vertex_selected = []
        uv_face_selected = []
        uv_edge_selected = []
        vert_selected = []
        uv_hidden_edges = []

        for f in bm.faces:
            face_selected = True
            for l in f.loops:
                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                uv_coords.extend(uv.uv.to_tuple())

                if uv.select and l.vert.select:
                    uv_vertex_selected.append(l.vert.index)
                
                if uv.select and uv_next.select and l.edge.select:
                    uv_edge_selected.append(l.edge.index)              

                if not l.face.select:
                    other = l.link_loop_radial_next
                    other_uv = other.link_loop_next[uv_layer]
                    split_uvs = uv.uv != other_uv.uv
                    if split_uvs or not other.face.select:
                        uv_hidden_edges.append(
                            (uv.uv.to_tuple(), uv_next.uv.to_tuple()))

                if face_selected and not uv.select:
                    face_selected = False

                if l.vert.select:
                    vert_selected.append(l.vert.index)

            if face_selected and f.select:
                uv_face_selected.append(f.index)

        result = Storage()

        result.uv_vertex_selected = np.array(uv_vertex_selected)
        result.uv_coords = np.array(uv_coords)
        result.uv_face_selected = np.array(uv_face_selected)
        result.uv_edge_selected = np.array(uv_edge_selected)
        result.vert_selected = np.array(vert_selected)
        result.uv_hidden_edges = np.array(uv_hidden_edges)

        return result

    def has_selection_changed(self, vert_selected, uv_vert_selected):
        if (np.array_equal(self.vert_selected, vert_selected) and
            np.array_equal(self.uv_vertex_selected, uv_vert_selected)):
            return False

        return True

    def apply_storage(self, storage):
        self.uv_vertex_selected = storage.uv_vertex_selected
        self.uv_coords = storage.uv_coords
        self.uv_face_selected = storage.uv_face_selected
        self.uv_edge_selected = storage.uv_edge_selected
        self.vert_selected = storage.vert_selected
        self.uv_hidden_edges = storage.uv_hidden_edges

    def fetchData(self, bm):
        looptris = bm.calc_loop_triangles()

        current = looptris[0][0].face.index
        faces = {}
        faces[current] = []

        for loops in looptris:
            for loop in loops:
                index = loop.face.index
                if index != current:
                    current = index
                    faces[current] = []

                faces[current].append(loop.vert.index)

        self.faceindex_to_loop = faces

    def create_vert_buffer(self, bm):
        verts, indices = np.unique(
            self.uv_vertex_selected, return_inverse=True)
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

        self.edge_buffer = (coords, indices)

    def create_hidden_edge_buffer(self, bm):
        if self.uv_hidden_edges.size == 0:
            self.hidden_edge_buffer =((), ())
            return

        edges = self.uv_hidden_edges.reshape(-1, 2)

        uv, indices = np.unique(edges, return_inverse=True, axis=0)
        uv = uv.tolist()

        indices = indices.reshape(-1, 2)
        indices = indices.astype(int).tolist()

        self.hidden_edge_buffer = (uv, indices)


    def create_face_buffer(self, bm):
        # if self.uv_face_selected == 0:
        #     self.face_buffer = ((), ())
        #     return

        loop_tris = []
        for f in self.uv_face_selected:
            loop_tris.extend(self.faceindex_to_loop[f])

        vert_indices = np.array(loop_tris).reshape(-1, 3)
        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.face_buffer = (coords, indices)
