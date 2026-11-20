from __future__ import annotations

import json
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from app.config import Settings
from app.services.blender import BlenderRunner

PROFILE = Path(r"D:\BambuStudio\resources\profiles\BBL")
MACHINE = PROFILE / "machine" / "Bambu Lab A1 0.4 nozzle.json"
PROCESS = PROFILE / "process" / "0.20mm Standard @BBL A1.json"
FILAMENT = PROFILE / "filament" / "Bambu PLA Basic @BBL A1.json"
SKIP_EXPAND = {"filament_map", "filament_map_2", "filament_nozzle_map"}
ALSO_PER_FILAMENT = {
    "fan_cooling_layer_time",
    "fan_max_speed",
    "fan_min_speed",
    "hot_plate_temp",
    "hot_plate_temp_initial_layer",
    "pre_start_fan_time",
    "slow_down_layer_time",
    "textured_plate_temp",
    "textured_plate_temp_initial_layer",
}
IDENTITY = "1 0 0 0 1 0 0 0 1 0 0 0"
OBJECT_TRANSFORM = re.compile(
    r'(<object\b[^>]*\bid=")(\d+)("[\s\S]*?<component\b[^>]*\btransform=")([^"]+)(")'
)
ITEM_TRANSFORM = re.compile(r'(<item\b[^>]*?\bobjectid=")(\d+)("[^>]*?\btransform=")([^"]+)(")')


def _fit(values: list, count: int) -> list:
    if count <= 0:
        return values
    if not values:
        return [""] * count
    if len(values) == count:
        return values
    if len(values) > count:
        return values[:count]
    return [*values, *([values[-1]] * (count - len(values)))]


def _pad(values: list, count: int, filler: str = "") -> list:
    current = list(values or [])
    if len(current) > count:
        return current[:count]
    return [*current, *([filler] * (count - len(current)))]


def patch_project(payload: dict, colors: list[str]) -> dict:
    count = len(colors)
    for key, value in list(payload.items()):
        if not isinstance(value, list):
            continue
        per_filament = (key.startswith("filament_") and key not in SKIP_EXPAND) or key in ALSO_PER_FILAMENT
        if per_filament:
            payload[key] = _fit(value, count)

    payload["filament_colour"] = [color.upper() for color in colors]
    payload["filament_settings_id"] = _fit(payload.get("filament_settings_id") or ["Bambu PLA Basic @BBL A1"], count)
    payload["filament_self_index"] = [str(index + 1) for index in range(count)]
    payload["filament_ids"] = _fit(payload.get("filament_ids") or [""], count)
    payload["inherits_group"] = _pad(payload.get("inherits_group") or [], count + 2)
    payload["different_settings_to_system"] = _pad(payload.get("different_settings_to_system") or [], count + 2)
    payload["flush_volumes_matrix"] = [
        "0" if row == column else "280" for row in range(count) for column in range(count)
    ]
    payload["flush_volumes_vector"] = ["140"] * (count * 2)
    return payload


def _translation(transform: str) -> str:
    numbers = transform.split()
    if len(numbers) < 12:
        return IDENTITY
    return f"1 0 0 0 1 0 0 0 1 {numbers[9]} {numbers[10]} {numbers[11]}"


def reseat_model(model_xml: str) -> tuple[str, list[str]]:
    """Move each part's position onto the plate item Bambu Studio actually displays."""
    placed: dict[str, str] = {}

    def move_component(match: re.Match[str]) -> str:
        placed[match.group(2)] = _translation(match.group(4))
        return f"{match.group(1)}{match.group(2)}{match.group(3)}{IDENTITY}{match.group(5)}"

    updated = OBJECT_TRANSFORM.sub(move_component, model_xml)
    object_ids: list[str] = []

    def move_item(match: re.Match[str]) -> str:
        object_id = match.group(2)
        object_ids.append(object_id)
        transform = placed.get(object_id, IDENTITY)
        return f"{match.group(1)}{object_id}{match.group(3)}{transform}{match.group(5)}"

    return ITEM_TRANSFORM.sub(move_item, updated), object_ids


