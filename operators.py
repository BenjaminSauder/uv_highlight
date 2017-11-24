import bpy
import mathutils
import bmesh

from . import main
from . import render

MOUSE_UPDATE = False


area_id = 0


class UpdateOperator(bpy.types.Operator):
    """ This operator grabs the mouse location
    """
    bl_idname = "uv.uv_mouse_position"
    bl_label = "UV Mouse location"
    bl_options = {"REGISTER", "INTERNAL"}

    def modal(self, context, event):
        global TRANSFORM_ACTIVE
        # UV_MOUSE = None
        # UV_TO_VIEW = None

        #first check if a mouseclick ended a transform op
        if (main.translate_active and
                    "MOUSE" in event.type):
            main.translate_active = False

        # print( event.type )
        if event.type == 'MOUSEMOVE':
            main.UV_MOUSE = None

        # print(event.type, time.time())
        for area in context.screen.areas:
            if area.type == "IMAGE_EDITOR":
                # area is somehow wrong, as it includes the header
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
                # print(self.mousepos)

                # clamp to area
                if (mouse_region_x > 0 and mouse_region_y > 0 and
                            mouse_region_x < region_x + width and
                            mouse_region_y < region_y + height):
                    main.UV_MOUSE = mathutils.Vector(region_to_view(mouse_region_x, mouse_region_y))

                    if event.type in self.hotkeys:
                        main.translate_active = True


                #register draw handler
                if area not in render.IMAGE_EDITORS.keys():
                    global area_id
                    handle = area.spaces[0].draw_handler_add(render.draw_callback_viewUV,
                                                             (area, UV_TO_VIEW, area_id),
                                                             'WINDOW', 'POST_PIXEL')

                    area_id = area_id + 1
                    render.IMAGE_EDITORS[area] = handle

        main.update(do_update_preselection=True)
        main.tag_redraw_all_views()

        # handle auto uv mode convertion
        if bpy.context.scene.uv_highlight.auto_convert_uvmode:
            mode = bpy.context.scene.tool_settings.use_uv_select_sync
            if mode != self.uvmode:
                if mode:
                    bpy.ops.uv.uv_to_selection('INVOKE_DEFAULT')
                else:
                    bpy.ops.uv.selection_to_uv('INVOKE_DEFAULT')

                self.uvmode = mode

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global MOUSE_UPDATE
        if MOUSE_UPDATE:
            return {"FINISHED"}
        MOUSE_UPDATE = True

        # print(context.area.type)

        self.uvmode = bpy.context.scene.tool_settings.use_uv_select_sync

        wm = context.window_manager
        self.hotkeys = []
        keymap = wm.keyconfigs['Blender'].keymaps['UV Editor']
        self.hotkeys.append(keymap.keymap_items["transform.translate"].type)
        self.hotkeys.append(keymap.keymap_items["transform.rotate"].type)
        self.hotkeys.append(keymap.keymap_items["transform.resize"].type)

        self.mousepos = (0, 0)
        print("UV Highlight: running")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}


