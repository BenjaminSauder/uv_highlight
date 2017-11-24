# UVHighlight
Addon to improve blenders uv display, and a a few uv-tools as well.

# Limitations
Working on high polycounts is rather slow in python, so some of what this addon does, should really be implemented on the C side of blender, as it's quite a heavy task to calculate the preselction etc. In general it should be fast enough for base meshes. Just be aware that this isnt the fastest thing ever!

I also added a vert count limit - so that it wont stall/crash blender on high poly meshes. 

There are probably quite a few things a more experienced blender programmer would solve differently - especially how I fetch triangulated faces is slow - hit me up if you have some good solutions/ideas :) 

# Installation 
1. download archive (zip) from github
2. rename the directory to "uv_highlight" - this is important
3. in blender preferences/addons "Install Add-on from File"

# Release Notes

1.0:
- initial release





I created some gifs which should show what each toggle and some of the tools do:

# Display Options

## Show selection in viewport: 
![show_selection_in_viewport](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/show_selection_in_viewport.gif)

## Show preselection:
This shows what you will select with your current mouse position, and it also shows you which verts / edges belong toghether on seams.
![show_selection_in_viewport](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/show_selection_in_viewport.gif)

Heres a small demo of how it shows edges:

![show_preselection_edge](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/show_preselection_edge.gif)

## Show non selected faces:
Displays all the non selected faces of the mesh - handy to not mess your layout
![show_non_selected_faces](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/show_non_selected_faces.gif)

## Show UDIM indices:
Eventhough blender does not support UDIMS as far as I know, it's sometimes handy to know how the UDIM tiles are laid out.
![show_udim_tiles](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/show_udim_tiles.gif)

All the colors can be tweaked in the addon preferences!

# Tools 

## Unwrap Selected Faces:
Does what the name says.. so you don't have to select only these faces, and go back and forth between modes etc.

## Pin / Unpin Islands:
Im not even sure if these are of any use - this tool pins every island which has no pins set, or the other way around.
![pin_unpin](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/pin_unpin.gif)

## Convert Mode:
Converts the current selection to/from Sync Mode. I'm really not a fan of this dual mode approach in blender, but to easen the pain I though it would be cool to convert back and forth between the two modes. Please notice that going back to Non-Sync Mode selects the whole mesh.
![convert_mode](https://github.com/BenjaminSauder/uv_highlight/blob/master/doc/convert_mode.gif)


## Auto convert sync uv mode:
Keeps track of mode change and converts automatically. The same as if you would press the button.

## Auto mark boundaries as seam:
Marks UV island borders as seams

## Auto mark boundaries as sharp:
For normalmapped models it's often desired to have hard edges around UV shells. This should do this automatically.
