# GhostTrack
Useful tool to track location or mobile number, so this tool can be called osint or also information gathering

<img src="https://github.com/HunxByts/GhostTrack/blob/main/asset/bn.png"/>

New update :
```Version 2.3```

### Features
- IP Tracker with Shodan integration
- Phone Number Tracker
- Username Tracker with variations
- Show Your IP

### Instalation on Linux (deb)
```
sudo apt-get install git
sudo apt-get install python3
```

### Set api variable
```
cp template.env .env
```
in .env paste by your api key for AbuseIPDBKey value

### Instalation on Termux
```
pkg install git
pkg install python3
```

### Usage Tool
```
git clone https://github.com/HunxByts/GhostTrack.git
cd GhostTrack
pip3 install -r requirements.txt
python3 GhostTR.py
```

### Features Details

**IP Tracker**: Tracks IP information and checks reputation with AbuseIPDB (requires free API key).

**Phone Number Tracker**: Gets information from phone numbers.

**Username Tracker**: Checks username on multiple social media platforms, including common variations. Uses advanced content analysis to accurately detect existing vs non-existing accounts (not just HTTP status codes).

**Show Your IP**: Displays your current IP address.
### Advanced Features

**Smart Account Detection**: The username tracker doesn't just check HTTP status codes. It analyzes the actual page content to detect:
- Platform-specific error messages
- Profile indicators (followers, posts, bio, etc.)
- Account suspension or deletion notices

This eliminates false positives where sites return HTTP 200 but show "account not found" messages.

**Username Variations**: Automatically generates and tests common username variations including:
- Adding numbers (123, 2024, etc.)
- Adding prefixes/suffixes (_username, username_official)
- Case variations (uppercase, lowercase, capitalize)
- Space replacements (_, ., -)
### Getting API Keys

**AbuseIPDB API Key** (for IP reputation checking):
1. Go to https://www.abuseipdb.com/
2. Create a free account
3. Go to API settings and generate your API key
4. Use it when prompted in the IP Tracker

<details>
<summary>:zap: Author :</summary>
- <strong><a href="https://github.com/HunxByts">HunxByts</a></strong>
</details>
