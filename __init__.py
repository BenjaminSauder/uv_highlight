bl_info = {
    "name": "Highlight UV",
    "category": "3D View",
    "author": "Benjamin Sauder",
    "description": "Show uv selections in the scene view",
    "version": (0, 1),
    "location": "ImageEditor > Tool Shelf",
    "blender": (2, 79, 0),
}

if "bpy" in locals():
    import importlib

    importlib.reload(main)
    importlib.reload(render)
    importlib.reload(operators)
    importlib.reload(props)
    importlib.reload(ui)
else:
    from . import (
        main,
        render,
        operators,
        props,
        ui,
    )

import bpy
from bpy.app.handlers import persistent

# stuff which needs to be registred in blender
classes = [
    props.UVHighlightProperties,
    operators.UpdateOperator,
    ui.IMAGE_PT_UV_HIGHLIGHT,
]

debug = True


def register():
    if debug:
        print("register")

    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.uv_highlight = bpy.props.PointerProperty(type=props.UVHighlightProperties)

    bpy.app.handlers.load_pre.append(pre_load_handler)
    bpy.app.handlers.load_post.append(post_load_handler)
    bpy.app.handlers.scene_update_post.append(main.handle_scene_update)

    render.enable()


@persistent
def pre_load_handler(dummy):
    if debug:
        print("pre load")

    bpy.app.handlers.scene_update_post.remove(main.handle_scene_update)
    render.disable()
    operators.MOUSE_UPDATE = False


@persistent
def post_load_handler(dummy):
    if debug:
        print("post load")

    bpy.app.handlers.scene_update_post.append(main.handle_scene_update)
    render.enable()


def unregister():
    if debug:
        print("unregister")

    bpy.app.handlers.scene_update_post.remove(main.handle_scene_update)
    render.disable()
    operators.MOUSE_UPDATE = False

    del bpy.types.Scene.uv_highlight

    for c in classes:
        bpy.utils.unregister_class(c)
