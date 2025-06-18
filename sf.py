#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         sf
# Purpose:      Main wrapper for calling all SpiderFoot modules
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     03/04/2012
# Copyright:   (c) Steve Micallef 2012
# Licence:     MIT
# -------------------------------------------------------------------------------

import argparse
import logging
import multiprocessing as mp
import os
import os.path
import random
import signal
import sys
import time
import threading
from copy import deepcopy
from pathlib import Path

import cherrypy
import cherrypy_cors
from cherrypy.lib import auth_digest

from sflib import SpiderFoot
from sfscan import startSpiderFootScanner
from sfwebui import SpiderFootWebUi
from spiderfoot import SpiderFootHelpers
from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootCorrelator
from spiderfoot.logger import logListenerSetup, logWorkerSetup

from spiderfoot import __version__

scanId = None
dbh = None

# 'Global' configuration options
# These can be overriden on a per-module basis, and some will
# be overridden from saved configuration settings stored in the DB.
sfConfig = {
    '_debug': False,  # Debug
    '_maxthreads': 3,  # Number of modules to run concurrently
    '__logging': True,  # Logging in general
    '__outputfilter': None,  # Event types to filter from modules' output
    # User-Agent to use for HTTP requests
    '_useragent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0',
    '_dnsserver': '',  # Override the default resolver
    '_fetchtimeout': 5,  # number of seconds before giving up on a fetch
    '_internettlds': 'https://publicsuffix.org/list/effective_tld_names.dat',
    '_internettlds_cache': 72,
    '_genericusers': ",".join(SpiderFootHelpers.usernamesFromWordlists(['generic-usernames'])),
    '__database': f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
    '__modules__': None,  # List of modules. Will be set after start-up.
    # List of correlation rules. Will be set after start-up.
    '__correlationrules__': None,
    '_socks1type': '',
    '_socks2addr': '',
    '_socks3port': '',
    '_socks4user': '',
    '_socks5pwd': '',
}
sfOptdescs = {
    '_debug': "Enable debugging?",
    '_maxthreads': "Max number of modules to run concurrently",
    '_useragent': "User-Agent string to use for HTTP requests. Prefix with an '@' to randomly select the User Agent from a file containing user agent strings for each request, e.g. @C:\\useragents.txt or @/home/bob/useragents.txt. Or supply a URL to load the list from there.",
    '_dnsserver': "Override the default resolver with another DNS server. For example, 8.8.8.8 is Google's open DNS server.",
    '_fetchtimeout': "Number of seconds before giving up on a HTTP request.",
    '_internettlds': "List of Internet TLDs.",
    '_internettlds_cache': "Hours to cache the Internet TLD list. This can safely be quite a long time given that the list doesn't change too often.",
    '_genericusers': "List of usernames that if found as usernames or as part of e-mail addresses, should be treated differently to non-generics.",
    '_socks1type': "SOCKS Server Type. Can be '4', '5', 'HTTP' or 'TOR'",
    '_socks2addr': 'SOCKS Server IP Address.',
    '_socks3port': 'SOCKS Server TCP Port. Usually 1080 for 4/5, 8080 for HTTP and 9050 for TOR.',
    '_socks4user': 'SOCKS Username. Valid only for SOCKS4 and SOCKS5 servers.',
    '_socks5pwd': "SOCKS Password. Valid only for SOCKS5 servers.",
    # This is a hack to get a description for an option not actually available.
    '_modulesenabled': "Modules enabled for the scan."
}


