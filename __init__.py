bl_info = {
    "name": "Highlight UV",
    "category": "3D View",
    "author": "Benjamin Sauder",
    "description": "Show uv selections in the scene view",
    "version": (0, 1),
    "location": "View3D > Tool Shelf",
    "blender": (2, 79, 0),
}


if "bpy" in locals():
    import importlib
    importlib.reload(draw)

else:
    from . import (
        draw,       
        )
  
import bpy
from bpy.app.handlers import persistent

classes = [
    draw.UpdateOperator,
]

def register():
    draw.enable()
    
    for c in classes:
        bpy.utils.register_class(c)    

    bpy.app.handlers.load_pre.append(pre_load_handler)
    bpy.app.handlers.load_post.append(post_load_handler)
    
@persistent
def pre_load_handler(dummy):
    print("pre load")
    draw.disable()
    draw.MOUSE_UPDATE = False

@persistent
def post_load_handler(dummy):
    print("post load")
    draw.enable()

    

def unregister():  
    draw.disable()
    for c in classes:
        bpy.utils.unregister_class(c)
            

