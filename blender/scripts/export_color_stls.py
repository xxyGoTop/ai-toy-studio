import os
import sys

import bpy

sys.path.append(os.path.dirname(__file__))
import split_by_color as split  # noqa: E402
from common import emit, ensure_parent, get_args  # noqa: E402

BED = 256.0
MAX_COLORS = 4
TARGET = 200.0


def quantize(buckets):
    groups = []
    for key, bucket in buckets.items():
        weight = sum(len(piece.faces) for piece in bucket.get("pieces", []))
        if weight <= 0:
            continue
        groups.append(
            {
                "rgb": bucket["rgb"],
                "hex": key,
                "name": bucket.get("name") or "颜色",
                "weight": weight,
                "pieces": list(bucket.get("pieces") or []),
                "material": bucket.get("material"),
            }
        )
    if not groups:
        return []

    def distance(a, b):
        return sum((a[i] - b[i]) ** 2 for i in range(3))

    while len(groups) > MAX_COLORS:
        pair = None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                gap = distance(groups[i]["rgb"], groups[j]["rgb"])
                if pair is None or gap < pair[0]:
                    pair = (gap, i, j)
        left, right = groups[pair[1]], groups[pair[2]]
        weight = left["weight"] + right["weight"]
        rgb = tuple(
            (left["rgb"][channel] * left["weight"] + right["rgb"][channel] * right["weight"]) / weight
            for channel in range(3)
        )
        merged = {
            "rgb": rgb,
            "hex": split.to_hex(rgb),
            "name": left["name"] if left["weight"] >= right["weight"] else right["name"],
            "weight": weight,
            "pieces": left["pieces"] + right["pieces"],
            "material": left.get("material") or right.get("material"),
        }
        groups = [item for index, item in enumerate(groups) if index not in {pair[1], pair[2]}]
        groups.append(merged)
    groups.sort(key=lambda item: item["weight"], reverse=True)
    return groups


def bounds(objects):
    xs, ys, zs = [], [], []
    for obj in objects:
        for vert in obj.data.vertices:
            xs.append(vert.co.x)
            ys.append(vert.co.y)
            zs.append(vert.co.z)
    if not xs:
        return None
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def fit_on_bed(objects, unit_scale):
    box = bounds(objects)
    if not box:
        return 1.0
    minx, miny, minz, maxx, maxy, maxz = box
    extent = max(maxx - minx, maxy - miny, maxz - minz, 1e-6)
    scaled_extent = extent * unit_scale
    fit = TARGET / scaled_extent if scaled_extent > 220 else 1.0
    scale = unit_scale * fit
    width = (maxx - minx) * scale
    depth = (maxy - miny) * scale
    shift_x = BED / 2 - ((minx + maxx) / 2) * scale
    shift_y = BED / 2 - ((miny + maxy) / 2) * scale
    shift_z = -minz * scale
    for obj in objects:
        for vert in obj.data.vertices:
            vert.co.x = vert.co.x * scale + shift_x
            vert.co.y = vert.co.y * scale + shift_y
            vert.co.z = vert.co.z * scale + shift_z
        obj.data.update()
    return scale


def main():
    args = get_args()
    input_file = os.path.abspath(args["input"])
    output_dir = os.path.abspath(args["output_dir"])
    unit_scale = float(args.get("unit_scale", "1"))
    if not os.path.exists(input_file):
        emit({"success": False, "error": f"Input not found: {input_file}"})
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)
    if os.path.splitext(input_file)[1].lower() != ".blend":
        split.clear_scene()
    split.import_file(input_file)
    buckets = split.collect_color_parts()
    split.remove_sources()
    groups = quantize(buckets)
    if not groups:
        emit({"success": False, "error": "没有可上色的网格"})
        sys.exit(1)

    prepared = {f"{index:02d}": group for index, group in enumerate(groups)}
    objects, parts = split.build_material_objects(prepared)
    if not objects:
        emit({"success": False, "error": "没有可导出的零件"})
        sys.exit(1)
    scale = fit_on_bed(objects, unit_scale)
    bpy.context.view_layer.update()

    written = []
    for index, obj in enumerate(objects):
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(output_dir, f"color_{index + 1}.stl")
        ensure_parent(path)
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, ascii_format=False)
        part = parts[index] if index < len(parts) else {"name": obj.name, "color": "#ffffff", "faces": 0}
        written.append(
            {
                "slot": index + 1,
                "name": part["name"],
                "color": part["color"],
                "faces": part["faces"],
                "file": path,
            }
        )

    emit({"success": True, "scale": scale, "source_colors": len(buckets), "parts": written})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
