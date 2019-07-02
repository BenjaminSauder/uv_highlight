import time

import bpy
import bmesh
from bpy.app.handlers import persistent

import numpy as np
import math
import mathutils

from mathutils import Matrix, Vector
from collections import defaultdict

from . import render


UV_MOUSE = None


class Context():

    def __init__(self):
        self.window = None
        self.screen = None
        self.scene = None
        self.active_object = None

    def as_dict(self):
        return {
            'window': self.window,
            'screen': self.screen,
            'scene': self.scene,
            'active_object': self.active_object,
        }


class Updater():
    def __init__(self, selection_data, renderer_view3d, renderer_uv):
        self.selection_data = selection_data
        self.renderer_view3d = renderer_view3d
        self.renderer_uv = renderer_uv
        self.mouse_update = False
        self.mouse_position = (0, 0)

    def start(self):
        return
        
        bpy.app.timers.register(self.timer)
        bpy.app.handlers.depsgraph_update_post.append(self.depsgraph_handler)

    def stop(self):
        self.renderer_uv.disable()
        self.renderer_view3d.disable()

        try:
            bpy.app.timers.unregister(self.timer)
            bpy.app.handlers.depsgraph_update_post.remove(
                self.depsgraph_handler)
        except Exception as e:
            pass

    def get_context(self):
        context = Context()

        window = bpy.context.window_manager.windows[0]
        context.window = window
        context.screen = window.screen
        context.active_object = bpy.context.scene.view_layers[0].objects.active

        return context

    def watch_mouse(self):

        # if not self.mouse_update:
        #    self.mouse_update = True
        bpy.ops.uv.mouseposition(
            self.get_context().as_dict(), 'INVOKE_DEFAULT')

    def timer(self):
        self.watch_mouse()
        if self.selection_data.update(self.get_context(), True):
            self.renderer_view3d.update(self.selection_data)

        return 0.5

    @persistent
    def depsgraph_handler(self, dummy):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for update in depsgraph.updates:
            uid = update.id
            #print(update.is_updated_geometry, update.is_updated_transform)
            # if uid == bpy.context.active_object:
            #     if not bpy.context.active_object.data.is_editmode:
            #         return

                # print(uid, update, update.is_updated_geometry,
                #       update.is_updated_transform)

            if self.selection_data.update(bpy.context, False):
                self.renderer_view3d.update(self.selection_data)


