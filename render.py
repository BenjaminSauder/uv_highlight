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

    prefs = bpy.context.user_preferences.addons[__package__].preferences

    t1 = time.perf_counter()
    # if not update():
    #    return
    t2 = time.perf_counter()

    obj = bpy.context.active_object
    mode = bpy.context.scene.tool_settings.uv_select_mode
    matrix = obj.matrix_world

    # draw selected
    bgl.glColor4f(*prefs.view3d_selection_color_verts_edges)
    if mode == "VERTEX":
        bgl.glPointSize(6.0)
        bgl.glBegin(bgl.GL_POINTS)

        for co, normal in main.selected_verts:
            bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
        bgl.glEnd()
        bgl.glPointSize(1.0)
    elif mode == "EDGE":
        bgl.glLineWidth(3.0)
        for edge in main.selected_edges:
            bgl.glBegin(bgl.GL_LINE_STRIP)
            for co, normal in edge[0]:
                bgl.glVertex3f(*(matrix * (co + normal * NORMALOFFSET)))
            bgl.glEnd()
    else:
        draw_vertex_array("selected_faces", bgl.GL_TRIANGLES, 3, prefs.view3d_selection_color_faces)

        '''
        bgl.glEnable(bgl.GL_CULL_FACE)
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glLineWidth(3.0)
        bgl.glColor4f(*prefs.view3d_selection_color_faces)
        bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)
        bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
        for f in main.selected_faces:
            bgl.glBegin(bgl.GL_POLYGON)
            for co, normal in f:
                bgl.glVertex3f(*(matrix * (co)))# + normal * NORMALOFFSET)))
            bgl.glEnd()

        '''

    # PRE HIGHLIGHT VERTS
    if settings.show_preselection and main.UV_MOUSE:
        bgl.glEnable(bgl.GL_BLEND)
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA)

        bgl.glColor4f(*prefs.view3d_preselection_color_verts_edges)

        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[0]:
            bgl.glPointSize(7.0)
            bgl.glBegin(bgl.GL_POINTS)
            # bgl.glColor3f(*red)
            co, normal = main.closest_vert[0]
            bgl.glVertex3f(*(matrix * co + normal * NORMALOFFSET))
            bgl.glEnd()

        elif mode == 'EDGE' and main.closest_edge and main.closest_edge[0]:
            bgl.glLineWidth(5.0)

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
            bgl.glPolygonOffset(.1, 1)
            bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
            bgl.glColor4f(*prefs.view3d_preselection_color_faces)
            for p in main.closest_face[0]:
                bgl.glBegin(bgl.GL_POLYGON)
                for co, normal in p:
                    bgl.glVertex3f(*(matrix * (co)))  # + normal * NORMALOFFSET)))
                bgl.glEnd()

    restore_opengl_defaults()

    t3 = time.perf_counter()
    # print( "fps: %.1f total: %.3f - update: %.3f - render: %.3f" % ( 1.0/(t3-t1), t3-t1, t2-t1, t3 - t2 ))


