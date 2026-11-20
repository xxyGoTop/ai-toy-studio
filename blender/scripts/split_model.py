import os
import sys

import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def main():
    """V0.5 preview: export each mesh object as a separate STL."""
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_dir = os.path.abspath(args["output_dir"])

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects found"})
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    files = []
    for obj in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(output_dir, f"{obj.name}.stl")
        ensure_parent(path)
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True)
        files.append(path)

    emit({"success": True, "files": files, "count": len(files)})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
