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

...existing code...
