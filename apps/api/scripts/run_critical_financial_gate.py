import json
import subprocess
import sys
from pathlib import Path


def main():
    api_dir = Path(__file__).parent.parent
    manifest_path = api_dir / "tests" / "critical_financial_paths.json"

    if not manifest_path.exists():
        print(f"ERROR: Manifest not found at {manifest_path}", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    cfp_nodes = set()
    for cfp in manifest.values():
        tests = cfp.get("tests", [])
        for t in tests:
            cfp_nodes.add(t)

    if not cfp_nodes:
        print("ERROR: No tests found in critical financial paths manifest", file=sys.stderr)
        sys.exit(1)

    node_list = sorted(list(cfp_nodes))

    print(f"Critical Financial Path Gate: Executing {len(node_list)} unique test nodes")
    for node in node_list:
        print(f"  - {node}")

    # Build pytest command
    cmd = ["uv", "run", "pytest", *node_list]

    # Run from apps/api directory to ensure pytest works correctly
    result = subprocess.run(cmd, cwd=api_dir)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
