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
from multiprocessing.connection import Listener
import os
import os.path
import signal
import sys
import time
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Optional, Union
import queue

import cherrypy
import cherrypy_cors
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
import uvicorn
from pydantic import BaseModel
try:
    from jose import JWTError, jwt
except ImportError as e:
    print(
        "Error: The 'jose' module is not installed. Please install it using 'pip install python-jose'."
    )
    raise e
from passlib.context import CryptContext

from sfapi import (
    app,
    initialize_spiderfoot,
    handle_database_interactions,
    handle_scan_status,
    handle_correlation_rules,
    handle_logging_and_error_handling,
)
from sflib import SpiderFoot
from sfwebui import SpiderFootWebUi
from spiderfoot import SpiderFootHelpers
from spiderfoot import SpiderFootDb
from spiderfoot import SpiderFootCorrelator
from spiderfoot.logger import logListenerSetup, logWorkerSetup, SafeQueueListener
from spiderfoot.scan_controller import start_spiderfoot_scanner

from spiderfoot.__version__ import __version__

scanId = None
dbh = None

# 'Global' configuration options
# be overridden from saved configuration settings stored in the DB.
sfConfig = {
    "_debug": False,  # Debug
    "_maxthreads": 3,  # Number of modules to run concurrently
    "__logging": True,  # Logging in general
    "__outputfilter": None,  # Event types to filter from modules' output
    # User-Agent to use for HTTP requests
    "_useragent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:62.0) Gecko/20100101 Firefox/62.0",
    "_dnsserver": "",  # Override the default resolver
    "_fetchtimeout": 5,  # number of seconds before giving up on a fetch
    "_internettlds": "https://publicsuffix.org/list/effective_tld_names.dat",
    "_internettlds_cache": 72,
    "_genericusers": ",".join(
        SpiderFootHelpers.usernamesFromWordlists(["generic-usernames"])
    ),
    "__database": f"{SpiderFootHelpers.dataPath()}/spiderfoot.db",
    "__modules__": None,  # List of modules. Will be set after start-up.
    # List of correlation rules. Will be set after start-up.
    "__correlationrules__": None,
    "_socks1type": "",
    "_socks2addr": "",
    "_socks3port": "",
    "_socks4user": "",
    "_socks5pwd": "",
    "_dbtype": "sqlite",  # Database type: sqlite or postgres
    "_dbhost": "localhost",  # PostgreSQL host
    "_dbport": 5432,  # PostgreSQL port
    "_dbname": "spiderfoot",  # PostgreSQL database name
    "_dbuser": "",  # PostgreSQL username
    "_dbpassword": "",  # PostgreSQL password
}
sfOptdescs = {
    "_debug": "Enable debugging?",
    "_maxthreads": "Max number of modules to run concurrently",
    "_useragent": "User-Agent string to use for HTTP requests. Prefix with an '@' to randomly select the User Agent from a file containing user agent strings for each request, e.g. @C:\\useragents.txt or @/home/bob/useragents.txt. Or supply a URL to load the list from there.",
    "_dnsserver": "Override the default resolver with another DNS server. For example, 8.8.8.8 is Google's open DNS server.",
    "_fetchtimeout": "Number of seconds before giving up on a HTTP request.",
    "_internettlds": "List of Internet TLDs.",
    "_internettlds_cache": "Hours to cache the Internet TLD list. This can safely be quite a long time given that the list doesn't change too often.",
    "_genericusers": "List of usernames that if found as usernames or as part of e-mail addresses, should be treated differently to non-generics.",
    "_socks1type": "SOCKS Server Type. Can be '4', '5', 'HTTP' or 'TOR'",
    "_socks2addr": "SOCKS Server IP Address.",
    "_socks3port": "SOCKS Server TCP Port. Usually 1080 for 4/5, 8080 for HTTP and 9050 for TOR.",
    "_socks4user": "SOCKS Username. Valid only for SOCKS4 and SOCKS5 servers.",
    "_socks5pwd": "SOCKS Password. Valid only for SOCKS5 servers.",
    "_modulesenabled": "Modules enabled for the scan.",
    "_dbtype": "Database type: sqlite or postgres",
    "_dbhost": "PostgreSQL host",
    "_dbport": "PostgreSQL port",
    "_dbname": "PostgreSQL database name",
    "_dbuser": "PostgreSQL username",
    "_dbpassword": "PostgreSQL password",
}

