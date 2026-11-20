import os
import sys

import bmesh
import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402

PALETTE = [
    (0.86, 0.28, 0.24),
    (0.95, 0.72, 0.18),
    (0.29, 0.62, 0.95),
    (0.36, 0.74, 0.42),
    (0.62, 0.42, 0.86),
    (0.95, 0.48, 0.22),
    (0.20, 0.72, 0.70),
    (0.92, 0.45, 0.62),
]
MAX_PARTS = 16


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
    elif ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=input_file)
    else:
        raise ValueError(f"Unsupported format: {ext}")


def principled(material):
    if not material or not material.use_nodes or not material.node_tree:
        return None
    for node in material.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def color_of(material):
    node = principled(material)
    if node:
        base = node.inputs.get("Base Color")
        rgb = None
        if base and not base.is_linked:
            value = base.default_value
            rgb = (float(value[0]), float(value[1]), float(value[2]))
        emission = node.inputs.get("Emission Color") or node.inputs.get("Emission")
        strength = node.inputs.get("Emission Strength")
        if emission and not emission.is_linked:
            value = emission.default_value
            emitted = (float(value[0]), float(value[1]), float(value[2]))
            factor = float(strength.default_value) if strength and not strength.is_linked else 1.0
            if factor > 0.2 and sum(emitted) > 0.08 and (rgb is None or sum(rgb) < 0.08):
                return emitted
        if rgb:
            return rgb
    if material:
        value = material.diffuse_color
        return (float(value[0]), float(value[1]), float(value[2]))
    return (0.78, 0.78, 0.76)


def to_hex(rgb):
    channels = [max(0, min(255, int(round(channel * 255)))) for channel in rgb]
    return "#{:02x}{:02x}{:02x}".format(*channels)


def make_material(name, rgb):
    material = bpy.data.materials.new(name[:60] or "零件")
    material.use_nodes = True
    node = principled(material)
    if node:
        node.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    material.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)
    return material


def world_bmesh(obj):
    mesh = obj.data.copy()
    mesh.transform(obj.matrix_world)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.verts.index_update()
    bm.faces.ensure_lookup_table()
    bpy.data.meshes.remove(mesh)
    return bm


def bounds(bm):
    xs = [vert.co.x for vert in bm.verts]
    ys = [vert.co.y for vert in bm.verts]
    zs = [vert.co.z for vert in bm.verts]
    if not xs:
        return None
    return min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)


def is_backdrop(name, box):
    lowered = name.lower()
    if any(token in lowered for token in ("地面", "ground", "floor", "影棚")):
        return True
    if not box:
        return True
    minx, miny, minz, maxx, maxy, maxz = box
    horizontal = max(maxx - minx, maxy - miny)
    height = maxz - minz
    return height < horizontal * 0.04 and horizontal > 8


def face_groups(bm):
    groups = {}
    for face in bm.faces:
        groups.setdefault(face.material_index, []).append(face)
    return groups


