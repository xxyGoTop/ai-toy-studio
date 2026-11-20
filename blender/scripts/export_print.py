import os
import sys

import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def export_stl(output_path: str, selected_only: bool = False):
    ensure_parent(output_path)
    bpy.ops.wm.stl_export(
        filepath=output_path,
        export_selected_objects=selected_only,
        ascii_format=False,
    )
    return output_path


def main():
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_path = os.path.abspath(args["output"])
    per_object = args.get("per_object", "0") in {"1", "true", "True"}

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects found"})
        sys.exit(1)

    exported = []
    if per_object:
        root, ext = os.path.splitext(output_path)
        for obj in meshes:
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            part_path = f"{root}_{obj.name}{ext or '.stl'}"
            export_stl(part_path, selected_only=True)
            exported.append(part_path)
    else:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in meshes:
            obj.select_set(True)
        export_stl(output_path, selected_only=True)
        exported.append(output_path)

    emit({"success": True, "files": exported})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
