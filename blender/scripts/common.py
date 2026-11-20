import json
import os
import sys


def get_args():
    args = sys.argv
    if "--" not in args:
        return {}
    args = args[args.index("--") + 1 :]
    result = {}
    i = 0
    while i < len(args):
        key = args[i].lstrip("-")
        if i + 1 < len(args) and not args[i + 1].startswith("--"):
            result[key] = args[i + 1]
            i += 2
        else:
            result[key] = "1"
            i += 1
    return result


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False))


def ensure_parent(path: str):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
