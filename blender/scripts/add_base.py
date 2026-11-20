import os
import sys

import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def main():
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_file = os.path.abspath(args.get("output", blend_file))
    thickness_mm = float(args.get("thickness_mm", 2.0))
    margin = float(args.get("margin", 1.05))

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects found"})
        sys.exit(1)

    corners = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    min_x = min(p.x for p in corners)
    max_x = max(p.x for p in corners)
    min_y = min(p.y for p in corners)
    max_y = max(p.y for p in corners)
    thickness = thickness_mm / 1000.0

    bpy.ops.mesh.primitive_cube_add(size=1)
    base = bpy.context.active_object
    base.name = "PrintBase"
    base.scale = ((max_x - min_x) * margin, (max_y - min_y) * margin, thickness)
    base.location = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0, thickness / 2.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    ensure_parent(output_file)
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    emit({"success": True, "output": output_file, "base": base.name})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
