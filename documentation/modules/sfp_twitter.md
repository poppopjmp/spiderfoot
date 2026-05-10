# sfp_twitter

**Purpose:**
Searches Twitter for profiles, mentions, and activity related to the target username, email, or domain. Useful for digital footprinting, threat actor tracking, and brand monitoring.

**Category:** Digital Footprint / Social Media

---

## Usage

- Enabled for username, email, and domain targets.
- Can be run from the web UI or CLI:

```sh
curl -X POST http://localhost:8001/api/v1/scans \
  -H "Content-Type: application/json" \
  -d '{"target": "johndoe", "modules": ["sfp_twitter"]}'
```

## Output Example

```pre
Username: johndoe
Mentions: 5
Profile: https://twitter.com/johndoe
Followers: 1200
```

## API Keys Required

- Twitter API key (required for advanced data)

## Tips

- Use to monitor social media exposure and threat actor activity.
- Combine with sfp_social and sfp_username for full context.

---

Authored by poppopjmp
