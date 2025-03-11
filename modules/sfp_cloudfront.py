# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:   sfp_cloudfront
# Purpose:  Check if a domain uses Amazon CloudFront CDN.
#
# Author:   Agostino Panico <van1sh@van1shland.io>
#
# Created:  01/02/2025
# Copyright:  (c) poppopjmp
# Licence:  MIT
# -------------------------------------------------------------------------------

import dns.resolver

from spiderfoot import SpiderFootEvent, SpiderFootPlugin


class sfp_cloudfront(SpiderFootPlugin):

    meta = {
        "name": "Amazon CloudFront Detector",
        "summary": "Identify domains using Amazon CloudFront CDN.",
        "flags": [],
        "useCases": ["Footprint", "Investigate", "Passive"],
        "categories": ["Content Delivery Networks"],
        "dataSource": {
            "website": "https://aws.amazon.com/cloudfront/",
            "model": "FREE_NOAUTH_UNLIMITED",
            "references": [
                "https://docs.aws.amazon.com/cloudfront/",
                "https://aws.amazon.com/cloudfront/features/",
            ],
            "favIcon": "https://a0.awsstatic.com/libra-css/images/site/fav/favicon.ico",
            "logo": "https://a0.awsstatic.com/libra-css/images/logos/aws_logo_smile_1200x630.png",
            "description": "Amazon CloudFront is a fast content delivery network (CDN) service that "
            "securely delivers data, videos, applications, and APIs to customers globally "
            "with low latency and high transfer speeds.",
        },
    }

    # Default options
    opts = {"verify_cname": True, "verify_dns": True, "verify_headers": True}

    # Option descriptions
    optdescs = {
        "verify_cname": "Check for CloudFront CNAME records.",
        "verify_dns": "Check DNS records for CloudFront domains.",
        "verify_headers": "Check HTTP response headers for CloudFront signatures.",
    }

    results = None
    errorState = False

    # CloudFront domains to check against
    CLOUDFRONT_DOMAINS = [".cloudfront.net"]

    # CloudFront specific HTTP headers
    CLOUDFRONT_HEADERS = ["X-Amz-Cf-Id", "Via"]

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    # What events is this module interested in for input
    def watchedEvents(self):
        return ["DOMAIN_NAME", "INTERNET_NAME", "AFFILIATE_INTERNET_NAME"]

    # What events this module produces
    def producedEvents(self):
        return [
            "CLOUD_PROVIDER",
            "CLOUD_INSTANCE_TYPE",
            "WEBSERVER_BANNER",
            "RAW_DNS_RECORDS",
        ]

    def queryDns(self, domain):
        """Check if domain has CloudFront CNAME records."""
        try:
            answers = dns.resolver.resolve(domain, "CNAME")
            records = [str(answer).rstrip(".").lower() for answer in answers]

            for record in records:
                for cloudfront_domain in self.CLOUDFRONT_DOMAINS:
                    if cloudfront_domain in record:
                        return record
            return None
        except Exception as e:
            self.debug(f"DNS resolution failed for {domain}: {e}")
            return None

    def checkHeaders(self, domain):
        """Check if domain's HTTP headers indicate CloudFront usage."""
        url = f"https://{domain}"
        res = self.sf.fetchUrl(
            url,
            timeout=self.opts["_fetchtimeout"],
            useragent=self.opts["_useragent"],
            verify=True,
        )

        if not res or not res.get("headers"):
            self.debug(f"No HTTP headers received from {domain}")
            return False

        headers = res["headers"]

        # Check for CloudFront specific headers
        for header in self.CLOUDFRONT_HEADERS:
            if header.lower() in [h.lower() for h in headers.keys()]:
                value = headers.get(header)
                if "cloudfront" in value.lower():
                    return True

        return False

    # Handle events sent to this module
    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        if self.errorState:
            return

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        domains_to_check = [eventData]

        # Check DNS for CloudFront CNAMEs
        if self.opts["verify_cname"] or self.opts["verify_dns"]:
            for domain in domains_to_check:
                cname_record = self.queryDns(domain)
                if cname_record:
                    for cloudfront_domain in self.CLOUDFRONT_DOMAINS:
                        if cloudfront_domain in cname_record:
                            # Found CloudFront CNAME
                            evt = SpiderFootEvent(
                                "CLOUD_PROVIDER",
                                "Amazon CloudFront",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)

                            evt = SpiderFootEvent(
                                "CLOUD_INSTANCE_TYPE", "CDN", self.__name__, event
                            )
                            self.notifyListeners(evt)

                            evt = SpiderFootEvent(
                                "RAW_DNS_RECORDS",
                                f"CNAME: {domain} -> {cname_record}",
                                self.__name__,
                                event,
                            )
                            self.notifyListeners(evt)
                            return

        # Check HTTP headers for CloudFront signatures
        if self.opts["verify_headers"]:
            for domain in domains_to_check:
                if self.checkHeaders(domain):
                    # Found CloudFront headers
                    evt = SpiderFootEvent(
                        "CLOUD_PROVIDER", "Amazon CloudFront", self.__name__, event
                    )
                    self.notifyListeners(evt)

                    evt = SpiderFootEvent(
                        "CLOUD_INSTANCE_TYPE", "CDN", self.__name__, event
                    )
                    self.notifyListeners(evt)

                    evt = SpiderFootEvent(
                        "WEBSERVER_BANNER",
                        "CloudFront CDN detected in HTTP headers",
                        self.__name__,
                        event,
                    )
                    self.notifyListeners(evt)
                    return
