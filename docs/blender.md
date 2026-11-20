# Blender Automation

Executable default:

```text
D:\blander5.3\blender.exe
```

## Scripts

| Script | Purpose |
|--------|---------|
| `import_model.py` | Import STL/OBJ/GLB into `.blend` |
| `normalize_model.py` | Scale to target height, ground to Z=0 |
| `validate_print.py` | Mesh quality report |
| `export_print.py` | Export STL |
| `add_base.py` | Add print base |
| `repair_mesh.py` | Basic merge/recalc normals |
| `split_model.py` | Per-object STL split (V0.5) |
| `add_joint.py` | Pin joint helper (V0.5) |

## Invocation

```powershell
& "D:\blander5.3\blender.exe" -b --python blender\scripts\import_model.py -- `
  --input storage\source\demo.glb `
  --output storage\processed\demo.blend
```

Backend wraps this via `BlenderRunner`.
