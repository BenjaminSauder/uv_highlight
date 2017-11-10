import bpy
import bgl
import time

from . import main

NORMALOFFSET = 0.0002

COLOR_RED = (1.0, 0.0, 0.0)
COLOR_GREEN = (0.0, 1.0, 0.0)
COLOR_BLUE = (0.0, 0.0, 1.0)
COLOR_CYAN = (0.0, 1.0, 1.0)
COLOR_BLACK = (0.0, 0.0, 0.0)
COLOR_WHITE = (1.0, 1.0, 1.0)

IMAGE_EDITORS = {}

handle_view3d = None


def enable():
    global handle_view3d
    if handle_view3d:
        return

    handle_view3d = bpy.types.SpaceView3D.draw_handler_add(draw_callback_view3D, (), 'WINDOW', 'POST_VIEW')

    IMAGE_EDITORS.clear()

    main.tag_redraw_all_views()


def disable():
    global handle_view3d
    if not handle_view3d:
        return

    bpy.types.SpaceView3D.draw_handler_remove(handle_view3d, 'WINDOW')
    handle_view3d = None

    for area, handle in IMAGE_EDITORS.items():
        bpy.types.SpaceImageEditor.draw_handler_remove(handle, 'WINDOW')

    IMAGE_EDITORS.clear()

    main.tag_redraw_all_views()


def draw_callback_view3D():
    if not main.isEditingUVs():
        return

    settings = bpy.context.scene.uv_highlight
    if not settings.show_in_viewport:
        return

    t1 = time.perf_counter()
    # if not update():
    #    return
    t2 = time.perf_counter()

    obj = bpy.context.active_object
    mode = bpy.context.scene.tool_settings.uv_select_mode
    matrix = obj.matrix_world



    # draw selected
    bgl.glColor3f(*COLOR_CYAN)
    if mode == "VERTEX":
        bgl.glPointSize(6.0)
        bgl.glBegin(bgl.GL_POINTS)

        for co, normal in main.selected_verts:
            bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
        bgl.glEnd()
        bgl.glPointSize(1.0)
    elif mode == "EDGE":
        bgl.glLineWidth(5.0)

        for edge in main.selected_edges:
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for co, normal in edge[0]:
                bgl.glVertex3f(*(matrix * (co)))  # + normal * NORMALOFFSET)))
            bgl.glEnd()
    else:
        bgl.glEnable(bgl.GL_CULL_FACE)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(3.0)
        bgl.glColor4f(*COLOR_CYAN, 0.4)
        for f in main.selected_faces:
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

    # PRE HIGHLIGHT VERTS
    if settings.show_preselection and main.UV_MOUSE:
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

        bgl.glColor4f(*COLOR_RED, 0.45)

        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[0]:
            bgl.glPointSize(7.0)
            bgl.glBegin(bgl.GL_POINTS)
            # bgl.glColor3f(*red)
            co, normal = main.closest_vert[0]
            bgl.glVertex3f(*(matrix * co + normal * NORMALOFFSET))
            bgl.glEnd()

        elif mode == 'EDGE' and main.closest_edge and main.closest_edge[0]:
            bgl.glLineWidth(5.0)
            bgl.glColor4f(*COLOR_RED, 1.0)
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for co, normal in main.closest_edge[0]:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
            bgl.glEnd()
        # draw FACE and ISLAND
        elif main.closest_face and main.closest_face[0]:
            bgl.glEnable(bgl.GL_CULL_FACE)
            # bgl.glEnable(bgl.GL_BLEND)
            # bgl.glLineWidth(3.0)
            # bgl.glColor4f(*red, 0.4)

            for p in main.closest_face[0]:
                bgl.glBegin(bgl.GL_POLYGON)
                for co, normal in p:
                    bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
                bgl.glEnd()

    restore_opengl_defaults()

    t3 = time.perf_counter()
    # print( "fps: %.1f total: %.3f - update: %.3f - render: %.3f" % ( 1.0/(t3-t1), t3-t1, t2-t1, t3 - t2 ))


