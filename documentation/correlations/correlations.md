# Correlation Rules: Reference and Examples

This page provides a reference for built-in and custom correlation rules, with links to YAML source and documentation for each rule. Use these as templates or inspiration for your own rules.

---

## Built-in Correlation Rules

Below are some of the key built-in rules included with SpiderFoot. Each rule is a YAML file in the `/correlations` directory. Click the rule name to view its YAML source and documentation:

| Rule Name | Description | YAML Source |
|-----------|-------------|-------------|
| Expired SSL Certificate | Finds hosts with expired SSL certificates | [cert_expired.yaml](../../../../correlations/cert_expired.yaml) |
| Open Cloud Bucket | Finds open cloud storage buckets | [cloud_bucket_open.yaml](../../../../correlations/cloud_bucket_open.yaml) |
| Related Open Cloud Bucket | Finds possibly related open cloud buckets | [cloud_bucket_open_related.yaml](../../../../correlations/cloud_bucket_open_related.yaml) |
| Data from Base64 | Finds interesting data in base64-encoded content | [data_from_base64.yaml](../../../../correlations/data_from_base64.yaml) |
| Data from Document Meta | Finds interesting data in document/image metadata | [data_from_docmeta.yaml](../../../../correlations/data_from_docmeta.yaml) |
| Internal Service Exposed | Finds internal services exposed to the Internet | [internal_service_exposed.yaml](../../../../correlations/internal_service_exposed.yaml) |
| Exposed Services (Fofa) | Finds services exposed using Fofa | [fofa_exposed_services.yaml](../../../../correlations/fofa_exposed_services.yaml) |
| Exposed Contacts (RocketReach) | Finds exposed contacts using RocketReach | [rocketreach_exposed_contacts.yaml](../../../../correlations/rocketreach_exposed_contacts.yaml) |
| Exposed Services (ZoomEye) | Finds services exposed using ZoomEye | [zoomeye_exposed_services.yaml](../../../../correlations/zoomeye_exposed_services.yaml) |

For a full list, see the `/correlations` folder in your installation.

---

## Writing and Testing Your Own Rules

- Start with the [template.yaml](../../../../correlations/template.yaml) file.
- Read the [README](../../../../correlations/README.md) in the `/correlations` directory for a full technical reference.
- See the [Correlation Engine and Correlation Rules](correlation.md) page for a deep dive on rule structure and advanced features.

---

## Visualizing Correlations

- See the [Correlation Analysis Guide](../../workflow/correlation_analysis.md) for practical usage, workflow, and visualization tips.
- Use the [CTI Reports](cti_reports.md) page to learn how to integrate correlation results into threat intelligence reporting.

---

## More Resources

- [Correlation Engine and Correlation Rules](correlation.md)
- [Correlation Analysis Guide](../../workflow/correlation_analysis.md)
- [CTI Reports](cti_reports.md)
- [/correlations/README.md](../../../../correlations/README.md)
- [/correlations/template.yaml](../../../../correlations/template.yaml)

---

*Maintainers: Steve Micallef <steve@binarypool.com>, poppopjmp <van1sh@van1shland.io>*