def load_modules_custom(mod_dir, log):
    """Custom module loader as fallback when SpiderFootHelpers.loadModulesAsDict fails."""
    sfModules = {}
    
    try:
        import importlib.util
        import os
        import sys
        
        # Add modules directory to Python path
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
        
        # Get all SpiderFoot module files
        module_files = [f for f in os.listdir(mod_dir) 
                       if f.startswith('sfp_') and f.endswith('.py') and f != 'sfp_template.py']
        
        log.info(f"Custom loader: attempting to load {len(module_files)} modules")
        
        loaded_count = 0
        failed_count = 0
        
        for module_file in module_files:
            try:
                module_name = module_file[:-3]  # Remove .py extension
                module_path = os.path.join(mod_dir, module_file)
                
                # Create module spec and load
                spec = importlib.util.spec_from_file_location(module_name, module_path)
                if spec is None:
                    log.warning(f"Could not create spec for {module_name}")
                    failed_count += 1
                    continue
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Register the module in sys.modules to ensure it can be pickled
                sys.modules[module_name] = module
                
                # Check if module has the expected class
                if hasattr(module, module_name):
                    module_class = getattr(module, module_name)
                    
                    # Basic validation - check if it looks like a SpiderFoot module
                    if hasattr(module_class, '__init__') and hasattr(module_class, 'setup'):                        # Create module info dict similar to what SpiderFootHelpers.loadModulesAsDict returns
                        try:
                            # Try to get module info without instantiating (avoid attribute errors)
                            info_dict = {}
                            
                            # Try to access _info directly from the class if it exists
                            if hasattr(module_class, '_info'):
                                class_info = getattr(module_class, '_info', {})
                                if isinstance(class_info, dict):
                                    info_dict = class_info
                            
                            # If no _info at class level, try creating a minimal instance with error handling
                            if not info_dict:
                                try:
                                    temp_instance = module_class()
                                    if hasattr(temp_instance, '_info'):
                                        info_dict = getattr(temp_instance, '_info', {})
                                except:
                                    # If instantiation fails, use defaults
                                    pass                            
                            module_info = {
                                'descr': info_dict.get('descr', 'No description'),
                                'provides': info_dict.get('provides', []),
                                'consumes': info_dict.get('consumes', []),
                                'opts': getattr(module_class, 'opts', {}),
                                'group': info_dict.get('group', [])
                            }
                            sfModules[module_name] = module_info
                            loaded_count += 1
                            
                        except Exception as e:
                            log.warning(f"Could not get info for {module_name}: {e}")                            # Still add the module with minimal info
                            sfModules[module_name] = {
                                'descr': 'No description available',
                                'provides': [],
                                'consumes': [],
                                'opts': getattr(module_class, 'opts', {}),
                                'group': []
                            }
                            loaded_count += 1
                    else:
                        log.warning(f"Module {module_name} class doesn't have expected SpiderFoot methods")
                        failed_count += 1
                else:
                    log.warning(f"Module {module_name} doesn't have expected class {module_name}")
                    failed_count += 1
                    
            except Exception as e:
                log.error(f"Failed to load module {module_file}: {e}")
                failed_count += 1
        
        log.info(f"Custom loader results: {loaded_count} loaded, {failed_count} failed")
        
    except Exception as e:
        log.error(f"Custom module loader failed: {e}")
        import traceback
        log.error(f"Traceback: {traceback.format_exc()}")
    
    return sfModules