def _rename_objects(model_settings: bytes, parts: list[dict], object_ids: list[str]) -> bytes:
    by_file = {f"color_{part['slot']}.stl": part for part in parts}
    root = ElementTree.fromstring(model_settings)
    for obj in root.findall("object"):
        part_node = obj.find("part")
        source_name = ""
        if part_node is not None:
            for meta in part_node.findall("metadata"):
                if meta.get("key") == "source_file":
                    source_name = Path(meta.get("value") or "").name
        part = by_file.get(source_name)
        if part is None:
            continue
        for meta in obj.findall("metadata"):
            if meta.get("key") == "name":
                meta.set("value", str(part["name"]))
            elif meta.get("key") == "extruder":
                meta.set("value", str(part["slot"]))
        if part_node is None:
            continue
        for meta in part_node.findall("metadata"):
            if meta.get("key") == "name":
                meta.set("value", str(part["name"]))
    plate = root.find("plate")
    if plate is not None:
        for existing in list(plate.findall("model_instance")):
            plate.remove(existing)
        for index, object_id in enumerate(object_ids, start=1):
            instance = ElementTree.SubElement(plate, "model_instance")
            for key, value in (
                ("object_id", object_id),
                ("instance_id", "0"),
                ("identify_id", str(index)),
            ):
                meta = ElementTree.SubElement(instance, "metadata")
                meta.set("key", key)
                meta.set("value", value)
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def patch_3mf(path: Path, parts: list[dict]) -> None:
    colors = [str(part["color"]) for part in parts]
    temporary = path.with_suffix(".patching.3mf")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(temporary, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "Metadata/project_settings.config":
                payload = json.loads(data.decode("utf-8"))
                payload = patch_project(payload, colors)
                data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            target.writestr(info, data)
    temporary.replace(path)


def build_colored_3mf(settings: Settings, source: Path, dest_3mf: Path, unit_scale: float) -> dict:
    slicer = Path(settings.bambu_studio_executable)
    if not slicer.exists():
        raise FileNotFoundError("还没有配置 Bambu Studio")
    for preset in (MACHINE, PROCESS, FILAMENT):
        if not preset.exists():
            raise FileNotFoundError(f"找不到 Bambu 预设：{preset.name}")

    work = settings.storage_root / "tmp" / f"color-{dest_3mf.stem}"
    if work.exists():
        for child in work.glob("*"):
            if child.is_file():
                child.unlink()
    work.mkdir(parents=True, exist_ok=True)

    result = BlenderRunner(settings).run_script(
        "export_color_stls.py",
        {"input": str(source), "output_dir": str(work), "unit_scale": unit_scale},
    )
    if not result.success or not isinstance(result.data, dict):
        detail = "分色导出失败"
        if isinstance(result.data, dict) and result.data.get("error"):
            detail = str(result.data["error"])
        elif result.stderr:
            detail = result.stderr[-500:]
        raise RuntimeError(detail)

    parts = result.data.get("parts") or []
    files = [Path(part["file"]) for part in parts if part.get("file")]
    if not files or any(not path.exists() for path in files):
        raise RuntimeError("没有写出分色 STL")

    dest_3mf.parent.mkdir(parents=True, exist_ok=True)
    if dest_3mf.exists():
        dest_3mf.unlink()
    filament_arg = ";".join([str(FILAMENT)] * len(files))
    command = [
        str(slicer),
        "--load-settings",
        f"{MACHINE};{PROCESS}",
        "--load-filaments",
        filament_arg,
        "--load-filament-ids",
        ",".join(str(index + 1) for index in range(len(files))),
        "--export-3mf",
        dest_3mf.name,
        "--outputdir",
        str(dest_3mf.parent),
        "--arrange",
        "0",
        *[str(path) for path in files],
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if completed.returncode != 0 or not dest_3mf.exists():
        message = (completed.stderr or completed.stdout or "Bambu Studio 没有生成 3MF")[-500:]
        raise RuntimeError(message)

    patch_3mf(dest_3mf, parts)
    return {
        "parts": [
            {"slot": part["slot"], "name": part["name"], "color": str(part["color"]).upper(), "faces": part["faces"]}
            for part in parts
        ],
        "source_colors": int(result.data.get("source_colors") or len(parts)),
        "scale": result.data.get("scale"),
    }


def open_studio(settings: Settings, project_file: Path) -> None:
    # Bambu Studio 改变自己的工作目录后无法解析相对路径，必须传绝对路径，
    # 否则会报“加载模型文件失败”并打开空盘。
    absolute = Path(project_file).resolve()
    subprocess.Popen([settings.bambu_studio_executable, str(absolute)], shell=False)
