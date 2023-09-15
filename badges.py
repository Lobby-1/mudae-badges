import json
from base64 import b64decode
from sys import argv
from time import sleep
from typing import NamedTuple, Self

from httpx import Client


class Config(NamedTuple):
    token: str
    channel_id: int
    presets: dict[str, str]
    timeout: float = 1.0

    @classmethod
    def from_file(cls, filename: str) -> Self:
        with open(filename, encoding="u8") as f:
            return cls(**json.load(f))


def validate_input(string: str) -> bool:
    return string.find("-") <= 0 and all(c in "-bigare1234" for c in string)


commands = {
    "-": "kakerarefund {user_id}",
    "b": "bronze",
    "i": "silver",
    "g": "gold",
    "a": "sapphire",
    "r": "ruby",
    "e": "emerald",
}


def process_badges(session: Client, string: str, timeout: float, user_id: str | int):
    send = lambda content: session.post("/messages", json={"content": content})
    i = 0
    while i < len(string):
        command = commands[string[i]]
        if i < len(string) - 1 and (amount := string[i + 1]).isdigit():
            command += f" {amount}"
            i += 1
        print("Refunding badges" if string[i] == "-" else f"Getting {command}")
        send(f"${command}".format(user_id=user_id))
        sleep(timeout)
        send("confirm" if string[i] == "-" else "y")
        sleep(timeout)
        i += 1


def main():
    config = Config.from_file("config.json")

    if len(argv) != 2 or not validate_input(string := argv[1]):
        print("Invalid string")
        return

    with Client(
        base_url=f"https://discord.com/api/v9/channels/{config.channel_id}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) discord/1.0.9017 Chrome/108.0.5359.215 Electron/22.3.12 Safari/537.36",
            "Authorization": config.token,
        },
    ) as session:
        user_id = b64decode(config.token.partition(".")[0]).decode()
        process_badges(session, string, config.timeout, user_id)


if __name__ == "__main__":
    main()