def draw_callback_viewUV(area, UV_TO_VIEW, id):
    # print(id)

    settings = bpy.context.scene.uv_highlight
    prefs = bpy.context.user_preferences.addons[__package__].preferences
    mode = bpy.context.scene.tool_settings.uv_select_mode

    # remove closed areas
    if len(area.regions) == 0 or area.type != "IMAGE_EDITOR":
        bpy.types.SpaceImageEditor.draw_handler_remove(IMAGE_EDITORS[area], 'WINDOW')
        IMAGE_EDITORS.pop(area, None)
        # area.spaces[0].draw_handler_remove(IMAGE_EDITORS[area], 'WINDOW')

        print("removing Image_Editor from drawing: %s" % id)
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
    #bgl.glLoadIdentity()

    origin = UV_TO_VIEW(0,0, False)
    axis = UV_TO_VIEW(1.0, 0, False)[0] - origin[0]

    M = (axis, 0, 0, 0,
         0, axis, 0, 0,
         0, 0, 1.0, 0,
         origin[0], origin[1], 0, 1.0)
    m = bgl.Buffer(bgl.GL_FLOAT, 16, M)
    bgl.glLoadMatrixf(m)

    #bgl.glGetFloatv( bgl.GL_DEPTH_RANGE, )
    if settings.show_hidden_faces:

        bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE)
        draw_vertex_array("hidden_edges", bgl.GL_LINES, 2, prefs.uv_hidden_faces)
        '''
        # draw uvs of non selected faces
        bgl.glLineWidth(0.1)
        bgl.glEnable(bgl.GL_CULL_FACE)
        # bgl.glEnable(bgl.GL_LINE_SMOOTH );
        bgl.glEnable(bgl.GL_BLEND);
        bgl.glBlendFunc(bgl.GL_SRC_ALPHA, bgl.GL_ONE_MINUS_SRC_ALPHA);
        bgl.glBegin(bgl.GL_LINES)

        for uv in main.hidden_edges:
            bgl.glColor4f(*prefs.uv_hidden_faces)
            bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
        bgl.glEnd()

        bgl.glDisable(bgl.GL_CULL_FACE)
        '''
    # PRE HIGHLIGHT VERTS
    if settings.show_preselection and main.UV_MOUSE and UV_TO_VIEW:
        if mode == 'VERTEX' and main.closest_vert and main.closest_vert[1]:

            bgl.glPointSize(5.0)
            bgl.glBegin(bgl.GL_POINTS)
            bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)

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
                bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.closest_edge[1][1], False)))
            # matching edge
            if main.other_edge and main.other_edge[1][0] and main.other_edge[1][1]:
                bgl.glColor4f(*prefs.uv_preselection_color_verts_edges)
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][0], False)))
                bgl.glVertex2i(*(UV_TO_VIEW(*main.other_edge[1][1], False)))
            bgl.glEnd()
        elif main.closest_face and main.closest_face[1]:
            bgl.glDisable(bgl.GL_CULL_FACE)
            bgl.glEnable(bgl.GL_BLEND)
            bgl.glLineWidth(1.5)
            bgl.glBlendFunc(bgl.GL_ONE, bgl.GL_ONE);

            r, g, b, a = prefs.uv_preselection_color_faces
            scale = a
            if mode == "ISLAND":
                scale = 0.5
            bgl.glColor4f(r * scale, g * scale, b * scale, a)

            for p in main.closest_face[1]:
                bgl.glBegin(bgl.GL_POLYGON)
                for uv in p:
                    bgl.glVertex2i(*(UV_TO_VIEW(*uv, False)))
                bgl.glEnd()

    bgl.glViewport(*tuple(viewport_info))
    bgl.glMatrixMode(bgl.GL_MODELVIEW)
    bgl.glPopMatrix()
    bgl.glMatrixMode(bgl.GL_PROJECTION)
    bgl.glPopMatrix()

    restore_opengl_defaults()


def restore_opengl_defaults():
    bgl.glPointSize(1)
    bgl.glLineWidth(1)
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glDisable(bgl.GL_CULL_FACE)
    bgl.glDisable(bgl.GL_LINE_SMOOTH);
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


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


compile_shader()


def draw_vertex_array(key, mode, dimensions, color):
    if key in VAO and VAO[key] and program:
        settings = bpy.context.scene.uv_highlight
        vao = VAO[key]

        bgl.glUseProgram(program)
        bgl.glUniform4f(bgl.glGetUniformLocation(program, "color"), *color)

        bgl.glPolygonOffset(settings.offset_factor, settings.offset_units)
        bgl.glEnable(bgl.GL_POLYGON_OFFSET_FILL)
        bgl.glEnable(bgl.GL_CULL_FACE)

        bgl.glEnableClientState(bgl.GL_VERTEX_ARRAY)
        bgl.glVertexPointer(dimensions, bgl.GL_FLOAT, 0, vao)

        bgl.glDrawArrays(mode, 0, int(len(vao) / dimensions))

        bgl.glDisableClientState(bgl.GL_VERTEX_ARRAY)
        bgl.glUseProgram(0)
