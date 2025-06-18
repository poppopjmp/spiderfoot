#!/usr/bin/env python3
"""Test multiprocessing argument passing for scan creation."""

import sys
import os
import multiprocessing as mp
import time
import logging
from copy import deepcopy

# Add the spiderfoot directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from sflib import SpiderFoot
from sfscan import startSpiderFootScanner
from spiderfoot import SpiderFootDb, SpiderFootHelpers
from spiderfoot.logger import logListenerSetup, logWorkerSetup

mp.set_start_method("spawn", force=True)

def test_multiprocessing_scan_creation():
    """Test creating a scan via multiprocessing like the web UI does."""
    
    # Initialize configuration
    config = {
        '_logfile': '',
        '_loglevel': 'INFO',
        '_maxthreads': 3,
        '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0',
        '_dnsserver': '',
        '_fetchtimeout': 5,
        '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
        '_internettlds_cache': 72,
        '_genericusers': "abuse,admin,billing,compliance,devnull,dns,ftp,hostmaster,inoc,ispfeedback,ispsupport,list-request,list,maildaemon,marketing,noc,no-reply,noreply,null,peering,peering-notify,peering-request,phish,phishing,postmaster,privacy,registrar,registry,root,routing-registry,rr,sales,security,spam,support,sysadmin,tech,undisclosed-recipients,unsubscribe,usenet,uucp,webmaster,www",
        '_malicious_useragents': "sqlmap,plecost,wpscan,netsparker,nessus,nikto,akto,w3af,wfuzz,openvas,zmeu,nmap,lgms,python-requests,python-urllib,masscan,nuclei,naabu,acunetix,arachni,burp,appspider,websecurify,grabber,wapiti,dirb,screamingfrog,httprint,zgrab,jaeles,winht,aiohttp,openvpn,sqli,xsser,whatweb,webfig,http",
        '_allowedfiletypes': "crt,txt,pdf,doc,docx,ppt,pptx,xls,xlsx,odt,ods,odp,avi,mp4,mp3,mp2,wmv,wav,mov,mpeg,flv,wma,ogg,webm,m4a,m4v",
        '_default_module': '',
        '__modules__': {},  # Will be populated by loadModules
        '__version__': '4.0',
        '__database': os.path.join(os.path.dirname(__file__), 'spiderfoot.db'),
    }
      # Load modules configuration
    sf = SpiderFoot(config)
    modconfig = sf.loadModules()
    config['__modules__'] = modconfig
    
    # Set up logging
    loggingQueue = mp.Queue()
    logListenerSetup(loggingQueue, config)
    logWorkerSetup(loggingQueue)
    log = logging.getLogger(f"spiderfoot.test")
    
    # Simulate web UI scan parameters
    scanname = "Test Scan"
    scantarget = "google.com"
    targetType = SpiderFootHelpers.targetTypeFromString(scantarget)
    modlist = ["sfp__stor_db", "sfp_accounts"]
    cfg = deepcopy(config)
    
    log.info(f"Test parameters: scanname={scanname}, scantarget={scantarget}, targetType={targetType}")
    
    if targetType is None:
        log.error(f"ERROR: targetType is None for target: {scantarget}")
        return False
    
    # Generate scan ID
    scanId = SpiderFootHelpers.genScanInstanceId()
    
    log.info(f"About to start multiprocessing with: scanname={scanname}, scanId={scanId}, scantarget={scantarget}, targetType={targetType}, modlist={modlist}")
    
    try:
        # This is exactly what the web UI does
        p = mp.Process(target=startSpiderFootScanner, args=(
            loggingQueue, scanname, scanId, scantarget, targetType, modlist, cfg))
        p.daemon = True
        p.start()
        
        # Wait a bit for the process to start and potentially fail
        time.sleep(3)
        
        if p.is_alive():
            log.info(f"Process started successfully, terminating for test...")
            p.terminate()
            p.join()
            return True
        else:
            log.error(f"Process failed to start or exited immediately")
            return False
            
    except Exception as e:
        log.error(f"Failed to start process: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    print("Testing multiprocessing scan creation...")
    success = test_multiprocessing_scan_creation()
    print(f"Test {'PASSED' if success else 'FAILED'}")
