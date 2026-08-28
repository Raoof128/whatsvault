"""whatsvault CLI entry point. Thin argparse dispatcher over commands.COMMANDS."""

import argparse
import json
import sys

from . import commands

_OPT_FLAGS = ["--device-id", "--job-id", "--candidate-id", "--decision", "--dlq-id", "--path"]
_BOOL_FLAGS = ["--reveal"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="whatsvault")
    sub = p.add_subparsers(dest="verb")
    for verb in sorted(commands.COMMANDS):
        sp = sub.add_parser(verb)
        for flag in _OPT_FLAGS:
            sp.add_argument(flag, default=None)
        for flag in _BOOL_FLAGS:
            sp.add_argument(flag, action="store_true", default=False)
    return p


def run(argv, ctx) -> int:
    args = build_parser().parse_args(argv)
    if not args.verb:
        return 2
    d = {k.replace("-", "_"): v for k, v in vars(args).items()}
    d.update(dict(vars(args).items()))  # keep hyphenless keys too
    result = commands.COMMANDS[args.verb](ctx, {k.replace("-", "_"): v for k, v in vars(args).items()})
    print(json.dumps(result, default=str))
    return 0 if result.get("ok", True) else 1


def main():  # pragma: no cover - production entry: opens real DBs via Keychain
    from ..crypto.keystore import KeyringKeyStore
    from ..db import connection as C
    from ..ops import fsperms, paths

    fsperms.harden_umask()
    p = paths.from_env()
    ks = KeyringKeyStore()
    ctx = commands.Ctx(
        C.open_existing("vault", p.vault_db, ks), C.open_existing("control", p.control_db, ks), ks=ks
    )
    sys.exit(run(sys.argv[1:], ctx))
