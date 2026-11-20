import os
import sys

import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def import_file(input_file: str):
    ext = os.path.splitext(input_file)[1].lower()
    if ext in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=input_file)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=input_file)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=input_file)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def main():
    args = get_args()
    input_file = os.path.abspath(args["input"])
    output_file = os.path.abspath(args["output"])

    if not os.path.exists(input_file):
        emit({"success": False, "error": f"Input not found: {input_file}"})
        sys.exit(1)

    clear_scene()
    import_file(input_file)

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects after import"})
        sys.exit(1)

    ensure_parent(output_file)
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    emit(
        {
            "success": True,
            "output": output_file,
            "mesh_count": len(meshes),
            "names": [obj.name for obj in meshes],
        }
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
