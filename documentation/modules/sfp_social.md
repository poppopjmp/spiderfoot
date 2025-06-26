# sfp_social

**Purpose:**
Searches social media platforms for mentions, profiles, and activity related to the target. Useful for digital footprinting, brand monitoring, and threat actor tracking.

**Category:** Digital Footprint / Social Media

---

## Usage

- Enabled for person, username, and domain targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s johndoe -t USERNAME -m sfp_social
```

## Output Example

```pre
Username: johndoe
Platforms Found: Twitter, Facebook, LinkedIn
Mentions: 12
Profile Links: https://twitter.com/johndoe, https://linkedin.com/in/johndoe
```

## API Keys Required

None (some platforms may require keys for advanced data)

## Tips

- Use to monitor brand or personal exposure on social media.
- Combine with sfp_username and sfp_email for full context.

---

Authored by poppopjmp
