import ipaddress
import socket
import time
import sys
import os
import ssl
import urllib.parse
import concurrent.futures
import random
from datetime import datetime

# --- CONFIGURATION ---
TIMEOUT_SSL = 2.0         # Latency Timeout (strict)
TIMEOUT_RW = 5.0          # Read/Write Timeout for Speed Tests
MAX_THREADS = 50          # Adjust based on CPU
UPLOAD_SIZE_KB = 300      # Size of upload test (in KB) - Enough to test throughput
OFFICIAL_FILE = "official_ranges.txt"
CUSTOM_FILE = "ranges.txt"
TOP_IPS_FILE = "top_ips.txt"
CONFIGS_FILE = "ready_configs.txt"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_file_lines(filename):
    if not os.path.exists(filename): return []
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip() and not line.startswith("#")]

def save_vless_template(vless_str):
    with open("vless_template.txt", "w") as f: f.write(vless_str.strip())

def load_vless_template():
    if os.path.exists("vless_template.txt"):
        with open("vless_template.txt", "r") as f: return f.read().strip()
    return None

def parse_vless(vless_link):
    try:
        parsed = urllib.parse.urlparse(vless_link)
        params = urllib.parse.parse_qs(parsed.query)
        port = parsed.port if parsed.port else 443
        sni = params.get('sni', [params.get('host', [parsed.hostname])])[0]
        return sni, port, parsed
    except: return None, None, None

def generate_new_vless(original_parsed, new_ip, tag):
    try:
        user_info = original_parsed.username
        port = original_parsed.port
        new_netloc = f"{user_info}@{new_ip}:{port}"
        new_url = urllib.parse.urlunparse((
            original_parsed.scheme,
            new_netloc,
            original_parsed.path,
            original_parsed.params,
            original_parsed.query,
            tag
        ))
        return new_url
    except: return "Error-Link"

def expand_to_subnet(ip_input):
    try:
        if "/" in ip_input: return ipaddress.ip_network(ip_input, strict=False)
        else: return ipaddress.ip_network(f"{ip_input}/24", strict=False)
    except: return None

# --- MEASUREMENT FUNCTIONS ---

def measure_latency(ip, port, sni):
    """ TLS Handshake Time """
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    start = time.time()
    try:
        sock = socket.create_connection((str(ip), port), timeout=TIMEOUT_SSL)
        with context.wrap_socket(sock, server_hostname=sni) as ssock: pass
        return (time.time() - start) * 1000
    except: return None

