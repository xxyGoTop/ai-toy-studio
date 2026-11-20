import os
import sys

import bmesh
import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def repair_object(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def main():
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_file = os.path.abspath(args.get("output", blend_file))

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects found"})
        sys.exit(1)

    for obj in meshes:
        repair_object(obj)

    ensure_parent(output_file)
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    emit({"success": True, "output": output_file, "repaired": [obj.name for obj in meshes]})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
