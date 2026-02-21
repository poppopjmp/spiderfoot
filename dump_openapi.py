"""Dump the FastAPI OpenAPI spec with clean operation IDs for TS codegen.

Post-processing:
1. Remove duplicate /api/v1/ routes (frontend uses /api/ legacy paths).
2. Derive short operationId from the Python function name + HTTP method
   (e.g. list_scans_api_v1_scans_get → list_scans).
3. Write the cleaned spec to frontend/openapi.json.
"""
import json
import re
from spiderfoot.api.main import app

spec = app.openapi()

# ── 1. Drop /api/v1/ paths (duplicates of /api/ legacy) ──────────────
paths = spec.get("paths", {})
cleaned_paths: dict = {}
for path, methods in list(paths.items()):
    if "/v1/" in path:
        continue
    cleaned_paths[path] = methods

# ── 2. Clean operationId → short Python function name ────────────────
_SUFFIX_RE = re.compile(
    r"_(?:api|ws)_(?:v\d+_)?"          # _api_ or _api_v1_
    r"[a-z0-9_]*"                       # rest of the URL segments
    r"_(?:get|post|put|patch|delete|head|options|websocket)$",  # HTTP method
    re.IGNORECASE,
)
seen_ids: dict[str, str] = {}

for path, methods in cleaned_paths.items():
    for method, operation in methods.items():
        if not isinstance(operation, dict):
            continue
        old_id = operation.get("operationId", "")
        # Strip the verbose path+method suffix to get the original func name
        clean = _SUFFIX_RE.sub("", old_id)
        if not clean:
            clean = old_id  # fallback: keep original
        # De-duplicate (rare, but e.g. health router has generic names)
        if clean in seen_ids and seen_ids[clean] != path:
            clean = f"{clean}_{method}"
        seen_ids[clean] = path
        operation["operationId"] = clean

spec["paths"] = cleaned_paths

with open("frontend/openapi.json", "w") as f:
    json.dump(spec, f, indent=2)

print(f"✓ Wrote frontend/openapi.json  ({len(cleaned_paths)} paths)")