def draw_callback_viewUV(area, UV_TO_VIEW, id):
    #print(id)

    settings =  bpy.context.scene.uv_highlight

    # remove closed areas
    if len(area.regions) == 0 or area.type != "IMAGE_EDITOR":
        bpy.types.SpaceImageEditor.draw_handler_remove(IMAGE_EDITORS[area], 'WINDOW')
        IMAGE_EDITORS.pop(area, None)
        # area.spaces[0].draw_handler_remove(IMAGE_EDITORS[area], 'WINDOW')

        print( "removing Image_Editor from drawing: %s" % id )
        return

    if not main.isEditingUVs() or area.spaces[0].mode != "VIEW":
        print("skipping Image_Editor from drawing: %s" % id)
        return

    viewport_info = bgl.Buffer(bgl.GL_INT, 4)
    bgl.glGetIntegerv(bgl.GL_VIEWPORT, viewport_info)

    for region in area.regions:
        if region.type == "WINDOW":
            width = region.width
            height = region.height
            region_x = region.x
            region_y = region.y

    bgl.glViewport(region_x, region_y, width, height)

    bgl.glMatrixMode(bgl.GL_MODELVIEW)
    bgl.glPushMatrix()
    bgl.glLoadIdentity()

    mode = bpy.context.scene.tool_settings.uv_select_mode

    if settings.show_hidden_faces:
        # draw uvs of non selected faces
        bgl.glLineWidth(0.1)
        bgl.glEnable(bgl.GL_CULL_FACE)
        # bgl.glEnable(bgl.GL_LINE_SMOOTH );
        bgl.glEnable(bgl.GL_BLEND);
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
        bgl.glBegin(bgl.GL_LINES)

        for uv in main.hidden_edges:
            bgl.glColor4f(0.4, 0.4, 0.4, 0.5)
            bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
        bgl.glEnd()

        bgl.glDisable(bgl.GL_CULL_FACE)

    # PRE HIGHLIGHT VERTS
    if settings.show_preselection and main.UV_MOUSE and UV_TO_VIEW:
        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[1]:

            bgl.glPointSize(5.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor3f(*COLOR_WHITE)

            if main.other_vert:
                bgl.glVertex2i(*UV_TO_VIEW(*main.other_vert))

            bgl.glVertex2i(*UV_TO_VIEW(*main.closest_vert[1], False))

            print(*main.closest_vert[1])

            bgl.glEnd()

            # print("MOUSE: %s, ClosestVert: %s - %s" % (UV_MOUSE, closestVert[1], view))
        elif mode == 'EDGE':
            # draw dark first, then overpaint with brighter colour
            bgl.glLineWidth(3.5)
            bgl.glEnable(bgl.GL_LINE_SMOOTH);
            bgl.glEnable(bgl.GL_BLEND);
            bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
            bgl.glBegin(bgl.GL_LINES)
            # edge
            if main.closest_edge and main.closest_edge[1][0] and main.closest_edge[1][1]:
                bgl.glColor3f(*COLOR_BLACK)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][1], False)))
            # matching edge
            if main.other_edge and main.other_edge[1][0] and main.other_edge[1][1]:
                bgl.glColor3f(*COLOR_BLACK)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][1], False)))
            bgl.glEnd()

            bgl.glLineWidth(2)
            bgl.glBegin(bgl.GL_LINES)
            # edge
            if main.closest_edge and main.closest_edge[1][0] and main.closest_edge[1][1]:
                bgl.glColor3f(*COLOR_WHITE)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][1], False)))
            # matching edge
            if main.other_edge and main.other_edge[1][0] and main.other_edge[1][1]:
                bgl.glColor3f(*COLOR_WHITE)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][1], False)))
            bgl.glEnd()
        elif main.closest_face and main.closest_face[1]:
            bgl.glDisable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glLineWidth(1.5)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE);
            scale = 0.25
            if mode == "ISLAND":
                scale = 0.1

            r, g, b = COLOR_WHITE
            bgl.glColor4f(r * scale, g * scale, b * scale, 1.0)
            for p in main.closest_face[1]:
                bgl.glBegin(bgl.GL_POLYGON)
                for uv in p:
                    bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
                bgl.glEnd()

    bgl.glViewport(*tuple(viewport_info))

    '''
    bgl.glMatrixMode(bgl.GL_MODELVIEW)
    bgl.glPopMatrix()
    bgl.glMatrixMode(bgl.GL_PROJECTION)
    bgl.glPopMatrix()
    '''

    restore_opengl_defaults()


def restore_opengl_defaults():
    bgl.glPointSize(1)
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glDisable(bgl.GL_CULL_FACE)
    bgl.glDisable(bgl.GL_LINE_SMOOTH);

    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)
