import argparse
import json
from pathlib import Path

from .contracts import Profile
from .ingestion import import_csv, quality_report
from .pipeline import build
from .store import Store


def main() -> None:
    parser = argparse.ArgumentParser(description="Quant Research Lab: offline research, not live trading")
    parser.add_argument("command", choices=["build", "import", "quality"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("frontend/public/data/dashboard.json"))
    parser.add_argument("--inputs", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--auto-demo", action="store_true")
    parser.add_argument("--public", action="store_true", help="Only export explicitly publishable data")
    args = parser.parse_args()
    store = Store(args.data_dir)
    if args.command == "build":
        result = build(store, args.output, args.inputs, args.auto_demo, args.public)
        print(
            json.dumps(
                {
                    "status": result["operational_status"],
                    "mode": result["mode"],
                    "datasets": len(result["datasets"]),
                    "output": str(args.output),
                },
                ensure_ascii=False,
            )
        )
    elif args.command == "import":
        if not args.csv or not args.profile:
            parser.error("import requires --csv and --profile")
        profile = Profile.model_validate_json(args.profile.read_text())
        print(json.dumps(import_csv(store, args.csv.read_bytes(), profile), ensure_ascii=False))
    else:
        for p in store.dataset_profiles():
            profile = Profile.model_validate(p)
            print(
                json.dumps(
                    {
                        "dataset_id": profile.dataset_id,
                        **quality_report(store.read_dataset(profile.dataset_id), profile),
                    },
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
