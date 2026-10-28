"""Install a local desktop launcher for the GOAT AI review server."""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_ID = "goat-ai-review.desktop"


def main() -> None:
    app_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"
    app_dir.mkdir(parents=True, exist_ok=True)
    launcher = ROOT / "start_review_viewer.sh"
    if not (ROOT / ".venv/bin/python").is_file():
        raise SystemExit("Install the project venv first; see README.md")
    desktop = app_dir / DESKTOP_ID
    # Desktop Exec quoting is deliberately restricted to paths with no embedded
    # double quotes, which covers the normal checkout and avoids shell parsing.
    if '"' in str(ROOT):
        raise SystemExit("A checkout path containing a double quote is unsupported")
    desktop.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=GOAT AI Review Viewer\n"
        "Comment=Open the newest GOAT AI replay review queue\n"
        f'Exec="{launcher}"\n'
        "Icon=applications-games\n"
        "Terminal=false\n"
        "Categories=Game;\n"
        "StartupNotify=false\n",
        encoding="utf-8")
    print(f"Installed {desktop}")

    # Cinnamon stores pinned apps per panel instance rather than in a GSettings
    # key. Update its existing list, preserving the user's order and settings.
    config_dir = Path.home() / ".config/cinnamon/spices/grouped-window-list@cinnamon.org"
    for config in config_dir.glob("*.json"):
        data = json.loads(config.read_text(encoding="utf-8"))
        apps = data.get("pinned-apps", {}).get("value")
        if isinstance(apps, list) and DESKTOP_ID not in apps:
            apps.append(DESKTOP_ID)
            temporary = config.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
            temporary.replace(config)
            print(f"Added to Cinnamon pinned apps: {config}")


if __name__ == "__main__":
    main()
