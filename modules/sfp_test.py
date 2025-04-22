    # What events is this module interested in for input
    def watchedEvents(self):
        return ["IP_ADDRESS", "AFFILIATE_IPADDR",
                "INTERNET_NAME", "AFFILIATE_INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self):
        return ["RAW_RIR_DATA", "GEOINFO"]