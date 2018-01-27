import bpy
import bgl
import time
import blf

from . import main

NORMALOFFSET = 0.0002

COLOR_RED = (1.0, 0.0, 0.0)
COLOR_GREEN = (0.0, 1.0, 0.0)
COLOR_BLUE = (0.0, 0.0, 1.0)
COLOR_CYAN = (0.0, 1.0, 1.0)
COLOR_BLACK = (0.0, 0.0, 0.0)
COLOR_WHITE = (1.0, 1.0, 1.0, 1.0)

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

    prefs = bpy.context.user_preferences.addons[__package__].preferences

    t1 = time.perf_counter()
    # if not update():
    #    return
    t2 = time.perf_counter()

    obj = bpy.context.active_object
    mode = bpy.context.scene.tool_settings.uv_select_mode
    matrix = obj.matrix_world

    # draw selected
    # bgl.glColor4f(*prefs.view3d_selection_color_verts_edges)

    #bgl.glMatrixMode(bgl.GL_MODELVIEW)
    #bgl.glPushMatrix()
    #bgl.glLoadIdentity()
    #print((len(matrix)))
    #m = bgl.Buffer(bgl.GL_FLOAT, 16, [entry for collumn in matrix for entry in collumn] )
    #bgl.glLoadMatrixf(m)

    if mode == "VERTEX":
        bgl.glPointSize(6.0)
        draw_vertex_array("selected_verts", bgl.GL_POINTS, 3, prefs.view3d_selection_color_verts_edges)
    elif mode == "EDGE":
        bgl.glLineWidth(3.0)
        bgl.glEnable(bgl.GL_POLYGON_OFFSET_LINE)
        bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)
        draw_vertex_array("selected_edges", bgl.GL_LINES, 3, prefs.view3d_selection_color_verts_edges)
        bgl.glDisable(bgl.GL_POLYGON_OFFSET_LINE)
    else:
        bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
        bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)
        draw_vertex_array("selected_faces", bgl.GL_TRIANGLES, 3, prefs.view3d_selection_color_faces)
        bgl.glDisable(bgl.GL_POLYGON_OFFSET_FILL)

    bgl.glPopMatrix()

    # PRE HIGHLIGHT
    if settings.show_preselection and main.UV_MOUSE:
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

        bgl.glColor4f(*prefs.view3d_preselection_color_verts_edges)

        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[0]:
            bgl.glPointSize(7.0)
            bgl.glEnable(bgl.GL_POLYGON_OFFSET_POINT)
            bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)

            bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)

            bgl.glBegin(bgl.GL_POINTS)
            co, normal = main.closest_vert[0]
            bgl.glVertex3f(*(matrix * co))
            bgl.glEnd()
            bgl.glDisable(bgl.GL_POLYGON_OFFSET_POINT)

        elif mode == 'EDGE' and main.closest_edge and main.closest_edge[0]:
            bgl.glLineWidth(7.0)
            bgl.glEnable(bgl.GL_POLYGON_OFFSET_LINE)
            bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)

            bgl.glBegin(bgl.GL_LINE_STRIP)
            for co, normal in main.closest_edge[0]:
                bgl.glVertex3f(*(matrix * co))
            bgl.glEnd()
            bgl.glDisable(bgl.GL_POLYGON_OFFSET_LINE)

        # draw FACE and ISLAND
        elif main.closest_face and main.closest_face[0]:
            bgl.glEnable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
            bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)
            draw_vertex_array("closest_faces", bgl.GL_TRIANGLES, 3, prefs.view3d_preselection_color_faces)
            bgl.glDisable(bgl.GL_POLYGON_OFFSET_FILL)

    bgl.glDisable(bgl.GL_POLYGON_OFFSET_FILL)
    restore_opengl_defaults()

    t3 = time.perf_counter()
    # print( "fps: %.1f total: %.3f - update: %.3f - render: %.3f" % ( 1.0/(t3-t1), t3-t1, t2-t1, t3 - t2 ))


