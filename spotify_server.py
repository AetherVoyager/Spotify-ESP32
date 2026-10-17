"""Spotify Web API -> /now-playing JSON for the ESP32 OLED.

Drop-in replacement for bot.py: same endpoints and response format,
but reads playback straight from Spotify instead of Discord presence.

One-time setup (Authorization Code + PKCE, no client secret needed):
    python spotify_server.py auth-url              # open the printed URL, approve
    python spotify_server.py auth-code "<url>"     # paste the URL you were redirected to
Then run:
    python spotify_server.py
"""

import asyncio
import base64
import hashlib
import json
import re
import secrets
import sys
import time
import urllib.parse
from pathlib import Path

import aiohttp
from aiohttp import web
from anyascii import anyascii
from indic_transliteration import sanscript

# ════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════

CLIENT_ID = ""  # from https://developer.spotify.com/dashboard
REDIRECT_URI = "http://127.0.0.1:8888/callback"  # must match the app settings exactly

PORT = 3000
LYRIC_LEAD = 2.4
POLL_INTERVAL = 3  # seconds between Spotify API polls
TRANSLITERATE = True  # OLED fonts are ASCII-only: romanize other scripts

BASE = Path(__file__).resolve().parent
TOKEN_FILE = BASE / "spotify_token.json"
VERIFIER_FILE = BASE / ".pkce_verifier"

SCOPES = "user-read-currently-playing user-read-playback-state"
TOKEN_URL = "https://accounts.spotify.com/api/token"

# ════════════════════════════════════════════════════════
# STATE
# ════════════════════════════════════════════════════════

current = {}

lyrics = {
    "key": "",
    "lines": [],
    "duration": 0,
}

token = {}

# ════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════

def save_token(data):
    # PKCE refresh tokens rotate, so keep the newest one
    if "refresh_token" not in data and "refresh_token" in token:
        data["refresh_token"] = token["refresh_token"]
    data["expires_at"] = time.time() + data.get("expires_in", 3600) - 60
    token.clear()
    token.update(data)
    TOKEN_FILE.write_text(json.dumps(token, indent=2))
    TOKEN_FILE.chmod(0o600)


def auth_url():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    VERIFIER_FILE.write_text(verifier)

    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    print("Open this URL, approve, then copy the full URL you land on")
    print("(the page itself will fail to load - that's expected):\n")
    print("https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params))


async def auth_code(redirected):
    query = urllib.parse.urlparse(redirected).query
    code = urllib.parse.parse_qs(query).get("code", [redirected.strip()])[0]

    async with aiohttp.ClientSession() as http:
        async with http.post(TOKEN_URL, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": VERIFIER_FILE.read_text(),
        }) as res:
            data = await res.json()

    if "access_token" not in data:
        sys.exit(f"[auth] failed: {data}")

    save_token(data)
    VERIFIER_FILE.unlink(missing_ok=True)
    print(f"[auth] saved {TOKEN_FILE}")


async def access_token(http):
    if time.time() < token.get("expires_at", 0):
        return token["access_token"]

    async with http.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": CLIENT_ID,
    }) as res:
        data = await res.json()

    if "access_token" not in data:
        raise RuntimeError(f"token refresh failed: {data}")

    save_token(data)
    print("[auth] token refreshed")
    return token["access_token"]

# ════════════════════════════════════════════════════════
# TRANSLITERATION
# ════════════════════════════════════════════════════════

# Indic Unicode blocks -> (sanscript scheme, drops final schwa like Hindi)
INDIC = [
    (0x0900, 0x097F, sanscript.DEVANAGARI, True),
    (0x0980, 0x09FF, sanscript.BENGALI, True),
    (0x0A00, 0x0A7F, sanscript.GURMUKHI, True),
    (0x0A80, 0x0AFF, sanscript.GUJARATI, True),
    (0x0B00, 0x0B7F, sanscript.ORIYA, False),
    (0x0C00, 0x0C7F, sanscript.TELUGU, False),
    (0x0C80, 0x0CFF, sanscript.KANNADA, False),
    (0x0D00, 0x0D7F, sanscript.MALAYALAM, False),
]


