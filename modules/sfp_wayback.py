    # What events is this module interested in for input
    def watchedEvents(self):
        return ["INTERNET_NAME", "DOMAIN_NAME"]

    # What events this module produces
    def producedEvents(self):
        return ["LINKED_URL_INTERNAL", "LINKED_URL_EXTERNAL", "WAYBACK_CONTENT"]