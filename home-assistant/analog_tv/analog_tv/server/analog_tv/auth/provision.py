"""Create a private credentials file on a trusted machine (stdlib only)."""
import argparse
import getpass
import hashlib
import os
import re
import secrets
import warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", help="New file; existing files are never overwritten")
    parser.add_argument("username")
    parser.add_argument("origin", help="Browser origin, e.g. https://tv.example.com")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.@+-]{1,64}", args.username):
        parser.error("Invalid username (use 1–64 ASCII letters, digits or ._@+-)")
    if not re.fullmatch(r"https://(?:[a-z0-9.-]+|\[[0-9a-f:]+\])(?::[0-9]{1,5})?", args.origin) and not re.fullmatch(
        r"http://(?:localhost|127\.0\.0\.1|\[::1\])(?::[0-9]{1,5})?", args.origin
    ):
        parser.error("Use a lowercase HTTPS origin, or HTTP loopback for development")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            password = getpass.getpass("New Admin password: ")
            confirm = getpass.getpass("Confirm password: ")
        except (getpass.GetPassWarning, EOFError):
            parser.error("Run this command in a terminal with hidden password input")
    if not 16 <= len(password) or len(password.encode()) > 1024 or password != confirm:
        parser.error("Passwords must match and contain at least 16 characters (max 1024 bytes)")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**17, r=8, p=1,
                            maxmem=192 * 1024**2, dklen=32)
    secure = str(args.origin.startswith("https://")).lower()
    try:
        with os.fdopen(os.open(args.destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(f"ANALOG_ADMIN_USERNAME={args.username}\n"
                       f"ANALOG_ADMIN_PASSWORD_HASH=scrypt:{salt.hex()}:{digest.hex()}\n"
                       f"ANALOG_SESSION_SECRET={secrets.token_urlsafe(48)}\n"
                       f"ANALOG_PUBLIC_BASE_URL={args.origin}\nANALOG_COOKIE_SECURE={secure}\n")
    except FileExistsError:
        parser.error("Destination already exists; choose a new file")
    print("Private credentials file created.")


if __name__ == "__main__":
    main()
