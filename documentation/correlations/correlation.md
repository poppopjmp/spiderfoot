# Correlations in SpiderFoot

> This section documents the Correlations feature, its rule engine, and how to write and manage correlation rules in SpiderFoot. This content is based on the latest updates as of 2025.

---

# What's New in Correlations (2025 Update)

- **New Correlation Rules:** Added rules for Fofa, RocketReach, and ZoomEye exposed services/contacts, and more.
- **Advanced Analysis Methods:** The engine now supports additional analysis methods such as `outlier`, `first_collection_only`, and `match_all_to_first_collection`.
- **Improved Error Handling:** If a rule contains syntax errors, SpiderFoot will now skip the invalid rule and continue loading others, providing detailed error messages at startup.
- **Rule ID and Filename:** The `id` field in each rule must exactly match the filename (excluding `.yaml`).
- **Terminology Consistency:** All references to rule components now use consistent terminology (e.g., "collections", "aggregation").

---

## Background

SpiderFoot’s goal is to automate OSINT collection and analysis to the greatest extent possible. Since its inception, SpiderFoot has heavily focused on automating OSINT collection and entity extraction, but the automation of common analysis tasks -- beyond some reporting and visualisations -- has been left entirely to the user. The meant that the strength of SpiderFoot's data collection capabilities has sometimes been its weakness since with so much data collected, users have often needed to export it and use other tools to weed out data of interest.

## Introducing Correlations

We started tackling this analysis gap with the launch of SpiderFoot  in 2019 through the introduction of the "Correlations" feature. This feature was represented by some 30 "correlation rules" that ran with each scan, analyzing data and presenting results reflecting SpiderFoot's opinionated view on what may be important or interesting. Here are a few of those rules as examples:

- Hosts/IPs reported as malicious by multiple data sources
- Outlier web servers (can be an indication of shadow IT)
- Databases exposed on the Internet
- Open ports revealing software versions
- and many more.

With that said, let's get into what these rules look like and how to write one.

## Key concepts

### YAML
The rules themselves are written in YAML. Why YAML? It’s easy to read, write, allows for comments and is increasingly commonplace in many modern tools.

### Rule structure
The simplest way to think of a SpiderFoot correlation rule is like a simple database query that consists of a few sections:

1. Defining the rule itself (`id`, `version` and `meta` sections).
2. Stating what you'd like to extract from the scan results (`collections` section).
3. Grouping that data in some way (`aggregation` section; optional).
4. Performing some analysis over that data in some way (`analysis` section; optional).
5. Presenting the results (`headline` section).

### Example rule
Here's an example rule that looks at SpiderFoot scan results for data revealing open TCP ports where the banner (the data returned upon connecting to the port) reports a software version. It does so by applying some regular expressions to the content of `TCP_PORT_OPEN_BANNER` data elements, filtering out some false positives and then grouping the results by the banner itself  so that one correlation result is created per banner revealing a version:

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

### The outcome
To show this in practice, we can run a simple scan against a target, in this case focusing on performing a port scan:

```sh
python3.9 ./sf.py -s www.binarypool.com -m sfp_dnsresolve,sfp_portscan_tcp
```

Example output:

```
2022-04-06 08:14:58,476 [INFO] sflib : Scan [94EB5F0B] for 'www.binarypool.com' initiated.
...
sfp_portscan_tcp    Open TCP Port Banner    SSH-2.0-OpenSSH_7.2p2 Ubuntu-4ubuntu2.10
...
2022-04-06 08:15:23,110 [INFO] correlation : New correlation [open_port_version]: Software version revealed on open port: SSH-2.0-OpenSSH_7.2p2 Ubuntu-4ubuntu2.10
2022-04-06 08:15:23,244 [INFO] sflib : Scan [94EB5F0B] completed.
```

We can see above that a port was found to be open by the `sfp_portscan_tcp` module, and it happens to include a version. The correlation rule `open_port_version` picked this up and reported it. This is also visible in the web interface.

**NOTE:** Rules will only succeed if relevant data exists in your scan results in the first place. In other words, correlation rules analyze scan data, they don't collect data from targets.

---

## Correlation Engine (2025+)

SpiderFoot's correlation engine allows you to define rules in YAML to analyze and relate collected OSINT data. The engine and rule storage are fully backend-agnostic and robust.

- Correlation rules are written in YAML and stored in the `/correlations` directory.
- The engine supports advanced analysis methods (`outlier`, `first_collection_only`, `match_all_to_first_collection`).
- Rule loading is robust: syntax errors in a rule will not prevent other rules from loading.
- The `id` field in each rule must match the filename.
- Correlation results are stored in the database and can be queried via the API or web UI.

### Writing Custom Rules

- Use the provided template and reference built-in rules for guidance.
- See the `/correlations/README.md` for a full technical reference.

### Backend-Aware Storage

- Correlation results and configuration are stored using backend-agnostic SQL, ensuring compatibility with both SQLite and PostgreSQL.

---

## Correlation Engine Architecture and Storage (2025+)

SpiderFoot's correlation engine is designed for reliability, extensibility, and backend-agnostic operation. Here are key technical details and best practices for advanced users and developers:

### Rule Storage and Loading

- All correlation rules are stored as YAML files in the `/correlations` directory.
- Rules are loaded at startup; syntax errors in one rule will not prevent others from loading. Errors are logged with full context.
- The `id` field in each rule must match the filename (excluding `.yaml`). This ensures traceability and prevents accidental rule duplication.
- Rules can be enabled/disabled by adding/removing them from the directory or via the web UI (if supported).

### Database Integration

- Correlation results, rule metadata, and configuration are stored in the main SpiderFoot database using backend-agnostic SQL.
- All upsert/replace operations use helpers to ensure correct behavior for both SQLite and PostgreSQL.
- Schema creation and migrations are idempotent and backend-aware. Unique constraints and composite keys are enforced where required.
- The correlation engine is robust to schema changes and will automatically migrate or update tables as needed.

### Querying and Using Correlation Results

- Correlation results are available in the web UI, via the REST API, and can be exported for further analysis.
- Results include references to the rule ID, scan instance, affected entities, and a human-readable headline.
- You can use the API to filter, search, and aggregate correlation results for reporting or integration with other tools.

### Writing and Testing Custom Rules

- Start with the provided template and reference built-in rules for best practices.
- Use the `collections` section to extract relevant data, `aggregation` to group, and `analysis` for advanced logic.
- Test new rules on sample scans and review the logs for errors or unexpected results.
- Use the `/correlations/README.md` for a full technical reference and advanced features.

### Backend Differences and Best Practices

- All correlation engine storage and queries are backend-agnostic. Placeholders, upserts, and type mapping are handled automatically.
- For SQLite, foreign key enforcement is enabled automatically. For PostgreSQL, connection pooling is recommended for high concurrency.
- Always back up your database before adding or modifying correlation rules in production.

### Troubleshooting

- If a rule fails to load, check the logs for detailed error messages (including YAML syntax and schema issues).
- If correlation results are missing, ensure your scan data contains the required event types and fields referenced by your rules.
- For database errors, see the [Configuration Guide](../configuration.md) for backend-specific troubleshooting.

---

For more advanced usage, see the [Correlation Analysis Guide](../../workflow/correlation_analysis.md) and the [Developer Guide](../../developer_guide.md).
