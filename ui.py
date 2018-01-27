import bpy

from .prefs import debug

class IMAGE_PT_tools_UV_HIGHLIGHT(bpy.types.Panel):
    bl_label = "UV Highlight Tools"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'TOOLS'
    bl_category = "Tools"
    bl_context = 'mesh_edit'

    @classmethod
    def poll(cls, context):
        sima = context.space_data
        return sima.show_uvedit and not context.tool_settings.use_uv_sculpt

    def draw(self, context):
        layout = self.layout

        '''
        col = layout.column(align=True)
        col.operator("uv.unwrap_selected_faces", text="Unwrap selected faces")

        col = layout.column(align=True)
        col.operator("uv.pin_islands", text="Pin unpinned UV Islands").action = "PIN"
        col.operator("uv.pin_islands", text="Unpin pinned UV Islands").action = "UNPIN"
        col.operator("uv.pin_islands", text="Unpin all UV Islands").action = "UNPIN_ALL"
        '''

        col = layout.column(align=True)
        col.enabled = not context.scene.uv_highlight.auto_convert_uvmode
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            col.operator("uv.selection_to_uv", text="Convert selection to UV Mode")
        else:
            col.operator("uv.uv_to_selection", text="Convert selection to Sync Mode")

        col = layout.column(align=True)
        col.prop(context.scene.uv_highlight, "auto_convert_uvmode", text="Auto convert sync uv mode")
        col.separator()

        col.prop(context.scene.uv_highlight, "boundaries_as_seams", text="Auto mark boundaries as seams")
        col = layout.column(align=True)
        col.prop(context.scene.uv_highlight, "boundaries_as_sharp", text="Auto mark boundaries as sharp")
        col.enabled = context.scene.uv_highlight.boundaries_as_seams



class IMAGE_PT_view_UV_HIGHLIGHT(bpy.types.Panel):
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
        col.label(text="Display:")
        col.prop(context.scene.uv_highlight, "show_in_viewport",  text="Show selection in viewport")
        col.prop(context.scene.uv_highlight, "show_preselection", text="Show Preselection")
        col.prop(context.scene.uv_highlight, "show_hidden_faces", text="Show non selected faces")
        col.prop(context.scene.uv_highlight, "show_udim_indices", text="Show UDIM indices")

        col = layout.column(align=True)
        col.enabled = not context.scene.uv_highlight.auto_convert_uvmode
        if bpy.context.scene.tool_settings.use_uv_select_sync:
            col.operator("uv.selection_to_uv", text="Convert selection to UV Mode")
        else:
            col.operator("uv.uv_to_selection", text="Convert selection to Sync Mode")

        col = layout.column(align=True)
        col.prop(context.scene.uv_highlight, "auto_convert_uvmode", text="Auto convert sync uv mode")
        col.separator()

        col.prop(context.scene.uv_highlight, "boundaries_as_seams", text="Auto mark boundaries as seams")
        col = layout.column(align=True)
        col.prop(context.scene.uv_highlight, "boundaries_as_sharp", text="Auto mark boundaries as sharp")
        col.enabled = context.scene.uv_highlight.boundaries_as_seams

        layout.separator()
        if debug:
            pass
            '''
            layout.separator()
            col = layout.column(align=True)
            col.prop(context.scene.uv_highlight, "offset_factor", text="offset_factor")
            col.prop(context.scene.uv_highlight, "offset_units", text="offset_units")
            '''