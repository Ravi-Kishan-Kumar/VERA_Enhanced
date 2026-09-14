"""Print labeling progress for all run checkpoints in data/labels/.

    .venv\\Scripts\\python.exe training\\scripts\\label_status.py
"""

from __future__ import annotations

import json
from pathlib import Path

LABELS = Path(__file__).resolve().parents[2] / "data" / "labels"


def main() -> None:
    runs = {}
    for path in sorted(LABELS.glob("run_*.json")):
        state = json.loads(path.read_text(encoding="utf-8"))
        runs[path.stem[4:]] = set(state["labels"])
        spec = state["specification"]
        print(
            f"{path.stem[4:]:16s} {spec['model']:22s} labels={len(state['labels']):5d} "
            f"requests={state['requests']:5d} errors={len(state['errors'])}"
        )
    reference = set((LABELS / "reference_ids.txt").read_text().split())
    primary, qwen = runs.get("primary-a", set()), runs.get("qwen-a", set())
    print(
        f"reference covered: primary {len(reference & primary)}/200, "
        f"qwen {len(reference & qwen)}/200 | both models: {len(primary & qwen)} "
        f"| union: {len(primary | qwen)}"
    )


if __name__ == "__main__":
    main()
