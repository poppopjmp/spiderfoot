# sfp_username

**Purpose:**
Searches for usernames related to the target across social media, forums, and public sources. Useful for digital footprinting, threat actor tracking, and exposure analysis.

**Category:** Data Gathering / Digital Footprint

---

## Usage

- Enabled for person, email, and organization targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s johndoe -t USERNAME -m sfp_username
```

## Output Example

```pre
Username: johndoe
Platforms Found: Twitter, Reddit, GitHub
Profile Links: https://twitter.com/johndoe, https://github.com/johndoe
```

## API Keys Required

None (some enrichment modules may require keys)

## Tips

- Use to track threat actors or monitor brand exposure.
- Combine with sfp_email and sfp_breach for full context.

---

*Authored by poppopjmp*
