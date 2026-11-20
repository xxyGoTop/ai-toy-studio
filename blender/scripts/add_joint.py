import json
import os
import sys

import bpy

sys.path.append(os.path.dirname(__file__))
from common import emit, ensure_parent, get_args  # noqa: E402


JOINT_CONFIG = {
    "pin_diameter": 3.0,
    "pin_length": 5.0,
    "clearance": 0.3,
    "wall_thickness": 1.5,
}


def main():
    """V0.5 scaffold: create a simple pin joint helper object."""
    args = get_args()
    blend_file = os.path.abspath(args["blend"])
    output_file = os.path.abspath(args.get("output", blend_file))
    config = dict(JOINT_CONFIG)
    if args.get("config_json"):
        config.update(json.loads(args["config_json"]))

    bpy.ops.wm.open_mainfile(filepath=blend_file)

    diameter_m = float(config["pin_diameter"]) / 1000.0
    length_m = float(config["pin_length"]) / 1000.0

    bpy.ops.mesh.primitive_cylinder_add(
        radius=diameter_m / 2.0,
        depth=length_m,
        location=(0.0, 0.0, length_m / 2.0),
    )
    pin = bpy.context.active_object
    pin.name = "JointPin"

    ensure_parent(output_file)
    bpy.ops.wm.save_as_mainfile(filepath=output_file)
    emit(
        {
            "success": True,
            "output": output_file,
            "joint": pin.name,
            "config": config,
            "note": "Tolerance must be validated with printed test pieces on A1",
        }
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        emit({"success": False, "error": str(exc)})
        sys.exit(1)
