#!/usr/bin/env python3
# GhostTR - IP and Username Tracker

import json
import requests
import time
import os
import re
import sys
import unicodedata
import itertools
import select
import termios
import tty
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from importlib import resources
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from sys import stderr
from dotenv import load_dotenv
import nmap
from ipwhois import IPWhois
from ipwhois.exceptions import IPDefinedError, ASNRegistryError

load_dotenv()

Bl = '\033[30m'
Re = '\033[1;31m'
Gr = '\033[1;32m'
Ye = '\033[1;33m'
Blu = '\033[1;34m'
Mage = '\033[1;35m'
Cy = '\033[1;36m'
Wh = '\033[1;37m'

abuse_key = os.getenv("AbuseIPDBKey")

if abuse_key is None or abuse_key.strip().lower() == "null":
    print(
        "WARN: AbuseIPDBKey is missing. IP reputation check will be skipped.\n"
        "      (Tip: copy template.env to .env and set AbuseIPDBKey)",
        file=stderr,
    )
    abuse_key = ""


# utilities

# decorator for attaching run_banner to a function
def is_option(func):
    def wrapper(*args, **kwargs):
        run_banner()
        func(*args, **kwargs)


    return wrapper


def generate_username_variations(username):
    """
    Generate smarter username variations, without exploding to millions.
    Order matters: most likely variants first.
    """
    username = (username or "").strip()
    if not username:
        return []

    seen = set()
    out = []

    def add(v: str):
        v = (v or "").strip()
        if not v:
            return
        if len(v) > 64:
            return
        if v not in seen:
            seen.add(v)
            out.append(v)

    def strip_accents(s: str) -> str:
        return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

    base = username
    add(base)

    lowered = base.lower()
    add(lowered)

    # Normalize separators and accents.
    base_no_acc = strip_accents(base)
    add(base_no_acc)
    base_no_acc_low = base_no_acc.lower()
    add(base_no_acc_low)

    # Collapse whitespace and common separators into tokens.
    tokens = [t for t in re.split(r"[\s._\-]+", base_no_acc_low) if t]
    if tokens:
        add("".join(tokens))
        add("_".join(tokens))
        add(".".join(tokens))
        add("-".join(tokens))

        if len(tokens) >= 2:
            first, last = tokens[0], tokens[-1]
            add(first + last)
            add(last + first)
            add(first[0] + last if first else "")
            add(first + last[0] if last else "")

    # If user already has digits, try separating and recombining.
    m = re.match(r"^([a-zA-Z._\-]+)(\d{1,6})$", base_no_acc_low)
    if m:
        name, digits = m.group(1), m.group(2)
        name_tokens = [t for t in re.split(r"[._\-]+", name) if t]
        if name_tokens:
            core = "".join(name_tokens)
            add(core + digits)
            add(core + "_" + digits)
            add(core + "." + digits)
            add(core + "-" + digits)

    # Prefix/suffix patterns commonly used.
    prefixes = ["the", "iam", "its", "im", "real", "official"]
    suffixes = ["official", "real", "the", "tv", "yt", "x", "hq", "vip"]
    for core in [base_no_acc_low, "".join(tokens) if tokens else base_no_acc_low]:
        for p in prefixes:
            add(p + core)
            add(p + "_" + core)
        for sfx in suffixes:
            add(core + sfx)
            add(core + "_" + sfx)

    # Years + small numbers (ranked).
    for y in [2026, 2025, 2024, 2023, 2022, 2021, 2020]:
        add(base_no_acc_low + str(y))
        add(("".join(tokens) if tokens else base_no_acc_low) + str(y))

    for n in ["1", "2", "3", "7", "9", "10", "11", "12", "69", "99", "100", "123", "1234"]:
        add(base_no_acc_low + n)
        add(("".join(tokens) if tokens else base_no_acc_low) + n)

    # Simple leetspeak (limited so it doesn't explode).
    leet_map = str.maketrans({"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7"})
    core_low = "".join(tokens) if tokens else base_no_acc_low
    leet = core_low.translate(leet_map)
    if leet != core_low:
        add(leet)
        add(leet + "1")
        add(leet + "69")

    # Remove leading @ if present and re-add.
    if base.startswith("@"):
        add(base[1:])
        add(base_no_acc_low.lstrip("@"))
    else:
        add("@" + base_no_acc_low)

    # Final light cleanup: avoid trailing dot or leading dot.
    cleaned = []
    for v in out:
        if v.startswith(".") or v.endswith("."):
            continue
        cleaned.append(v)
    return cleaned


