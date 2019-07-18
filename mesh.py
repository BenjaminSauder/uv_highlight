import bpy
import bmesh
import numpy as np
import time


class StoredSelections():
    pass


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

        self.target = obj.name
        self.matrix = obj.matrix_world.copy()

        if len(mesh.vertices) > 50000:
            print("skip")
            return False

        bm = bmesh.from_edit_mesh(mesh)
        uv_layer = bm.loops.layers.uv.verify()

        # update geometry buffers
        selection_updated = False
        if update_selection_only:
            data = self.fetch_selection_data(bm, uv_layer)
            if self.has_selection_changed(data):
                self.update_stored_selections(data)
                selection_updated = True
            else:
                return False

        self.is_updating = True

        if not selection_updated:
            result = self.fetch_selection_data(bm, uv_layer)
            self.update_stored_selections(result)

        if not update_selection_only or not self.faceindex_to_loop:
            self.fetch_mesh_data(bm, uv_layer)

        # update render buffers
        bm.verts.ensure_lookup_table()
        self.create_vert_buffer(bm)
        bm.edges.ensure_lookup_table()
        self.create_edge_buffer(bm)
        self.create_hidden_edge_buffer(bm)
        self.create_face_buffer(bm)

        self.last_update = time.perf_counter()
        self.is_updating = False

        return True

    def fetch_selection_data(self, bm, uv_layer):
        vert_selected = []
        uv_vertex_selected = []
        uv_face_selected = []
        uv_edge_selected = []

        for f in bm.faces:
            face_selected = True
            for l in f.loops:
                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                if uv.select and l.vert.select:
                    uv_vertex_selected.append(l.vert.index)

                if l.vert.select:
                    vert_selected.append(l.vert.index)

                if uv.select and uv_next.select and l.edge.select:
                    uv_edge_selected.append(l.edge.index)

                if face_selected and not uv.select:
                    face_selected = False

            if face_selected and l.face.select:
                uv_face_selected.append(l.face.index)

        result = StoredSelections()
        result.vert_selected = np.array(vert_selected)
        result.uv_vertex_selected = np.array(uv_vertex_selected)
        result.uv_edge_selected = np.array(uv_edge_selected)
        result.uv_face_selected = np.array(uv_face_selected)

        return result

    def update_stored_selections(self, stored_selections):
        self.vert_selected = stored_selections.vert_selected
        self.uv_vertex_selected = stored_selections.uv_vertex_selected
        self.uv_edge_selected = stored_selections.uv_edge_selected
        self.uv_face_selected = stored_selections.uv_face_selected

    def has_selection_changed(self, new_selections):
        if (np.array_equal(self.vert_selected, new_selections.vert_selected) and
                np.array_equal(self.uv_vertex_selected, new_selections.uv_vertex_selected)):
            return False

        return True

    def fetch_mesh_data(self, bm, uv_layer):        
        looptris = bm.calc_loop_triangles()

        current = looptris[0][0].face.index
        faces = {}
        faces[current] = []

        uv_coords = []

        uv_hidden_edges = []

        for loops in looptris:

            for l in loops:
                index = l.face.index
                if index != current:
                    current = index
                    faces[current] = []

                faces[current].append(l.vert.index)

                uv = l[uv_layer]
                uv_next = l.link_loop_next[uv_layer]

                uv_coords.extend(uv.uv.to_tuple())

                # this collects the hidden edges - it's a bit complicated as I dont want to draw over currently shown uv borders
                # hence this tests if the other polygon is selected and if it is, checks the uvs if those are split.
                # one could ignore all of this - but the overdrawing looks ugly..
                if not l.face.select:
                    other = l.link_loop_radial_next
                    do_append = not other.face.select
                    if not do_append:
                        other_uv = other[uv_layer]
                        other_uv_next = other.link_loop_next[uv_layer]
                        do_append = uv.uv != other_uv_next.uv or uv_next.uv != other_uv.uv

                    if do_append:
                        uv_hidden_edges.append(
                            (uv.uv.to_tuple(), uv_next.uv.to_tuple()))

        self.faceindex_to_loop = faces
        self.uv_coords = np.array(uv_coords)
        self.uv_hidden_edges = np.array(uv_hidden_edges)

    # RENDER BUFFERS

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

        self.edge_buffer = (coords, indices)

    def create_hidden_edge_buffer(self, bm):
        if self.uv_hidden_edges.size == 0:
            self.hidden_edge_buffer = ((), ())
            return

        edges = self.uv_hidden_edges.reshape(-1, 2)

        uv, indices = np.unique(edges, return_inverse=True, axis=0)
        uv = uv.tolist()

        indices = indices.reshape(-1, 2)
        indices = indices.astype(int).tolist()

        self.hidden_edge_buffer = (uv, indices)

    def create_face_buffer(self, bm):
        loop_tris = []
        for f in self.uv_face_selected:
            loop_tris.extend(self.faceindex_to_loop[f])

        vert_indices = np.array(loop_tris).reshape(-1, 3)
        verts, indices = np.unique(vert_indices, return_inverse=True)
        coords = [bm.verts[index].co.to_tuple() for index in verts]
        indices = indices.astype(int)

        self.face_buffer = (coords, indices)
