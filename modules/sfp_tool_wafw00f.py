# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfp_tool_wafw00f
# Purpose:     SpiderFoot plug-in for using the WAFW00F tool.
#              Tool: https://github.com/EnableSecurity/wafw00f
#
# Author:      <bcoles@gmail.com>
#
# Created:     2021-03-10
# Copyright:   (c) bcoles 2021
# Licence:     MIT
# -------------------------------------------------------------------------------
from subprocess import PIPE, Popen, TimeoutExpired

from spiderfoot import SpiderFootEvent, SpiderFootPlugin, SpiderFootHelpers

# Module now uses the logging from the SpiderFootPlugin base class

class sfp_tool_wafw00f(SpiderFootPlugin):
    meta = {
        'name': "Tool - WAFW00F",
        'summary': "Identify what Web Application Firewall (WAF) is in use on the target website.",
        'flags': ["tool", "slow", "invasive"],
        'useCases': ["Footprint", "Investigate"],
        'categories': ["Crawling and Scanning"],
        'toolDetails': {
            'name': "WAFW00F",
            'description': "WAFW00F allows one to identify and fingerprint "
                           "Web Application Firewall (WAF) products protecting a website.",
            'website': 'https://github.com/EnableSecurity/wafw00f',
            'repository': 'https://github.com/EnableSecurity/wafw00f'
        }
    }

    opts = {
        'pythonbinary': 'python3',
        'wafw00f_path': ''
    }

    optdescs = {
        'pythonbinary': "Path to Python 3 binary for WAFW00F. If WAFW00F is installed in a Python environment with other versions, specify 'python3' here.",
        'wafw00f_path': "Path to the wafw00f executable file. Must be set."
    }

    results = None
    errorState = False

    def setup(self, sfc, userOpts=dict()):
        self.sf = sfc
        self.results = self.tempStorage()
        self.errorState = False
        self.__dataSource__ = "Target Website"

        for opt in list(userOpts.keys()):
            self.opts[opt] = userOpts[opt]

    def watchedEvents(self):
        return ['INTERNET_NAME', 'IP_ADDRESS']

    def producedEvents(self):
        return ['RAW_RIR_DATA', 'WEBSERVER_TECHNOLOGY']

    def handleEvent(self, event):
        eventName = event.eventType
        srcModuleName = event.module
        eventData = event.data

        self.debug(f"Received event, {eventName}, from {srcModuleName}")

        if self.errorState:
            return

        if eventData in self.results:
            self.debug(f"Skipping {eventData}, already checked.")
            return

        self.results[eventData] = True

        if not self.opts['wafw00f_path']:
            self.error("You enabled sfp_tool_wafw00f but did not set a path to the tool!")
            self.errorState = True
            return

        tool_path = self.opts['wafw00f_path']
        tool_name = self.meta['toolDetails']['name']
        pythonBinary = self.opts['pythonbinary']

        if not SpiderFootHelpers.sanitiseInput(eventData):
            self.error(f"Invalid input, refusing to run {tool_name}: {eventData}")
            return

        args = [
            pythonBinary,
            tool_path,
            '-a',
            '-v',
            eventData
        ]
        
        try:
            p = Popen(args, stdout=PIPE, stderr=PIPE)
            stdout, stderr = p.communicate(input=None, timeout=60)
        except TimeoutExpired:
            p.kill()
            stdout, stderr = p.communicate()
            self.error(f"{tool_name} took too long to complete for {eventData}")
            return
        except Exception as e:
            self.error(f"Error running {tool_name}: {e}")
            return

        if p.returncode != 0:
            self.error(f"{tool_name} failed to run: {stderr.decode('utf-8').strip() if stderr else ''}")
            return

        if stdout:
            output = stdout.decode('utf-8')
            found_waf = False
            firewall_name = None
            
            for line in output.splitlines():
                if "No WAF detected" in line:
                    found_waf = False
                    break
                
                if "is behind a" in line or "seems to be behind" in line:
                    found_waf = True
                    firewall_name = line.strip()
                
                if "No WAF detected by" in line:
                    found_waf = False
                    
            if found_waf and firewall_name:
                evt = SpiderFootEvent('RAW_RIR_DATA', f"{tool_name} detected: {firewall_name}", self.__name__, event)
                self.notifyListeners(evt)

                tech = ' '.join(firewall_name.split(' ')[4:])
                evt = SpiderFootEvent('WEBSERVER_TECHNOLOGY', f"WAF: {tech}", self.__name__, event)
                self.notifyListeners(evt)
            else:
                self.debug(f"{tool_name} did not detect a WAF for {eventData}")
        else:
            self.debug(f"{tool_name} did not produce any output for {eventData}")

# End of sfp_tool_wafw00f class