class HeartBeatOperator(bpy.types.Operator):
    """Operator which runs its self from a timer"""
    bl_idname = "uv.uv_highlight_heartbeat"
    bl_label = "Modal Timer Operator"
    bl_options = {"REGISTER", "INTERNAL"}
    _timer = None

    def modal(self, context, event):
        main.heartbeat()
        return {'PASS_THROUGH'}

    def execute(self, context):
        if MOUSE_UPDATE:
            print("timer is already running")
            return {'CANCELLED'}

        self._timer = context.window_manager.event_timer_add(1.0 / 30.0, context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.window_manager.event_timer_remove(self._timer)
        return {'CANCELLED'}


### TOOOS

class UVToSelection(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "uv.uv_to_selection"
    bl_label = "UV to selection"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        mode = bpy.context.scene.tool_settings.uv_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        verts = set()

        for f in bm.faces:
            selected = True
            for l in f.loops:
                uv = l[uv_layer]
                if uv.select:
                    verts.add(l.vert)
                else:
                    selected = False

            if mode == "FACE" or mode == "ISLAND":
                f.select_set(selected)
            else:
                f.select_set(False)

        if mode == "FACE" or mode == "ISLAND":
            bm.select_mode = {'FACE'}
        elif mode == "EDGE":
            for e in bm.edges:
                e.select_set(e.verts[0] in verts and e.verts[1] in verts)
            bm.select_mode = {'EDGE'}
        else:
            for v in bm.verts:
                v.select_set(v in verts)
            bm.select_mode = {'VERT'}

        bm.select_flush_mode()
        bmesh.update_edit_mesh(mesh)

        context.scene.tool_settings.mesh_select_mode = (
            mode == "VERTEX", mode == "EDGE", mode == "FACE" or mode == "ISLAND")

        bpy.context.scene.tool_settings.use_uv_select_sync = True

        return {"FINISHED"}


class SelectionToUV(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "uv.selection_to_uv"
    bl_label = "Selection to UV"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        vert_selection, edge_selection, face_selection = context.scene.tool_settings.mesh_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        for f in bm.faces:
            for l in f.loops:
                # if l.vert.select:
                l[uv_layer].select = l.vert.select

        bpy.context.scene.tool_settings.use_uv_select_sync = False
        bpy.ops.mesh.select_all(action='SELECT')

        if vert_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "VERTEX"
        elif edge_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "EDGE"
        elif face_selection:
            bpy.context.scene.tool_settings.uv_select_mode = "FACE"

        return {"FINISHED"}


class PinIslands(bpy.types.Operator):
    """ Pins uv islands which have not set any pins. Locking them into place basically
      """
    bl_idname = "uv.pin_islands"
    bl_label = "Pin unpinned uv islands"
    bl_options = {"REGISTER", "UNDO"}

    ACTIONS = [
        ("PIN", "Pin Islands", "", 1),
        ("UNPIN", "Unpin Islands", "", 2),
        ("UNPIN_ALL", "Unpin all", "", 3),
    ]

    action = bpy.props.EnumProperty(items=ACTIONS, name="Action")

    def execute(self, context):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        vert_selection, edge_selection, face_selection = context.scene.tool_settings.mesh_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        faces = set(bm.faces)
        islands = []

        print(self.action)

        while len(faces) > 0:
            island = main.parse_uv_island(bm, faces.pop().index)
            faces = faces.difference(island)
            islands.append(island)

        for island in islands:
            pinned = False
            all_pinned = True
            for f in island:
                for l in f.loops:
                    if l[uv_layer].pin_uv:
                        pinned = True
                    else:
                        if all_pinned:
                            all_pinned = False

                if pinned and not all_pinned:
                    break

            if not pinned and self.action == "PIN":
                for f in island:
                    for l in f.loops:
                        l[uv_layer].pin_uv = True

            if (all_pinned and self.action == "UNPIN") or self.action == "UNPIN_ALL":
                for f in island:
                    for l in f.loops:
                        l[uv_layer].pin_uv = False

        bmesh.update_edit_mesh(mesh)

        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


class UnwrapSelectedFaces(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "uv.unwrap_selected_faces"
    bl_label = "Unwraps the current uv-face selection"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        vert_selection, edge_selection, face_selection = context.scene.tool_settings.mesh_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()

        selected_faces = set()
        selected_face_uvs = set()

        for f in bm.faces:
            if f.select:
                selected_faces.add((f.index))

            selected = True
            loops = set()

            for l in f.loops:
                loops.add(l.index)
                if not l[uv_layer].select:
                    selected = False

            if selected:
                selected_face_uvs.union(loops)

            f.select_set(selected)

        bpy.ops.uv.unwrap()

        for f in bm.faces:
            for l in f.loops:
                if l.index in selected_face_uvs:
                    l[uv_layer].select = True

            f.select_set(f.index in selected_faces)

        bmesh.update_edit_mesh(mesh)
        return {"FINISHED"}
