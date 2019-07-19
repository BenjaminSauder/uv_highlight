import bpy
from bpy.app.handlers import persistent

from . import (
    main,
    prefs,
    props,
    operators,
    ui,
)


bl_info = {
    "name": "Highlight UV",
    "category": "3D View",
    "author": "Benjamin Sauder",
    "description": "Show uv selections in the scene view",
    "version": (0, 3),
    "location": "ImageEditor > Tool Shelf",
    "blender": (2, 80, 0),
}


# stuff which needs to be registred in blender
classes = [    
    props.UVHighlightSettings,
    operators.UV_OT_Timer,
    prefs.Addon,
    ui.IMAGE_PT_uv_highlight,
]


@persistent
def pre_load_handler(dummy):
    pass


@persistent
def post_load_handler(dummy):
    pass


def register():
    print("register")
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.uv_highlight = bpy.props.PointerProperty(type=props.UVHighlightSettings)

    main.updater.start()


def unregister():

    main.updater.stop()

    print("unregister")
    for c in classes:
        bpy.utils.unregister_class(c)
