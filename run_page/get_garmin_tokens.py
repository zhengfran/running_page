"""Generate a python-garminconnect tokenstore for GitHub Actions."""

import argparse
import getpass
from pathlib import Path


def prompt_mfa():
    return input("Garmin MFA code: ").strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("email", nargs="?", help="Garmin email")
    parser.add_argument("password", nargs="?", help="Garmin password")
    parser.add_argument(
        "--is-cn",
        dest="is_cn",
        action="store_true",
        help="Use Garmin China endpoints",
    )
    parser.add_argument(
        "--tokenstore",
        default=".garminconnect",
        help="Directory or JSON file path for garmin_tokens.json",
    )
    parser.add_argument(
        "--print-secret",
        action="store_true",
        help="Print the token JSON for `gh secret set GARMIN_TOKENS_JSON`",
    )
    options = parser.parse_args()

    email = options.email or input("Garmin email: ").strip()
    password = options.password or getpass.getpass("Garmin password: ")

    from garminconnect import Garmin
    from garminconnect.client import token_file_path

    client = Garmin(email, password, is_cn=options.is_cn, prompt_mfa=prompt_mfa)
    mfa_status, _legacy_token = client.login(tokenstore=options.tokenstore)
    if mfa_status:
        raise RuntimeError("MFA was required but not completed")

    token_file = token_file_path(options.tokenstore)
    token_json = Path(token_file).read_text(encoding="utf-8").strip()
    print(f"Wrote Garmin tokenstore: {token_file}")
    if options.print_secret:
        print(token_json)


if __name__ == "__main__":
    main()
