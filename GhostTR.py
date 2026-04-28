#!/usr/bin/python
# << CODE BY HUNX04
# << MAU RECODE ??? IZIN DULU LAH,  MINIMAL TAG AKUN GITHUB MIMIN YANG MENGARAH KE AKUN INI, LEBIH GAMPANG SI PAKE FORK
# << KALAU DI ATAS TIDAK DI IKUTI MAKA AKAN MENDAPATKAN DOSA KARENA MIMIN GAK IKHLAS
# “Wahai orang-orang yang beriman! Janganlah kamu saling memakan harta sesamamu dengan jalan yang batil,” (QS. An Nisaa': 29). Rasulullah SAW juga melarang umatnya untuk mengambil hak orang lain tanpa izin.

# IMPORT MODULE

import json
import requests
import time
import os
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from sys import stderr

Bl = '\033[30m'  # VARIABLE BUAT WARNA CUYY
Re = '\033[1;31m'
Gr = '\033[1;32m'
Ye = '\033[1;33m'
Blu = '\033[1;34m'
Mage = '\033[1;35m'
Cy = '\033[1;36m'
Wh = '\033[1;37m'


# utilities

# decorator for attaching run_banner to a function
def is_option(func):
    def wrapper(*args, **kwargs):
        run_banner()
        func(*args, **kwargs)


    return wrapper


def generate_username_variations(username):
    variations = [username]
    # Common variations
    variations.append(username + "123")
    variations.append(username + "1234")
    variations.append(username + "_")
    variations.append("_" + username)
    variations.append(username + ".")
    variations.append(username + "official")
    variations.append(username + "real")
    variations.append(username + "1")
    variations.append(username + "2")
    variations.append(username + "3")
    variations.append(username + "2023")
    variations.append(username + "2024")
    variations.append(username + "2025")
    variations.append(username + "2026")
    variations.append(username.replace(" ", ""))
    variations.append(username.replace(" ", "_"))
    variations.append(username.replace(" ", "."))
    variations.append(username.replace(" ", "-"))
    variations.append(username.lower())
    variations.append(username.upper())
    variations.append(username.capitalize())
    # If username has spaces, split and try combinations
    parts = username.split()
    if len(parts) > 1:
        variations.append(''.join(parts))
        variations.append(parts[0] + parts[1])
        variations.append(parts[0][0] + parts[1])
    # Add numbers at end
    for i in range(10):
        variations.append(username + str(i))
    # Remove duplicates
    return list(set(variations))


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
            # GitHub returns 200 for all profiles, even non-existent ones
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
    ip = input(f"{Wh}\n Enter IP target : {Gr}")  # INPUT IP ADDRESS

    # Ask for AbuseIPDB API Key
    abuse_key = input(f"{Wh}\n Enter your AbuseIPDB API Key (or press Enter to skip) : {Gr}")

    print()
    print(f' {Wh}============= {Gr}SHOW INFORMATION IP ADDRESS {Wh}=============')
    try:
        req_api = requests.get(f"http://ipwho.is/{ip}", timeout=10)  # API IPWHOIS.IS
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

                    # Interpretation du score
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

        # Additional free IP info from ipinfo.io (no API key needed for basic info)
        try:
            ipinfo_response = requests.get(f"https://ipinfo.io/{ip}/json", timeout=10)
            if ipinfo_response.status_code == 200:
                ipinfo_data = ipinfo_response.json()
                if not ipinfo_data.get('bogon', False):  # Skip if it's a bogon IP
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
        except Exception as e:
            pass  # Silently skip if ipinfo.io fails
    except requests.RequestException as e:
        print(f"{Re}Error: Failed to fetch IP information - {e}")
    except json.JSONDecodeError:
        print(f"{Re}Error: Invalid response from API")
    except Exception as e:
        print(f"{Re}Error: {e}")


@is_option
def phoneGW():
    User_phone = input(
        f"\n {Wh}Enter phone number target {Gr}Ex [+6281xxxxxxxxx] {Wh}: {Gr}")  # INPUT NUMBER PHONE
    default_region = "ID"  # DEFAULT NEGARA INDONESIA

    parsed_number = phonenumbers.parse(User_phone, default_region)  # VARIABLE PHONENUMBERS
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
        variations = generate_username_variations(username)
        results = {}
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
            {"url": "https://www.periscope.tv/{}", "name": "Periscope"},
            {"url": "https://www.twitch.tv/{}", "name": "Twitch"},
            {"url": "https://www.dribbble.com/{}", "name": "Dribbble"},
            {"url": "https://www.stumbleupon.com/stumbler/{}", "name": "StumbleUpon"},
            {"url": "https://www.ello.co/{}", "name": "Ello"},
            {"url": "https://www.producthunt.com/@{}", "name": "Product Hunt"},
            {"url": "https://www.snapchat.com/add/{}", "name": "Snapchat"},
            {"url": "https://www.telegram.me/{}", "name": "Telegram"},
            {"url": "https://www.weheartit.com/{}", "name": "We Heart It"}
        ]
        for variation in variations:
            print(f"{Wh}Checking variation: {Gr}{variation}")
            for site in social_media:
                url = site['url'].format(variation)
                exists, result = check_account_exists(url, site['name'], variation)
                if exists:
                    results[f"{site['name']} ({variation})"] = result
                else:
                    results[f"{site['name']} ({variation})"] = (f"{Ye}{result} {Ye}!")
    except Exception as e:
        print(f"{Re}Error : {e}")
        return

    print(f"\n {Wh}========== {Gr}SHOW INFORMATION USERNAME {Wh}==========")
    print()
    for site, url in results.items():
        print(f" {Wh}[ {Gr}+ {Wh}] {site} : {Gr}{url}")


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