def mesh_from_bmesh(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if material:
        mesh.materials.append(material)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def take_faces(source, faces):
    dest = bmesh.new()
    dest_verts = {}
    for face in faces:
        verts = []
        for vert in face.verts:
            copied = dest_verts.get(vert.index)
            if copied is None:
                copied = dest.verts.new(vert.co)
                dest_verts[vert.index] = copied
            verts.append(copied)
        try:
            dest.faces.new(verts)
        except ValueError:
            continue
    return dest


def loose_islands(bm):
    bm.faces.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    seen = set()
    islands = []
    for face in bm.faces:
        if face.index in seen:
            continue
        stack = [face]
        seen.add(face.index)
        group = []
        while stack:
            current = stack.pop()
            group.append(current)
            for edge in current.edges:
                for linked in edge.link_faces:
                    if linked.index not in seen:
                        seen.add(linked.index)
                        stack.append(linked)
        islands.append(group)
    islands.sort(key=len, reverse=True)
    return islands


def place(obj, center_x, center_y):
    verts = obj.data.vertices
    if not verts:
        return
    xs = [vert.co.x for vert in verts]
    ys = [vert.co.y for vert in verts]
    zs = [vert.co.z for vert in verts]
    dx = center_x - (min(xs) + max(xs)) / 2
    dy = center_y - (min(ys) + max(ys)) / 2
    dz = -min(zs)
    for vert in verts:
        vert.co.x += dx
        vert.co.y += dy
        vert.co.z += dz
    obj.data.update()


def layout(objects):
    sizes = []
    for obj in objects:
        xs = [vert.co.x for vert in obj.data.vertices] or [0]
        ys = [vert.co.y for vert in obj.data.vertices] or [0]
        sizes.append((max(max(xs) - min(xs), 0.02), max(max(ys) - min(ys), 0.02)))
    widest = max(width for width, _height in sizes)
    gap = max(widest * 0.06, 0.02)
    row_limit = widest * 1.65
    cursor_x = 0.0
    cursor_y = 0.0
    row_height = 0.0
    for obj, (width, height) in zip(objects, sizes):
        if cursor_x > 0 and cursor_x + width > row_limit:
            cursor_y -= row_height + gap
            cursor_x = 0.0
            row_height = 0.0
        place(obj, cursor_x + width / 2, cursor_y - height / 2)
        cursor_x += width + gap
        row_height = max(row_height, height)


def collect_color_parts():
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    buckets = {}
    for obj in meshes:
        if not obj.data.polygons:
            continue
        bm = world_bmesh(obj)
        box = bounds(bm)
        if is_backdrop(obj.name, box):
            bm.free()
            continue
        for slot, faces in face_groups(bm).items():
            material = obj.data.materials[slot] if slot < len(obj.data.materials) else None
            rgb = color_of(material)
            key = to_hex(rgb)
            bucket = buckets.setdefault(
                key,
                {
                    "rgb": rgb,
                    "material": material,
                    "name": material.name if material else "未命名",
                    "pieces": [],
                },
            )
            bucket["pieces"].append(take_faces(bm, faces))
        bm.free()
    return buckets


def build_material_objects(buckets):
    ranked = sorted(buckets.values(), key=lambda item: sum(len(piece.faces) for piece in item.get("pieces", [])), reverse=True)
    if len(ranked) > MAX_PARTS:
        extras = ranked[MAX_PARTS - 1 :]
        ranked = ranked[: MAX_PARTS - 1]
        merged = extras[0]
        for extra in extras[1:]:
            merged.setdefault("pieces", []).extend(extra.get("pieces", []))
        merged["name"] = "其余颜色"
        ranked.append(merged)

    objects = []
    parts = []
    for index, bucket in enumerate(ranked):
        pieces = bucket.get("pieces") or []
        if not pieces:
            continue
        combined = bmesh.new()
        for piece in pieces:
            piece.verts.index_update()
            vert_map = {}
            for vert in piece.verts:
                vert_map[vert.index] = combined.verts.new(vert.co)
            for face in piece.faces:
                try:
                    combined.faces.new([vert_map[vert.index] for vert in face.verts])
                except ValueError:
                    continue
            piece.free()
        face_count = len(combined.faces)
        if face_count == 0:
            combined.free()
            continue
        material = bucket.get("material") or make_material(bucket["name"], bucket["rgb"])
        name = bucket["name"] or f"颜色{index + 1}"
        obj = mesh_from_bmesh(name, combined, material)
        objects.append(obj)
        parts.append({"name": name, "color": to_hex(bucket["rgb"]), "faces": face_count})
    return objects, parts


def build_loose_objects(single):
    pieces = single.get("pieces") or []
    combined = bmesh.new()
    for piece in pieces:
        piece.verts.index_update()
        vert_map = {}
        for vert in piece.verts:
            vert_map[vert.index] = combined.verts.new(vert.co)
        for face in piece.faces:
            try:
                combined.faces.new([vert_map[vert.index] for vert in face.verts])
            except ValueError:
                continue
        piece.free()
    islands = loose_islands(combined)
    if len(islands) <= 1:
        material = make_material("整体", PALETTE[0])
        obj = mesh_from_bmesh("整体", combined, material)
        return [obj], [{"name": "整体", "color": to_hex(PALETTE[0]), "faces": len(obj.data.polygons)}], "single"

    keep = islands[: MAX_PARTS - 1] if len(islands) > MAX_PARTS else islands
    rest = islands[MAX_PARTS - 1 :] if len(islands) > MAX_PARTS else []
    objects = []
    parts = []
    for index, island in enumerate(keep):
        rgb = PALETTE[index % len(PALETTE)]
        name = f"零件{index + 1}"
        material = make_material(name, rgb)
        piece = take_faces(combined, island)
        obj = mesh_from_bmesh(name, piece, material)
        objects.append(obj)
        parts.append({"name": name, "color": to_hex(rgb), "faces": len(obj.data.polygons)})
    if rest:
        faces = [face for island in rest for face in island]
        material = make_material("其余零件", (0.62, 0.62, 0.62))
        piece = take_faces(combined, faces)
        obj = mesh_from_bmesh("其余零件", piece, material)
        objects.append(obj)
        parts.append({"name": "其余零件", "color": "#9e9e9e", "faces": len(obj.data.polygons)})
    combined.free()
    return objects, parts, "loose"


def remove_sources():
    for obj in list(bpy.context.scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def main():
    args = get_args()
    input_file = os.path.abspath(args["input"])
    output_file = os.path.abspath(args["output"])
    if not os.path.exists(input_file):
        emit({"success": False, "error": f"Input not found: {input_file}"})
        sys.exit(1)

    if os.path.splitext(input_file)[1].lower() != ".blend":
        clear_scene()
    import_file(input_file)

    buckets = collect_color_parts()
    remove_sources()
    used = [bucket for bucket in buckets.values() if bucket.get("pieces")]
    if not used:
        emit({"success": False, "error": "没有可拆分的网格"})
        sys.exit(1)

    if len(used) >= 2:
        objects, parts = build_material_objects(buckets)
        mode = "material"
    else:
        objects, parts, mode = build_loose_objects(used[0])

    if not objects:
        emit({"success": False, "error": "拆分后没有零件"})
        sys.exit(1)

    layout(objects)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    ensure_parent(output_file)
    bpy.ops.export_scene.gltf(filepath=output_file, export_format="GLB", use_selection=True)
    emit({"success": True, "output": output_file, "mode": mode, "count": len(parts), "parts": parts})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
