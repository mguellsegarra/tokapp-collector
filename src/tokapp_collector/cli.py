from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

from .app import build_components
from .config import AppConfig, ConfigError
from .models import TokappMessage
from .runner import Runner


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="tokapp-collector")
    result.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Fitxer de variables d'entorn (per defecte .env)",
    )
    result.add_argument("--verbose", action="store_true")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("once", help="Executa un únic cicle")
    commands.add_parser("run", help="Executa el collector contínuament")
    demo = commands.add_parser("demo", help="Executa una demostració sense xarxa")
    demo.add_argument("--output-dir", type=Path, default=Path("data/demo"))
    doctor = commands.add_parser("doctor", help="Valida configuració i connexions")
    doctor.add_argument("--network", action="store_true", help="Prova login TokApp i bot Telegram")
    classify = commands.add_parser("classify", help="Classifica un text manualment")
    classify.add_argument("text")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if args.command == "demo":
            from .demo import run_demo

            print(json.dumps(run_demo(args.output_dir), ensure_ascii=False, indent=2))
            return 0
        config = AppConfig.from_env(args.env_file)
        components = build_components(config)
        if args.command == "once":
            stats = Runner(
                components["service"], components["publisher"], config.poll_interval_seconds
            ).run_once()
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            return 1 if stats["errors"] else 0
        if args.command == "run":
            Runner(
                components["service"], components["publisher"], config.poll_interval_seconds
            ).run_forever()
            return 0
        if args.command == "doctor":
            rules = config.load_rules()
            result = {
                "configuration": "ok",
                "data_dir": str(config.data_dir),
                "ai_provider": config.ai_provider,
                "model": config.openai_model if config.ai_provider == "openai" else None,
                "ack_received": config.ack_received,
                "child_profiles": sorted((rules.get("child_aliases") or {}).keys()),
            }
            if args.network:
                components["tokapp"].login()
                result["tokapp"] = "login ok"
                result["publisher"] = config.publisher_mode
                if config.publisher_mode == "telegram" and components["telegram"] is not None:
                    bot = components["telegram"].get_me()
                    result["telegram"] = f"bot ok: @{bot.get('username', 'sense_username')}"
                else:
                    result["telegram"] = "skipped (local publisher)"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "classify":
            message = TokappMessage(
                id=0,
                text=args.text,
                sender="Prova manual",
                moment="",
                raw={},
            )
            analysis = components["classifier"].classify(message)
            print(json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2))
            return 0
    except (ConfigError, ValueError) as error:
        print(f"Error de configuració: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        logging.getLogger(__name__).exception("Execució fallida")
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0
