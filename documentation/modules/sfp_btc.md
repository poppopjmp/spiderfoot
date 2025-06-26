# sfp_btc

**Purpose:**
Identifies and analyzes Bitcoin addresses related to the target, checking for transactions, balances, and exposure in breaches or dark web sources.

**Category:** Cryptocurrency / Threat Intelligence

---

## Usage

- Enabled for domain, email, and text targets.
- Can be run from the web UI or CLI:

```sh
python sf.py -s example.com -t DOMAIN_NAME -m sfp_btc
```

## Output Example

```pre
Bitcoin Address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
Transactions: 1000+
Balance: 12.5 BTC
Exposed In: Breach data, dark web
```

## API Keys Required

None (uses public blockchain APIs)

## Tips

- Use to track cryptocurrency exposure and risk.
- Combine with sfp_breach and sfp_email for full threat context.

---

Authored by poppopjmp