def main():
    """Main entry point."""
    # Set up logging first
    log = logging.getLogger(f"spiderfoot.{__name__}")
    
    try:
        # Ensure we're in the correct directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # Add current directory to Python path
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
            
        # Check Python version first
        if sys.version_info < (3, 9):
            print("SpiderFoot requires Python 3.9 or higher.")
            sys.exit(-1)

        # Check for legacy database files
        if os.path.exists('spiderfoot.db'):
            print(
                f"ERROR: spiderfoot.db file exists in {os.path.dirname(__file__)}")
            print("SpiderFoot no longer supports loading the spiderfoot.db database from the application directory.")
            print(
                f"The database is now loaded from your home directory: {Path.home()}/.spiderfoot/spiderfoot.db")
            print(
                f"This message will go away once you move or remove spiderfoot.db from {os.path.dirname(__file__)}")
            sys.exit(-1)

        # Check for legacy passwd files
        if os.path.exists('passwd'):
            print(f"ERROR: passwd file exists in {os.path.dirname(__file__)}")
            print("SpiderFoot no longer supports loading credentials from the application directory.")
            print(
                f"The passwd file is now loaded from your home directory: {Path.home()}/.spiderfoot/passwd")
            print(
                f"This message will go away once you move or remove passwd from {os.path.dirname(__file__)}")
            sys.exit(-1)

        try:
            # web server config
            sfWebUiConfig = {
                'host': '127.0.0.1',
                'port': 5001,
                'root': '/',
                'cors_origins': [],
            }

            # FastAPI server config
            sfApiConfig = {
                'host': '127.0.0.1',
                'port': 8001,
                'workers': 1,
                'log_level': 'info',
                'reload': False
            }

            p = argparse.ArgumentParser(
                description=f"SpiderFoot {__version__}: Open Source Intelligence Automation.")
            p.add_argument("-d", "--debug", action='store_true',
                        help="Enable debug output.")
            p.add_argument("-l", "--listen", metavar="IP:port",
                        help="IP and port to listen on.")
            p.add_argument("--api", action='store_true',
                        help="Start FastAPI server instead of web UI.")
            p.add_argument("--api-listen", metavar="IP:port",
                        help="IP and port for FastAPI server to listen on.")
            p.add_argument("--api-workers", type=int, default=1,
                        help="Number of FastAPI worker processes.")
            p.add_argument("--both", action='store_true',
                        help="Start both web UI and FastAPI servers.")
            p.add_argument("-m", metavar="mod1,mod2,...",
                        type=str, help="Modules to enable.")
            p.add_argument("-M", "--modules", action='store_true',
                        help="List available modules.")
            p.add_argument("-C", "--correlate", metavar="scanID",
                        help="Run correlation rules against a scan ID.")
            p.add_argument("-s", metavar="TARGET", help="Target for the scan.")
            p.add_argument("-t", metavar="type1,type2,...", type=str,
                        help="Event types to collect (modules selected automatically).")
            p.add_argument("-u", choices=["all", "footprint", "investigate", "passive"],
                        type=str, help="Select modules automatically by use case")
            p.add_argument("-T", "--types", action='store_true',
                        help="List available event types.")
            p.add_argument("-o", choices=["tab", "csv", "json"],
                        type=str, help="Output format. Tab is default.")
            p.add_argument("-H", action='store_true',
                        help="Don't print field headers, just data.")
            p.add_argument("-n", action='store_true',
                        help="Strip newlines from data.")
            p.add_argument("-r", action='store_true',
                        help="Include the source data field in tab/csv output.")
            p.add_argument("-S", metavar="LENGTH", type=int,
                        help="Maximum data length to display. By default, all data is shown.")
            p.add_argument("-D", metavar='DELIMITER', type=str,
                        help="Delimiter to use for CSV output. Default is ,.")
            p.add_argument("-f", action='store_true',
                        help="Filter out other event types that weren't requested with -t.")
            p.add_argument("-F", metavar="type1,type2,...", type=str,
                        help="Show only a set of event types, comma-separated.")
            p.add_argument("-x", action='store_true', help="STRICT MODE. Will only enable modules that can directly consume your target, and if -t was specified only those events will be consumed by modules. This overrides -t and -m options.")
            p.add_argument("-q", action='store_true',
                        help="Disable logging. This will also hide errors!")
            p.add_argument("-V", "--version", action='store_true',
                        help="Display the version of SpiderFoot and exit.")
            p.add_argument("--max-threads", type=int,
                        help="Max number of modules to run concurrently.")

            args = p.parse_args()

            if args.version:
                print(f"SpiderFoot {__version__}: Open Source Intelligence Automation.")
                sys.exit(0)

            if args.max_threads:
                sfConfig['_maxthreads'] = args.max_threads

            if args.debug:
                sfConfig['_debug'] = True
            else:
                sfConfig['_debug'] = False

            if args.q:
                sfConfig['__logging'] = False

            loggingQueue = mp.Queue()
            logListenerSetup(loggingQueue, sfConfig)
            logWorkerSetup(loggingQueue)

            # Add descriptions of the global config options
            sfConfig['__globaloptdescs__'] = sfOptdescs

            # Load each module in the modules directory with a .py extension
            sfModules = {}  # Initialize sfModules at the beginning
            try:
                # Get the correct modules path - ensure we're looking in the right place
                script_dir = os.path.dirname(os.path.abspath(__file__))
                mod_dir = os.path.join(script_dir, 'modules')
                
                # Debug: Print current working directory and script directory
                log.info(f"Script directory: {script_dir}")
                log.info(f"Current working directory: {os.getcwd()}")
                log.info(f"Looking for modules in: {mod_dir}")
                
                # Check if modules directory exists at the expected location
                if not os.path.exists(mod_dir) or not os.path.isdir(mod_dir):
                    log.warning(f"Modules directory not found at: {mod_dir}")
                    
                    # Try alternative paths
                    alternative_paths = [
                        os.path.join(os.getcwd(), 'modules'),  # Current working directory
                        '/home/spiderfoot/modules',            # Container absolute path
                        os.path.join(script_dir, '..', 'modules'),  # Parent directory
                        './modules'                            # Relative path
                    ]
                    
                    mod_dir = None
                    for alt_path in alternative_paths:
                        abs_path = os.path.abspath(alt_path)
                        log.info(f"Trying alternative path: {abs_path}")
                        if os.path.exists(abs_path) and os.path.isdir(abs_path):
                            # Check if it actually contains Python files
                            py_files = [f for f in os.listdir(abs_path) if f.endswith('.py') and f.startswith('sfp_')]
                            if py_files:
                                mod_dir = abs_path
                                log.info(f"Found modules directory with {len(py_files)} Python files at: {mod_dir}")
                                break
                            else:
                                log.info(f"Directory exists but contains no SpiderFoot modules: {abs_path}")
                    
                    if not mod_dir:
                        # List contents of script directory for debugging
                        log.error(f"Contents of script directory {script_dir}:")
                        try:
                            for item in os.listdir(script_dir):
                                item_path = os.path.join(script_dir, item)
                                if os.path.isdir(item_path):
                                    log.error(f"  [DIR]  {item}")
                                else:
                                    log.error(f"  [FILE] {item}")
                        except Exception as e:
                            log.error(f"Cannot list directory contents: {e}")
                        
                        log.critical("No modules directory found in any expected location")
                        return sfModules  # Return empty dict instead of sys.exit
                
                log.info(f"Loading modules from: {mod_dir}")
                
                # Additional validation: check if directory has any Python files
                try:
                    py_files = [f for f in os.listdir(mod_dir) if f.endswith('.py')]
                    sfp_files = [f for f in py_files if f.startswith('sfp_')]
                    log.info(f"Found {len(py_files)} total Python files, {len(sfp_files)} SpiderFoot modules")
                    
                    if len(sfp_files) == 0:
                        log.critical(f"No SpiderFoot modules (sfp_*.py) found in {mod_dir}")
                        log.critical(f"Python files found: {py_files[:10]}...")  # Show first 10
                        return sfModules  # Return empty dict instead of sys.exit
                        
                except Exception as e:
                    log.critical(f"Cannot read modules directory {mod_dir}: {e}")
                    return sfModules  # Return empty dict instead of sys.exit
                
                # Now try to load the modules
                try:
                    log.info("Attempting to load modules with SpiderFootHelpers.loadModulesAsDict...")
                    
                    # First, let's test if we can import SpiderFootHelpers properly
                    try:
                        from spiderfoot import SpiderFootHelpers
                        log.info("SpiderFootHelpers imported successfully")
                    except Exception as e:
                        log.critical(f"Failed to import SpiderFootHelpers: {e}")
                        return sfModules  # Return empty dict instead of sys.exit
                    
                    # Test loading a single module manually to diagnose issues
                    sample_modules = [f for f in os.listdir(mod_dir) if f.startswith('sfp_') and f.endswith('.py')][:3]
                    log.info(f"Testing manual import of sample modules: {sample_modules}")
                    
                    for sample_mod in sample_modules:
                        try:
                            mod_name = sample_mod[:-3]  # Remove .py extension
                            log.info(f"Testing import of {mod_name}")
                            
                            # Add modules directory to Python path temporarily
                            if mod_dir not in sys.path:
                                sys.path.insert(0, mod_dir)
                            
                            # Try to import the module
                            import importlib.util
                            spec = importlib.util.spec_from_file_location(mod_name, os.path.join(mod_dir, sample_mod))
                            if spec is None:
                                log.error(f"Could not create spec for {mod_name}")
                                continue
                                
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            log.info(f"Successfully imported {mod_name}")
                            
                            # Check if the module has the expected SpiderFoot class
                            if hasattr(module, mod_name):
                                log.info(f"Module {mod_name} has expected class")
                            else:
                                log.warning(f"Module {mod_name} missing expected class")
                                
                        except Exception as e:
                            log.error(f"Failed to import {mod_name}: {e}")
                            log.error(f"Error type: {type(e).__name__}")
                            import traceback
                            log.error(f"Traceback: {traceback.format_exc()}")
                    
                    # Now try the actual SpiderFootHelpers.loadModulesAsDict
                    log.info("Calling SpiderFootHelpers.loadModulesAsDict...")
                    sfModules = SpiderFootHelpers.loadModulesAsDict(mod_dir, ['sfp_template.py'])
                      # If the standard method fails, try our custom loader
                    if not sfModules:
                        log.warning("Standard loadModulesAsDict failed, trying custom loader...")
                        sfModules = load_modules_custom(mod_dir, log)
                    
                except Exception as e:
                    log.critical(f"Exception during module loading: {e}")
                    import traceback
                    log.critical(f"Full traceback: {traceback.format_exc()}")
                      # Try custom loader as fallback
                    log.info("Trying custom module loader as fallback...")
                    try:
                        sfModules = load_modules_custom(mod_dir, log)
                    except Exception as e2:
                        log.critical(f"Custom loader also failed: {e2}")
                        return sfModules  # Return empty dict
                
                if not sfModules:
                    log.critical(f"Both standard and custom module loaders failed for directory: {mod_dir}")
                    # ... existing debugging code ...
                    sys.exit(-1)
                    
            except Exception as e:
                log.critical(f"Failed to load modules: {e}", exc_info=True)
                sys.exit(-1)

            log.info(f"Successfully loaded {len(sfModules)} modules")
            sfConfig['__modules__'] = sfModules

            # Load correlation rules
            try:
                import yaml
                correlations_dir = os.path.join(script_dir, 'correlations')
                correlation_rules = []
                
                if os.path.exists(correlations_dir):
                    for filename in os.listdir(correlations_dir):
                        if filename.endswith('.yaml') and filename != 'template.yaml':
                            filepath = os.path.join(correlations_dir, filename)
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    rule = yaml.safe_load(f)
                                    if rule and isinstance(rule, dict):
                                        rule['id'] = filename[:-5]  # Remove .yaml extension
                                        correlation_rules.append(rule)
                            except Exception as e:
                                log.warning(f"Failed to load correlation rule {filename}: {e}")
                
                sfConfig['__correlationrules__'] = correlation_rules
                log.info(f"Loaded {len(correlation_rules)} correlation rules")
            except Exception as e:
                log.warning(f"Failed to load correlation rules: {e}")
                sfConfig['__correlationrules__'] = []# Handle different command line options
            if args.correlate:
                # Correlate
                dbh = SpiderFootDb(sfConfig, init=True)
                correlator = SpiderFootCorrelator(sfConfig, dbh)
                correlator.correlateAll(args.correlate)
                sys.exit(0)

            if args.modules:
                # List modules
                modKeys = sorted(sfModules.keys())
                print(f"Total modules: {len(modKeys)}")
                for modName in modKeys:
                    info = sfModules[modName]
                    print(f"{modName}: {info.get('descr', 'No description')}")
                sys.exit(0)

            if args.types:
                # List event types
                dbh = SpiderFootDb(sfConfig, init=True)
                etypes = dbh.eventTypes()
                if etypes:
                    print(f"Total event types: {len(etypes)}")
                    for etype in sorted(etypes, key=lambda x: x[1]):
                        print(f"{etype[1]}")
                sys.exit(0)

            # Handle scanning mode
            if args.s:
                start_scan(sfConfig, sfModules, args, loggingQueue)
                return

            # Handle server modes
            if args.listen:
                listenhost, listenport = args.listen.split(":")
                sfWebUiConfig['host'] = listenhost
                sfWebUiConfig['port'] = int(listenport)

            if args.api_listen:
                apihost, apiport = args.api_listen.split(":")
                sfApiConfig['host'] = apihost
                sfApiConfig['port'] = int(apiport)

            if args.api_workers:
                sfApiConfig['workers'] = args.api_workers

            if args.api:
                start_fastapi_server(sfApiConfig, sfConfig, loggingQueue)
            elif args.both:                start_both_servers(sfWebUiConfig, sfApiConfig, sfConfig, loggingQueue)
            else:
                start_web_server(sfWebUiConfig, sfConfig, loggingQueue)
                
        except Exception as e:
            log.critical(f"Unhandled exception in main configuration: {e}", exc_info=True)
            sys.exit(-1)

    except KeyboardInterrupt:
        log.info("Interrupted.")
        sys.exit(0)
    except Exception as e:
        log.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(-1)