def indic_block(ch):
    cp = ord(ch)
    for lo, hi, scheme, schwa in INDIC:
        if lo <= cp <= hi:
            return lo, scheme, schwa
    return None


def romanize_word(word, lo, scheme, schwa):
    # ITRANS lowercased reads like everyday romanized typing ("punchiri", "pennazhake")
    out = sanscript.transliterate(word, scheme, sanscript.ITRANS)
    # ñ: "punchiri", "manju", "niranju" rather than "puñciri", "mañu", "niraññu"
    out = out.replace("~n~n", "nj").replace("~nch", "nch").replace("~nj", "nj").replace("~n", "nj")
    out = re.sub(r"[~^.{}]", "", out).lower()
    # "तुम" -> "tum", not "tuma": drop the inherent a after a final bare consonant
    last = ord(word[-1]) - lo
    if schwa and 0x15 <= last <= 0x39 and out.endswith("a") and len(out) > 1:
        out = out[:-1]
    return out


def to_ascii(text):
    if not TRANSLITERATE or text.isascii():
        return text

    # sanscript's Tamil scheme adds aspirates Tamil doesn't have ("gh", "dh").
    # Indic blocks share one layout, so read Tamil as Malayalam instead;
    # ன (Tamil-only alveolar n) becomes ന.
    text = "".join(
        "ന" if c == "ன" else chr(ord(c) + 0x180) if "஀" <= c <= "௿" else c
        for c in text
    )

    out = []
    for word in re.split(r"(\s+)", text):
        block = next((indic_block(c) for c in word if indic_block(c)), None)
        if block:
            # transliterate each run of that script, keep any Latin/punctuation as-is
            lo = block[0]
            parts = re.split(f"([{chr(lo)}-{chr(lo + 0x7F)}]+)", word)
            word = "".join(
                romanize_word(p, *block) if p and indic_block(p[0]) else p
                for p in parts
            )
        out.append(anyascii(word))
    return "".join(out)

# ════════════════════════════════════════════════════════
# FETCH LYRICS
# ════════════════════════════════════════════════════════

def parse_lyrics(data):
    synced = data.get("syncedLyrics", "") or ""
    plain = data.get("plainLyrics", "") or ""
    lines = []

    # synced lyrics
    if synced:
        for line in synced.split("\n"):
            m = re.match(r'\[(\d+):(\d+\.\d+)\](.*)', line)
            if m:
                secs = int(m.group(1)) * 60 + float(m.group(2))
                text = m.group(3).strip()
                if text:
                    lines.append({"time": secs, "text": text})

    # plain lyrics fallback
    elif plain:
        lines = [
            {"time": 0, "text": l.strip()}
            for l in plain.split("\n")
            if l.strip()
        ]

    return lines


