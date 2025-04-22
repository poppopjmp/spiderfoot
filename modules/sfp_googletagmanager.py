    # What events is this module interested in for input
    def watchedEvents(self):
        return ["LINKED_URL_INTERNAL", "LINKED_URL_EXTERNAL", "TARGET_WEB_CONTENT"]

    # What events this module produces
    def producedEvents(self):
        return ["GOOGLE_TAGMANAGER_ID", "INTERNET_NAME"]