# OAuth2 configuration
SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username)
    if user is None:
        raise credentials_exception
    return user


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


@app.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(
        fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# Fake database for demonstration purposes
fake_users_db = {
    "johndoe": {
        "username": "johndoe",
        "full_name": "John Doe",
        "email": "johndoe@example.com",
        "hashed_password": get_password_hash("secret"),
        "disabled": False,
    }
}


class TokenData(BaseModel):
    username: Union[str, None] = None


class User(BaseModel):
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None
    disabled: Union[bool, None] = None


class UserInDB(User):
    hashed_password: str


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


def setup_logging(config: dict) -> queue.Queue:
    """
    Set up logging for SpiderFoot using the customized logger.py implementation.

    Args:
        config (dict): SpiderFoot configuration options

    Returns:
        queue.Queue: The logging queue for passing log records
    """
    try:
        # Create the logging queue
        loggingQueue = queue.Queue(-1)  # No limit on size

        # Set log level based on debug setting
        log_level = logging.DEBUG if config.get(
            "_debug", False) else logging.INFO

        # Disable logging if specified
        if not config.get("__logging", True):
            logging.disable(logging.CRITICAL)
            return loggingQueue

        # Set up the queue handler and listener
        queueHandler = logging.handlers.QueueHandler(loggingQueue)
        handler = logging.StreamHandler()
        handler.setLevel(log_level)

        # Create a formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

        # Set up the queue listener with the handler
        listener = SafeQueueListener(loggingQueue, handler)

        # Configure the root logger to use our queue handler
        logging.basicConfig(level=log_level, handlers=[queueHandler])

        # Start the listener
        listener.start()

        # Set up logListener and logWorker from spiderfoot.logger module
        logListener = logListenerSetup(loggingQueue, config)
        logWorkerSetup(loggingQueue)

        return loggingQueue
    except Exception as e:
        print(f"Failed to set up logging: {e}")
        # Fall back to basic logging in case of failure
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        return queue.Queue(-1)


def main() -> None:
    try:
        # web server config
        sfWebUiConfig = {
            "host": "127.0.0.1",
            "port": 5001,
            "root": "/",
            "cors_origins": [],
        }

        p = argparse.ArgumentParser(
            description=f"SpiderFoot  {__version__}: Open Source Intelligence Automation."
        )
        p.add_argument(
            "-d", "--debug", action="store_true", help="Enable debug output."
        )
        p.add_argument(
            "-l", "--listen", metavar="IP:port", help="IP and port to listen on."
        )
        p.add_argument(
            "-m", metavar="mod1,mod2,...", type=str, help="Modules to enable."
        )
        p.add_argument(
            "-M", "--modules", action="store_true", help="List available modules."
        )
        p.add_argument(
            "-C",
            "--correlate",
            metavar="scanID",
            help="Run correlation rules against a scan ID.",
        )
        p.add_argument("-s", metavar="TARGET", help="Target for the scan.")
        p.add_argument(
            "-t",
            metavar="type1,type2,...",
            type=str,
            help="Event types to collect (modules selected automatically).",
        )
        p.add_argument(
            "-u",
            choices=["all", "footprint", "investigate", "passive"],
            type=str,
            help="Select modules automatically by use case",
        )
        p.add_argument(
            "-T", "--types", action="store_true", help="List available event types."
        )
        p.add_argument(
            "-o",
            choices=["tab", "csv", "json"],
            type=str,
            help="Output format. Tab is default.",
        )
        p.add_argument(
            "-H", action="store_true", help="Don't print field headers, just data."
        )
        p.add_argument("-n", action="store_true",
                       help="Strip newlines from data.")
        p.add_argument(
            "-r",
            action="store_true",
            help="Include the source data field in tab/csv output.",
        )
        p.add_argument(
            "-S",
            metavar="LENGTH",
            type=int,
            help="Maximum data length to display. By default, all data is shown.",
        )
        p.add_argument(
            "-D",
            metavar="DELIMITER",
            type=str,
            help="Delimiter to use for CSV output. Default is ,.",
        )
        p.add_argument(
            "-f",
            action="store_true",
            help="Filter out other event types that weren't requested with -t.",
        )
        p.add_argument(
            "-F",
            metavar="type1,type2,...",
            type=str,
            help="Show only a set of event types, comma-separated.",
        )
        p.add_argument(
            "-x",
            action="store_true",
            help="STRICT MODE. Will only enable modules that can directly consume your target, and if -t was specified only those events will be consumed by modules. This overrides -t and -m options.",
        )
        p.add_argument(
            "-q",
            action="store_true",
            help="Disable logging. This will also hide errors!",
        )
        p.add_argument(
            "-V",
            "--version",
            action="store_true",
            help="Display the version of SpiderFoot and exit.",
        )
        p.add_argument(
            "-max-threads", type=int, help="Max number of modules to run concurrently."
        )
        p.add_argument(
            "--rest-api", action="store_true", help="Start the REST API."
        )  # P9f5e
        p.add_argument(
            "--dbtype",
            choices=["sqlite", "postgres"],
            default="sqlite",
            help="Database type: sqlite or postgres.",
        )
        p.add_argument("--dbhost", type=str, help="PostgreSQL host.")
        p.add_argument("--dbport", type=int, help="PostgreSQL port.")
        p.add_argument("--dbname", type=str, help="PostgreSQL database name.")
        p.add_argument("--dbuser", type=str, help="PostgreSQL username.")
        p.add_argument("--dbpassword", type=str, help="PostgreSQL password.")
        p.add_argument(
            "--enable-oauth", action="store_true", help="Enable OAuth2 authentication."
        )

        args = p.parse_args()  # Parse arguments after defining p

        if args.version:
            print(
                f"SpiderFoot {__version__}: Open Source Intelligence Automation.")
            sys.exit(0)

        if args.max_threads:
            sfConfig["_maxthreads"] = args.max_threads

        if args.debug:
            sfConfig["_debug"] = True
        else:
            sfConfig["_debug"] = False

        if args.q:
            sfConfig["__logging"] = False

        if args.dbtype:
            sfConfig["_dbtype"] = args.dbtype
        if args.dbhost:
            sfConfig["_dbhost"] = args.dbhost
        if args.dbport:
            sfConfig["_dbport"] = args.dbport
        if args.dbname:
            sfConfig["_dbname"] = args.dbname
        if args.dbuser:
            sfConfig["_dbuser"] = args.dbuser
        if args.dbpassword:
            sfConfig["_dbpassword"] = args.dbpassword

        # Initialize the logging system
        logging_queue = (
            mp.Queue(-1)
            if sfConfig.get("__multiprocessing", False)
            else queue.Queue(-1)
        )
        log_listener = logListenerSetup(logging_queue, sfConfig)
        logger = logWorkerSetup(logging_queue)

        # Add queue to config so it can be passed to modules
        sfConfig["__logging_queue"] = logging_queue

        # Set up logging
        loggingQueue = setup_logging(sfConfig)
        log = logging.getLogger(f"spiderfoot.{__name__}")

        # Add descriptions of the global config options
        sfConfig["__globaloptdescs__"] = sfOptdescs

        # Load each module in the modules directory with a .py extension
        try:
            mod_dir = os.path.dirname(os.path.abspath(__file__)) + "/modules/"
            sfModules = SpiderFootHelpers.loadModulesAsDict(
                mod_dir, ["sfp_template.py"]
            )
        except Exception as e:
            log.critical(f"Failed to load modules: {e}", exc_info=True)
            sys.exit(-1)

        if not sfModules:
            log.critical(f"No modules found in modules directory: {mod_dir}")
            sys.exit(-1)

        # Load each correlation rule in the correlations directory with
        # a .yaml extension
        try:
            correlations_dir = (
                os.path.dirname(os.path.abspath(__file__)) + "/correlations/"
            )
            correlationRulesRaw = SpiderFootHelpers.loadCorrelationRulesRaw(
                correlations_dir, ["template.yaml"]
            )
        except Exception as e:
            log.critical(
                f"Failed to load correlation rules: {e}", exc_info=True)
            sys.exit(-1)

        # Initialize database handle
        try:
            if sfConfig["_dbtype"] == "postgres":
                dbh = SpiderFootDb(sfConfig, dbtype="postgres")
            else:
                dbh = SpiderFootDb(sfConfig)
        except Exception as e:
            log.critical(f"Failed to initialize database: {e}", exc_info=True)
            sys.exit(-1)

        # Sanity-check the rules and parse them
        sfCorrelationRules = list()
        if not correlationRulesRaw:
            log.error(
                f"No correlation rules found in correlations directory: {correlations_dir}"
            )
        else:
            try:
                correlator = SpiderFootCorrelator(dbh, correlationRulesRaw)
                sfCorrelationRules = correlator.get_ruleset()
            except Exception as e:
                log.critical(
                    f"Failure initializing correlation rules: {e}", exc_info=True
                )
                sys.exit(-1)

        # Add modules and correlation rules to sfConfig so they can be used elsewhere
        sfConfig["__modules__"] = sfModules
        sfConfig["__correlationrules__"] = sfCorrelationRules

        if args.correlate:
            if not correlationRulesRaw:
                log.error(
                    "Unable to perform correlations as no correlation rules were found."
                )
                sys.exit(-1)

            try:
                log.info(
                    f"Running {len(correlationRulesRaw)} correlation rules against scan, {args.correlate}."
                )
                corr = SpiderFootCorrelator(
                    dbh, correlationRulesRaw, args.correlate)
                corr.run_correlations()
            except Exception as e:
                log.critical(
                    f"Unable to run correlation rules: {e}", exc_info=True)
                sys.exit(-1)
            sys.exit(0)

        if args.modules:
            log.info("Modules available:")
            for m in sorted(sfModules.keys()):
                if "__" in m:
                    continue
                print(f"{m.ljust(25)}  {sfModules[m]['descr']}")
            sys.exit(0)

        if args.types:
            dbh = SpiderFootDb(sfConfig, init=True)
            log.info("Types available:")
            typedata = dbh.eventTypes()
            types = dict()
            for r in typedata:
                types[r[1]] = r[0]

            for t in sorted(types.keys()):
                print(f"{t.ljust(45)}  {types[t]}")
            sys.exit(0)

        if args.listen:
            try:
                (host, port) = args.listen.split(":")
            except Exception:
                log.critical("Invalid ip:port format.")
                sys.exit(-1)

            sfWebUiConfig["host"] = host
            sfWebUiConfig["port"] = port

            start_web_server(sfWebUiConfig, sfConfig,
                             loggingQueue, args.enable_oauth)
            sys.exit(0)

        if args.rest_api:  # P217d
            start_rest_api_server(args.enable_oauth)  # P217d
            log.info("REST API server started successfully.")
            sys.exit(0)

        start_scan(sfConfig, sfModules, args, loggingQueue)

        # Stop the listener when done
        Listener.stop()

    except Exception as e:
        log.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(-1)


def start_scan(sfConfig: dict, sfModules: dict, args, loggingQueue) -> None:
    """
    Start a scan based on the provided configuration and command-line arguments.

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

        if sfConfig["__logging"]:
            log.info(f"Modules enabled ({len(modlist)}): {','.join(modlist)}")

        cfg = sf.configUnserialize(dbh.configGet(), sfConfig)

        # Debug mode is a variable that gets stored to the DB, so re-apply it
        if args.debug:
            cfg["_debug"] = True
        else:
            cfg["_debug"] = False

        # If strict mode is enabled, filter the output from modules.
        if args.x and args.t:
            cfg["__outputfilter"] = args.t.split(",")

        prepare_scan_output(args)

        execute_scan(loggingQueue, target, targetType, modlist, cfg, log)

        return
    except Exception as e:
        log.critical(f"Unhandled exception in start_scan: {e}", exc_info=True)
        sys.exit(-1)


def validate_arguments(args, log):
    if not args.s:
        log.error(
            "You must specify a target when running in scan mode. Try --help for guidance."
        )
        sys.exit(-1)

    if args.x and not args.t:
        log.error("-x can only be used with -t. Use --help for guidance.")
        sys.exit(-1)

    if args.x and args.m:
        log.error(
            "-x can only be used with -t and not with -m. Use --help for guidance."
        )
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
        target = f'"{target}"'
    if "." not in target and not target.startswith("+") and '"' not in target:
        target = f'"{target}"'
    targetType = SpiderFootHelpers.targetTypeFromString(target)

    if not targetType:
        log.error(f"Could not determine target type. Invalid target: {target}")
        sys.exit(-1)

    target = target.strip('"')
    return target, targetType


def prepare_modules(args, sf, sfModules, log, targetType):
    """
    Prepare the list of modules to be used in the scan based on the provided arguments.

    Args:
        args (argparse.Namespace): Command-line arguments.
        sf (SpiderFoot): SpiderFoot instance.
        sfModules (dict): Dictionary of available modules.
        log (logging.Logger): Logger instance.
        targetType (str): Type of the target.

    Returns:
        list: List of modules to be used in the scan.
    """
    modlist = list()
    if not args.t and not args.m and not args.u:
        log.warning(
            "You didn't specify any modules, types or use case, so all modules will be enabled."
        )
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

    # Select modules if the user selected use case
    if args.u:
        # Make the first letter uppercase
        usecase = args.u[0].upper() + args.u[1:]
        for mod in sfConfig["__modules__"]:
            if usecase == "All" or usecase in sfConfig["__modules__"][mod]["group"]:
                modlist.append(mod)

    # Add sfp__stor_stdout to the module list
    typedata = dbh.eventTypes()
    types = dict()
    for r in typedata:
        types[r[1]] = r[0]

    # Configure options for the sfp__stor_stdout module
    sfp__stor_stdout_opts = sfConfig["__modules__"]["sfp__stor_stdout"]["opts"]
    sfp__stor_stdout_opts["_eventtypes"] = types

    # Handle command-line arguments for filtering and output formatting
    if args.f:
        if args.f and not args.t:
            log.error("You can only use -f with -t. Use --help for guidance.")
            sys.exit(-1)
        sfp__stor_stdout_opts["_showonlyrequested"] = True

    if args.F:
        sfp__stor_stdout_opts["_requested"] = args.F.split(",")
        sfp__stor_stdout_opts["_showonlyrequested"] = True

    if args.o:
        if args.o not in ["tab", "csv", "json"]:
            log.error(
                "Invalid output format selected. Must be 'tab', 'csv' or 'json'.")
            sys.exit(-1)
        sfp__stor_stdout_opts["_format"] = args.o

    if args.t:
        sfp__stor_stdout_opts["_requested"] = args.t.split(",")

    if args.n:
        sfp__stor_stdout_opts["_stripnewline"] = True

    if args.r:
        sfp__stor_stdout_opts["_showsource"] = True

    if args.S:
        sfp__stor_stdout_opts["_maxlength"] = args.S

    if args.D:
        sfp__stor_stdout_opts["_csvdelim"] = args.D

    # Handle strict mode (-x) for module selection
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
                if not sfModules[mod]["provides"]:
                    continue
                if r in sfModules[mod].get("provides", []) and mod not in modlist:
                    modlist.append(mod)

    return modlist


def prepare_scan_output(args):
    """
    Prepare the output format for the scan results based on command-line arguments.

    Args:
        args (argparse.Namespace): Command-line arguments.
    """
    if args.o == "json":
        print("[", end="")
    elif not args.H:
        delim = "\t"

        if args.o == "tab":
            delim = "\t"

        if args.o == "csv":
            if args.D:
                delim = args.D
            else:
                delim = ","

        # Include headers if requested
        if args.r:
            if delim == "\t":
                headers = delim.join(
                    ["Source".ljust(30), "Type".ljust(45),
                     "Source Data", "Data"]
                )
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
        p = mp.Process(
            target=start_spiderfoot_scanner,
            args=(loggingQueue, scanName, scanId,
                  target, targetType, modlist, cfg),
        )
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
            if p.is_alive():
                log.error(
                    f"Timeout reached ({timeout}s) waiting for scan {scanId} post-processing to complete."
                )
                sys.exit(-1)

            if sfConfig["__logging"]:
                log.info(f"Scan completed with status {info[5]}")
            sys.exit(0)


def start_web_server(
    sfWebUiConfig: dict, sfConfig: dict, loggingQueue=None, enable_oauth=False
) -> None:
    """
    Start the web server so you can start looking at results

    Args:
        sfWebUiConfig (dict): web server options
        sfConfig (dict): SpiderFoot config options
        loggingQueue (Queue): main SpiderFoot logging queue
        enable_oauth (bool): Flag to enable or disable OAuth2 authentication
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        web_host = sfWebUiConfig.get("host", "127.0.0.1")
        web_port = sfWebUiConfig.get("port", 5001)
        web_root = sfWebUiConfig.get("root", "/")
        cors_origins = sfWebUiConfig.get("cors_origins", [])

        cherrypy.config.update(
            {
                "log.screen": False,
                "server.socket_host": web_host,
                "server.socket_port": int(web_port),
            }
        )

        log.info(f"Starting web server at {web_host}:{web_port} ...")

        # Enable access to static files via the web directory
        conf = {
            "/query": {
                "tools.encode.text_only": False,
                "tools.encode.add_charset": True,
            },
            "/static": {
                "tools.staticdir.on": True,
                "tools.staticdir.dir": "static",
                "tools.staticdir.root": f"{os.path.dirname(os.path.abspath(__file__))}/spiderfoot",
            },
        }

        using_ssl = False
        key_path = SpiderFootHelpers.dataPath() + "/spiderfoot.key"
        crt_path = SpiderFootHelpers.dataPath() + "/spiderfoot.crt"
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
            cherrypy.server.ssl_module = "builtin"
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
        cherrypy.config.update(
            {
                "cors.expose.on": True,
                "cors.expose.origins": cors_origins,
                "cors.preflight.origins": cors_origins,
            }
        )

        print("")
        print("*************************************************************")
        print(" Use SpiderFoot by starting your web browser of choice and ")
        print(f" browse to {url}")
        print("*************************************************************")
        print("")

        # Disable auto-reloading of content
        cherrypy.engine.autoreload.unsubscribe()

        # Set up queue listener if we have a logging queue
        if loggingQueue:
            queueListener = logging.handlers.QueueListener(
                loggingQueue, *log.handlers)
            queueListener.start()

        log.info(f"Starting web server at {web_host}:{web_port} ...")

        cherrypy.quickstart(
            SpiderFootWebUi(sfWebUiConfig, sfConfig, loggingQueue),
            script_name=web_root,
            config=conf,
        )
    except Exception as e:
        log.critical(
            f"Unhandled exception in start_web_server: {e}", exc_info=True)
        sys.exit(-1)


def handle_abort(signal, frame) -> None:
    """
    Handle interrupt and abort scan.

    Args:
        signal: Signal number.
        frame: Current stack frame.
    """
    try:
        log = logging.getLogger(f"spiderfoot.{__name__}")

        global dbh
        global scanId

        # Check if scanId and dbh are set
        if scanId and dbh:
            log.info(f"Aborting scan [{scanId}] ...")
            # Update scan status to "ABORTED"
            dbh.scanInstanceSet(scanId, None, None, "ABORTED")
        sys.exit(-1)
    except Exception as e:
        log.critical(
            f"Unhandled exception in handle_abort: {e}", exc_info=True)
        sys.exit(-1)


def check_rest_api_implementation() -> None:
    """
    Check if the implementation of the REST API is aligned and correctly linked to the core SpiderFoot functionality.
    """
    import requests

    log = logging.getLogger(f"spiderfoot.{__name__}")

    time.sleep(10)

    api_endpoints = [
        "/start_scan",
        "/stop_scan/{scan_id}",
        "/scan_results/{scan_id}",
        "/modules",
        "/active_scans",
        "/scan_status/{scan_id}",
        "/scan_history",
        "/export_scan_results/{scan_id}",
        "/import_api_key",
        "/export_api_keys",
        "/scan_correlations/{scan_id}",
        "/scan_logs/{scan_id}",
        "/scan_summary/{scan_id}",
    ]

    base_url = "http://127.0.0.1:8000"

    for endpoint in api_endpoints:
        try:
            response = requests.options(f"{base_url}{endpoint}")
            if response.status_code != 200:
                log.error(
                    f"Endpoint {endpoint} is not correctly linked. Status code: {response.status_code}"
                )
        except Exception as e:
            log.error(f"Error checking endpoint {endpoint}: {e}")


def start_rest_api_server(enable_oauth=False) -> None:  # P3926
    """
    Start the REST API server using FastAPI.

    This function initializes and starts the REST API server using FastAPI.
    The server will listen on all available network interfaces (0.0.0.0) and port 8000.
    """
    initialize_spiderfoot()
    handle_database_interactions()
    handle_scan_status()
    handle_correlation_rules()
    handle_logging_and_error_handling()

    log = logging.getLogger(f"spiderfoot.{__name__}")

    uvicorn.run(app, host="0.0.0.0", port=8000)  # P3926
    check_rest_api_implementation()


def generate_openapi_schema() -> dict:
    """
    Generate the OpenAPI schema for the SpiderFoot API.

    This function generates the OpenAPI schema for the SpiderFoot API using FastAPI's get_openapi utility.

    Returns:
        dict: The OpenAPI schema.
    """
    return get_openapi(
        title="SpiderFoot API",
        version=__version__,
        description="API documentation for SpiderFoot",
        routes=app.routes,
    )


def serve_swagger_ui() -> None:
    """
    Serve the Swagger UI for the SpiderFoot API.

    This function serves the Swagger UI for the SpiderFoot API using FastAPI's get_swagger_ui_html utility.
    """
    app = FastAPI()

    @app.get("/docs", response_class=HTMLResponse)
    async def get_swagger_ui():
        return get_swagger_ui_html(openapi_url="/openapi.json", title="SpiderFoot API")


if __name__ == "__main__":
    if sys.version_info < (3, 9):
        print("SpiderFoot requires Python 3.9 or higher.")
        sys.exit(-1)

    if len(sys.argv) <= 1:
        print(
            "SpiderFoot requires -l <ip>:<port> to start the web server. Try --help for guidance."
        )
        sys.exit(-1)

    from pathlib import Path

    if os.path.exists("spiderfoot.db"):
        print(
            f"ERROR: spiderfoot.db file exists in {os.path.dirname(__file__)}")
        print(
            f"The database is now loaded from your home directory: {Path.home()}/.spiderfoot/spiderfoot.db"
        )
        print(
            f"This message will go away once you move or remove spiderfoot.db from {os.path.dirname(__file__)}"
        )
        sys.exit(-1)

    from pathlib import Path

    if os.path.exists("passwd"):
        print(f"ERROR: passwd file exists in {os.path.dirname(__file__)}")
        print(
            f"The passwd file is now loaded from your home directory: {Path.home()}/.spiderfoot/passwd"
        )
        print(
            f"This message will go away once you move or remove passwd from {os.path.dirname(__file__)}"
        )
        sys.exit(-1)

    main()
