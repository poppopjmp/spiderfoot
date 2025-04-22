# -------------------------------------------------------------------------------
# Name:         sfp_twitter
# Purpose:      Query Twitter for name and location information.
#
# Author:      <bcoles@gmail.com>
#
# Created:     2018-10-17
# Copyright:   (c) bcoles 2018
# Licence:     MIT
# -------------------------------------------------------------------------------

import re

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_twitter(SpiderFootPlugin):

    meta = {
        'name': "Twitter",
        'summary': "Gather name and location from Twitter profiles.",
        'flags': [],
        'useCases': ["Footprint", "Investigate", "Passive"],
        'categories': ["Social Media"],
        'dataSource': {
            'website': "https://twitter.com/",
            'model': "FREE_NOAUTH_UNLIMITED",
            'references': [],
            'favIcon': "https://abs.twimg.com/favicons/twitter.ico",
            'logo': "https://abs.twimg.com/responsive-web/web/icon-ios.8ea219d4.png",
            'description': "Twitter is an American microblogging and social networking service "
            "on which users post and interact with messages known as \"tweets\". "
            "Registered users can post, like, and retweet tweets, but unregistered users can only read them.",
        }
    }

    # Default options
    opts = {
    }

    # Option descriptions
    optdescs = {
    }

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.__dataSource__ = "Twitter"
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["SOCIAL_MEDIA"]

    # What events this module produces
    def producedEvents(self):
        return ["RAW_RIR_DATA", "GEOINFO"]

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventName not in self.watchedEvents():
            return

        # Ensure we are only processing Twitter-related SOCIAL_MEDIA events
        if not eventData.startswith("Twitter"):
            self.debug(f"Skipping non-Twitter event: {eventData}")
            return

        # Extract the Twitter handle/URL from the data
        try:
            # Assuming format like "Twitter: <SFURL>https://twitter.com/username</SFURL>"
            url = eventData.split("<SFURL>")[1].split("</SFURL>")[0]
            username = url.split("/")[-1]
        except Exception as e:
            self.error(f"Could not extract Twitter username from {eventData}: {e}")
            return
        
        if username in self.results:
            self.debug(f"Skipping {username}, already checked.")
            return
            
        self.results[username] = True
        
        # Here you would implement API calls to Twitter to gather information
        # For example: user profile, location data, etc.
        # The implementation would depend on current Twitter API availability
        
        # Example simulating Twitter API response
        api_response = self.queryTwitterApi(username)
        if api_response:
            # Report the raw data
            evt = SpiderFootEvent("RAW_RIR_DATA", str(api_response), 
                                  self.__name__, event)
            self.notifyListeners(evt)
            
            # If location information is available in the profile
            if api_response.get('location'):
                evt = SpiderFootEvent("GEOINFO", api_response.get('location'), 
                                     self.__name__, event)
                self.notifyListeners(evt)

    def queryTwitterApi(self, username):
        """Query the Twitter API for information about a username.
        
        Args:
            username (str): Twitter username
            
        Returns:
            dict: Information about the Twitter account, or None on failure
        """
        # This would be replaced with actual Twitter API calls
        # Current implementation would depend on Twitter API v2 endpoints
        # and authentication requirements
        
        self.debug(f"Would query Twitter API for username: {username}")
        
        # Since actual API implementation would require API keys and complex OAuth,
        # we're just returning None for now. In a real implementation, this would
        # make HTTP requests to the Twitter API and return the parsed response.
        return None

# End of sfp_twitter class