def draw_callback_viewUV(area, UV_TO_VIEW, id):
    # print(id, area.spaces[0].image, area.spaces[0].show_uvedit )

    settings = bpy.context.scene.uv_highlight
    prefs = bpy.context.user_preferences.addons[__package__].preferences
    mode = bpy.context.scene.tool_settings.uv_select_mode

    # remove closed areas
    if len(area.regions) == 0 or area.type != "IMAGE_EDITOR":
        bpy.types.SpaceImageEditor.draw_handler_remove(IMAGE_EDITORS[area], 'WINDOW')
        IMAGE_EDITORS.pop(area, None)
        # print("removing Image_Editor from drawing: %s" % id)
        return

    # dont show this if the area is in Image mode :D
    if not main.isEditingUVs() or area.spaces[0].mode != "VIEW" or not area.spaces[0].show_uvedit:
        # print("skipping Image_Editor from drawing: %s" % id)
        return

    sync_mode = bpy.context.scene.tool_settings.use_uv_select_sync

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
    # bgl.glLoadIdentity()

    origin = UV_TO_VIEW(0, 0, False)
    axis = UV_TO_VIEW(1.0, 0, False)[0] - origin[0]

    M = (axis, 0, 0, 0,
         0, axis, 0, 0,
         0, 0, 1.0, 0,
         origin[0], origin[1], 0, 1.0)
    m = bgl.Buffer(bgl.GL_FLOAT, 16, M)
    bgl.glLoadMatrixf(m)



    if settings.show_hidden_faces and not sync_mode:
        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)
        draw_vertex_array("hidden_edges", bgl.GL_LINES, 2, prefs.uv_hidden_faces)

    if settings.show_udim_indices:
        draw_udim_tiles(M, prefs.udim_markers)

    # PRE HIGHLIGHT VERTS
    if settings.show_preselection and main.UV_MOUSE and UV_TO_VIEW and not sync_mode:
        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[1]:
            bgl.glLoadIdentity()
            bgl.glPointSize(5.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)

            if main.other_vert:
                bgl.glVertex2i(*UV_TO_VIEW(*main.other_vert))

            bgl.glVertex2i(*UV_TO_VIEW(main.closest_vert[1][0], main.closest_vert[1][1], False))

            bgl.glEnd()

            # print("MOUSE: %s, ClosestVert: %s - %s" % (UV_MOUSE, closestVert[1], view))
        elif mode == 'EDGE':
            # draw dark first, then overpaint with brighter colour
            bgl.glLoadIdentity()
            bgl.glLineWidth(3.5)
            bgl.glEnable(bgl.GL_LINE_SMOOTH)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
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
                bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][1], False)))
            # matching edge
            if main.other_edge and main.other_edge[1][0] and main.other_edge[1][1]:
                bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][1], False)))
            bgl.glEnd()

        else:

            bgl.glDisable((bgl.GL_CULL_FACE))
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)

            draw_vertex_array("closest_face_uvs", bgl.GL_TRIANGLES, 2, prefs.uv_preselection_color_faces)

    bgl.glViewport(*tuple(viewport_info))
    bgl.glMatrixMode(bgl.GL_MODELVIEW)
    bgl.glPopMatrix()
    bgl.glMatrixMode(bgl.GL_PROJECTION)
    bgl.glPopMatrix()

    restore_opengl_defaults()


# UDM_TILES = [1001, 1002, 1003, 1104, 1010]
UDM_TILES = []
def set_udims(udims):
    #print("udims:", udims)
    global UDM_TILES
    UDM_TILES.clear()
    verts = []

    for tile in udims:
        UDM_TILES.append(tile)

        y, x = udim_to_xy(tile)

        # ignore first tile for quad drawing
        if x == 0 and y == 0:
            continue

        verts.extend([x, y, x + 1, y,
                      x + 1, y, x + 1, y + 1,
                      x + 1, y + 1, x, y + 1,
                      x, y + 1, x, y])


    create_vao("udims", verts)


