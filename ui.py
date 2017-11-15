import bpy

from .prefs import debug

class IMAGE_PT_UV_HIGHLIGHT(bpy.types.Panel):
    bl_label = "UV Highlight"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_context = 'mesh_edit'

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return sima.show_uvedit and not context.tool_settings.use_uv_sculpt


    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)

        col.prop(context.scene.uv_highlight, "show_in_viewport",  text="Show selection in viewport")
        col.prop(context.scene.uv_highlight, "show_preselection", text="Show Preselection")
        col.prop(context.scene.uv_highlight, "show_hidden_faces", text="Show non selected faces")

        layout.separator()
        col = layout.column(align=True)
        col.operator("wm.uv_to_selection", text="UV to selection")


        layout.separator()
        if debug:
            layout.separator()
            col = layout.column(align=True)
            col.prop(context.scene.uv_highlight, "offset_factor", text="offset_factor")
            col.prop(context.scene.uv_highlight, "offset_units", text="offset_units")