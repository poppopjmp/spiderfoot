#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:        sfcli
# Purpose:     Command Line Interface for SpiderFoot.
#
# Author:      Steve Micallef <steve@binarypool.com>
#
# Created:     03/05/2017
# Copyright:   (c) Steve Micallef 2017
# Licence:     MIT
# -------------------------------------------------------------------------------

import argparse
import sys
import os
import cmd
import codecs
import io
import json
import re
import shlex
import time
from os.path import expanduser
import difflib

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from spiderfoot import __version__
from spiderfoot.cli.config import CLIConfig
from spiderfoot.cli.output import bcolors
from spiderfoot.cli.banner import ASCII_LOGO, COPYRIGHT_INFO
from spiderfoot.cli.commands import CommandRegistry, load_all_commands


try:
    import readline
    if hasattr(readline, 'parse_and_bind'):
        readline.parse_and_bind('tab: complete')
        # Enable Ctrl+R reverse search if available
        try:
            readline.parse_and_bind(r'"\\C-r": reverse-search-history')
        except Exception:
            pass
except Exception:
    try:
        import pyreadline as readline
    except Exception:
        readline = None  # Continue without readline if unavailable


class SpiderFootCli(cmd.Cmd):
    version = __version__  # Dynamically get version from central location
    pipecmd = None
    output = None
    modules = []
    types = []
    correlationrules = []
    prompt = "sf> "
    nohelp = "[!] Unknown command '%s'."
    knownscans = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = CLIConfig()
        self.registry = CommandRegistry()
        load_all_commands(self.registry)
        self._init_dynamic_completions()
        self._init_inline_help()

    def _init_dynamic_completions(self):
        """Initialize dynamic completion lists by querying the API."""
        try:
            # Preload modules, types, workspaces, targets, scan IDs
            self.modules = self._fetch_api_list('/api/modules')
            self.types = self._fetch_api_list('/api/types')
            self.workspaces = self._fetch_api_list('/api/workspaces')
            self.targets = self._fetch_api_list('/api/targets')
            self.knownscans = self._fetch_api_list('/api/scans')
        except Exception:
            pass

    def _fetch_api_list(self, endpoint):
        """Helper to fetch a list from the API."""
        result = self.request(endpoint)
        if not result:
            return []
        try:
            data = json.loads(result)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and 'data' in data:
                return data['data']
        except Exception:
            return []
        return []

    def _init_inline_help(self):
        """Prepare inline help mapping for commands."""
        self.inline_help = {}
        for cmd, entry in self.registry.commands.items():
            doc = entry.get('func').__doc__
            if doc:
                self.inline_help[cmd] = doc.strip().split('\n')[0]

    # Auto-complete for these commands
    def complete_start(self, text, line, startidx, endidx):
        return self.complete_default(text, line, startidx, endidx)

    def complete_find(self, text, line, startidx, endidx):
        return self.complete_default(text, line, startidx, endidx)

    def complete_data(self, text, line, startidx, endidx):
        return self.complete_default(text, line, startidx, endidx)

    # Command completion for arguments
    def complete_default(self, text, line, startidx, endidx):
        ret = list()

        if not isinstance(text, str):
            return ret

        if not isinstance(line, str):
            return ret

        if "-m" in line and line.find("-m") > line.find("-t"):
            for m in self.modules:
                if m.startswith(text):
                    ret.append(m)

        if "-t" in line and line.find("-t") > line.find("-m"):
            for t in self.types:
                if t.startswith(text):
                    ret.append(t)
        return ret

    def dprint(self, msg, err=False, deb=False, plain=False, color=None):
        cout = ""
        sout = ""
        pfx = ""
        col = ""
        if err:
            pfx = "[!]"
            if self.config['cli.color']:
                col = bcolors.DARKRED
        else:
            pfx = "[*]"
            if self.config['cli.color']:
                col = bcolors.DARKGREEN
        if deb:
            if not self.config["cli.debug"]:
                return
            pfx = "[+]"
            if self.config['cli.color']:
                col = bcolors.GREY

        if color:
            pfx = ""
            col = color

        if err or not self.config["cli.silent"]:
            if not plain or color:
                cout = col + bcolors.BOLD + pfx + " " + bcolors.ENDC + col + msg + bcolors.ENDC
                sout = pfx + " " + msg
            else:
                cout = msg
                sout = msg

            print(cout)

        if self.config['cli.spool']:
            f = codecs.open(
                self.config['cli.spool_file'], "a", encoding="utf-8")
            f.write(sout)
            f.write('\n')
            f.close()

    # Shortcut commands
    def do_debug(self, line):
        """Debug Short-cut command for set cli.debug = 1."""
        if self.config['cli.debug']:
            val = "0"
        else:
            val = "1"
        return self.do_set("cli.debug = " + val)

    def do_spool(self, line):
        """Spool Short-cut command for set cli.spool = 1/0."""
        if self.config['cli.spool']:
            val = "0"
        else:
            val = "1"

        if self.config['cli.spool_file']:
            return self.do_set("cli.spool = " + val)

        self.edprint(
            "You haven't set cli.spool_file. Set that before enabling spooling.")

        return None

    def do_history(self, line):
        """History [-l] Short-cut command for set cli.history = 1/0.

        Add -l to just list the history.
        """
        c = self.myparseline(line)

        if '-l' in c[0]:
            i = 0
            while i < readline.get_current_history_length():
                self.dprint(readline.get_history_item(i), plain=True)
                i += 1
            return None

        if self.config['cli.history']:
            val = "0"
        else:
            val = "1"

        return self.do_set("cli.history = " + val)

    # Run before all commands to handle history and spooling
    def precmd(self, line):
        # Show inline help for the command as the user types
        if hasattr(self, 'inline_help') and readline and line:
            try:
                cmd = shlex.split(line)[0]
                if cmd in self.inline_help:
                    print(f"\n[HELP] {cmd}: {self.inline_help[cmd]}")
            except Exception:
                pass
        if self.config['cli.history'] and line != "EOF":
            f = codecs.open(
                self.config["cli.history_file"], "a", encoding="utf-8")
            f.write(line)
            f.write('\n')
            f.close()
        if self.config['cli.spool']:
            f = codecs.open(
                self.config["cli.spool_file"], "a", encoding="utf-8")
            f.write(self.prompt + line)
            f.write('\n')
            f.close()

        return line

    # Debug print
    def ddprint(self, msg):
        self.dprint(msg, deb=True)

    # Error print
    def edprint(self, msg):
        self.dprint(msg, err=True)
        # If the error is about an unknown command, suggest similar ones
        if isinstance(msg, str) and msg.startswith("[!] Unknown command"):
            cmd = msg.split("'")[1] if "'" in msg else None
            if cmd:
                suggestions = difflib.get_close_matches(cmd, self.registry.all_commands(), n=3)
                if suggestions:
                    self.dprint(f"Did you mean: {', '.join(suggestions)}?", err=True)

    # Print nice tables.
    def pretty(self, data, titlemap=None):
        if not data:
            return ""

        out = list()
        # Get the column titles
        maxsize = dict()
        if isinstance(data[0], dict):
            cols = list(data[0].keys())
        else:
            # for lists, use the index numbers as titles
            cols = list(map(str, list(range(0, len(data[0])))))

        # Strip out columns that don't have titles
        if titlemap:
            nc = list()
            for c in cols:
                if c in titlemap:
                    nc.append(c)
            cols = nc

        spaces = 2
        # Find the maximum column sizes
        for r in data:
            for i, c in enumerate(r):
                if isinstance(r, list):
                    # we have  list index
                    cn = str(i)
                    if isinstance(c, int):
                        v = str(c)
                    if isinstance(c, str):
                        v = c
                else:
                    # we have a dict key
                    cn = c
                    v = str(r[c])
                # print(str(cn) + ", " + str(c) + ", " + str(v))
                if len(v) > maxsize.get(cn, 0):
                    maxsize[cn] = len(v)

        # Adjust for long titles
        if titlemap:
            for c in maxsize:
                if len(titlemap.get(c, c)) > maxsize[c]:
                    maxsize[c] = len(titlemap.get(c, c))

        # Display the column titles
        for i, c in enumerate(cols):
            if titlemap:
                t = titlemap.get(c, c)
            else:
                t = c
            # out += t
            out.append(t)
            sdiff = maxsize[c] - len(t) + 1
            # out += " " * spaces
            out.append(" " * spaces)
            if sdiff > 0 and i < len(cols) - 1:
                # out += " " * sdiff
                out.append(" " * sdiff)
        # out += "\n"
        out.append('\n')

        # Then the separator
        for i, c in enumerate(cols):
            # out += "-" * ((maxsize[c]+spaces))
            out.append("-" * ((maxsize[c] + spaces)))
            if i < len(cols) - 1:
                # out += "+"
                out.append("+")
        # out += "\n"
        out.append("\n")

        # Then the actual data
        # ts = time.time()
        for r in data:
            i = 0
            di = 0
            tr = type(r)
            for c in r:
                if tr == list:
                    # we have  list index
                    cn = str(i)
                    tc = type(c)
                    if tc == int:
                        v = str(c)
                    if tc == str:
                        v = c
                else:
                    # we have a dict key
                    cn = c
                    v = str(r[c])
                if cn not in cols:
                    i += 1
                    continue

                out.append(v)
                lv = len(v)
                # there is a preceeding space if this is after the
                # first column
                # sdiff = number of spaces between end of word and |
                if di == 0:
                    sdiff = (maxsize[cn] - lv) + spaces
                else:
                    sdiff = (maxsize[cn] - lv) + spaces - 1
                if di < len(cols) - 1:
                    # out += " " * sdiff
                    out.append(" " * sdiff)
                if di < len(cols) - 1:
                    # out += "| "
                    out.append("| ")
                di += 1
                i += 1
            # out += "\n"
            out.append("\n")

        # print("time: " + str(time.time() - ts))
        return ''.join(out)

    # Make a request to the SpiderFoot server
    def request(self, url, post=None):
        from spiderfoot.cli.network import SpiderFootApiClient
        api_client = SpiderFootApiClient(self.config)
        # Show progress indicator for long-running API calls
        import threading
        import sys
        stop_spinner = [False]
        def spinner():
            i = 0
            chars = '|/-\\'
            while not stop_spinner[0]:
                sys.stdout.write(f'\r[API] Working... {chars[i % len(chars)]}')
                sys.stdout.flush()
                time.sleep(0.1)
                i += 1
            sys.stdout.write('\r' + ' ' * 30 + '\r')
            sys.stdout.flush()
        t = threading.Thread(target=spinner)
        t.daemon = True
        t.start()
        try:
            try:
                result = api_client.request(url, post=post)
            except Exception as e:
                self.edprint(f"Failed communicating with server: {url}\nReason: {e}")
                result = None
        finally:
            stop_spinner[0] = True
            t.join()
        if result is None:
            self.edprint(f"Failed communicating with server: {url}")
        return result

    def emptyline(self):
        return

    def completedefault(self, text, line, begidx, endidx):
        # Enhanced dynamic completion for scan IDs, modules, workspaces, targets
        tokens = shlex.split(line[:begidx])
        if not tokens:
            return []
        last = tokens[-1]
        if last in ('-m', '--module'):
            return [m for m in self.modules if m.startswith(text)]
        if last in ('-t', '--type'):
            return [t for t in self.types if t.startswith(text)]
        if last in ('-w', '--workspace'):
            return [w for w in self.workspaces if w.startswith(text)]
        if last in ('-T', '--target'):
            return [t for t in self.targets if t.startswith(text)]
        if last in ('-s', '--scan'):
            return [s for s in self.knownscans if s.startswith(text)]
        # Fallback to command names
        return [c for c in self.registry.all_commands() if c.startswith(text)]

    # Parse the command line, returns a list of lists:
    # sf> scans "blahblah test" | top 10 | grep foo ->
    # [[ 'blahblah test' ], [[ 'top', '10' ], [ 'grep', 'foo']]]
    def myparseline(self, cmdline, replace=True):
        ret = [list(), list()]

        if not cmdline:
            return ret

        try:
            s = shlex.split(cmdline)
        except Exception as e:
            self.edprint(f"Error parsing command: {e}")
            return ret

        for c in s:
            if c == '|':
                break
            if replace and c.startswith("$") and c in self.config:
                ret[0].append(self.config[c])
            else:
                ret[0].append(c)

        if s.count('|') == 0:
            return ret

        # Handle any pipe commands at the end
        ret[1] = list()
        i = 0
        ret[1].append(list())
        for t in s[(s.index('|') + 1):]:
            if t == '|':
                i += 1
                ret[1].append(list())
            # Replace variables
            elif t.startswith("$") and t in self.config:
                ret[1][i].append(self.config[t])
            else:
                ret[1][i].append(t)

        return ret

    # Send the command output to the user, processing the pipes
    # that may have been used.
    def send_output(self, data, cmd, titles=None, total=True, raw=False):
        from spiderfoot.cli.output import pretty_table
        out = None
        try:
            if raw:
                j = data
                totalrec = 0
            else:
                j = json.loads(data)
                totalrec = len(j)
        except Exception as e:
            # Try to show API error details if present
            try:
                err = json.loads(data)
                if isinstance(err, dict) and 'error' in err:
                    self.edprint(f"API error: {err['error'].get('message', err['error'])}")
                    return
            except Exception:
                pass
            self.edprint(f"Unable to parse data from server: {e}")
            return

        if raw:
            out = data
        else:
            if self.config['cli.output'] == "json":
                out = json.dumps(j, indent=4, separators=(',', ': '))
            elif self.config['cli.output'] == "pretty":
                out = pretty_table(j, titlemap=titles)
            else:
                self.edprint(
                    f"Unknown output format '{self.config['cli.output']}'.")
                return

        c = self.myparseline(cmd)

        # If no pipes, just display the output
        if len(c[1]) == 0:
            self.dprint(out, plain=True)
            if total:
                self.dprint(f"Total records: {totalrec}")
            return

        for pc in c[1]:
            newout = ""
            if len(pc) == 0:
                self.edprint("Invalid syntax.")
                return
            pipecmd = pc[0]
            pipeargs = " ".join(pc[1:])
            if pipecmd not in ["str", "regex", "file", "grep", "top", "last"]:
                self.edprint("Unrecognised pipe command.")
                return

            if pipecmd == "regex":
                p = re.compile(pipeargs, re.IGNORECASE)
                for r in out.split("\n"):
                    if re.match(p, r.strip()):
                        newout += r + "\n"

            if pipecmd in ['str', 'grep']:
                for r in out.split("\n"):
                    if pipeargs.lower() in r.strip().lower():
                        newout += r + "\n"

            if pipecmd == "top":
                if not pipeargs.isdigit():
                    self.edprint("Invalid syntax.")
                    return
                newout = "\n".join(out.split("\n")[0:int(pipeargs)])

            if pipecmd == "last":
                if not pipeargs.isdigit():
                    self.edprint("Invalid syntax.")
                    return
                tot = len(out.split("\n"))
                i = tot - int(pipeargs)
                newout = "\n".join(out.split("\n")[i:])

            if pipecmd == "file":
                try:
                    f = codecs.open(pipeargs, "w", encoding="utf-8")
                    f.write(out)
                    f.close()
                except Exception as e:
                    self.edprint(f"Unable to write to file: {e}")
                    return
                self.dprint(f"Successfully wrote to file '{pipeargs}'.")
                return

            out = newout

        self.dprint(newout, plain=True)

    # Modular command dispatch
    def default(self, line):
        try:
            cmd, *args = shlex.split(line)
        except Exception as e:
            self.edprint(f"[!] Command parse error: {e}")
            return
        entry = self.registry.get(cmd)
        if entry:
            try:
                entry['func'](self, line)
            except Exception as e:
                self.edprint(f"[!] Command error: {e}")
        else:
            self.edprint(self.nohelp % cmd)

    # Legacy command methods for backward compatibility (can be removed if not needed)
    def do_ping(self, line):
        entry = self.registry.get("ping")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "ping")

    def do_scans(self, line):
        entry = self.registry.get("scans")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "scans")

    def do_modules(self, line, cacheonly=False):
        entry = self.registry.get("modules")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "modules")

    def do_types(self, line, cacheonly=False):
        entry = self.registry.get("types")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "types")

    def do_correlationrules(self, line, cacheonly=False):
        entry = self.registry.get("correlationrules")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "correlationrules")

    def do_data(self, line):
        entry = self.registry.get("data")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "data")

    def do_export(self, line):
        entry = self.registry.get("export")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "export")

    def do_logs(self, line):
        entry = self.registry.get("logs")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "logs")

    def do_start(self, line):
        entry = self.registry.get("start")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "start")

    def do_stop(self, line):
        entry = self.registry.get("stop")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "stop")

    def do_delete(self, line):
        entry = self.registry.get("delete")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "delete")

    def do_scaninfo(self, line):
        entry = self.registry.get("scaninfo")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "scaninfo")

    def do_correlations(self, line):
        entry = self.registry.get("correlations")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "correlations")

    def do_summary(self, line):
        entry = self.registry.get("summary")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "summary")

    def do_find(self, line):
        entry = self.registry.get("find")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "find")

    def do_query(self, line):
        entry = self.registry.get("query")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "query")

    def do_set(self, line):
        entry = self.registry.get("set")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "set")

    def do_help(self, line):
        entry = self.registry.get("help")
        if entry:
            entry['func'](self, line)
        else:
            self.edprint(self.nohelp % "help")

    # Execute a shell command locally and return the output
    def do_shell(self, line):
        """Shell Run a shell command locally."""
        self.dprint("Running shell command:" + str(line))
        self.dprint(os.popen(line).read(), plain=True)  # noqa: DUO106

    def do_clear(self, line):
        """Clear Clear the screen."""
        sys.stderr.write("\x1b[2J\x1b[H")

    # Exit the CLI
    def do_exit(self, line):
        """Exit Exit the SpiderFoot CLI."""
        return True

    # Ctrl-D
    def do_EOF(self, line):
        """EOF (Ctrl-D) Exit the SpiderFoot CLI."""
        print("\n")
        return True

    def preloop(self):
        # Backward compatibility: load history if enabled and readline is available
        if hasattr(self.config, 'get') and self.config.get('cli.history', True) and readline:
            try:
                with codecs.open(self.config.get('cli.history_file', ''), "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        readline.add_history(line.strip())
            except Exception:
                pass
        super().preloop()

    def postcmd(self, stop, line):
        # Backward compatibility: save history if enabled and readline is available
        if hasattr(self.config, 'get') and self.config.get('cli.history', True) and readline and line.strip():
            try:
                with codecs.open(self.config.get('cli.history_file', ''), "a", encoding="utf-8") as f:
                    f.write(line.strip() + '\n')
            except Exception:
                pass
        return super().postcmd(stop, line)

    def cmdloop(self, intro=None):
        # Guarantee interactive CLI experience
        if sys.stdin.isatty():
            super().cmdloop(intro=intro)
        else:
            # Non-interactive mode (e.g. piped input)
            for line in sys.stdin:
                self.onecmd(line)


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description='SpiderFoot: Open Source Intelligence Automation.')
    p.add_argument("-d", "--debug", help="Enable debug output.",
                   action='store_true')
    p.add_argument("-s", metavar="URL", type=str,
                   help="Connect to SpiderFoot server on URL. By default, a connection to http://127.0.0.1:8001 will be attempted.")
    p.add_argument("-u", metavar="USER", type=str,
                   help="Username to authenticate to SpiderFoot server.")
    p.add_argument("-p", metavar="PASS", type=str,
                   help="Password to authenticate to SpiderFoot server. Consider using -P PASSFILE instead so that your password isn't visible in your shell history or in process lists!")
    p.add_argument("-P", metavar="PASSFILE", type=str,
                   help="File containing password to authenticate to SpiderFoot server. Ensure permissions on the file are set appropriately!")
    p.add_argument("-e", metavar="FILE", type=str,
                   help="Execute commands from FILE.")
    p.add_argument("-l", metavar="FILE", type=str,
                   help="Log command history to FILE. By default, history is stored to ~/.spiderfoot_history unless disabled with -n.")
    p.add_argument("-n", action='store_true', help="Disable history logging.")
    p.add_argument("-o", metavar="FILE", type=str,
                   help="Spool commands and output to FILE.")
    p.add_argument(
        "-i", help="Allow insecure server connections when using SSL", action='store_true')
    p.add_argument(
        "-q", help="Silent output, only errors reported.", action='store_true')
    p.add_argument("-k", help="Turn off color-coded output.",
                   action='store_true')
    p.add_argument(
        "-b", "-v", help="Print the banner w/ version and exit.", action='store_true')

    args = p.parse_args()

    config = CLIConfig()

    # Map command-line to config
    if args.u:
        config['cli.username'] = args.u
    if args.p:
        config['cli.password'] = args.p
    if args.P:
        try:
            with open(args.P, 'r') as f:
                config['cli.password'] = f.readlines()[0].strip('\n')
        except Exception as e:
            print(f"Unable to open {args.P}: ({e})")
            sys.exit(-1)
    if args.i:
        config['cli.ssl_verify'] = False
    if args.k:
        config['cli.color'] = False
    if args.s:
        config['cli.server_baseurl'] = args.s
    if args.debug:
        config['cli.debug'] = True
    if args.q:
        config['cli.silent'] = True
    if args.n:
        config['cli.history'] = False
    if args.l:
        config['cli.history_file'] = args.l
    else:
        try:
            config['cli.history_file'] = expanduser(
                "~") + "/.spiderfoot_history"
        except Exception as e:
            print(f"Failed to set 'cli.history_file': {e}")
            print("Using '.spiderfoot_history' in working directory")
            config['cli.history_file'] = ".spiderfoot_history"
    if args.o:
        config['cli.spool'] = True
        config['cli.spool_file'] = args.o

    # Load commands from a file
    if args.e:
        try:
            with open(args.e, 'r') as f:
                cin = f.read()
        except Exception as e:
            print(f"Unable to open {args.e}: ({e})")
            sys.exit(-1)
    else:
        cin = sys.stdin
    s = SpiderFootCli(stdin=cin)
    s.identchars += "$"
    s.config = config

    # Debug: print registered commands
    print("[DEBUG] Registered commands:", list(s.registry.all_commands()))

    # Banner and version output
    if not args.q:
        s.dprint(ASCII_LOGO, plain=True, color=bcolors.GREYBLUE)
        s.dprint(COPYRIGHT_INFO, plain=True, color=bcolors.GREYBLUE_DARK)
        s.dprint(f"Version {s.version}.")
        if args.b:
            sys.exit(0)

    # Test connectivity to the server
    s.do_ping("")

    if not args.n:
        try:
            f = codecs.open(
                s.config['cli.history_file'], "r", encoding="utf-8")
            for line in f.readlines():
                pass  # History loading to be modularized
            s.dprint("Loaded previous command history.")
        except Exception:
            pass

    # Run CLI
    if args.e or not os.isatty(0):
        try:
            s.use_rawinput = False
            s.prompt = ""
            s.cmdloop()
        finally:
            if args.e:
                try:
                    cin.close()
                except Exception:
                    pass
        sys.exit(0)
    try:
        s.dprint("Type 'help' or '?'.")
        s.cmdloop()
    except KeyboardInterrupt:
        print("\n")
        sys.exit(0)
