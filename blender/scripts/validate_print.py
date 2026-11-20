import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


def inspect_mesh(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
    boundary = sum(1 for edge in bm.edges if edge.is_boundary)
    loose_verts = sum(1 for vertex in bm.verts if not vertex.link_edges)
    volume = None
    if bm.faces and all(edge.is_manifold for edge in bm.edges):
        try:
            volume = abs(bm.calc_volume(signed=True))
        except Exception:  # noqa: BLE001
            volume = None

    bm.free()
    return {
        "name": obj.name,
        "vertices": len(obj.data.vertices),
        "faces": len(obj.data.polygons),
        "non_manifold_edges": non_manifold,
        "boundary_edges": boundary,
        "loose_vertices": loose_verts,
        "volume_m3": volume,
        "watertight": non_manifold == 0 and boundary == 0,
    }


def world_bounds(meshes):
    corners = [
        obj.matrix_world @ Vector(corner)
        for obj in meshes
        for corner in obj.bound_box
    ]
    xs = [p.x for p in corners]
    ys = [p.y for p in corners]
    zs = [p.z for p in corners]
    return {
        "x": (max(xs) - min(xs)) * 1000.0,
        "y": (max(ys) - min(ys)) * 1000.0,
        "z": (max(zs) - min(zs)) * 1000.0,
    }


def main():
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    report_path = args.get("report")
    max_bed_mm = float(args.get("max_bed_mm", 240))

    bpy.ops.wm.open_mainfile(filepath=blend_file)
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        emit({"success": False, "error": "No mesh objects found"})
        sys.exit(1)

    mesh_reports = [inspect_mesh(obj) for obj in meshes]
    dimensions = world_bounds(meshes)

    checks = []
    status = "INFO"

    for item in mesh_reports:
        if item["non_manifold_edges"] > 0:
            checks.append(
                {
                    "level": "ERROR",
                    "code": "NON_MANIFOLD",
                    "message": f"{item['name']} has {item['non_manifold_edges']} non-manifold edges",
                }
            )
            status = "ERROR"
        if item["boundary_edges"] > 0:
            checks.append(
                {
                    "level": "WARNING",
                    "code": "OPEN_BOUNDARY",
                    "message": f"{item['name']} has {item['boundary_edges']} boundary edges",
                }
            )
            if status != "ERROR":
                status = "WARNING"
        if item["loose_vertices"] > 0:
            checks.append(
                {
                    "level": "WARNING",
                    "code": "LOOSE_VERTICES",
                    "message": f"{item['name']} has {item['loose_vertices']} loose vertices",
                }
            )
            if status != "ERROR":
                status = "WARNING"

    for axis, value in dimensions.items():
        if value > max_bed_mm:
            checks.append(
                {
                    "level": "ERROR",
                    "code": "OVERSIZE",
                    "message": f"Dimension {axis.upper()}={value:.1f}mm exceeds bed limit {max_bed_mm}mm",
                }
            )
            status = "ERROR"

    if dimensions["z"] < 1.0:
        checks.append(
            {
                "level": "WARNING",
                "code": "TOO_FLAT",
                "message": "Model height is under 1mm; verify units",
            }
        )
        if status != "ERROR":
            status = "WARNING"

    checks.append(
        {
            "level": "INFO",
            "code": "MESH_STATS",
            "message": f"{len(meshes)} mesh object(s), dims={dimensions}",
        }
    )

    report = {
        "success": True,
        "status": status,
        "dimensions_mm": dimensions,
        "meshes": mesh_reports,
        "checks": checks,
        "recommendations": [
            item["message"] for item in checks if item["level"] in {"ERROR", "WARNING"}
        ],
    }

    if report_path:
        ensure_parent(report_path)
        with open(report_path, "w", encoding="utf-8") as handle:
            import json

            json.dump(report, handle, ensure_ascii=False, indent=2)
        report["report_path"] = report_path

    emit(report)
    if status == "ERROR":
        # Validation completed; ERROR is a model quality signal, not a script crash.
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
