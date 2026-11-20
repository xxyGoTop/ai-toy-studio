import os
import sys

import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def get_mesh_objects():
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def world_corners(meshes):
    return [
        obj.matrix_world @ Vector(corner)
        for obj in meshes
        for corner in obj.bound_box
    ]


def normalize_model(target_height_mm=100.0):
    meshes = get_mesh_objects()
    if not meshes:
        raise ValueError("No mesh objects found")

    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0
    bpy.context.view_layer.update()

    corners = world_corners(meshes)
    min_z = min(p.z for p in corners)
    max_z = max(p.z for p in corners)
    height_m = max_z - min_z
    if height_m <= 0:
        raise ValueError("Invalid model dimensions")

    scale = (float(target_height_mm) / 1000.0) / height_m
    for obj in meshes:
        obj.location *= scale
        obj.scale = [v * scale for v in obj.scale]

    bpy.context.view_layer.update()
    corners = world_corners(meshes)
    lowest_z = min(p.z for p in corners)
    for obj in meshes:
        obj.location.z -= lowest_z

    bpy.context.view_layer.update()
    corners = world_corners(meshes)
    xs = [p.x for p in corners]
    ys = [p.y for p in corners]
    zs = [p.z for p in corners]
    return {
        "width_mm": (max(xs) - min(xs)) * 1000.0,
        "depth_mm": (max(ys) - min(ys)) * 1000.0,
        "height_mm": (max(zs) - min(zs)) * 1000.0,
        "scale": scale,
    }


def maybe_add_base(thickness_mm: float):
    meshes = get_mesh_objects()
    corners = world_corners(meshes)
    min_x = min(p.x for p in corners)
    max_x = max(p.x for p in corners)
    min_y = min(p.y for p in corners)
    max_y = max(p.y for p in corners)

    width = max(max_x - min_x, 0.01)
    depth = max(max_y - min_y, 0.01)
    thickness = float(thickness_mm) / 1000.0

    bpy.ops.mesh.primitive_cube_add(size=1)
    base = bpy.context.active_object
    base.name = "PrintBase"
    base.scale = (width * 1.05, depth * 1.05, thickness)
    base.location = (
        (min_x + max_x) / 2.0,
        (min_y + max_y) / 2.0,
        thickness / 2.0,
    )
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def main():
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_file = os.path.abspath(args.get("output", blend_file))
    target_height_mm = float(args.get("target_height_mm", 100))
    add_base = args.get("add_base", "0") in {"1", "true", "True"}
    base_thickness_mm = float(args.get("base_thickness_mm", 2.0))

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    dims = normalize_model(target_height_mm)
    if add_base:
        maybe_add_base(base_thickness_mm)
        dims = normalize_model(target_height_mm)

    ensure_parent(output_file)
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    emit({"success": True, "output": output_file, "dimensions_mm": dims})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
