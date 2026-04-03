import argparse
import os

import httpx


def extract_field1(payload: dict) -> str | None:
    field1 = payload.get("field1")
    if field1 is not None:
        return str(field1)
    feeds = payload.get("feeds")
    if isinstance(feeds, list) and feeds:
        last_feed = feeds[-1]
        if isinstance(last_feed, dict) and last_feed.get("field1") is not None:
            return str(last_feed.get("field1"))
    return None


def build_url(
    base_url: str,
    channel_id: str | None,
    read_api_key: str | None,
    full_url: str | None,
) -> str:
    if full_url:
        return full_url
    if not channel_id:
        raise ValueError("Debes indicar --channel-id o THINGSPEAK_CHANNEL_ID.")
    url = f"{base_url.rstrip('/')}/channels/{channel_id}/fields/1/last.json"
    if read_api_key:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}api_key={read_api_key}"
    return url


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica ThingSpeak leyendo el último valor del feed field1."
    )
    parser.add_argument("--base-url", default=os.getenv("THINGSPEAK_BASE_URL", "https://api.thingspeak.com"))
    parser.add_argument("--channel-id", default=os.getenv("THINGSPEAK_CHANNEL_ID"))
    parser.add_argument("--read-api-key", default=os.getenv("THINGSPEAK_READ_API_KEY"))
    parser.add_argument("--url", default=os.getenv("THINGSPEAK_FIELD1_URL"))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("THINGSPEAK_TIMEOUT", "10")))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    full_url = args.url
    if not full_url and args.read_api_key and args.read_api_key.startswith("http"):
        full_url = args.read_api_key
    try:
        url = build_url(
            base_url=args.base_url,
            channel_id=args.channel_id,
            read_api_key=args.read_api_key if not full_url else None,
            full_url=full_url,
        )
        response = httpx.get(url, timeout=args.timeout)
        response.raise_for_status()
        payload = response.json()
        field1 = extract_field1(payload)
        if field1 is None:
            print("ThingSpeak respondió, pero no se encontró field1 en el último registro.")
            print(payload)
            return 1
        print(f"Último field1: {field1}")
        print(f"Payload: {payload}")
        return 0
    except Exception as exc:
        print(f"Falló la consulta a ThingSpeak: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