def iter_username_variations_infinite(username):
    """
    API: infinite (or near-infinite) variations generator.

    - Yields the smart finite set first (best guesses).
    - Then yields an endless stream of new, unique-ish variants (mostly numeric suffix patterns).
    - Designed to avoid repeating the same small set (unlike cycling a list).
    """
    seed = (username or "").strip()
    if not seed:
        return

    # First, yield the smart finite set.
    base_list = generate_username_variations(seed)
    emitted = set()

    def emit(v: str):
        v = (v or "").strip()
        if not v:
            return
        if len(v) > 64:
            return
        if v.startswith(".") or v.endswith("."):
            return
        if v in emitted:
            return
        emitted.add(v)
        yield v

    for v in base_list:
        yield from emit(v)

    # Choose a stable "core" to extend indefinitely.
    def strip_accents(s: str) -> str:
        return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

    seed_no_acc = strip_accents(seed).lower().lstrip("@").strip()
    tokens = [t for t in re.split(r"[\s._\-]+", seed_no_acc) if t]
    core = "".join(tokens) if tokens else re.sub(r"[\s._\-]+", "", seed_no_acc)
    core = core or seed_no_acc or seed.lower().lstrip("@")

    # Patterns we will rotate through for each increasing number.
    seps = ["", "_", ".", "-"]
    prefixes = ["", "the", "iam", "its", "im", "real", "official"]
    suffixes = ["", "official", "real", "tv", "yt", "x", "hq", "vip"]

    # Endless numeric stream (fast + very common in real usernames).
    for n in itertools.count(0):
        s_n = str(n)
        s_padded2 = f"{n:02d}" if n < 100 else None
        s_padded3 = f"{n:03d}" if n < 1000 else None

        candidates = []

        # Core + number with separators.
        for sep in seps:
            candidates.append(core + sep + s_n)
            if s_padded2:
                candidates.append(core + sep + s_padded2)
            if s_padded3:
                candidates.append(core + sep + s_padded3)

        # Prefix + core + number.
        for p in prefixes:
            if not p:
                continue
            candidates.append(p + core + s_n)
            candidates.append(p + "_" + core + s_n)

        # Core + suffix + number.
        for sfx in suffixes:
            if not sfx:
                continue
            candidates.append(core + sfx + s_n)
            candidates.append(core + "_" + sfx + s_n)

        # Year-like pattern (useful even beyond current year).
        if 2000 <= n <= 2099:
            candidates.append(core + str(n))
            candidates.append(core + "_" + str(n))

        for v in candidates:
            yield from emit(v)


def _try_import_sherlock():
    """
    Try importing Sherlock from the installed `sherlock-project` package.
    Returns (sherlock_mod, SitesInformation, QueryStatus, data_json_path) or (None, ...).
    """
    try:
        from sherlock_project import sherlock as sherlock_mod  # type: ignore
        from sherlock_project.sites import SitesInformation  # type: ignore
        from sherlock_project.result import QueryStatus  # type: ignore

        traversable = resources.files("sherlock_project").joinpath("resources").joinpath("data.json")
        with resources.as_file(traversable) as p:
            data_path = str(p)
        return sherlock_mod, SitesInformation, QueryStatus, data_path
    except Exception:
        return None, None, None, None


@contextmanager
def _cbreak_stdin():
    """
    Put stdin in cbreak mode to read single keys (ESC).
    Only used for infinite mode on Unix-like terminals.
    """
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_nonblocking():
    try:
        r, _, _ = select.select([sys.stdin], [], [], 0)
        if r:
            return sys.stdin.read(1)
    except Exception:
        return None
    return None