def measure_download(ip):
    """ Download ~1MB from Cloudflare """
    headers = (
        f"GET /__down?bytes=1000000 HTTP/1.1\r\n"
        f"Host: speed.cloudflare.com\r\nUser-Agent: ScanV8\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    start = time.time()
    downloaded = 0
    try:
        sock = socket.create_connection((str(ip), 80), timeout=TIMEOUT_RW)
        sock.sendall(headers)
        while True:
            chunk = sock.recv(8192)
            if not chunk: break
            downloaded += len(chunk)
            if time.time() - start > TIMEOUT_RW: break
        sock.close()
        
        duration = time.time() - start
        if duration <= 0: duration = 0.01
        mbps = (downloaded * 8) / (duration * 1_000_000)
        return mbps if downloaded > 5000 else 0
    except: return 0

def measure_upload(ip):
    """ Upload Random Data to Cloudflare """
    # Generate random payload
    data_size = UPLOAD_SIZE_KB * 1024
    payload = os.urandom(data_size) 
    
    headers = (
        f"POST /__up HTTP/1.1\r\n"
        f"Host: speed.cloudflare.com\r\n"
        f"User-Agent: ScanV8\r\n"
        f"Content-Length: {data_size}\r\n"
        f"Connection: close\r\n\r\n"
    ).encode()
    
    start = time.time()
    try:
        sock = socket.create_connection((str(ip), 80), timeout=TIMEOUT_RW)
        sock.sendall(headers)
        sock.sendall(payload)
        
        # We don't need to read the full response, just sending confirms upload bandwidth
        # But reading the first byte confirms server received it.
        sock.recv(1024) 
        sock.close()
        
        duration = time.time() - start
        if duration <= 0: duration = 0.01
        mbps = (data_size * 8) / (duration * 1_000_000)
        return mbps
    except: return 0

def worker(ip, port, sni):
    # Step 1: Check Latency (Fastest check)
    lat = measure_latency(ip, port, sni)
    if not lat: return None
    
    # Step 2: Check Download
    dl_speed = measure_download(ip)
    if dl_speed < 0.1: return None # Filter dead download
    
    # Step 3: Check Upload (Only for survivors)
    ul_speed = measure_upload(ip)
    
    return {
        'ip': str(ip), 
        'latency': lat, 
        'download': dl_speed, 
        'upload': ul_speed
    }

def main():
    clear_screen()
    print("==============================================")
    print("   CLOUDFLARE SCANNER V8 (UPLOAD MASTER)")
    print("==============================================")

    # --- SETUP ---
    vless_raw = load_vless_template()
    sni, port, parsed_vless = None, 443, None

    if vless_raw:
        print("[*] VLESS template found.")
        if input("Use saved template? (y/n): ").lower() != 'y': vless_raw = None
    if not vless_raw:
        vless_raw = input("\nEnter VLESS URL: ").strip()
        save_vless_template(vless_raw)
    
    if vless_raw.startswith("vless://"):
        sni, port, parsed_vless = parse_vless(vless_raw)
        print(f"[*] Target SNI: {sni}")
    else:
        sni = "google.com"
        print("[!] Using default SNI (google.com)")

    # --- MODE SELECTION ---
    print("\nSelect Scan Mode:")
    print("1. Official Ranges (from official_ranges.txt)")
    print("2. Custom Ranges (from ranges.txt)")
    print("3. Single IP Input")
    choice = input("Option: ").strip()
    
    networks = []
    if choice == '1':
        lines = load_file_lines(OFFICIAL_FILE)
        for l in lines: 
            net = expand_to_subnet(l)
            if net: networks.append(net)
    elif choice == '2':
        lines = load_file_lines(CUSTOM_FILE)
        for l in lines:
            net = expand_to_subnet(l)
            if net: networks.append(net)
    elif choice == '3':
        inp = input("Enter IP: ").strip()
        net = expand_to_subnet(inp)
        if net: networks.append(net)
    
    if not networks: return

    # --- SCANNING ---
    all_ips = []
    for n in networks: all_ips.extend(list(n.hosts()))
    total = len(all_ips)
    print(f"\n[Phase 1] Analyzing {total} IPs (Ping + DL + UL)...")
    
    results = []
    completed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(worker, ip, port, sni): ip for ip in all_ips}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
            completed += 1
            sys.stdout.write(f"\rProgress: {completed}/{total} | Valid: {len(results)}")
            sys.stdout.flush()

    if not results:
        print("\n[!] No working IPs found.")
        return

    # --- RANKING LOGIC ---
    # 1. Top Speed (Max Download)
    top_dl = sorted(results, key=lambda x: x['download'], reverse=True)[:3]
    
    # 2. Top Quality (Low Latency + Good Upload)
    # Logic: Filter IPs with Upload > 0.5 Mbps, then sort by Latency
    quality_candidates = [r for r in results if r['upload'] > 0.5]
    if not quality_candidates: quality_candidates = results # Fallback
    top_qual = sorted(quality_candidates, key=lambda x: x['latency'])[:3]

    # --- DISPLAY ---
    print("\n\n" + "="*60)
    print(f"🚀 TOP 3 DOWNLOAD SPEED (Streaming)")
    for i in top_dl:
        print(f"{i['ip']:<15} | DL: {i['download']:.2f} Mbps | UL: {i['upload']:.2f} Mbps | Ping: {i['latency']:.0f} ms")

    print("-" * 60)
    print(f"💎 TOP 3 QUALITY (Gaming & Calls - Low Ping + Upload)")
    for i in top_qual:
        print(f"{i['ip']:<15} | Ping: {i['latency']:.0f} ms | UL: {i['upload']:.2f} Mbps | DL: {i['download']:.2f} Mbps")
    print("="*60)

    # --- SAVE TO FILE ---
    ts = get_timestamp()
    with open(TOP_IPS_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n=== SCAN DATE: {ts} ===\n")
        f.write(f"Source Mode: {choice} | Count: {total}\n")
        f.write("--- High Download ---\n")
        for i in top_dl: f.write(f"{i['ip']} | DL:{i['download']:.2f} | UL:{i['upload']:.2f} | P:{i['latency']:.0f}\n")
        f.write("--- High Quality (Balanced) ---\n")
        for i in top_qual: f.write(f"{i['ip']} | P:{i['latency']:.0f} | UL:{i['upload']:.2f} | DL:{i['download']:.2f}\n")
    print(f"\n[+] Results appended to '{TOP_IPS_FILE}'")

    if parsed_vless:
        with open(CONFIGS_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n// === Generated: {ts} ===\n")
            for idx, item in enumerate(top_dl, 1):
                tag = f"🚀DL_{idx}_{item['download']:.1f}M_{ts[-5:]}"
                f.write(generate_new_vless(parsed_vless, item['ip'], tag) + "\n")
            for idx, item in enumerate(top_qual, 1):
                tag = f"💎Qual_{idx}_P{item['latency']:.0f}_U{item['upload']:.1f}M"
                f.write(generate_new_vless(parsed_vless, item['ip'], tag) + "\n")
        print(f"[+] Configs appended to '{CONFIGS_FILE}'")

    input("\nScan Finished. Press Enter to exit...")

if __name__ == "__main__":
    main()