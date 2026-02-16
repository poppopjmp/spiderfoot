# Quick Start

*Author: poppopjmp*

This guide will help you run your first scan in minutes using either the Docker microservices deployment or the standalone mode. Follow these steps for a fast and successful start with SpiderFoot.

---

## Docker Compose (Recommended)

1. **Clone and start the stack:**

   ```bash
   git clone https://github.com/poppopjmp/spiderfoot.git
   cd spiderfoot
   cp .env.example .env
   # Edit .env — change passwords, uncomment profile sections as needed

   # Core only (5 services)
   docker compose -f docker-compose-microservices.yml up --build -d

   # Or full stack (all services except SSO)
   docker compose -f docker-compose-microservices.yml --profile full up --build -d
   ```

2. **Open the Web UI:**
   - **Core mode:** Navigate to [http://localhost:3000](http://localhost:3000)
   - **With proxy profile:** Navigate to [https://localhost](https://localhost)
   - Log in with the default credentials (`admin` / `admin`).

   ![Login](images/login.png)

3. **Create a New Scan:**
   - Click **New Scan** from the sidebar or dashboard.
   - Enter your target (e.g., `example.com`).
   - Select the target type and choose module categories.
   - Click **Run Scan**.

   ![New Scan](images/new_scan.png)

4. **View Results:**
   - Results appear in real time. The **Dashboard** shows active scans and key metrics.

   ![Dashboard](images/dashboard.png)

   - Click any scan row to open the **Scan Detail** view with Summary, Browse, Graph, GeoMap, Correlations, and AI Report tabs.

   ![Scan Detail - Summary](images/scan_detail_summary.png)

5. **Browse Data:**
   - Use the **Browse** tab to filter by event type, risk level, and source module.

   ![Scan Detail - Browse](images/scan_detail_browse.png)

6. **Visualize Relationships:**
   - The **Graph** tab shows an interactive force-directed graph of entity relationships.

   ![Scan Detail - Graph](images/scan_detail_graph.png)

7. **View Geographic Data:**
   - The **GeoMap** tab plots discovered IP addresses on a world map with risk coloring.

   ![Scan Detail - GeoMap](images/scan_detail_geomap.png)

8. **Review Correlations:**
   - The **Correlations** tab shows automated findings from the 94-rule YAML correlation engine.

   ![Scan Detail - Correlations](images/scan_detail_correlations.png)

9. **Generate AI Reports:**
   - The **AI Report** tab produces a comprehensive Cyber Threat Intelligence report using LLM analysis.

   ![Scan Detail - AI Report](images/scan_detail_ai_report.png)

---

## Standalone Mode

```bash
pip install -r requirements.txt
python sf.py -l 127.0.0.1:5001
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

---

## Command-Line Example

Run a scan directly from the CLI:

```bash
python sf.py -s example.com -t DOMAIN_NAME -m sfp_dnsresolve,sfp_ssl,sfp_whois
```

- Use `python sf.py -M` to list all modules.
- Use `python sf.py -M <module>` for help on a specific module.

---

## Workspaces

Organize related scans into **Workspaces** for multi-target campaigns, recurring assessments, or team collaboration. Each workspace groups scans, tracks notes, and provides workspace-level analytics.

![Workspaces](images/workspaces.png)

---

## Troubleshooting

- If you have issues, see the [Troubleshooting Guide](troubleshooting.md).
- For help with modules, see the [Modules Guide](modules.md).
- For configuration and API keys, see the [Configuration Guide](configuration.md).

---

Next: [Configuration](configuration.md) for API keys, advanced settings, and more tips.