# this is 0 based..
def udim_to_xy(udim):
    return int(str(udim)[:2]) - 10, int(str(udim)[2:]) - 1


def draw_udim_tiles(M, color):

    if len(UDM_TILES) == 0:
        return

    bgl.glMatrixMode(bgl.GL_MODELVIEW)
    bgl.glPushMatrix()
    bgl.glLoadIdentity()

    bgl.glColor4f(*color)

    # label placement
    for tile in UDM_TILES:
        y, x = udim_to_xy(tile)
        #print("label:",y,x)

        font_id = 0
        font_size = maprange((64, 512), (8, 12), M[0])
        if (M[0] > 64):
            blf.size(font_id, int(font_size), 72)
            offset = M[0] * (1 / 32.0)
            blf.position(font_id, x * M[0] + M[12] + offset, y * M[0] + M[13] + offset, 0)
            blf.draw(font_id, str(tile))

    bgl.glPopMatrix()

    bgl.glLineWidth(1.0)
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)
    draw_vertex_array("udims", bgl.GL_LINES, 2, color)


def restore_opengl_defaults():
    bgl.glPointSize(1)
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ZERO)
    bgl.glDisable(bgl.GL_CULL_FACE)
    bgl.glDisable(bgl.GL_LINE_SMOOTH);
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


def maprange(a, b, value):
    (a1, a2), (b1, b2) = a, b
    return b1 + ((value - a1) * (b2 - b1) / (a2 - a1))


VAO = {}


def create_vao(name, verts):
    vao = None

    if len(verts) > 0:
        vao = bgl.Buffer(bgl.GL_FLOAT, len(verts), verts)

    '''
    if name == "hidden_edges":
        vertices = [0, 0,
                    100, 100]
        vao = bgl.Buffer(bgl.GL_FLOAT, len(vertices), vertices)
    '''

    VAO[name] = vao


'''
def set_selected_faces_vao(verts):
    global VAO

    #print("---------------")
    #for i in range(0, len(verts), 3):
    #    print("(%s, %s, %s)" % (verts[i], verts[i+1], verts[i+2]))

    vertices = [-1, 0, 0,
                1, 0, 0,
                -1, 0, 1,

                1, 0, 0,
                -1, 0,1,
                1, 0, 1,

                ]

    VAO["selected_faces"] = create_vao(verts)
'''

shaderVertString = """
void main()
{
    gl_Position =  ftransform();
}
"""

shaderFragString = """
uniform vec4 color;
void main()
{
    gl_FragColor = color;
}
"""

program = None


def compile_shader():
    global program
    program = bgl.glCreateProgram()

    shaderVert = bgl.glCreateShader(bgl.GL_VERTEX_SHADER)
    shaderFrag = bgl.glCreateShader(bgl.GL_FRAGMENT_SHADER)

    bgl.glShaderSource(shaderVert, shaderVertString)
    bgl.glShaderSource(shaderFrag, shaderFragString)

    bgl.glCompileShader(shaderVert)
    bgl.glCompileShader(shaderFrag)

    bgl.glAttachShader(program, shaderVert)
    bgl.glAttachShader(program, shaderFrag)

    bgl.glLinkProgram(program)

    bgl.glDeleteShader(shaderVert)
    bgl.glDeleteShader(shaderFrag)





def draw_vertex_array(key, mode, dimensions, color):
    if key in VAO and VAO[key] and program:
        vao = VAO[key]

        bgl.glUseProgram(program)
        bgl.glUniform4f(bgl.glGetUniformLocation(program, "color"), *color)

        bgl.glEnableClientState(bgl.GL_VERTEX_ARRAY)
        bgl.glVertexPointer(dimensions, bgl.GL_FLOAT, 0, vao)
        bgl.glDrawArrays(mode, 0, int(len(vao) / dimensions))

        bgl.glDisableClientState(bgl.GL_VERTEX_ARRAY)
        bgl.glUseProgram(0)


compile_shader()
