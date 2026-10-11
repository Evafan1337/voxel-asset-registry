"""Prepare a saved ImageGen request without making a network or API call."""

import argparse
from pathlib import Path

from .sketch import prepare_sketch


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    sketch = commands.add_parser("sketch", help="Prepare a prompt and request for ImageGen via an agent")
    sketch.add_argument("brief", type=Path)
    sketch.add_argument("--out", required=True, type=Path, help="New run directory; existing directories are preserved")
    args = parser.parse_args()
    try:
        result = prepare_sketch(args.brief, args.out)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"impressor: {exc}\n")
    print(f"Prepared: {result / 'imagegen_request.json'}")
    print("Rendering is pending. Ask the agent to run this request with the built-in ImageGen tool.")


if __name__ == "__main__":
    main()