class SelectionData():

    def __init__(self):
        self.matrix = None
        
        self.bm_instance = None
        self.uv_layer = None
        self.selections = []

        self.last_update = 0
        self.selection_changed_test = ()
        
        self.uv_edges = []
        self.uv_to_loop = {}
        self.faces_to_uvs = defaultdict(set)
        self.uvs_to_faces = defaultdict(set)

        self.buffer_edges = ()
        self.buffer_faces = ()

    def update(self, context, update_selection_only):

        # if not self.bm_instance or not self.bm_instance.is_valid:
        if not hasattr(context, 'active_object'):
            return

        obj = context.active_object
        self.matrix = obj.matrix_world

        mesh = obj.data
        if not mesh.is_editmode:
            return

        self.bm_instance = bmesh.from_edit_mesh(mesh)
        self.uv_layer = self.bm_instance.loops.layers.uv.verify()
        self.bm_instance.verts.ensure_lookup_table()

        refresh = True

        perf_time = time.perf_counter()
        if update_selection_only:
            if not self.has_selection_changed():
                refresh = False

        if refresh:
            t = time.perf_counter()

            if self.last_update + 0.2 < t:
                print ("#" * 66)
                print( "selection changed: %s"  % (time.perf_counter() - perf_time))

                #print("Refresh Data:", time.time())
                self.fetchData(update_selection_only)
                print( "refresh data: %s"  % (time.perf_counter() - t))

                perf_time = time.perf_counter()
                self.assembleBuffers()
                print( "refresh buffers: %s"  % (time.perf_counter() - t))

                self.last_update = t                
                
        return refresh

    def get_selection(self):

        verts_selection = [vert.index for vert in self.bm_instance.verts if vert.select]        
        uv_selection = []
        for vert in verts_selection:                        
             for loop in self.bm_instance.verts[vert].link_loops:
                uv = loop[self.uv_layer]
                if uv.select:
                    uv_selection.append(loop.index)
        return (verts_selection, uv_selection)

    def has_selection_changed(self):
        current = self.get_selection()    
        return self.selection_changed_test != current

    def assembleBuffers(self):
        if self.bm_instance == None:
            return      

        #self.buffer_edges = self.assembleEdgeBuffer()
        self.buffer_faces = self.assembleFaceBuffer()

    def assembleEdgeBuffer(self):

        if len(self.selections[1]) == 0:
            return ((), ())

        coords = []
        indices = []

        for edge in self.selections[1]:
            for vert in edge.verts:
                indices.append(vert.index)
        
        indices = tuple(indices)
        for index in set(indices):
            vert = self.bm_instance.verts[index]
            coords.append(vert.co)

        return (coords, indices)

    def assembleFaceBuffer(self):

        if len(self.selections[2]) == 0:
            return ((), ())

        vert_indices = []
        looptris = self.bm_instance.calc_loop_triangles()
        for tri in looptris:
            if tri[0].face.index in self.selections[2]:
                vert_indices.append(
                    (tri[0].vert.index, (tri[1].vert.index), (tri[2].vert.index)))

        coords = []

        arr = np.array(vert_indices)
        flat = arr.ravel()

        mapping = {}
        indices = []    
        current = 0
        for index, item in enumerate(flat):

            if item in mapping:
                indices.append(mapping[item])
            else:
                vert = self.bm_instance.verts[item]
                coords.append(vert.co)
                mapping[item] = current
                indices.append(current)
                current += 1

        indices = np.array(indices)
        indices = np.hsplit(indices, int(len(indices) / 3))

        return (coords, indices)
        
    def fetchData(self, update_selection_only):
        self.selection_changed_test = self.get_selection()

        #print("fetch data")
        update_uvs = not update_selection_only

        self.selections.clear()

        selected_verts = []
        selected_edges = set()
        selected_faces = set()

        edges = set()
        if update_uvs:
            self.uv_edges.clear()
            self.uv_to_loop.clear()
            self.uvs_to_faces.clear()
            self.faces_to_uvs.clear()

        for face in self.bm_instance.faces:

            start = face.loops[0]
            current = None
            face_uvs_selected = True

            while start != current:

                if current == None:
                    current = start

                uv = current[self.uv_layer]
                next_uv = current.link_loop_next[self.uv_layer]

                # uv edges
                if update_uvs:
                    uv_co = uv.uv.copy()
                    edge = current.edge.index
                    if edge not in edges:
                        edges.add(edge)

                        self.uv_edges.append(uv_co.x)
                        self.uv_edges.append(uv_co.y)
                        self.uv_edges.append(next_uv.uv.x)
                        self.uv_edges.append(next_uv.uv.y)

                    if face.select:
                        uv_co.resize_3d()
                        uv_co.freeze()
                        self.uv_to_loop[uv_co] = current

                        id = uv_co.to_tuple(8), current.vert.index
                        self.faces_to_uvs[face.index].add(id)
                        self.uvs_to_faces[id].add(face.index)

                # mesh verts
                if uv.select:
                    vert = current.vert
                    selected_verts.append(vert.index)

                elif face_uvs_selected:
                    face_uvs_selected = False

                # mesh edges
                if uv.select and next_uv.select:
                    selected_edges.add(current.edge)

                current = current.link_loop_next

            # mesh faces
            if face_uvs_selected and face.select:
                selected_faces.add(face.index)

        self.selections = [selected_verts, selected_edges, selected_faces]

        if update_uvs:
            self.update_kdtree()

    def update_kdtree(self):
        self.kdtree = mathutils.kdtree.KDTree(len(self.uv_to_loop))
        insert = self.kdtree.insert
        for index, (key, value) in enumerate(self.uv_to_loop.items()):
            # co_idx = key, index #TODO test if this is faster with *co_idx
            insert(key, index)

        self.kdtree.balance()


updater = Updater(SelectionData(), render.RendererView3d(),
                  render.RendererUV())

# from . import test

# test.main()
