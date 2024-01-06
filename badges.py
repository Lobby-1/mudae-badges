import argparse
import json
import sys
from base64 import b64decode
from dataclasses import asdict, dataclass, field
from time import sleep
from typing import Self, cast

from httpx import Client, Response

REFUND_CHAR = "!"


@dataclass
class Config:
    FILENAME = "config.json"

    token: str = field(repr=False)
    channel_id: int
    presets: dict[str, str] = field(default_factory=dict)
    timeout: float = 1.0

    @classmethod
    def from_file(cls, filename: str = FILENAME) -> Self:
        with open(filename, encoding="u8") as f:
            return cls(**json.load(f))

    def to_file(self, filename: str = FILENAME) -> None:
        with open(filename, "w", encoding="u8") as f:
            json.dump(asdict(self), f, indent=4)


COMMANDS = {
    REFUND_CHAR: "kakerarefund {user_id}",
    "b": "bronze",
    "i": "silver",
    "g": "gold",
    "a": "sapphire",
    "r": "ruby",
    "e": "emerald",
}


def validate_input(string: str) -> bool:
    return string.find(REFUND_CHAR) <= 0 and all(c.isdigit() or c in COMMANDS for c in string)


def process_badges(session: Client, seq: str, timeout: float, user_id: str | int) -> None:
    def send(content: str) -> Response:
        return session.post("/messages", json={"content": content})

    i = 0
    while i < len(seq):
        command = COMMANDS[seq[i]]
        if i < len(seq) - 1 and (amount := seq[i + 1]).isdigit():
            command += f" {amount}"
            i += 1
        print("Refunding badges" if seq[i] == REFUND_CHAR else f"Getting {command}")
        send(f"${command}".format(user_id=user_id))
        sleep(timeout)
        send("confirm" if seq[i] == REFUND_CHAR else "y")
        sleep(timeout)
        i += 1


class Args(argparse.Namespace):
    sequence: str | None
    preset: str | None

    timeout: float | None
    channel: int | None
    skip_refund: bool
    list_presets: bool
    delete: list[str] | None


def parse_args() -> Args:
    epilog = f"""\
valid sequence characters:
{"\n".join(f"  {k}\t{c.partition(' ')[0]}" for k, c in COMMANDS.items())}
1-4\tbadge level

example:
  python %(prog)s -p foo -b2i2g2r4i4
  refund, bronze 2, silver 2, gold 2, ruby 4, silver 4\
"""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Automate Mudae badges",
        add_help=False,
        epilog=epilog,
    )

    required = parser.add_argument_group(
        title="required (any)",
        description="if both options are specified, save the sequence under preset name",
    )
    required.add_argument("sequence", nargs="?", help="badges sequence string")
    required.add_argument("-p", "--preset", help="preset name to execute")

    optional = parser.add_argument_group(title="options")
    optional.add_argument("-t", "--timeout", type=float, help="delay between messages")
    optional.add_argument("-c", "--channel", metavar="ID", type=int, help="discord channel ID")
    optional.add_argument("-s", "--skip-refund", action="store_true", help="skip refund step")
    optional.add_argument("-l", "--list-presets", action="store_true", help="view saved presets")
    optional.add_argument("-d", "--delete", metavar="PRESET", nargs="+", help="delete saved preset")
    optional.add_argument("-h", "--help", action="help", help=argparse.SUPPRESS)

    args = parser.parse_args(None if sys.argv[1:] else ["--help"], namespace=Args())
    if not (args.list_presets or args.delete or args.sequence or args.preset):
        req = ", ".join(action.dest for action in required._group_actions)
        parser.error(f"at least one of the following arguments are required: {req}")
    return args


def list_presets(config: Config) -> None:
    if not config.presets:
        print("No saved presets.")
    else:
        print("Saved presets:")
        offset = len(max(config.presets, key=len))
        print("\n".join(f"{preset:<{offset}} - {seq}" for preset, seq in config.presets.items()))


def delete_presets(config: Config, presets: list[str]) -> bool:
    not_found = list[str]()
    for preset in presets:
        if preset in config.presets:
            del config.presets[preset]
        else:
            not_found.append(preset)

    match not_found:
        case []:
            config.to_file()
            print(f"Deleted preset{'s' if len(presets)>1 else ''} {', '.join(map(repr, presets))}.")
            return True
        case [preset]:
            print(f"Preset {preset!r} does not exist.")
        case _:
            print(f"Presets {', '.join(map(repr, not_found))} do not exist.")
    return False


def save_preset(config: Config, preset: str, seq: str) -> None:
    if existing_seq := config.presets.get(preset):
        prompt = f"Preset '{preset} - {existing_seq}' already exists, overwrite? (Y/n): "
        if input(prompt).strip().lower() not in ("y", ""):
            return
    config.presets[preset] = seq
    config.to_file()
    print(f"Sequence {seq!r} saved as {preset!r}.")


def main() -> bool:
    args = parse_args()
    config = Config.from_file()

    if args.list_presets:
        list_presets(config)
        return True
    if args.delete:
        return delete_presets(config, args.delete)

    if sequence := args.sequence:
        if not validate_input(sequence):
            print("Invalid sequence.")
            return False
        if args.preset:
            save_preset(config, args.preset, sequence)
            return True
    else:
        sequence = config.presets.get(cast(str, args.preset))
        if not sequence:
            print(f"Preset {args.preset!r} does not exist.")
            return False

    if args.skip_refund:
        sequence = sequence.removeprefix(REFUND_CHAR)
    if not sequence:
        print("Empty sequence!")
        return False

    with Client(
        base_url=f"https://discord.com/api/v9/channels/{args.channel or config.channel_id}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, "
            "like Gecko) discord/1.0.9017 Chrome/108.0.5359.215 Electron/22.3.12 Safari/537.36",
            "Authorization": config.token,
        },
    ) as session:
        user_id = b64decode(config.token.partition(".")[0]).decode()
        process_badges(session, sequence, args.timeout or config.timeout, user_id)
    return True


if __name__ == "__main__":
    try:
        sys.exit(not main())
    except KeyboardInterrupt:
        sys.exit(1)