def start_scan(sfConfig: dict, sfModules: dict, args, loggingQueue) -> None:
    """Start a scan based on the provided configuration and command-line
    arguments.

    Args:
        sfConfig (dict): SpiderFoot config options
        sfModules (dict): modules
        args (argparse.Namespace): command line args
        loggingQueue (Queue): main SpiderFoot logging queue
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        global dbh
        global scanId

        dbh = SpiderFootDb(sfConfig, init=True)
        sf = SpiderFoot(sfConfig)

        validate_arguments(args, log)

        target, targetType = process_target(args, log)

        modlist = prepare_modules(args, sf, sfModules, log, targetType)

        if len(modlist) == 0:
            log.error("Based on your criteria, no modules were enabled.")
            sys.exit(-1)

        modlist += ["sfp__stor_db", "sfp__stor_stdout",
                    "sfp__stor_elasticsearch"]

        if sfConfig['__logging']:
            log.info(f"Modules enabled ({len(modlist)}): {','.join(modlist)}")

        cfg = sf.configUnserialize(dbh.configGet(), sfConfig)

        # Debug mode is a variable that gets stored to the DB, so re-apply it
        if args.debug:
            cfg['_debug'] = True
        else:
            cfg['_debug'] = False

        # If strict mode is enabled, filter the output from modules.
        if args.x and args.t:
            cfg['__outputfilter'] = args.t.split(",")

        prepare_scan_output(args)

        execute_scan(loggingQueue, target, targetType, modlist, cfg, log)

        return
    except Exception as e:
        log.critical(f"Unhandled exception in start_scan: {e}", exc_info=True)
        sys.exit(-1)


def validate_arguments(args, log):
    if not args.s:
        log.error(
            "You must specify a target when running in scan mode. Try --help for guidance.")
        sys.exit(-1)

    if args.x and not args.t:
        log.error("-x can only be used with -t. Use --help for guidance.")
        sys.exit(-1)

    if args.x and args.m:
        log.error(
            "-x can only be used with -t and not with -m. Use --help for guidance.")
        sys.exit(-1)

    if args.r and (args.o and args.o not in ["tab", "csv"]):
        log.error("-r can only be used when your output format is tab or csv.")
        sys.exit(-1)

    if args.H and (args.o and args.o not in ["tab", "csv"]):
        log.error("-H can only be used when your output format is tab or csv.")
        sys.exit(-1)

    if args.D and args.o != "csv":
        log.error("-D can only be used when using the csv output format.")
        sys.exit(-1)


def process_target(args, log):
    target = args.s
    # Usernames and names - quoted on the commandline - won't have quotes,
    # so add them.
    if " " in target:
        target = f"\"{target}\""
    if "." not in target and not target.startswith("+") and '"' not in target:
        target = f"\"{target}\""
    targetType = SpiderFootHelpers.targetTypeFromString(target)

    if not targetType:
        log.error(f"Could not determine target type. Invalid target: {target}")
        sys.exit(-1)

    target = target.strip('"')
    return target, targetType


def prepare_modules(args, sf, sfModules, log, targetType):
    modlist = list()
    if not args.t and not args.m and not args.u:
        log.warning(
            "You didn't specify any modules, types or use case, so all modules will be enabled.")
        for m in list(sfModules.keys()):
            if "__" in m:
                continue
            modlist.append(m)

    signal.signal(signal.SIGINT, handle_abort)
    # If the user is scanning by type..
    # 1. Find modules producing that type
    if args.t:
        types = args.t
        modlist = sf.modulesProducing(types)
        newmods = deepcopy(modlist)
        newmodcpy = deepcopy(newmods)

        # 2. For each type those modules consume, get modules producing
        while len(newmodcpy) > 0:
            for etype in sf.eventsToModules(newmodcpy):
                xmods = sf.modulesProducing([etype])
                for mod in xmods:
                    if mod not in modlist:
                        modlist.append(mod)
                        newmods.append(mod)
            newmodcpy = deepcopy(newmods)
            newmods = list()

    # Easier if scanning by module
    if args.m:
        modlist = list(filter(None, args.m.split(",")))

    # Select modules if the user selected usercase
    if args.u:
        # Make the first Letter Uppercase
        usecase = args.u[0].upper() + args.u[1:]
        for mod in sfConfig['__modules__']:
            if usecase == 'All' or usecase in sfConfig['__modules__'][mod]['group']:
                modlist.append(mod)

    # Add sfp__stor_stdout to the module list
    typedata = dbh.eventTypes()
    types = dict()
    for r in typedata:
        types[r[1]] = r[0]

    sfp__stor_stdout_opts = sfConfig['__modules__']['sfp__stor_stdout']['opts']
    sfp__stor_stdout_opts['_eventtypes'] = types
    if args.f:
        if args.f and not args.t:
            log.error("You can only use -f with -t. Use --help for guidance.")
            sys.exit(-1)
        sfp__stor_stdout_opts['_showonlyrequested'] = True
    if args.F:
        sfp__stor_stdout_opts['_requested'] = args.F.split(",")
        sfp__stor_stdout_opts['_showonlyrequested'] = True
    if args.o:
        if args.o not in ["tab", "csv", "json"]:
            log.error(
                "Invalid output format selected. Must be 'tab', 'csv' or 'json'.")
            sys.exit(-1)
        sfp__stor_stdout_opts['_format'] = args.o
    if args.t:
        sfp__stor_stdout_opts['_requested'] = args.t.split(",")
    if args.n:
        sfp__stor_stdout_opts['_stripnewline'] = True
    if args.r:
        sfp__stor_stdout_opts['_showsource'] = True
    if args.S:
        sfp__stor_stdout_opts['_maxlength'] = args.S
    if args.D:
        sfp__stor_stdout_opts['_csvdelim'] = args.D
    if args.x:
        tmodlist = list()
        modlist = list()
        xmods = sf.modulesConsuming([targetType])
        for mod in xmods:
            if mod not in modlist:
                tmodlist.append(mod)

        # Remove any modules not producing the type requested
        rtypes = args.t.split(",")
        for mod in tmodlist:
            for r in rtypes:
                if not sfModules[mod]['provides']:
                    continue
                if r in sfModules[mod].get('provides', []) and mod not in modlist:
                    modlist.append(mod)

    return modlist


def prepare_scan_output(args):
    if args.o == "json":
        print("[", end='')
    elif not args.H:
        delim = "\t"

        if args.o == "tab":
            delim = "\t"

        if args.o == "csv":
            if args.D:
                delim = args.D
            else:
                delim = ","

        if args.r:
            if delim == "\t":
                headers = delim.join(
                    ["Source".ljust(30), "Type".ljust(45), "Source Data", "Data"])
            else:
                headers = delim.join(["Source", "Type", "Source Data", "Data"])
        else:
            if delim == "\t":
                headers = delim.join(
                    ["Source".ljust(30), "Type".ljust(45), "Data"])
            else:
                headers = delim.join(["Source", "Type", "Data"])

        print(headers)


def execute_scan(loggingQueue, target, targetType, modlist, cfg, log):
    # Start running a new scan
    scanName = target
    scanId = SpiderFootHelpers.genScanInstanceId()
    try:
        p = mp.Process(target=startSpiderFootScanner, args=(
            loggingQueue, scanName, scanId, target, targetType, modlist, cfg))
        p.daemon = True
        p.start()
    except Exception as e:
        log.error(f"Scan [{scanId}] failed: {e}")
        sys.exit(-1)

    # Poll for scan status until completion
    while True:
        time.sleep(1)
        info = dbh.scanInstanceGet(scanId)
        if not info:
            continue
        if info[5] in ["ERROR-FAILED", "ABORT-REQUESTED", "ABORTED", "FINISHED"]:
            # allow 60 seconds for post-scan correlations to complete
            timeout = 60
            p.join(timeout=timeout)
            if (p.is_alive()):
                log.error(
                    f"Timeout reached ({timeout}s) waiting for scan {scanId} post-processing to complete.")
                sys.exit(-1)

            if sfConfig['__logging']:
                log.info(f"Scan completed with status {info[5]}")
            sys.exit(0)


def start_fastapi_server(sfApiConfig: dict, sfConfig: dict, loggingQueue=None) -> None:
    """Start the FastAPI server.

    Args:
        sfApiConfig (dict): FastAPI server options
        sfConfig (dict): SpiderFoot config options
        loggingQueue (Queue): main SpiderFoot logging queue
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        # Check if FastAPI dependencies are available
        try:
            import uvicorn
            import fastapi
        except ImportError:
            log.error("FastAPI dependencies not found. Please install with: pip install fastapi uvicorn")
            sys.exit(-1)

        api_host = sfApiConfig.get('host', '127.0.0.1')
        api_port = sfApiConfig.get('port', 8001)
        api_workers = sfApiConfig.get('workers', 1)
        api_log_level = sfApiConfig.get('log_level', 'info')
        api_reload = sfApiConfig.get('reload', False)

        log.info(f"Starting FastAPI server at {api_host}:{api_port} ...")

        # Check if sfapi.py exists
        sfapi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sfapi.py')
        if not os.path.exists(sfapi_path):
            log.error("sfapi.py not found. Please ensure the FastAPI module is available.")
            sys.exit(-1)

        print("")
        print("*************************************************************")
        print(" SpiderFoot FastAPI server is starting...")
        print(f" API will be available at: http://{api_host}:{api_port}")
        print(f" API documentation at: http://{api_host}:{api_port}/api/docs")
        print("*************************************************************")
        print("")

        # Run FastAPI server
        uvicorn.run(
            "sfapi:app",
            host=api_host,
            port=api_port,
            workers=api_workers,
            log_level=api_log_level,
            reload=api_reload,
            access_log=True
        )

    except Exception as e:
        log.critical(f"Unhandled exception in start_fastapi_server: {e}", exc_info=True)
        sys.exit(-1)


