# Correlation Engine and Correlation Rules

## Overview

SpiderFoot's correlation system automates the analysis of scan results to identify patterns, shared infrastructure, outliers, and potential risks across all your scans. It consists of two main parts:

- **Correlation Engine (Module):** The backend logic that loads, executes, and manages correlation rules, producing correlation results for each scan or workspace.
- **Correlation Rules (YAML):** Human-readable YAML files in the `/correlations` directory that define what to look for in scan data, how to group it, and how to present findings.

---

## How the Correlation Engine Works

1. **Loads all YAML rules** from the `/correlations` directory at startup or scan time.
2. **For each scan or workspace:**
   - Extracts all events and data elements from the scan database.
   - Applies each rule's `collections`, `aggregation`, and `analysis` logic to the data.
   - Generates correlation results for any matches, including a headline, risk, and references to the underlying data.
3. **Results** are shown in the web UI (Correlation Dashboard), can be exported via the CLI, and are stored in the database for reporting and automation.

---

## Anatomy of a Correlation Rule (YAML)

A correlation rule is a YAML file with the following structure:

```yaml
id: open_port_version
version: 1
meta:
  name: Open TCP port reveals version
  description: >
    A possible software version has been revealed on an open port. Such
    information may reveal the use of old/unpatched software used by
    the target.
  risk: INFO
collections:
  collect:
      - method: exact
        field: type
        value: TCP_PORT_OPEN_BANNER
      - method: regex
        field: data
        value: .*[0-9]\.[0-9].*
      - method: regex
        field: data
        value: not .*Mime-Version.*
      - method: regex
        field: data
        value: not .*HTTP/1.*
aggregation:
  field: data
headline: "Software version revealed on open port: {data}"
```

- **id:** Unique identifier for the rule (matches filename, no spaces)
- **version:** Rule version (always "1" for now)
- **meta:** Name, description, and risk level (HIGH, MEDIUM, LOW, INFO)
- **collections:** How to select data from scan results (exact match, regex, etc.)
- **aggregation:** (Optional) How to group results (e.g., by value)
- **analysis:** (Optional) How to filter/group results further (e.g., threshold, outlier)
- **headline:** Message shown in the UI/CLI for each finding

---

## Rule Components Explained

- **Meta:** Describes the rule for humans and sets the risk level.
- **Collections:** One or more `collect` blocks, each with one or more `method` blocks (exact/regex) to extract and filter data from the scan database.
- **Aggregation:** (Optional) Groups the collected data for further analysis or reporting.
- **Analysis:** (Optional) Applies logic to aggregated data, such as thresholds or outlier detection, to decide what gets reported.
- **Headline:** The summary/title for each correlation result, with placeholders for data fields (e.g., `{data}`).
