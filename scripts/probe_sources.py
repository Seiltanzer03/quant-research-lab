"""Small real-source connectivity check. Never republishes provider price history."""

import json
import re
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta


def main() -> None:
    failed = False
    for symbol in ["XAU/USD", "USATECH.IDX/USD"]:
        params = {
            "path": "chart/json3",
            "splits": "true",
            "stocks": "true",
            "time_direction": "N",
            "jsonp": "quantlab",
            "offer_side": "B",
            "instrument": symbol,
            "interval": "1MIN",
            "limit": "60",
            "last_update": str(int((datetime.now(UTC) - timedelta(days=1)).timestamp() * 1000)),
        }
        url = "https://freeserv.dukascopy.com/2.0/index.php?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=20) as response:
                text = response.read().decode()
                match = re.fullmatch(r"\s*quantlab\((\[[\s\S]*\])\);?\s*", text)
                if not match:
                    raise ValueError(f"Unexpected response HTTP {response.status}; bytes={len(text)}")
                rows = json.loads(match.group(1))
                if not rows or not all(len(row) >= 6 for row in rows):
                    raise ValueError("Missing OHLC rows")
                print(
                    json.dumps(
                        {
                            "symbol": symbol,
                            "status": "OK",
                            "rows": len(rows),
                            "last_open_utc": datetime.fromtimestamp(rows[-1][0] / 1000, UTC).isoformat(),
                            "cors": response.headers.get("Access-Control-Allow-Origin"),
                        }
                    ),
                    flush=True,
                )
        except Exception as exc:
            failed = True
            print(json.dumps({"symbol": symbol, "status": "UNAVAILABLE", "error": str(exc)}), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
