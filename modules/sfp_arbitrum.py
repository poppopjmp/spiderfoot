from spiderfoot import SpiderFootPlugin, SpiderFootEvent

class sfp_arbitrum(SpiderFootPlugin):
    """Monitors Arbitrum blockchain for transactions and emits events."""
    meta = {
        'name': "Arbitrum Blockchain Monitor",
        'summary': "Monitors Arbitrum blockchain for transactions and emits events.",
        'flags': ['apikey'],
        'useCases': ["Passive", "Investigate"],
        'categories': ["Reputation Systems"],
        'dataSource': {
            'name': 'Arbiscan',
            'summary': 'Arbiscan API for Arbitrum blockchain monitoring',
            'model': 'FREE_AUTH_LIMITED',
            'apiKeyInstructions': [
                'Register at https://arbiscan.io/',
                'Get your API key and paste it into the module configuration.'
            ]
        }
    }

    opts = {
        "api_key": "",
        "addresses": "",  # Comma-separated Arbitrum addresses
        "max_transactions": 10,
        "start_block": 0,
        "end_block": 0,
        "min_value": 0.0,
        "event_types": "transfer,contract",  # Comma-separated event types
        "output_format": "summary"  # summary, full
    }

    optdescs = {
        "api_key": "Arbiscan API key.",
        "addresses": "Comma-separated list of Arbitrum addresses.",
        "max_transactions": "Maximum number of transactions to fetch per address.",
        "start_block": "Start block number for filtering transactions (0 for earliest).",
        "end_block": "End block number for filtering transactions (0 for latest).",
        "min_value": "Minimum transaction value (ETH) to include.",
        "event_types": "Comma-separated list of event types to include (e.g., transfer,contract).",
        "output_format": "Output format: summary (default) or full."
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.opts.update(userOpts)
        self.debug("[setup] Options: {}".format(self.opts))
        # Option validation
        if not self.opts.get("api_key"):
            self.error("[setup] API key is required.")
            raise ValueError("API key is required for Arbitrum module.")
        if not self.opts.get("addresses") or not str(self.opts.get("addresses")).strip():
            self.error("[setup] addresses is required.")
            raise ValueError("addresses is required for Arbitrum module.")
        if not isinstance(self.opts.get("max_transactions"), int) or self.opts["max_transactions"] <= 0:
            self.error("[setup] max_transactions must be a positive integer.")
            raise ValueError("max_transactions must be a positive integer.")
        if self.opts.get("output_format") not in ["summary", "full"]:
            self.error("[setup] output_format must be 'summary' or 'full'.")
            raise ValueError("output_format must be 'summary' or 'full'.")

    def watchedEvents(self):
        return ["ROOT"]

    def producedEvents(self):
        return ["ARBITRUM_ADDRESS", "ARBITRUM_TX"]

    def handleEvent(self, event):
        """
        Handle ROOT event and monitor Arbitrum blockchain for transactions for configured addresses.
        Emits ARBITRUM_TX and ARBITRUM_ADDRESS events for each relevant transaction found.
        """
        self.debug(f"[handleEvent] Received event: {event.eventType}")
        if event.eventType not in self.watchedEvents():
            self.debug(f"[handleEvent] Ignoring event type: {event.eventType}")
            return

        import requests
        addresses = [a.strip() for a in str(self.opts.get("addresses", "")).split(",") if a.strip()]
        api_key = self.opts.get("api_key")
        max_tx = int(self.opts.get("max_transactions", 10))
        start_block = int(self.opts.get("start_block", 0))
        end_block = int(self.opts.get("end_block", 0))
        min_value = float(self.opts.get("min_value", 0.0))
        event_types = [e.strip().lower() for e in str(self.opts.get("event_types", "transfer,contract")).split(",") if e.strip()]
        output_format = self.opts.get("output_format", "summary")

        for address in addresses:
            url = (
                f"https://api.arbiscan.io/api?module=account&action=txlist&address={address}"
                f"&startblock={start_block}&endblock={end_block if end_block > 0 else 99999999}"
                f"&sort=desc&apikey={api_key}"
            )
            self.debug(f"[handleEvent] Fetching transactions for {address} from {url}")
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code != 200:
                    self.error(f"[handleEvent] Arbiscan API error: {resp.status_code}")
                    continue
                data = resp.json()
                if data.get("status") != "1" or not data.get("result"):
                    self.info(f"[handleEvent] No transactions found for {address}.")
                    continue
                txs = data["result"][:max_tx]
                for tx in txs:
                    value_eth = float(tx.get("value", 0)) / 1e18
                    if value_eth < min_value:
                        continue
                    tx_type = "transfer" if tx.get("input", "0x") == "0x" else "contract"
                    if tx_type not in event_types:
                        continue
                    if output_format == "summary":
                        tx_summary = f"From: {tx.get('from')} To: {tx.get('to')} Value: {value_eth} ETH Hash: {tx.get('hash')} Block: {tx.get('blockNumber')}"
                        evt = SpiderFootEvent(
                            "ARBITRUM_TX",
                            tx_summary,
                            self.__class__.__name__,
                            event
                        )
                        self.notifyListeners(evt)
                    else:
                        evt = SpiderFootEvent(
                            "ARBITRUM_TX",
                            str(tx),
                            self.__class__.__name__,
                            event
                        )
                        self.notifyListeners(evt)
                # Emit ARBITRUM_ADDRESS event for the address
                evt_addr = SpiderFootEvent(
                    "ARBITRUM_ADDRESS",
                    address,
                    self.__class__.__name__,
                    event
                )
                self.notifyListeners(evt_addr)
            except Exception as e:
                self.error(f"[handleEvent] Error fetching Arbitrum transactions for {address}: {e}")

    def shutdown(self):
        self.debug("[shutdown] Shutting down Arbitrum module.")
