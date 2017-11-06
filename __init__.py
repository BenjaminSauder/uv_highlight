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
    draw.SimpleMouseOperator,
]

def register():
    draw.enable()
    
    for c in classes:
        bpy.utils.register_class(c)    

    #bpy.app.handlers.load_post.append(load_handler)
    

@persistent
def load_handler(dummy):    
    draw.setup()
    print("uv view init")
    

def unregister():  
    draw.disable()
    for c in classes:
        bpy.utils.unregister_class(c)
            