def start_both_servers(sfWebUiConfig: dict, sfApiConfig: dict, sfConfig: dict, loggingQueue=None) -> None:
    """Start both the web UI and FastAPI servers concurrently.

    Args:
        sfWebUiConfig (dict): web server options
        sfApiConfig (dict): FastAPI server options
        sfConfig (dict): SpiderFoot config options
        loggingQueue (Queue): main SpiderFoot logging queue
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        # Check if FastAPI dependencies are available
        try:
            import uvicorn
            import fastapi
        except ImportError:
            log.error("FastAPI dependencies not found. Please install with: pip install fastapi uvicorn")
            log.info("Starting only the web UI server...")
            start_web_server(sfWebUiConfig, sfConfig, loggingQueue)
            return

        web_host = sfWebUiConfig.get('host', '127.0.0.1')
        web_port = sfWebUiConfig.get('port', 5001)
        api_host = sfApiConfig.get('host', '127.0.0.1')
        api_port = sfApiConfig.get('port', 8001)

        log.info(f"Starting both servers - Web UI: {web_host}:{web_port}, API: {api_host}:{api_port}")

        print("")
        print("*************************************************************")
        print(" SpiderFoot is starting both servers...")
        print(f" Web UI: http://{web_host}:{web_port}")
        print(f" FastAPI: http://{api_host}:{api_port}")
        print(f" API Docs: http://{api_host}:{api_port}/api/docs")
        print("*************************************************************")
        print("")

        # Start FastAPI server in a separate thread
        def run_fastapi():
            try:
                # Check if sfapi.py exists
                sfapi_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sfapi.py')
                if not os.path.exists(sfapi_path):
                    log.error("sfapi.py not found. FastAPI server will not start.")
                    return

                uvicorn.run(
                    "sfapi:app",
                    host=api_host,
                    port=api_port,
                    workers=1,  # Use single worker when running alongside CherryPy
                    log_level=sfApiConfig.get('log_level', 'info'),
                    reload=False,  # Disable reload when running alongside CherryPy
                    access_log=True
                )
            except Exception as e:
                log.error(f"FastAPI server error: {e}")

        # Start FastAPI in background thread
        fastapi_thread = threading.Thread(target=run_fastapi, daemon=True)
        fastapi_thread.start()

        # Give FastAPI a moment to start
        time.sleep(2)

        # Start CherryPy web server (this will block)
        start_web_server(sfWebUiConfig, sfConfig, loggingQueue)

    except Exception as e:
        log.critical(f"Unhandled exception in start_both_servers: {e}", exc_info=True)
        sys.exit(-1)


def start_web_server(sfWebUiConfig: dict, sfConfig: dict, loggingQueue=None) -> None:
    """Start the web server so you can start looking at results.

    Args:
        sfWebUiConfig (dict): web server options
        sfConfig (dict): SpiderFoot config options
        loggingQueue (Queue): main SpiderFoot logging queue
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        web_host = sfWebUiConfig.get('host', '127.0.0.1')
        web_port = sfWebUiConfig.get('port', 5001)
        web_root = sfWebUiConfig.get('root', '/')
        cors_origins = sfWebUiConfig.get('cors_origins', [])

        cherrypy.config.update({
            'log.screen': False,
            'server.socket_host': web_host,
            'server.socket_port': int(web_port)
        })

        log.info(f"Starting web server at {web_host}:{web_port} ...")

        # Enable access to static files via the web directory
        conf = {
            '/query': {
                'tools.encode.text_only': False,
                'tools.encode.add_charset': True,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static',
                'tools.staticdir.root': f"{os.path.dirname(os.path.abspath(__file__))}/spiderfoot"
            }
        }

        secrets = dict()
        passwd_file = SpiderFootHelpers.dataPath() + '/passwd'
        if os.path.isfile(passwd_file):
            if not os.access(passwd_file, os.R_OK):
                log.error("Could not read passwd file. Permission denied.")
                sys.exit(-1)

            with open(passwd_file, 'r') as f:
                passwd_data = f.readlines()

            for line in passwd_data:
                if line.strip() == '':
                    continue

                if ':' not in line:
                    log.error(
                        "Incorrect format of passwd file, must be username:password on each line.")
                    sys.exit(-1)

                u = line.strip().split(":")[0]
                p = ':'.join(line.strip().split(":")[1:])

                if not u or not p:
                    log.error(
                        "Incorrect format of passwd file, must be username:password on each line.")
                    sys.exit(-1)

                secrets[u] = p

        if secrets:
            log.info("Enabling authentication based on supplied passwd file.")
            conf['/'] = {
                'tools.auth_digest.on': True,
                'tools.auth_digest.realm': web_host,
                'tools.auth_digest.get_ha1': auth_digest.get_ha1_dict_plain(secrets),
                'tools.auth_digest.key': random.SystemRandom().randint(0, 99999999)
            }
        else:
            warn_msg = "\n********************************************************************\n"
            warn_msg += "Warning: passwd file contains no passwords. Authentication disabled.\n"
            warn_msg += "Please consider adding authentication to protect this instance!\n"
            warn_msg += "Refer to https://github.com/poppopjmp/spiderfoot/wiki. \n"
            warn_msg += "********************************************************************\n"
            log.warning(warn_msg)

        using_ssl = False
        key_path = SpiderFootHelpers.dataPath() + '/spiderfoot.key'
        crt_path = SpiderFootHelpers.dataPath() + '/spiderfoot.crt'
        if os.path.isfile(key_path) and os.path.isfile(crt_path):
            if not os.access(crt_path, os.R_OK):
                log.critical(
                    f"Could not read {crt_path} file. Permission denied.")
                sys.exit(-1)

            if not os.access(key_path, os.R_OK):
                log.critical(
                    f"Could not read {key_path} file. Permission denied.")
                sys.exit(-1)

            log.info("Enabling SSL based on supplied key and certificate file.")
            cherrypy.server.ssl_module = 'builtin'
            cherrypy.server.ssl_certificate = crt_path
            cherrypy.server.ssl_private_key = key_path
            using_ssl = True

        if using_ssl:
            url = "https://"
        else:
            url = "http://"

        if web_host == "0.0.0.0":  # nosec
            url = f"{url}127.0.0.1:{web_port}"
        else:
            url = f"{url}{web_host}:{web_port}{web_root}"
            cors_origins.append(url)

        cherrypy_cors.install()
        cherrypy.config.update({
            'cors.expose.on': True,
            'cors.expose.origins': cors_origins,
            'cors.preflight.origins': cors_origins
        })

        print("")
        print("*************************************************************")
        print(" Use SpiderFoot by starting your web browser of choice and ")
        print(f" browse to {url}")
        print("*************************************************************")
        print("")

        # Disable auto-reloading of content
        cherrypy.engine.autoreload.unsubscribe()

        cherrypy.quickstart(SpiderFootWebUi(
            sfWebUiConfig, sfConfig, loggingQueue), script_name=web_root, config=conf)
    except Exception as e:
        log.critical(
            f"Unhandled exception in start_web_server: {e}", exc_info=True)
        sys.exit(-1)


def handle_abort(signal, frame) -> None:
    """Handle interrupt and abort scan.

    Args:
        signal: TBD
        frame: TBD
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        global dbh
        global scanId

        if scanId and dbh:
            log.info(f"Aborting scan [{scanId}] ...")
            dbh.scanInstanceSet(scanId, None, None, "ABORTED")
        sys.exit(-1)
    except Exception as e:
        log.critical(
            f"Unhandled exception in handle_abort: {e}", exc_info=True)
        sys.exit(-1)


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        print("SpiderFoot usage:")
        print("  Web UI:       python sf.py -l <ip>:<port>")
        print("  FastAPI:      python sf.py --api [--api-listen <ip>:<port>]")
        print("  Both servers: python sf.py --both [-l <ip>:<port>] [--api-listen <ip>:<port>]")
        print("  CLI scan:     python sf.py -s <target> [options]")
        print("Try --help for full guidance.")
        sys.exit(-1)

    main()
