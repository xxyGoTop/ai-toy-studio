"""Create a simple demo STL using Blender for local pipeline smoke tests."""
import os
import sys

import bpy

output = os.path.abspath(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else None
if not output:
    raise SystemExit("Usage: blender -b --python make_demo_stl.py -- <output.stl>")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.mesh.primitive_uv_sphere_add(radius=0.04, location=(0, 0, 0.05))
head = bpy.context.active_object
head.name = "Head"

bpy.ops.mesh.primitive_cube_add(size=0.06, location=(0, 0, 0.02))
body = bpy.context.active_object
body.name = "Body"
body.scale = (1.2, 0.8, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

os.makedirs(os.path.dirname(output), exist_ok=True)
bpy.ops.object.select_all(action="SELECT")
bpy.ops.wm.stl_export(filepath=output, export_selected_objects=True)
print({"success": True, "output": output})
