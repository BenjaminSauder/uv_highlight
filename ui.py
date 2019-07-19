import bpy

class IMAGE_PT_uv_highlight(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "View"
    bl_label = "UV Highlight"

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return sima.show_uvedit

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.label(text="Display:")
        col.prop(context.scene.uv_highlight, "show_in_viewport",  text="Show in 3D Viewport")
        col.prop(context.scene.uv_highlight, "show_preselection", text="Show Preselection")
        col.prop(context.scene.uv_highlight, "show_hidden_faces", text="Show non selected faces")
        # col.prop(context.scene.uv_highlight, "show_udim_indices", text="Show UDIM indices")