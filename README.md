# CF-Scanner-Pro (V8) 🚀

A fast, multi-threaded Python script to scan and find the best Cloudflare IPs (Clean IPs) based on **Latency**, **Download Speed**, and **Upload Speed**.

Designed to bypass censorship by finding "Clean IPs" that work with VLESS/VMess configurations over Cloudflare CDN.

## ✨ Features
- **Multi-threaded Scanning:** fast scanning logic.
- **Real Upload Test:** Filters out "Zombie IPs" (IPs with good ping but 0 upload speed due to throttling).
- **Download Speed Test:** Finds the best IPs for streaming.
- **Smart Ranking:** Generates two lists:
  - 🚀 **Top Speed:** Best for downloading/streaming.
  - 💎 **Top Quality:** Best for calls & gaming (Low Latency + Stable Upload).
- **Subnet Support:** Automatically scans `/24` ranges for single IPs.
- **VLESS Config Generator:** Automatically generates ready-to-use VLESS links with the found IPs.

## 🛠️ Usage

1. **Install Python 3:** Make sure Python is installed on your system.
2. **Prepare Ranges:**
   - Create a file named `ranges.txt` and put your IP ranges (CIDR) or single IPs there.
   - Or use the built-in "Official Ranges" mode.
3. **Run the Script:**
   ```bash
   python scanner.py
4. Enter VLESS Config
On the first run, the script will prompt you for a VLESS URL template. This link is saved locally and used to generate new, working configurations with the found IPs.
5. Check Results
top_ips.txt: Contains detailed metrics for the best-performing IPs.
ready_configs.txt: Contains your updated VLESS links, ready to be imported into your VPN client (e.g., v2rayN, Nekoray, Streisand).
⚠️ Disclaimer
This tool is intended for educational purposes and network diagnostic analysis only. The developer is not responsible for any misuse of this software.
🤝 Contributing
Contributions are welcome! Feel free to fork the repository, report bugs, or submit pull requests to enhance the scanning algorithms.