async def fetch_lyrics(http, artist, title, album, duration_s):
    params = {
        "artist_name": artist,
        "track_name": title,
        "album_name": album,
        "duration": round(duration_s),
    }

    for attempt in range(3):
        try:
            async with http.get(
                "https://lrclib.net/api/get",
                params=params,
                headers={"User-Agent": "ESP32-Spotify/1.0"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as res:
                if res.status == 404:
                    print("[lrclib] no lyrics found")
                    return [], 0
                data = await res.json()

            lines = parse_lyrics(data)
            print(f"[lrclib] success ({len(lines)} lines)")
            return lines, data.get("duration", 0)

        except Exception as e:
            print(f"[lrclib] retry {attempt+1}/3 error: {e}")
            await asyncio.sleep(1)

    print("[lrclib] failed after 3 retries")
    return [], 0

# ════════════════════════════════════════════════════════
# GET CURRENT LYRIC
# ════════════════════════════════════════════════════════

def get_lyric(progress_secs):
    lines = lyrics["lines"]
    duration = lyrics["duration"]

    if not lines:
        return {"prev": "", "curr": "", "next": ""}

    # plain lyrics mode
    if lines[0]["time"] == 0:
        total = duration or 200
        i = min(int((progress_secs / total) * len(lines)), len(lines) - 1)
        return {
            "prev": lines[i - 1]["text"] if i > 0 else "",
            "curr": lines[i]["text"],
            "next": lines[i + 1]["text"] if i + 1 < len(lines) else "",
        }

    # synced lyrics mode
    idx = 0
    for i, line in enumerate(lines):
        if line["time"] <= progress_secs:
            idx = i
        else:
            break

    return {
        "prev": lines[idx - 1]["text"] if idx > 0 else "",
        "curr": lines[idx]["text"],
        "next": lines[idx + 1]["text"] if idx + 1 < len(lines) else "",
    }

# ════════════════════════════════════════════════════════
# SPOTIFY POLLING
# ════════════════════════════════════════════════════════

async def poll_once(http):
    headers = {"Authorization": f"Bearer {await access_token(http)}"}

    async with http.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=10),
    ) as res:
        if res.status == 204:  # nothing playing
            current["playing"] = False
            return
        if res.status == 429:
            wait = int(res.headers.get("Retry-After", 5))
            print(f"[spotify] rate limited, waiting {wait}s")
            await asyncio.sleep(wait)
            return
        if res.status == 401:
            token["expires_at"] = 0  # force refresh next poll
            return
        res.raise_for_status()
        data = await res.json()

    item = data.get("item")
    if not data.get("is_playing") or not item or item.get("type") != "track":
        current["playing"] = False
        return

    artists = [a["name"] for a in item["artists"]]
    artist = ", ".join(artists)
    title = item["name"]
    duration_ms = item["duration_ms"]
    key = item["id"] or f"{artist}|{title}"

    # fetch lyrics when new track detected
    if lyrics["key"] != key:
        print(f"[spotify] now playing: {artist} - {title}")
        lines, duration = await fetch_lyrics(
            http, artists[0], title, item["album"]["name"], duration_ms / 1000
        )
        lyrics.update({"key": key, "lines": lines, "duration": duration})

    current.update({
        "playing": True,
        "title": title,
        "artist": artist,
        "album": item["album"]["name"],
        # local clock anchor so position keeps ticking between polls
        "start_epoch": time.time() - data["progress_ms"] / 1000,
        "duration_ms": duration_ms,
        "track_id": item["id"],
    })


async def poll_loop():
    async with aiohttp.ClientSession() as http:
        while True:
            try:
                await poll_once(http)
            except Exception as e:
                print(f"[spotify] error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

# ════════════════════════════════════════════════════════
# API
# ════════════════════════════════════════════════════════

async def handle_now_playing(request):
    if not current.get("playing"):
        return web.json_response({"playing": False})

    pos_ms = min(
        int((time.time() - current["start_epoch"]) * 1000),
        current["duration_ms"],
    )
    lyric = get_lyric(pos_ms / 1000 + LYRIC_LEAD)

    return web.json_response({
        "playing": True,
        "title": to_ascii(current["title"]),
        "artist": to_ascii(current["artist"]),
        "position_ms": pos_ms,
        "duration_ms": current["duration_ms"],
        "lyric_prev": to_ascii(lyric["prev"]),
        "lyric_curr": to_ascii(lyric["curr"]),
        "lyric_next": to_ascii(lyric["next"]),
    })


async def handle_debug(request):
    return web.json_response({
        "current": current,
        "lyrics": {
            "key": lyrics["key"],
            "total": len(lyrics["lines"]),
            "duration": lyrics["duration"],
            "sample": lyrics["lines"][:5],
        }
    })

# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════

async def main():
    if not TOKEN_FILE.exists():
        sys.exit("[auth] no token yet - run: python spotify_server.py auth-url")
    token.update(json.loads(TOKEN_FILE.read_text()))

    app = web.Application()
    app.router.add_get("/now-playing", handle_now_playing)
    app.router.add_get("/debug", handle_debug)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()

    print(f"[server] http://0.0.0.0:{PORT}/now-playing")
    await poll_loop()


if __name__ == "__main__":
    if not CLIENT_ID:
        sys.exit("Set CLIENT_ID at the top of spotify_server.py first")

    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "auth-url":
        auth_url()
    elif cmd == "auth-code":
        asyncio.run(auth_code(sys.argv[2]))
    else:
        asyncio.run(main())
