import bpy

debug = True


class Addon(bpy.types.AddonPreferences):
    bl_idname = __package__

    max_verts : bpy.props.IntProperty("Max Verts", default=50000)

    view3d_selection_verts_edges : bpy.props.FloatVectorProperty(name="view3d_selection_verts_edges",
                                                                 subtype="COLOR",
                                                                 default=(
                                                                     1.0, 0.2, 0.0, 1.0),
                                                                 size=4)

    view3d_selection_faces : bpy.props.FloatVectorProperty(name="view3d_selection_faces",
                                                           subtype="COLOR",
                                                           default=(
                                                               1.0, 0.2, 0.0, 0.35),
                                                           size=4)

    view3d_preselection_verts_edges : bpy.props.FloatVectorProperty(name="view3d_preselection_verts_edges ",
                                                                    subtype="COLOR",
                                                                    default=(
                                                                        1.0, 1.0, 0.0, 1.0),
                                                                    size=4)

    view3d_preselection_faces : bpy.props.FloatVectorProperty(name="view3d_preselection_faces",
                                                              subtype="COLOR",
                                                              default=(
                                                                  1.0, 1.0, 0.0, 0.4),
                                                              size=4)

    uv_matching_edges : bpy.props.FloatVectorProperty(name="uv_matching_edges",
                                                                subtype="COLOR",
                                                                default=(
                                                                    1.0, 0.2, 0.0, 0.2),
                                                                size=4)

    uv_preselection_verts_edges : bpy.props.FloatVectorProperty(name="uv_preselection_verts_edges",
                                                                subtype="COLOR",
                                                                default=(
                                                                    1.0, 1.0, 0.0, 1.0),
                                                                size=4)

    uv_preselection_faces : bpy.props.FloatVectorProperty(name="uv_preselection_faces",
                                                          subtype="COLOR",
                                                          default=(
                                                              1.0, 1.0, 0.0, 0.4),
                                                          size=4)

    # udim_markers = bpy.props.FloatVectorProperty(name="udim_markers",
    #                                              subtype="COLOR",
    #                                              default=(1.0, 1.0, 1.0, 0.25),
    #                                              size=4)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        col = row.column()

        col.prop(self, "max_verts", text="Maximum verts")
        col.separator()
        col.separator()

        #view3d colors
        col.prop(self, "view3d_selection_verts_edges",
                 text="3D View uv verts/edges selection")
        col.prop(self, "view3d_preselection_verts_edges",
                 text="3D View uv verts/edges pre-selection")
        col.prop(self, "view3d_selection_faces",
                 text="3D View uv faces selection")
        col.prop(self, "view3d_preselection_faces",
                 text="3D View uv faces pre-selection")

        #uv colors
        col.prop(self, "uv_matching_edges",
                 text="UV Editor matching edges")
        col.prop(self, "uv_preselection_verts_edges",
                 text="UV Editor verts/edges pre-selection")
        col.prop(self, "uv_preselection_faces",
                 text="UV Editor faces/islands pre-selection")

        # col.prop(self, "udim_markers", text="Image Editor UDIM tiles and label")
