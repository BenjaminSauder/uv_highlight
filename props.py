import bpy

class UVHighlightProperties(bpy.types.PropertyGroup):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'

    show_in_viewport = bpy.props.BoolProperty(default=True)
    show_preselection = bpy.props.BoolProperty(default=True)
    show_hidden_faces = bpy.props.BoolProperty(default=True)

    offset_factor = bpy.props.FloatProperty(default = -.1)
    offset_units = bpy.props.FloatProperty(default = 1)


