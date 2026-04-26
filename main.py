import requests
import re
import time
from playwright.sync_api import sync_playwright

# 1. API Endpoint and Headers
EVENTS_URL = "https://api.cdnlivetv.tv/api/v1/events/sports/?user=cdnlivetv&plan=free"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

HEADERS = {
    "Accept": "application/json",
    "Origin": "https://streamsports99.su",
    "Referer": "https://streamsports99.su/",
    "User-Agent": USER_AGENT
}

# 2. FILTER: Only extract these sports
TARGET_SPORTS = ["Soccer", "Cricket", "Fight"]

def build_playlist():
    print("[*] Fetching Sports Events API...")
    resp = requests.get(EVENTS_URL, headers=HEADERS)
    if resp.status_code != 200:
        print(f"[-] Failed to fetch API. Status: {resp.status_code}")
        return

    data = resp.json()
    sports_categories = data.get("cdn-live-tv", {})
    
    print("[*] Starting Playwright Browser...")
    
    with sync_playwright() as p:
        # Server-friendly arguments for GitHub Actions
        browser = p.chromium.launch(
            headless=True, 
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            extra_http_headers={
                "Referer": "https://streamsports99.su/",
                "Origin": "https://streamsports99.su"
            }
        )
        page = context.new_page()
        
        with open("playlist.m3u", "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            channel_id = 1
            
            for sport, events in sports_categories.items():
                # Apply the filter here
                if sport not in TARGET_SPORTS:
                    continue
                    
                if not isinstance(events, list):
                    continue
                    
                for event in events:
                    # Only grab matches that are LIVE right now
                    if event.get("status") != "live":
                        continue 
                    
                    match_name = f"[{sport}] {event.get('homeTeam', event.get('event', 'Live'))} vs {event.get('awayTeam', '')}"
                    logo = event.get("homeTeamIMG", event.get("eventIMG", ""))
                    channels = event.get("channels", [])
                    
                    for ch in channels:
                        ch_name = ch.get("channel_name", "Stream")
                        player_url = ch.get("url")
                        
                        if not player_url:
                            continue
                            
                        print(f"-> Extracting: {match_name} ({ch_name})")
                        caught_m3u8 = []
                        
                        def intercept_request(request):
                            if ".m3u8" in request.url:
                                caught_m3u8.append(request.url)
                        
                        page.on("request", intercept_request)
                        
                        try:
                            page.goto(player_url, wait_until="networkidle", timeout=15000)
                        except:
                            pass # Ignore timeouts
                        
                        # Wait for the token
                        for _ in range(8):
                            if caught_m3u8:
                                break
                            time.sleep(1)
                            
                        page.remove_listener("request", intercept_request)
                        
                        if caught_m3u8:
                            final_url = caught_m3u8[-1]
                            f.write(f'#EXTINF:-1 tvg-chno="{channel_id}" tvg-id="{sport}.{channel_id}" tvg-name="{match_name} ({ch_name})" tvg-logo="{logo}" group-title="{sport}",{match_name} ({ch_name})\n')
                            f.write(f'#EXTVLCOPT:http-referrer={player_url}\n')
                            f.write(f'#EXTVLCOPT:http-origin={player_url}\n')
                            f.write(f'#EXTVLCOPT:http-user-agent={USER_AGENT}\n')
                            f.write(f'{final_url}\n\n')
                            channel_id += 1
                            print(f"  [+] Success!")
                        
                        # Sleep to avoid DDoS flags
                        time.sleep(2)
                        
        browser.close()
        print("\n[+] Finished! Saved to 'playlist.m3u'")

if __name__ == "__main__":
    build_playlist()
