# sfp_gravatar

**Purpose:**
Searches Gravatar for avatars, profile data, and associated emails related to the target. Useful for digital footprinting and attribution.

**Category:** Digital Footprint / Attribution

---

## Usage

- Enabled for email and username targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s user@example.com -t EMAILADDR -m sfp_gravatar
```

## Output Example

```pre
Email: user@example.com
Avatar: https://www.gravatar.com/avatar/abc123
Profile: John Doe, johndoe.com
```

## API Keys Required

None

## Tips

- Use to enrich person and email investigations.
- Combine with sfp_email and sfp_username for full context.

---

Authored by poppopjmp
