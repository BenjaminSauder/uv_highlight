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
    bl_idname = "wm.uv_mouse_position"
    bl_label = "UV Mouse location"
    bl_options = {"REGISTER", "INTERNAL"}



    def modal(self, context, event):

        # UV_MOUSE = None
        # UV_TO_VIEW = None
        main.UV_MOUSE = None
        if event.type == 'MOUSEMOVE':
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
                    #else:
                    #    main.UV_MOUSE = None

                    #print(main.UV_MOUSE)

                    if area not in render.IMAGE_EDITORS.keys():
                        global area_id
                        handle = area.spaces[0].draw_handler_add(render.draw_callback_viewUV, (area, UV_TO_VIEW, area_id),
                                                                 'WINDOW', 'POST_PIXEL')

                        area_id = area_id  + 1
                        render.IMAGE_EDITORS[area] = handle

        main.update(True)
        main.tag_redraw_all_views()
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global MOUSE_UPDATE
        if MOUSE_UPDATE:
            return {"FINISHED"}
        MOUSE_UPDATE = True

        print(context.area.type)

        self.mousepos = (0, 0)
        print("UV Highlight: running")
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}



class UVToSelection(bpy.types.Operator):
    """ Sets the selection base on the uv selection
    """
    bl_idname = "wm.uv_to_selection"
    bl_label = "UV to selection"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        mesh = context.active_object.data
        bm = bmesh.from_edit_mesh(mesh)

        mode = bpy.context.scene.tool_settings.uv_select_mode

        uv_layer = bm.loops.layers.uv.verify()
        bm.faces.layers.tex.verify()


        verts = set()
        faces = set()
        edges = set()

        for f in bm.faces:
            selected = True
            for l in f.loops:
                uv = l[uv_layer]
                if uv.select:
                    verts.add(l.vert)
                else:
                    selected = False

            if selected:
                faces.add(f)

        if mode == "FACE" or mode == "ISLAND":
            for f in bm.faces:
                f.select_set(f in faces)
        elif mode =="EDGE":
            for e in bm.edges:
                select = True
                for l in e.link_loops:
                    uv = l[uv_layer]
                    if not uv.select:
                        select = False
                e.select_set(select)
        else:
            for v in bm.verts:
                v.select_set(v in verts)

        bmesh.update_edit_mesh(mesh)

        return {"FINISHED"}