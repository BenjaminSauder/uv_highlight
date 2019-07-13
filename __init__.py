import bpy
from bpy.app.handlers import persistent

from . import (
    main,
    operators,

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
    operators.UV_OT_mouseposition,
    operators.UV_OT_Timer,
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

    main.updater.start()


def unregister():

    main.updater.stop()

    print("unregister")
    for c in classes:
        bpy.utils.unregister_class(c)