def check_account_exists(url, site_name, username):
    """Check if account exists on social media by analyzing response content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)

        # Check for 404 or other error status codes
        if response.status_code == 404:
            return False, "Account not found"
        elif response.status_code in [403, 410]:
            return False, "Account not found"
        elif response.status_code != 200:
            return False, f"HTTP {response.status_code}"

        content = response.text.lower()
        final_url = response.url.lower()

        # Platform-specific checks - each platform has unique error messages
        if site_name == "Instagram":
            # Instagram error messages (EN/FR/ES)
            error_msgs = [
                "sorry, this page isn't available", "this account doesn",
                "compte introuvable", "page non trouvée", "cuenta no encontrada"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Profile indicators
            profile_indicators = ["followers", "following", "posts", "IGTV"]
            if any(ind in content for ind in profile_indicators) and f"instagram.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Twitter" or site_name == "X":
            # Twitter/X error messages
            error_msgs = [
                "this account doesn", "account suspended", "account doesn't exist",
                "compte introuvable", "cuenta no encontrada", "conta não encontrada"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Profile indicators
            profile_indicators = ["joined", "tweets", "following", "followers"]
            if any(ind in content for ind in profile_indicators) and f"twitter.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Facebook":
            # Facebook error messages
            error_msgs = [
                "this content isn't available right now", "the link you followed may be broken",
                "this isn't a valid page", "compte introuvable", "contenido no disponible"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Profile indicators
            profile_indicators = ["friends", "likes", "followers", "posts"]
            if any(ind in content for ind in profile_indicators) and f"facebook.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "GitHub":
            # GitHub error messages
            error_msgs = [
                "not found", "the page you're looking for doesn't exist",
                "there isn't a github pages site here", "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # GitHub returns 200 for many profile-like pages; rely on content indicators.
            # Key difference: fake profiles show "popular repositories" but real users don't
            if "popular repositories" in content:
                return False, "Account not found"
            # Real profiles have contribution graph with actual years
            if "contribution-graph" in content or ("contribution" in content and "year" in content):
                return True, url
            # Check for actual numeric stats (e.g., "11 repositories")
            import re
            repo_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s+repos', content)
            contrib_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s+contribution', content)
            if repo_match or contrib_match:
                return True, url
            # Check for pinned items (real users have pinned repos)
            if "pinned-item" in content:
                return True, url
            # No indicators found = account doesn't exist
            return False, "Account not found"

        elif site_name == "YouTube" or site_name == "Youtube":
            # YouTube error messages
            error_msgs = [
                "this channel does not exist", "channel not found", "video not available",
                "this video is unavailable", "compte introuvable", "canal no encontrado"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Channel indicators
            profile_indicators = ["subscribers", "videos", "views", "subscribe"]
            if any(ind in content for ind in profile_indicators) and f"youtube.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "TikTok":
            # TikTok uses WAF bot protection - detect challenge pages first
            # If we see "please wait" or WAF elements, it's blocking us
            if "please wait" in content or "wafchallenge" in content or "_wafchallenge" in content:
                return False, "Blocked by TikTok (WAF)"
            # TikTok error messages - MULTILINGUAL including French
            error_msgs = [
                "couldn't find this account", "user not found", "account not found",
                "compte introuvable", "cuenta no encontrada", "conta não encontrada",
                "this account may have been deleted", "profile not found",
                "no se encontró la cuenta", "perfil não encontrado"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Profile indicators - TikTok specific
            profile_indicators = ["following", "followers", "likes", "views", "tiktok"]
            # Check if URL still contains @username (not redirected)
            if f"tiktok.com/@{username.lower()}" in final_url:
                # But also check for actual profile content, not just WAF page
                if "please wait" not in content and "waf" not in content:
                    return True, url
            return False, "Account not found"

        elif site_name == "LinkedIn":
            # LinkedIn error messages
            error_msgs = [
                "this profile is not available", "page not found", "profile not found",
                "the page you requested doesn't exist", "compte introuvable", "perfil no encontrado"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Profile indicators
            profile_indicators = ["experience", "education", "skills", "connections"]
            if any(ind in content for ind in profile_indicators) and f"linkedin.com/in/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Pinterest":
            # Pinterest error messages
            error_msgs = [
                "isn't anything here", "no pins found", "page not found",
                "compte introuvable", "no se encontró"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["pins", "boards", "followers", "following"]
            if any(ind in content for ind in profile_indicators) and f"pinterest.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Tumblr":
            # Tumblr error messages
            error_msgs = [
                "there's nothing here", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["posts", "followers", "dashboard"]
            if any(ind in content for ind in profile_indicators) and f"tumblr.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "SoundCloud":
            # SoundCloud error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["tracks", "followers", "following", "playlists"]
            if any(ind in content for ind in profile_indicators) and f"soundcloud.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Snapchat":
            # Snapchat error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable", "no se encontró"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["snapcode", "stories", "friends"]
            if any(ind in content for ind in profile_indicators) and f"snapchat.com/add/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Behance":
            # Behance error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["projects", "appreciations", "followers"]
            if any(ind in content for ind in profile_indicators) and f"behance.net/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Medium":
            # Medium error messages
            error_msgs = [
                "page not found", "doesn't exist", "not found",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["followers", "stories", "publications"]
            if any(ind in content for ind in profile_indicators) and f"medium.com/@{username.lower()}" in final_url:
                return True, url

        elif site_name == "Quora":
            # Quora error messages
            error_msgs = [
                "page not found", "doesn't exist", "not found",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["answers", "questions", "followers"]
            if any(ind in content for ind in profile_indicators) and f"quora.com/profile/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Flickr":
            # Flickr error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["photos", "photostream", "sets"]
            if any(ind in content for ind in profile_indicators) and f"flickr.com/people/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Twitch":
            # Twitch error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist", "channel not found",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["followers", "views", "videos", "live"]
            if any(ind in content for ind in profile_indicators) and f"twitch.tv/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Dribbble":
            # Dribbble error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["shots", "followers", "likes"]
            if any(ind in content for ind in profile_indicators) and f"dribbble.com/{username.lower()}" in final_url:
                return True, url

        elif site_name == "Telegram":
            # Telegram error messages
            error_msgs = [
                "not found", "doesn", "invalid",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            # Telegram usually redirects or shows username
            if f"t.me/{username.lower()}" in final_url and "tg" not in error_msgs:
                return True, url

        elif site_name == "We Heart It":
            # We Heart It error messages
            error_msgs = [
                "not found", "page not found", "doesn't exist",
                "compte introuvable"
            ]
            for msg in error_msgs:
                if msg in content:
                    return False, "Account not found"
            profile_indicators = ["hearts", "followers", "posts"]
            if any(ind in content for ind in profile_indicators) and f"weheartit.com/{username.lower()}" in final_url:
                return True, url

        # For unknown sites, use generic checks
        else:
            # Generic error messages (multilingual)
            error_indicators = [
                "page not found", "not found", "doesn't exist", "account not found",
                "user not found", "profile not found", "content not available",
                "this page isn't available", "the link you followed may be broken",
                "compte introuvable", "cuenta no encontrada", "conta não encontrada",
                "perfil no encontrado", "profil non trouvé", "seite nicht gefunden"
            ]

            for indicator in error_indicators:
                if indicator in content:
                    return False, "Account not found"

            # If URL redirected to login or home page, account likely doesn't exist
            if "login" in final_url or "signin" in final_url:
                return False, "Account not found (redirected to login)"

            # If no error indicators and we got 200, assume account exists
            return True, url

        # Default fallback
        return True, url

    except requests.RequestException as e:
        return False, f"Request error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


# FUNCTIONS FOR MENU
@is_option
def IP_Track():
    ip = input(f"{Wh}\n Enter IP target : {Gr}")

    print()
    print(f' {Wh}============= {Gr}SHOW INFORMATION IP ADDRESS {Wh}=============')
    try:
        req_api = requests.get(f"http://ipwho.is/{ip}", timeout=10)
        ip_data = req_api.json()
        if not ip_data.get("success", True):
            print(f"{Re}Error: Invalid IP or API error")
            return
        time.sleep(2)
        print(f"{Wh}\n IP target       :{Gr}", ip)
        print(f"{Wh} Type IP         :{Gr}", ip_data.get("type", "N/A"))
        print(f"{Wh} Country         :{Gr}", ip_data.get("country", "N/A"))
        print(f"{Wh} Country Code    :{Gr}", ip_data.get("country_code", "N/A"))
        print(f"{Wh} City            :{Gr}", ip_data.get("city", "N/A"))
        print(f"{Wh} Continent       :{Gr}", ip_data.get("continent", "N/A"))
        print(f"{Wh} Continent Code  :{Gr}", ip_data.get("continent_code", "N/A"))
        print(f"{Wh} Region          :{Gr}", ip_data.get("region", "N/A"))
        print(f"{Wh} Region Code     :{Gr}", ip_data.get("region_code", "N/A"))
        print(f"{Wh} Latitude        :{Gr}", ip_data.get("latitude", "N/A"))
        print(f"{Wh} Longitude       :{Gr}", ip_data.get("longitude", "N/A"))
        if "latitude" in ip_data and "longitude" in ip_data:
            lat = int(ip_data['latitude'])
            lon = int(ip_data['longitude'])
            print(f"{Wh} Maps            :{Gr}", f"https://www.google.com/maps/@{lat},{lon},8z")
        print(f"{Wh} EU              :{Gr}", ip_data.get("is_eu", "N/A"))
        print(f"{Wh} Postal          :{Gr}", ip_data.get("postal", "N/A"))
        print(f"{Wh} Calling Code    :{Gr}", ip_data.get("calling_code", "N/A"))
        print(f"{Wh} Capital         :{Gr}", ip_data.get("capital", "N/A"))
        print(f"{Wh} Borders         :{Gr}", ip_data.get("borders", "N/A"))
        if "flag" in ip_data and "emoji" in ip_data["flag"]:
            print(f"{Wh} Country Flag    :{Gr}", ip_data["flag"]["emoji"])
        if "connection" in ip_data:
            print(f"{Wh} ASN             :{Gr}", ip_data["connection"].get("asn", "N/A"))
            print(f"{Wh} ORG             :{Gr}", ip_data["connection"].get("org", "N/A"))
            print(f"{Wh} ISP             :{Gr}", ip_data["connection"].get("isp", "N/A"))
            print(f"{Wh} Domain          :{Gr}", ip_data["connection"].get("domain", "N/A"))
        if "timezone" in ip_data:
            print(f"{Wh} ID              :{Gr}", ip_data["timezone"].get("id", "N/A"))
            print(f"{Wh} ABBR            :{Gr}", ip_data["timezone"].get("abbr", "N/A"))
            print(f"{Wh} DST             :{Gr}", ip_data["timezone"].get("is_dst", "N/A"))
            print(f"{Wh} Offset          :{Gr}", ip_data["timezone"].get("offset", "N/A"))
            print(f"{Wh} UTC             :{Gr}", ip_data["timezone"].get("utc", "N/A"))
            if "current_time" in ip_data["timezone"]:
                print(f"{Wh} Current Time    :{Gr}", ip_data["timezone"]["current_time"])
            else:
                print(f"{Wh} Current Time    :{Gr} Not available")

        # IP Reputation Check (AbuseIPDB)
        if abuse_key.strip():
            try:
                abuse_headers = {
                    'Accept': 'application/json',
                    'Key': abuse_key
                }
                abuse_url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={ip}&maxAgeInDays=90"
                abuse_response = requests.get(abuse_url, headers=abuse_headers, timeout=10)

                if abuse_response.status_code == 200:
                    abuse_data = abuse_response.json()['data']
                    print(f"\n {Wh}============= {Gr}ABUSEIPDB REPUTATION {Wh}=============")
                    print(f"{Wh} IP Address       :{Gr}", abuse_data.get('ipAddress', 'N/A'))
                    print(f"{Wh} Abuse Score      :{Gr}", f"{abuse_data.get('abuseConfidenceScore', 0)}%")
                    print(f"{Wh} Total Reports    :{Gr}", abuse_data.get('totalReports', 0))
                    print(f"{Wh} Last Reported    :{Gr}", abuse_data.get('lastReportedAt', 'Never'))
                    print(f"{Wh} ISP              :{Gr}", abuse_data.get('isp', 'N/A'))
                    print(f"{Wh} Domain           :{Gr}", abuse_data.get('domain', 'N/A'))
                    print(f"{Wh} Country          :{Gr}", abuse_data.get('countryCode', 'N/A'))

                    score = abuse_data.get('abuseConfidenceScore', 0)
                    if score >= 80:
                        print(f"{Wh} Risk Level       :{Re} HIGH - Potentially malicious")
                    elif score >= 50:
                        print(f"{Wh} Risk Level       :{Ye} MEDIUM - Monitor closely")
                    elif score >= 20:
                        print(f"{Wh} Risk Level       :{Ye} LOW - Some reports")
                    else:
                        print(f"{Wh} Risk Level       :{Gr} CLEAN - No significant reports")
                else:
                    print(f"{Re}AbuseIPDB API Error: {abuse_response.status_code} - {abuse_response.text}{Re}")
            except requests.RequestException as e:
                print(f"{Re}Error connecting to AbuseIPDB: {e}{Re}")
            except Exception as e:
                print(f"{Re}Error with AbuseIPDB: {e}{Re}")
        else:
            print(f"{Ye}AbuseIPDB check skipped - no API key provided{Ye}")

        try:
            ipinfo_response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
            if ipinfo_response.status_code == 200:
                ipinfo_data = ipinfo_response.json()
                if not ipinfo_data.get('bogon', False):
                    print(f"\n {Wh}============= {Gr}ADDITIONAL IP INFO {Wh}=============")
                    if 'hostname' in ipinfo_data:
                        print(f"{Wh} Hostname         :{Gr}", ipinfo_data.get('hostname', 'N/A'))
                    if 'org' in ipinfo_data:
                        print(f"{Wh} Organization    :{Gr}", ipinfo_data.get('org', 'N/A'))
                    if 'asn' in ipinfo_data:
                        asn_info = ipinfo_data['asn']
                        print(f"{Wh} ASN Info         :{Gr}", asn_info.get('asn', 'N/A'))
                        print(f"{Wh} ASN Name         :{Gr}", asn_info.get('name', 'N/A'))
                        print(f"{Wh} ASN Domain       :{Gr}", asn_info.get('domain', 'N/A'))
        except Exception:
            pass

        try:
            whois_client = IPWhois(ip)
            whois_data = whois_client.lookup_rdap(depth=1)
            print(f"\n {Wh}============= {Gr}IPWHOIS RDAP DATA {Wh}=============")
            print(f"{Wh} ASN              :{Gr}", whois_data.get('asn', 'N/A'))
            print(f"{Wh} ASN Country      :{Gr}", whois_data.get('asn_country_code', 'N/A'))
            network = whois_data.get('network', {})
            if network:
                print(f"{Wh} Network Name     :{Gr}", network.get('name', 'N/A'))
                print(f"{Wh} Network Handle   :{Gr}", network.get('handle', 'N/A'))
                print(f"{Wh} Network CIDR     :{Gr}", network.get('cidr', 'N/A'))
                print(f"{Wh} Network Country  :{Gr}", network.get('country', 'N/A'))
        except (IPDefinedError, ASNRegistryError) as e:
            print(f"{Ye}IPWhois lookup skipped: {e}{Ye}")
        except Exception as e:
            print(f"{Ye}IPWhois error: {e}{Ye}")

        try:
            nm = nmap.PortScanner()
            scan_args = "-Pn -F"
            print(f"\n {Wh}============= {Gr}NMAP FAST SCAN {Wh}=============")
            nm.scan(ip, arguments=scan_args)
            hosts = nm.all_hosts()
            if hosts:
                for host in hosts:
                    print(f"{Wh} Host             :{Gr}{host}")
                    for proto in nm[host].all_protocols():
                        ports = nm[host][proto].keys()
                        print(f"{Wh} Protocol         :{Gr}{proto}")
                        for port in sorted(ports):
                            port_data = nm[host][proto][port]
                            state = port_data.get('state', 'unknown')
                            service = port_data.get('name', 'N/A')
                            print(f"{Wh} Port {port:>5} :{Gr} {state:<7} {Wh}service:{Gr} {service}")
            else:
                print(f"{Ye}Nmap scan returned no hosts. Host may be down or nmap failed.{Ye}")
        except Exception as e:
            print(f"{Ye}Nmap scan error: {e}{Ye}")
    except requests.RequestException as e:
        print(f"{Re}Error: Failed to fetch IP information - {e}")
    except json.JSONDecodeError:
        print(f"{Re}Error: Invalid response from API")
    except Exception as e:
        print(f"{Re}Error: {e}")


@is_option
def phoneGW():
    User_phone = input(
        f"\n {Wh}Enter phone number target {Gr}Ex [+6281xxxxxxxxx] {Wh}: {Gr}")
    default_region = "ID"

    parsed_number = phonenumbers.parse(User_phone, default_region)
    region_code = phonenumbers.region_code_for_number(parsed_number)
    jenis_provider = carrier.name_for_number(parsed_number, "en")
    location = geocoder.description_for_number(parsed_number, "id")
    is_valid_number = phonenumbers.is_valid_number(parsed_number)
    is_possible_number = phonenumbers.is_possible_number(parsed_number)
    formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    formatted_number_for_mobile = phonenumbers.format_number_for_mobile_dialing(parsed_number, default_region,
                                                                                with_formatting=True)
    number_type = phonenumbers.number_type(parsed_number)
    timezone1 = timezone.time_zones_for_number(parsed_number)
    timezoneF = ', '.join(timezone1)

    print(f"\n {Wh}========== {Gr}SHOW INFORMATION PHONE NUMBERS {Wh}==========")
    print(f"\n {Wh}Location             :{Gr} {location}")
    print(f" {Wh}Region Code          :{Gr} {region_code}")
    print(f" {Wh}Timezone             :{Gr} {timezoneF}")
    print(f" {Wh}Operator             :{Gr} {jenis_provider}")
    print(f" {Wh}Valid number         :{Gr} {is_valid_number}")
    print(f" {Wh}Possible number      :{Gr} {is_possible_number}")
    print(f" {Wh}International format :{Gr} {formatted_number}")
    print(f" {Wh}Mobile format        :{Gr} {formatted_number_for_mobile}")
    print(f" {Wh}Original number      :{Gr} {parsed_number.national_number}")
    print(
        f" {Wh}E.164 format         :{Gr} {phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)}")
    print(f" {Wh}Country code         :{Gr} {parsed_number.country_code}")
    print(f" {Wh}Local number         :{Gr} {parsed_number.national_number}")
    if number_type == phonenumbers.PhoneNumberType.MOBILE:
        print(f" {Wh}Type                 :{Gr} This is a mobile number")
    elif number_type == phonenumbers.PhoneNumberType.FIXED_LINE:
        print(f" {Wh}Type                 :{Gr} This is a fixed-line number")
    else:
        print(f" {Wh}Type                 :{Gr} This is another type of number")


@is_option
def TrackLu():
    try:
        username = input(f"\n {Wh}Enter Username : {Gr}")
        print(f"\n {Wh}Variations mode:")
        print(f" {Wh}[ {Gr}1{Wh} ] {Gr}Normal{Wh} (Y/n between variations)")
        print(f" {Wh}[ {Gr}2{Wh} ] {Gr}Infini{Wh} (auto, ESC to stop, no Y/n, generates new variants)")
        print(f" {Wh}[ {Gr}3{Wh} ] {Gr}No variations{Wh} (only exact username)")
        mode = input(f"\n {Wh}Select mode (default 1): {Gr}").strip()
        if mode not in {"1", "2", "3"}:
            mode = "1"

        if mode == "3":
            variations = [username.strip()]
        else:
            variations = generate_username_variations(username)
        results = {}
        safe_variations = [v for v in variations if v and not v.endswith(".") and not v.startswith(".")]

        sherlock_mod, SitesInformation, QueryStatus, data_path = _try_import_sherlock()

        if sherlock_mod is not None:
            cpu = os.cpu_count() or 4
            print(f"{Ye}Sherlock enabled{Wh} {Wh}(cpu={cpu}){Wh}")

            class _SilentNotify:
                def start(self, message=None):
                    return

                def update(self, result):
                    return

                def finish(self, message=None):
                    return

            sites = SitesInformation(data_path, honor_exclusions=True)
            try:
                sites.remove_nsfw_sites()
            except Exception:
                pass
            site_data = {site.name: site.information for site in sites}
            print(f"{Wh}Sites loaded: {Gr}{len(site_data)}{Wh}\n")

            def _check_variation(variation: str):
                print(f"{Wh}Checking variation: {Gr}{variation}{Wh} {Ye}(sites={len(site_data)}){Wh}")
                notify = _SilentNotify()
                try:
                    sherlock_results = sherlock_mod.sherlock(
                        variation,
                        site_data,
                        notify,
                        dump_response=False,
                        proxy=None,
                        timeout=30,
                    )
                except Exception as e:
                    print(f" {Wh}[ {Ye}! {Wh}] {Ye}Sherlock error: {e}{Wh}\n")
                    return

                found_any = False
                for site_name, payload in sherlock_results.items():
                    status = payload.get("status")
                    if status is not None and status.status == QueryStatus.CLAIMED:
                        found_any = True
                        url_user = payload.get("url_user") or payload.get("url_main") or ""
                        results[f"{site_name} ({variation})"] = url_user
                        print(f" {Wh}[ {Gr}+ {Wh}] {site_name}: {Gr}{url_user}")

                if not found_any:
                    print(f" {Wh}[ {Ye}- {Wh}] {Ye}No hits for this variation{Wh}")
                print()

        else:
            # Fallback checker (limited site list).
            social_media = [
                {"url": "https://www.facebook.com/{}", "name": "Facebook"},
                {"url": "https://www.twitter.com/{}", "name": "Twitter"},
                {"url": "https://www.instagram.com/{}", "name": "Instagram"},
                {"url": "https://www.linkedin.com/in/{}", "name": "LinkedIn"},
                {"url": "https://www.github.com/{}", "name": "GitHub"},
                {"url": "https://www.pinterest.com/{}", "name": "Pinterest"},
                {"url": "https://www.tumblr.com/{}", "name": "Tumblr"},
                {"url": "https://www.youtube.com/{}", "name": "Youtube"},
                {"url": "https://soundcloud.com/{}", "name": "SoundCloud"},
                {"url": "https://www.snapchat.com/add/{}", "name": "Snapchat"},
                {"url": "https://www.tiktok.com/@{}", "name": "TikTok"},
                {"url": "https://www.behance.net/{}", "name": "Behance"},
                {"url": "https://www.medium.com/@{}", "name": "Medium"},
                {"url": "https://www.quora.com/profile/{}", "name": "Quora"},
                {"url": "https://www.flickr.com/people/{}", "name": "Flickr"},
                {"url": "https://www.twitch.tv/{}", "name": "Twitch"},
                {"url": "https://www.dribbble.com/{}", "name": "Dribbble"},
                {"url": "https://www.telegram.me/{}", "name": "Telegram"},
                {"url": "https://www.weheartit.com/{}", "name": "We Heart It"},
            ]

            cpu = os.cpu_count() or 4
            # Requests are I/O bound: threads improve throughput and typically use multiple cores too.
            max_workers = min(64, max(8, cpu * 5), len(social_media))
            print(f"{Ye}Sherlock not installed{Wh} {Wh}(fallback, workers={max_workers}){Wh}\n")

            def _check_variation(variation: str):
                print(f"{Wh}Checking variation: {Gr}{variation}{Wh} {Ye}(workers={max_workers}){Wh}")

                def _task(site):
                    url = site["url"].format(variation)
                    exists, result = check_account_exists(url, site["name"], variation)
                    return site["name"], exists, result

                found_any = False
                per_site = {}
                with ThreadPoolExecutor(max_workers=max_workers) as ex:
                    futures = [ex.submit(_task, site) for site in social_media]
                    for fut in as_completed(futures):
                        site_name, exists, result = fut.result()
                        per_site[site_name] = (exists, result)

                for site_name in sorted(per_site.keys()):
                    exists, result = per_site[site_name]
                    if exists:
                        found_any = True
                        results[f"{site_name} ({variation})"] = result
                        print(f" {Wh}[ {Gr}+ {Wh}] {site_name}: {Gr}{result}")

                if not found_any:
                    print(f" {Wh}[ {Ye}- {Wh}] {Ye}No hits for this variation{Wh}")
                print()

        if mode == "2":
            # Infinite mode: auto-run variations until ESC.
            print(f"{Ye}Infinite mode started. Press ESC to stop.{Wh}\n")
            try:
                with _cbreak_stdin():
                    it = iter_username_variations_infinite(username)
                    while True:
                        variation = next(it)
                        _check_variation(variation)
                        key = _read_key_nonblocking()
                        if key == "\x1b":
                            print(f"{Wh}\nStopped (ESC).{Wh}\n")
                            break
            except Exception:
                # If terminal doesn't allow cbreak (rare), fallback to KeyboardInterrupt.
                it = iter_username_variations_infinite(username)
                while True:
                    variation = next(it)
                    _check_variation(variation)
        else:
            # Normal mode: confirm each next variation.
            for idx, variation in enumerate(safe_variations):
                if idx > 0:
                    ans = input(f"{Wh}Check variation {Gr}{variation}{Wh}? (Y/n): {Gr}").strip().lower()
                    if ans in {"n", "no"}:
                        print(f"{Wh}\nStopped variations.{Wh}\n")
                        break
                _check_variation(variation)

        print(f"\n {Wh}========== {Gr}SHOW INFORMATION USERNAME {Wh}==========")
        print()
        for site, url in results.items():
            print(f" {Wh}[ {Gr}+ {Wh}] {site} : {Gr}{url}")
    except Exception as e:
        print(f"{Re}Error : {e}")
        return


@is_option
def showIP():
    respone = requests.get('https://api.ipify.org/')
    Show_IP = respone.text

    print(f"\n {Wh}========== {Gr}SHOW INFORMATION YOUR IP {Wh}==========")
    print(f"\n {Wh}[{Gr} + {Wh}] Your IP Adrress : {Gr}{Show_IP}")
    print(f"\n {Wh}==============================================")


# OPTIONS
options = [
    {
        'num': 1,
        'text': 'IP Tracker',
        'func': IP_Track
    },
    {
        'num': 2,
        'text': 'Show Your IP',
        'func': showIP

    },
    {
        'num': 3,
        'text': 'Phone Number Tracker',
        'func': phoneGW
    },
    {
        'num': 4,
        'text': 'Username Tracker',
        'func': TrackLu
    },
    {
        'num': 0,
        'text': 'Exit',
        'func': exit
    }
]


def clear():
    # for windows
    if os.name == 'nt':
        _ = os.system('cls')
    # for mac and linux
    else:
        _ = os.system('clear')


def call_option(opt):
    if not is_in_options(opt):
        raise ValueError('Option not found')
    for option in options:
        if option['num'] == opt:
            if 'func' in option:
                option['func']()
            else:
                print('No function detected')


def execute_option(opt):
    try:
        call_option(opt)
        input(f'\n{Wh}[ {Gr}+ {Wh}] {Gr}Press enter to continue')
        main()
    except ValueError as e:
        print(e)
        time.sleep(2)
        execute_option(opt)
    except KeyboardInterrupt:
        print(f'\n{Wh}[ {Re}! {Wh}] {Re}Exit')
        time.sleep(2)
        exit()


def option_text():
    text = ''
    for opt in options:
        text += f'{Wh}[ {opt["num"]} ] {Gr}{opt["text"]}\n'
    return text


def is_in_options(num):
    for opt in options:
        if opt['num'] == num:
            return True
    return False


def option():
    # BANNER TOOLS
    clear()
    stderr.writelines(fr"""
       ________               __      ______                __
      / ____/ /_  ____  _____/ /_    /_  __/________ ______/ /__
     / / __/ __ \/ __ \/ ___/ __/_____/ / / ___/ __ `/ ___/ //_/
    / /_/ / / / / /_/ (__  ) /_/_____/ / / /  / /_/ / /__/ ,<
    \____/_/ /_/\____/____/\__/     /_/ /_/   \__,_/\___/_/|_|

              {Wh}[ + ]  C O D E   B Y  H U N X  [ + ]
    """)

    stderr.writelines(f"\n\n\n{option_text()}")


def run_banner():
    clear()
    time.sleep(1)
    stderr.writelines(fr"""{Wh}
         .-.
       .'   `.          {Wh}--------------------------------
       :g g   :         {Wh}| {Gr}GHOST - TRACKER - IP ADDRESS {Wh}|
       : o    `.        {Wh}|       {Gr}@CODE BY HUNXBYTS      {Wh}|
      :         ``.     {Wh}--------------------------------
     :             `.
    :  :         .   `.
    :   :          ` . `.
     `.. :            `. ``;
        `:;             `:'
           :              `.
            `.              `.     .
              `'`'`'`---..,___`;.-'
        """)
    time.sleep(0.5)


def main():
    clear()
    option()
    time.sleep(1)
    try:
        opt = int(input(f"{Wh}\n [ + ] {Gr}Select Option : {Wh}"))
        execute_option(opt)
    except ValueError:
        print(f'\n{Wh}[ {Re}! {Wh}] {Re}Please input number')
        time.sleep(2)
        main()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f'\n{Wh}[ {Re}! {Wh}] {Re}Exit')
        time.sleep(2)
        exit()
