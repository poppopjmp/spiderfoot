#  -*- coding: utf-8 -*-
import html
import json
import os
import os.path
import random
import re
import ssl
import typing
import urllib.parse
import uuid
from pathlib import Path
import sys

try:
    from importlib import resources, files
except ImportError:

    try:
        # Try the importlib_resources backport if available
        import importlib_resources

        files = importlib_resources.files
    except ImportError:
        # Fallback implementation
        from importlib.resources import path as resources_path

        class FilesAdapter:
            def __init__(self, package):
                self.package = package

            def joinpath(self, resource):
                return resources_path(self.package, resource)

        def files(package):
            return FilesAdapter(package)


import networkx as nx
from bs4 import BeautifulSoup, SoupStrainer
from networkx.readwrite.gexf import GEXFWriter
import phonenumbers
import ipaddress


if sys.version_info >= (3, 8):  # PEP 589 support (TypedDict)

    class _GraphNode(typing.TypedDict):
        id: str  # noqa: A003
        label: str
        x: int
        y: int
        size: str
        color: str

    class _GraphEdge(typing.TypedDict):
        id: str  # noqa: A003
        source: str
        target: str

    class _Graph(typing.TypedDict, total=False):
        nodes: typing.List[_GraphNode]
        edges: typing.List[_GraphEdge]

    class Tree(typing.TypedDict):
        name: str
        children: typing.Optional[typing.List["Tree"]]

    class ExtractedLink(typing.TypedDict):
        source: str
        original: str

else:
    _GraphNode = typing.Dict[str, typing.Union[str, int]]

    _GraphEdge = typing.Dict[str, str]

    _GraphObject = typing.Union[_GraphNode, _GraphEdge]

    _Graph = typing.Dict[str, typing.List[_GraphObject]]

    _Tree_name = str

    _Tree_children = typing.Optional[typing.List["Tree"]]

    Tree = typing.Dict[str, typing.Union[_Tree_name, _Tree_children]]

    ExtractedLink = typing.Dict[str, str]


EmptyTree = typing.Dict[None, object]


class SpiderFootHelpers:
    """SpiderFoot helper functions.

    This class is used to store static helper functions which are
    designed to function independent of scan config or global config.

    Todo:
       Eventually split this class into separate files.
    """

    log = None  # Added log attribute

    @staticmethod
    def dataPath() -> str:
        """Returns the file system location of SpiderFoot data and configuration files.

        Returns:
            str: SpiderFoot data file system path
        """
        path = os.environ.get("SPIDERFOOT_DATA")
        if not path:
            path = f"{Path.home()}/.spiderfoot/"
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def cachePath() -> str:
        """Returns the file system location of the cacha data files.

        Returns:
            str: SpiderFoot cache file system path
        """
        path = os.environ.get("SPIDERFOOT_CACHE")
        if not path:
            path = f"{Path.home()}/.spiderfoot/cache"
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def logPath() -> str:
        """Returns the file system location of SpiderFoot log files.

        Returns:
            str: SpiderFoot data file system path
        """
        path = os.environ.get("SPIDERFOOT_LOGS")
        if not path:
            path = f"{Path.home()}/.spiderfoot/logs"
        if not os.path.isdir(path):
            os.makedirs(path, exist_ok=True)
        return path

    @staticmethod
    def loadModulesAsDict(
        path: str, ignore_files: typing.Optional[typing.List[str]] = None
    ) -> dict:
        """Load modules from modules directory.

        Args:
            path (str): file system path for modules directory
            ignore_files (list): List of module file names to ignore

        Returns:
            dict: SpiderFoot modules

        Raises:
            TypeError: ignore file list was invalid
            ValueError: module path does not exist
            SyntaxError: module data is malformed
        """
        if ignore_files is None:
            ignore_files = []

        if not isinstance(ignore_files, list):
            raise TypeError(
                f"ignore_files is {type(ignore_files)}; expected list()")

        if not os.path.isdir(path):
            raise ValueError(f"Modules directory does not exist: {path}")

        sfModules = dict()
        valid_categories = [
            "Content Analysis",
            "Crawling and Scanning",
            "DNS",
            "Leaks, Dumps and Breaches",
            "Passive DNS",
            "Public Registries",
            "Real World",
            "Reputation Systems",
            "Search Engines",
            "Secondary Networks",
            "Social Media",
        ]

        for filename in os.listdir(path):
            # Skip files that do not start with 'sfp_' or do not end with '.py'
            if not filename.startswith("sfp_") or not filename.endswith(".py"):
                continue
            # Skip files that are in the ignore list
            if filename in ignore_files:
                continue

            modName = filename.split(".")[0]
            sfModules[modName] = dict()
            try:
                mod = __import__("modules." + modName,
                                 globals(), locals(), [modName])
                sfModules[modName]["object"] = getattr(mod, modName)()
                mod_dict = sfModules[modName]["object"].asdict()
                sfModules[modName].update(mod_dict)
            except Exception as e:
                raise SyntaxError(f"Error loading module {modName}: {e}")

            # Ensure the module has only one category and it is valid
            if len(sfModules[modName]["cats"]) > 1:
                raise SyntaxError(
                    f"Module {modName} has multiple categories defined but only one is supported."
                )
            if (
                sfModules[modName]["cats"] and
                sfModules[modName]["cats"][0] not in valid_categories
            ):
                raise SyntaxError(
                    f"Module {modName} has invalid category '{sfModules[modName]['cats'][0]}'."
                )

        return sfModules

    @staticmethod
    def loadCorrelationRulesRaw(
        path: str, ignore_files: typing.Optional[typing.List[str]] = None
    ) -> typing.Dict[str, str]:
        """Load correlation rules from correlations directory.

        Args:
            path (str): file system path for correlations directory
            ignore_files (list[str]): List of module file names to ignore

        Returns:
            dict[str, str]: raw correlation rules

        Raises:
            TypeError: ignore file list was invalid
            ValueError: module path does not exist
        """
        if not ignore_files:
            ignore_files = []

        if not isinstance(ignore_files, list):
            raise TypeError(
                f"ignore_files is {type(ignore_files)}; expected list()")

        if not os.path.isdir(path):
            raise ValueError(f"Correlations directory does not exist: {path}")

        correlationRulesRaw: typing.Dict[str, str] = dict()
        for filename in os.listdir(path):
            if not filename.endswith(".yaml"):
                continue
            if filename in ignore_files:
                continue

            ruleName = filename.split(".")[0]
            with open(path + filename, "r") as f:
                correlationRulesRaw[ruleName] = f.read()

        return correlationRulesRaw

    @staticmethod
    def targetTypeFromString(target: str) -> typing.Optional[str]:
        """Return the scan target seed data type for the specified scan target input.

        Args:
            target (str): scan target seed input

        Returns:
            str: scan target seed data type
        """
        if not target:
            return None

        # NOTE: the regex order is important
        regexToType = [
            {r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$": "IP_ADDRESS"},
            {r"^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/\d+$": "NETBLOCK_OWNER"},
            {r"^.*@.*$": "EMAILADDR"},
            {r"^\+[0-9]+$": "PHONE_NUMBER"},
            {r"^\".+\s+.+\"$": "HUMAN_NAME"},
            {r"^\".+\"$": "USERNAME"},
            {r"^[0-9]+$": "BGP_AS_OWNER"},
            {r"^[0-9a-f:]+$": "IPV6_ADDRESS"},
            {r"^[0-9a-f:]+::/[0-9]+$": "NETBLOCKV6_OWNER"},
            {
                r"^(([a-z0-9]|[a-z0-9][a-z0-9\-]*[a-z0-9])\.)+([a-z0-9]|[a-z0-9][a-z0-9\-]*[a-z0-9])$": "INTERNET_NAME"
            },
            {
                r"^(bc(0([ac-hj-np-z02-9]{39}|[ac-hj-np-z02-9]{59})|1[ac-hj-np-z02-9]{8,87})|[13][a-km-zA-HJ-NP-Z1-9]{25,35})$": "BITCOIN_ADDRESS"
            },
        ]

        # Parse the target and set the target type
        for rxpair in regexToType:
            rx = list(rxpair.keys())[0]
            if re.match(rx, target, re.IGNORECASE | re.UNICODE):
                return list(rxpair.values())[0]

        return None

    @staticmethod
    def urlRelativeToAbsolute(url: str) -> typing.Optional[str]:
        """Turn a relative URL path into an absolute path.

        Args:
            url (str): URL

        Returns:
            str: URL relative path
        """
        if not url:
            return None

        if not isinstance(url, str):
            return None

        if ".." not in url:
            return url

        finalBits: typing.List[str] = list()

        for chunk in url.split("/"):
            if chunk != "..":
                finalBits.append(chunk)
                continue

            # Don't pop the last item off if we're at the top
            if len(finalBits) <= 1:
                continue

            # Don't pop the last item off if the first bits are not the path
            if "://" in url and len(finalBits) <= 3:
                continue

            finalBits.pop()

        return "/".join(finalBits)

    @staticmethod
    def urlBaseDir(url: str) -> typing.Optional[str]:
        """Extract the top level directory from a URL

        Args:
            url (str): URL

        Returns:
            str: base directory
        """
        if not url:
            return None

        if not isinstance(url, str):
            return None

        bits = url.split("/")

        # For cases like 'www.somesite.com'
        if len(bits) == 0:
            return url + "/"

        # For cases like 'http://www.blah.com'
        if "://" in url and url.count("/") < 3:
            return url + "/"

        base = "/".join(bits[:-1])

        return base + "/"

    @staticmethod
    def urlBaseUrl(url: str) -> typing.Optional[str]:
        """Extract the scheme and domain from a URL.

        Note: Does not return the trailing slash! So you can do .endswith() checks.

        Args:
            url (str): URL

        Returns:
            str: base URL without trailing slash
        """
        if not url:
            return None

        if not isinstance(url, str):
            return None

        if "://" in url:
            bits = re.match(r"(\w+://.[^/:\?]*)[:/\?].*", url)
        else:
            bits = re.match(r"(.[^/:\?]*)[:/\?]", url)

        if bits is None:
            return url.lower()

        return bits.group(1).lower()

    @staticmethod
    def dictionaryWordsFromWordlists(
        wordlists: typing.Optional[typing.List[str]] = None,
    ) -> typing.Set[str]:
        """Return dictionary words from several language dictionaries.

        Args:
            wordlists (list[str]): list of wordlist file names to read (excluding file extension).

        Returns:
            set[str]: words from dictionaries

        Raises:
            IOError: Error reading wordlist file
        """
        words: typing.Set[str] = set()

        if wordlists is None:
            wordlists = ["english", "german", "french", "spanish"]

        for d in wordlists:
            try:
                with files("spiderfoot.dicts.ispell").joinpath(f"{d}.dict").open(
                    errors="ignore"
                ) as dict_file:
                    for w in dict_file.readlines():
                        words.add(w.strip().lower().split("/")[0])
            except Exception as e:
                raise IOError(
                    f"Could not read wordlist file '{d}.dict'") from e

        return words

    @staticmethod
    def humanNamesFromWordlists(
        wordlists: typing.Optional[typing.List[str]] = None,
    ) -> typing.Set[str]:
        """Return list of human names from wordlist file.

        Args:
            wordlists (list[str]): list of wordlist file names to read (excluding file extension).

        Returns:
            set[str]: human names from wordlists

        Raises:
            IOError: Error reading wordlist file
        """
        words: typing.Set[str] = set()

        if wordlists is None:
            wordlists = ["names"]

        for d in wordlists:
            try:
                with files("spiderfoot.dicts.ispell").joinpath(f"{d}.dict").open(
                    errors="ignore"
                ) as dict_file:
                    for w in dict_file.readlines():
                        words.add(w.strip().lower().split("/")[0])
            except Exception as e:
                raise IOError(
                    f"Could not read wordlist file '{d}.dict'") from e

        return words

    @staticmethod
    def usernamesFromWordlists(wordlists):
        """Get common usernames from wordlists

        Args:
            wordlists (list): List of wordlists

        Returns:
            list: List of usernames
        """
        usernames = list()

        try:
            from importlib.resources import files, as_file
        except ImportError:
            from importlib_resources import files, as_file

        for d in wordlists:
            try:
                resource = files("spiderfoot.dicts").joinpath(f"{d}.txt")
                with as_file(resource) as path:
                    with open(path, errors="ignore") as dict_file:
                        for line in dict_file:
                            username = line.strip()
                            if username and not username.startswith("#"):
                                usernames.append(username)
            except Exception as e:
                raise IOError(f"Could not read wordlist file '{d}.txt'") from e

        return usernames

    @staticmethod
    def buildGraphGexf(
        root: str,
        title: str,
        data: typing.List[str],
        flt: typing.Optional[typing.List[str]] = None,
    ) -> str:
        """Convert supplied raw data into GEXF (Graph Exchange XML Format) format (e.g. for Gephi).

        Args:
            root (str): TBD
            title (str): unused
            data (list[str]): Scan result as list
            flt (list[str]): List of event types to include. If not set everything is included.

        Returns:
            str: GEXF formatted XML
        """
        if not flt:
            flt = []

        mapping = SpiderFootHelpers.buildGraphData(data, flt)
        graph = nx.Graph()

        nodelist: typing.Dict[str, int] = dict()
        ncounter = 0
        for pair in mapping:
            (dst, src) = pair

            # Leave out this special case
            if dst == "ROOT" or src == "ROOT":
                continue

            color = {"r": 0, "g": 0, "b": 0, "a": 0}

            if dst not in nodelist:
                ncounter = ncounter + 1
                if dst in root:
                    color["r"] = 255
                graph.add_node(dst)
                graph.nodes[dst]["viz"] = {"color": color}
                nodelist[dst] = ncounter

            if src not in nodelist:
                ncounter = ncounter + 1
                if src in root:
                    color["r"] = 255
                graph.add_node(src)
                graph.nodes[src]["viz"] = {"color": color}
                nodelist[src] = ncounter

            graph.add_edge(src, dst)

        gexf = GEXFWriter(graph=graph)
        return str(gexf).encode("utf-8")

    @staticmethod
    def buildGraphJson(
        root: str, data: typing.List[str], flt: typing.Optional[typing.List[str]] = None
    ) -> str:
        """Convert supplied raw data into JSON format for SigmaJS.

        Args:
            root (str): TBD
            data (list[str]): Scan result as list
            flt (list[str]): List of event types to include. If not set everything is included.

        Returns:
            str: TBD
        """
        if not flt:
            flt = []

        mapping = SpiderFootHelpers.buildGraphData(data, flt)
        ret: _Graph = {}
        ret["nodes"] = list()
        ret["edges"] = list()

        nodelist: typing.Dict[str, int] = dict()
        ecounter = 0
        ncounter = 0
        for pair in mapping:
            (dst, src) = pair
            col = "#000"

            # Leave out this special case
            if dst == "ROOT" or src == "ROOT":
                continue

            if dst not in nodelist:
                ncounter = ncounter + 1

                if dst in root:
                    col = "#f00"

                ret["nodes"].append(
                    {
                        "id": str(ncounter),
                        "label": str(dst),
                        "x": random.SystemRandom().randint(1, 1000),
                        "y": random.SystemRandom().randint(1, 1000),
                        "size": "1",
                        "color": col,
                    }
                )

                nodelist[dst] = ncounter

            if src not in nodelist:
                ncounter = ncounter + 1

                if src in root:
                    col = "#f00"

                ret["nodes"].append(
                    {
                        "id": str(ncounter),
                        "label": str(src),
                        "x": random.SystemRandom().randint(1, 1000),
                        "y": random.SystemRandom().randint(1, 1000),
                        "size": "1",
                        "color": col,
                    }
                )

                nodelist[src] = ncounter

            ecounter = ecounter + 1

            ret["edges"].append(
                {
                    "id": str(ecounter),
                    "source": str(nodelist[src]),
                    "target": str(nodelist[dst]),
                }
            )

        return json.dumps(ret)

    @staticmethod
    def buildGraphData(
        data: typing.List[str], flt: typing.Optional[typing.List[str]] = None
    ) -> typing.Set[typing.Tuple[str, str]]:
        """Return a format-agnostic collection of tuples to use as the
        basis for building graphs in various formats.

        Args:
            data (list[str]): Scan result as list
            flt (list[str]): List of event types to include. If not set everything is included.

        Returns:
            set[tuple[str, str]]: TBD

        Raises:
            ValueError: data value was invalid
            TypeError: data type was invalid
        """
        if not flt:
            flt = []

        if not isinstance(data, list):
            raise TypeError(f"data is {type(data)}; expected list()")

        if not data:
            raise ValueError("data is empty")

        def get_next_parent_entities(
            item: str, pids: typing.Optional[typing.List[str]] = None
        ) -> typing.List[str]:
            if not pids:
                pids = []

            ret: typing.List[str] = list()

            for [parent, entity_id] in parents[item]:
                if entity_id in pids:
                    continue
                if parent in entities:
                    ret.append(parent)
                else:
                    pids.append(entity_id)
                    for p in get_next_parent_entities(parent, pids):
                        ret.append(p)
            return ret

        mapping: typing.Set[typing.Tuple[str, str]] = set()
        entities: typing.Dict[str, bool] = dict()
        parents: typing.Dict[str, typing.List[typing.List[str]]] = dict()

        for row in data:
            if len(row) != 15:
                raise ValueError(f"data row length is {len(row)}; expected 15")

            if row[11] == "ENTITY" or row[11] == "INTERNAL":
                # List of all valid entity values
                if len(flt) > 0:
                    if row[4] in flt or row[11] == "INTERNAL":
                        entities[row[1]] = True
                else:
                    entities[row[1]] = True

            if row[1] not in parents:
                parents[row[1]] = list()
            parents[row[1]].append([row[2], row[8]])

        for entity in entities:
            for [parent, _id] in parents[entity]:
                if parent in entities:
                    if entity != parent:
                        # Add entity parent
                        mapping.add((entity, parent))
                else:
                    # Check parent for entityship.
                    next_parents = get_next_parent_entities(parent)
                    for next_parent in next_parents:
                        if entity != next_parent:
                            # Add next entity parent
                            mapping.add((entity, next_parent))
        return mapping

    @staticmethod
    def dataParentChildToTree(
        data: typing.Dict[str, typing.Optional[typing.List[str]]],
    ) -> typing.Union[Tree, EmptyTree]:
        """Converts a dictionary of k -> array to a nested
        tree that can be digested by d3 for visualizations.

        Args:
            data (dict): dictionary of k -> array

        Returns:
            dict: nested tree

        Raises:
            ValueError: data value was invalid
            TypeError: data type was invalid
        """
        if not isinstance(data, dict):
            raise TypeError(f"data is {type(data)}; expected dict()")

        if not data:
            raise ValueError("data is empty")

        def get_children(
            needle: str, haystack: typing.Dict[str, typing.Optional[typing.List[str]]]
        ) -> typing.Optional[typing.List[Tree]]:
            ret: typing.List[Tree] = list()

            if needle not in list(haystack.keys()):
                return None

            if haystack[needle] is None:
                return None

            for c in haystack[needle]:
                ret.append({"name": c, "children": get_children(c, haystack)})
            return ret

        # Find the element with no parents, that's our root.
        root = None
        for k in list(data.keys()):
            if data[k] is None:
                continue

            contender = True
            for ck in list(data.keys()):
                if data[ck] is None:
                    continue

                if k in data[ck]:
                    contender = False

            if contender:
                root = k
                break

        if root is None:
            return {}

        return {"name": root, "children": get_children(root, data)}

    @staticmethod
    def validLEI(lei: str) -> bool:
        """Check if the provided string is a valid Legal Entity Identifier (LEI).

        Args:
            lei (str): The LEI number to check.

        Returns:
            bool: string is a valid LEI

        Note:
            ISO 17442 has been withdrawn and is not accurate
            https://www.gleif.org/en/about-lei/iso-17442-the-lei-code-structure
        """
        if not isinstance(lei, str):
            return False

        if not re.match(r"^[A-Z0-9]{18}[0-9]{2}$", lei, re.IGNORECASE):
            return False

        return True

    @staticmethod
    def validEmail(email: str) -> bool:
        """Check if the provided string is a valid email address.

        Args:
            email (str): The email address to check.

        Returns:
            bool: email is a valid email address
        """
        if not isinstance(email, str):
            return False

        if "@" not in email:
            return False

        if not re.match(
            r"^([\%a-zA-Z\.0-9_\-\+]+@[a-zA-Z\.0-9\-]+\.[a-zA-Z\.0-9\-]+)$", email
        ):
            return False

        if len(email) < 6:
            return False

        # Skip strings with messed up URL encoding
        if "%" in email:
            return False

        # Skip strings which may have been truncated
        if "..." in email:
            return False

        return True

    @staticmethod
    def validPhoneNumber(phone: str) -> bool:
        """Check if the provided string is a valid phone number.

        Args:
            phone (str): The phone number to check.

        Returns:
            bool: string is a valid phone number
        """
        if not isinstance(phone, str):
            return False

        try:
            return phonenumbers.is_valid_number(phonenumbers.parse(phone))
        except Exception:
            return False

    @staticmethod
    def genScanInstanceId() -> str:
        """Generate an globally unique ID for this scan.

        Returns:
            str: scan instance unique ID
        """
        return str(uuid.uuid4()).split("-")[0].upper()

    @staticmethod
    def extractLinksFromHtml(
        url: str, data: str, domains: typing.Optional[typing.List[str]]
    ) -> typing.Dict[str, ExtractedLink]:
        """Find all URLs within the supplied content.

        This function does not fetch any URLs.

        A dictionary will be returned, where each link will have the keys:
          'source': The URL where the link was obtained from
          'original': What the link looked like in the content it was obtained from

        The key will be the *absolute* URL of the link obtained, so for example if
        the link '/abc' was obtained from 'http://xyz.com', the key in the dict will
        be 'http://xyz.com/abc' with the 'original' attribute set to '/abc'

        Args:
            url (str): base URL used to construct absolute URLs from relative URLs
            data (str): data to examine for links
            domains: TBD

        Returns:
            dict: links

        Raises:
            TypeError: argument was invalid type
        """
        returnLinks: typing.Dict[str, ExtractedLink] = dict()

        if not isinstance(url, str):
            raise TypeError(f"url {type(url)}; expected str()")

        if not isinstance(data, str):
            raise TypeError(f"data {type(data)}; expected str()")

        if isinstance(domains, str):
            domains = [domains]

        tags = {
            "a": "href",
            "img": "src",
            "script": "src",
            "link": "href",
            "area": "href",
            "base": "href",
            "form": "action",
        }

        links: typing.List[typing.Union[typing.List[str], str]] = []

        try:
            for t in list(tags.keys()):
                for lnk in BeautifulSoup(
                    data, features="lxml", parse_only=SoupStrainer(t)
                ).find_all(t):
                    if lnk.has_attr(tags[t]):
                        links.append(lnk[tags[t]])
        except Exception:
            return returnLinks

        try:
            proto = url.split(":")[0]
        except Exception:
            proto = "http"

        # Loop through all the URLs/links found
        for link in links:
            if not isinstance(link, str):
                link = str(link)

            link = link.strip()

            if len(link) < 1:
                continue

            # Don't include stuff likely part of some dynamically built incomplete
            # URL found in Javascript code (character is part of some logic)
            if (
                link[len(link) - 1] in [".", "#"] or
                link[0] == "+" or
                "javascript:" in link.lower() or
                "()" in link or
                '+"' in link or
                '"+' in link or
                "+'" in link or
                "'+" in link or
                "data:image" in link or
                " +" in link or
                "+ " in link
            ):
                continue

            # Filter in-page links
            if re.match(".*#.[^/]+", link):
                continue

            # Ignore mail links
            if "mailto:" in link.lower():
                continue

            # URL decode links
            if "%2f" in link.lower():
                link = urllib.parse.unquote(link)

            absLink = None

            # Capture the absolute link:
            # If the link contains ://, it is already an absolute link
            if "://" in link:
                absLink = link

            # If the link starts with //, it is likely a protocol relative URL
            elif link.startswith("//"):
                absLink = proto + ":" + link

            # If the link starts with a /, the absolute link is off the base URL
            elif link.startswith("/"):
                absLink = SpiderFootHelpers.urlBaseUrl(url) + link

            # Maybe the domain was just mentioned and not a link, so we make it one
            for domain in domains:
                if absLink is None and domain.lower() in link.lower():
                    absLink = proto + "://" + link

            # Otherwise, it's a flat link within the current directory
            if absLink is None:
                absLink = SpiderFootHelpers.urlBaseDir(url) + link

            # Translate any relative pathing (../)
            absLink = SpiderFootHelpers.urlRelativeToAbsolute(absLink)
            returnLinks[absLink] = {"source": url, "original": link}

        return returnLinks

    @staticmethod
    def extractHashesFromText(data: str) -> typing.List[typing.Tuple[str, str]]:
        """Extract all hashes within the supplied content.

        Args:
            data (str): text to search for hashes

        Returns:
            list[tuple[str, str]]: list of tuples containing (hash_type, hash_value)
        """
        ret: typing.List[typing.Tuple[str, str]] = list()

        if not isinstance(data, str):
            return ret

        # Optimized regex patterns using word boundaries - more efficient
        # and just as effective as the more complex patterns
        hashes = {
            "MD5": re.compile(r"\b([a-fA-F0-9]{32})\b"),
            "SHA1": re.compile(r"\b([a-fA-F0-9]{40})\b"),
            "SHA256": re.compile(r"\b([a-fA-F0-9]{64})\b"),
            "SHA512": re.compile(r"\b([a-fA-F0-9]{128})\b"),
        }

        # Extract each hash type and add to the results
        for hash_type, pattern in hashes.items():
            matches = pattern.findall(data)
            for match in matches:
                ret.append((hash_type, match))

        return ret

    @staticmethod
    def extractUrlsFromRobotsTxt(robotsTxtData: str) -> typing.List[str]:
        """Parse the contents of robots.txt to extract disallowed paths.

        Args:
            robotsTxtData (str): robots.txt file contents

        Returns:
            list[str]: list of patterns which should not be followed

        Todo:
            Check and parse User-Agent directives.
            Handle whitespace properly - " " is not a valid disallowed path.
        """
        returnArr: typing.List[str] = list()

        if not isinstance(robotsTxtData, str):
            return returnArr

        # Improved regex to better handle robots.txt format
        # Matches after 'Disallow:' and captures until whitespace or a comment
        disallow_pattern = re.compile(
            r"^\s*Disallow:\s*([^ #\r\n]+)", re.IGNORECASE)

        for line in robotsTxtData.splitlines():
            match = disallow_pattern.search(line)
            if match and match.group(1):
                # Only add non-empty paths
                path = match.group(1).strip()
                if path:
                    returnArr.append(path)

        return returnArr

    @staticmethod
    def extractPgpKeysFromText(data: str) -> typing.List[str]:
        """Extract all PGP keys within the supplied content.

        Args:
            data (str): text to search for PGP keys

        Returns:
            list[str]: list of PGP keys
        """
        if not isinstance(data, str):
            return list()

        keys: typing.Set[str] = set()

        # Improved regex to match PGP key blocks
        # This pattern looks for BEGIN and END block markers that are commonly found in PGP keys
        pattern = re.compile(
            r"-----BEGIN PGP (?:PUBLIC|PRIVATE) KEY BLOCK-----.*?-----END PGP (?:PUBLIC|PRIVATE) KEY BLOCK-----",
            re.DOTALL | re.MULTILINE,
        )

        for match in pattern.finditer(data):
            key = match.group(0)
            # Filter out keys that are too short to be valid
            if len(key) >= 300:
                keys.add(key)

        return list(keys)

    @staticmethod
    def extractEmailsFromText(data: str) -> typing.List[str]:
        """Extract all email addresses within the supplied content.

        Args:
            data (str): text to search for email addresses

        Returns:
            list[str]: list of email addresses
        """
        if not isinstance(data, str):
            return list()

        emails: typing.Set[str] = set()
        matches = re.findall(
            r"([\%a-zA-Z\.0-9_\-\+]+@[a-zA-Z\.0-9\-]+\.[a-zA-Z\.0-9\-]+)", data
        )

        for match in matches:
            if SpiderFootHelpers.validEmail(match):
                emails.add(match)

        return list(emails)

    @staticmethod
    def extractIbansFromText(data: str) -> typing.List[str]:
        """Find all International Bank Account Numbers (IBANs) within the supplied content.

        Extracts possible IBANs using a generic regex.

        Checks whether possible IBANs are valid or not
        using country-wise length check and Mod 97 algorithm.

        Args:
            data (str): text to search for IBANs

        Returns:
            list[str]: list of IBAN
        """
        if not isinstance(data, str):
            return list()

        ibans: typing.Set[str] = set()

        # Dictionary of country codes and their respective IBAN lengths
        ibanCountryLengths = {
            "AL": 28,
            "AD": 24,
            "AT": 20,
            "AZ": 28,
            "ME": 22,
            "BH": 22,
            "BY": 28,
            "BE": 16,
            "BA": 20,
            "BR": 29,
            "BG": 22,
            "CR": 22,
            "HR": 21,
            "CY": 28,
            "CZ": 24,
            "DK": 18,
            "DO": 28,
            "EG": 29,
            "SV": 28,
            "FO": 18,
            "FI": 18,
            "FR": 27,
            "GE": 22,
            "DE": 22,
            "GI": 23,
            "GR": 27,
            "GL": 18,
            "GT": 28,
            "VA": 22,
            "HU": 28,
            "IS": 26,
            "IQ": 23,
            "IE": 22,
            "IL": 23,
            "JO": 30,
            "KZ": 20,
            "XK": 20,
            "KW": 30,
            "LV": 21,
            "LB": 28,
            "LI": 21,
            "LT": 20,
            "LU": 20,
            "MT": 31,
            "MR": 27,
            "MU": 30,
            "MD": 24,
            "MC": 27,
            "DZ": 24,
            "AO": 25,
            "BJ": 28,
            "VG": 24,
            "BF": 27,
            "BI": 16,
            "CM": 27,
            "CV": 25,
            "CG": 27,
            "EE": 20,
            "GA": 27,
            "GG": 22,
            "IR": 26,
            "IM": 22,
            "IT": 27,
            "CI": 28,
            "JE": 22,
            "MK": 19,
            "MG": 27,
            "ML": 28,
            "MZ": 25,
            "NL": 18,
            "NO": 15,
            "PK": 24,
            "PS": 29,
            "PL": 28,
            "PT": 25,
            "QA": 29,
            "RO": 24,
            "LC": 32,
            "SM": 27,
            "ST": 25,
            "SA": 24,
            "SN": 28,
            "RS": 22,
            "SC": 31,
            "SK": 24,
            "SI": 19,
            "ES": 24,
            "CH": 21,
            "TL": 23,
            "TN": 24,
            "TR": 26,
            "UA": 29,
            "AE": 23,
            "GB": 22,
            "SE": 24,
        }

        # Normalize input data to remove whitespace
        data = data.replace(" ", "")

        # Extract alphanumeric characters of lengths ranging from 15 to 32
        # and starting with two characters
        matches = re.findall("[A-Za-z]{2}[A-Za-z0-9]{13,30}", data)

        for match in matches:
            iban = match.upper()

            countryCode = iban[0:2]

            if countryCode not in ibanCountryLengths.keys():
                continue

            if len(iban) != ibanCountryLengths[countryCode]:
                continue

            # Convert IBAN to integer format.
            # Move the first 4 characters to the end of the string,
            # then convert all characters to integers; where A = 10, B = 11, ...., Z = 35
            iban_int = iban[4:] + iban[0:4]
            for character in iban_int:
                if character.isalpha():
                    iban_int = iban_int.replace(
                        character, str((ord(character) - 65) + 10)
                    )

            # Check IBAN integer mod 97 for remainder
            if int(iban_int) % 97 != 1:
                continue

            ibans.add(iban)

        return list(ibans)

    @staticmethod
    def extractCreditCardsFromText(data: str) -> typing.List[str]:
        """Find all credit card numbers with the supplied content.

        Extracts numbers with lengths ranging from 13 - 19 digits

        Checks the numbers using Luhn's algorithm to verify
        if the number is a valid credit card number or not

        Args:
            data (str): text to search for credit card numbers

        Returns:
            list[str]: list of credit card numbers
        """
        if not isinstance(data, str):
            return list()

        creditCards: typing.Set[str] = set()

        # Remove whitespace from data.
        # Credit cards might contain spaces between them
        # which will cause regex mismatch
        data = data.replace(" ", "")

        # Extract all numbers with lengths ranging from 13 - 19 digits
        matches = re.findall(r"[0-9]{13,19}", data)

        # Verify each extracted number using Luhn's algorithm
        for match in matches:
            if int(match) == 0:
                continue

            ccNumber = match

            ccNumberTotal = 0
            isSecondDigit = False

            for digit in ccNumber[::-1]:
                d = int(digit)
                if isSecondDigit:
                    d *= 2
                ccNumberTotal += int(d / 10)
                ccNumberTotal += d % 10

                isSecondDigit = not isSecondDigit
            if ccNumberTotal % 10 == 0:
                creditCards.add(match)
        return list(creditCards)

    @staticmethod
    def extractUrlsFromText(content: str) -> typing.List[str]:
        """Extract all URLs from a string.

        Args:
            content (str): text to search for URLs

        Returns:
            list[str]: list of identified URLs
        """
        if not isinstance(content, str):
            return []

        # https://tools.ietf.org/html/rfc3986#section-3.3
        return re.findall(
            r"(https?://[a-zA-Z0-9-\.:]+/[\-\._~!\$&'\(\)\*\+\,\;=:@/a-zA-Z0-9]*)",
            html.unescape(content),
        )

    @staticmethod
    def sslDerToPem(der_cert: bytes) -> str:
        """Given a certificate as a DER-encoded blob of bytes, returns a PEM-encoded string version of the same certificate.

        Args:
            der_cert (bytes): certificate in DER format

        Returns:
            str: PEM-encoded certificate as a byte string

        Raises:
            TypeError: arg type was invalid
        """
        if not isinstance(der_cert, bytes):
            raise TypeError(f"der_cert is {type(der_cert)}; expected bytes()")

        return ssl.DER_cert_to_PEM_cert(der_cert)

    @staticmethod
    def countryNameFromCountryCode(countryCode: str) -> typing.Optional[str]:
        """Convert a country code to full country name.

        Args:
            countryCode (str): country code

        Returns:
            str: country name
        """
        if not isinstance(countryCode, str):
            return None

        return SpiderFootHelpers.countryCodes().get(countryCode.upper())

    @staticmethod
    def countryNameFromTld(tld: str) -> typing.Optional[str]:
        """Retrieve the country name associated with a TLD.

        Args:
            tld (str): Top level domain

        Returns:
            str: country name
        """
        if not isinstance(tld, str):
            return None

        country_name = SpiderFootHelpers.countryCodes().get(tld.upper())

        if country_name:
            return country_name

        country_tlds = {
            # List of TLD not associated with any country
            "COM": "United States",
            "NET": "United States",
            "ORG": "United States",
            "GOV": "United States",
            "MIL": "United States",
        }

        country_name = country_tlds.get(tld.upper())

        if country_name:
            return country_name

        return None

    @staticmethod
    def countryCodes() -> typing.Dict[str, str]:
        """Dictionary of country codes and associated country names.

        Returns:
            dict[str, str]: country codes and associated country names
        """

        return {
            "AF": "Afghanistan",
            "AX": "Aland Islands",
            "AL": "Albania",
            "DZ": "Algeria",
            "AS": "American Samoa",
            "AD": "Andorra",
            "AO": "Angola",
            "AI": "Anguilla",
            "AQ": "Antarctica",
            "AG": "Antigua and Barbuda",
            "AR": "Argentina",
            "AM": "Armenia",
            "AW": "Aruba",
            "AU": "Australia",
            "AT": "Austria",
            "AZ": "Azerbaijan",
            "BS": "Bahamas",
            "BH": "Bahrain",
            "BD": "Bangladesh",
            "BB": "Barbados",
            "BY": "Belarus",
            "BE": "Belgium",
            "BZ": "Belize",
            "BJ": "Benin",
            "BM": "Bermuda",
            "BT": "Bhutan",
            "BO": "Bolivia",
            "BQ": "Bonaire, Saint Eustatius and Saba",
            "BA": "Bosnia and Herzegovina",
            "BW": "Botswana",
            "BV": "Bouvet Island",
            "BR": "Brazil",
            "IO": "British Indian Ocean Territory",
            "VG": "British Virgin Islands",
            "BN": "Brunei",
            "BG": "Bulgaria",
            "BF": "Burkina Faso",
            "BI": "Burundi",
            "KH": "Cambodia",
            "CM": "Cameroon",
            "CA": "Canada",
            "CV": "Cape Verde",
            "KY": "Cayman Islands",
            "CF": "Central African Republic",
            "TD": "Chad",
            "CL": "Chile",
            "CN": "China",
            "CX": "Christmas Island",
            "CC": "Cocos Islands",
            "CO": "Colombia",
            "KM": "Comoros",
            "CK": "Cook Islands",
            "CR": "Costa Rica",
            "HR": "Croatia",
            "CU": "Cuba",
            "CW": "Curacao",
            "CY": "Cyprus",
            "CZ": "Czech Republic",
            "CD": "Democratic Republic of the Congo",
            "DK": "Denmark",
            "DJ": "Djibouti",
            "DM": "Dominica",
            "DO": "Dominican Republic",
            "TL": "East Timor",
            "EC": "Ecuador",
            "EG": "Egypt",
            "SV": "El Salvador",
            "GQ": "Equatorial Guinea",
            "ER": "Eritrea",
            "EE": "Estonia",
            "ET": "Ethiopia",
            "FK": "Falkland Islands",
            "FO": "Faroe Islands",
            "FJ": "Fiji",
            "FI": "Finland",
            "FR": "France",
            "GF": "French Guiana",
            "PF": "French Polynesia",
            "TF": "French Southern Territories",
            "GA": "Gabon",
            "GM": "Gambia",
            "GE": "Georgia",
            "DE": "Germany",
            "GH": "Ghana",
            "GI": "Gibraltar",
            "GR": "Greece",
            "GL": "Greenland",
            "GD": "Grenada",
            "GP": "Guadeloupe",
            "GU": "Guam",
            "GT": "Guatemala",
            "GG": "Guernsey",
            "GN": "Guinea",
            "GW": "Guinea-Bissau",
            "GY": "Guyana",
            "HT": "Haiti",
            "HM": "Heard Island and McDonald Islands",
            "HN": "Honduras",
            "HK": "Hong Kong",
            "HU": "Hungary",
            "IS": "Iceland",
            "IN": "India",
            "ID": "Indonesia",
            "IR": "Iran",
            "IQ": "Iraq",
            "IE": "Ireland",
            "IM": "Isle of Man",
            "IL": "Israel",
            "IT": "Italy",
            "CI": "Ivory Coast",
            "JM": "Jamaica",
            "JP": "Japan",
            "JE": "Jersey",
            "JO": "Jordan",
            "KZ": "Kazakhstan",
            "KE": "Kenya",
            "KI": "Kiribati",
            "XK": "Kosovo",
            "KW": "Kuwait",
            "KG": "Kyrgyzstan",
            "LA": "Laos",
            "LV": "Latvia",
            "LB": "Lebanon",
            "LS": "Lesotho",
            "LR": "Liberia",
            "LY": "Libya",
            "LI": "Liechtenstein",
            "LT": "Lithuania",
            "LU": "Luxembourg",
            "MO": "Macao",
            "MK": "Macedonia",
            "MG": "Madagascar",
            "MW": "Malawi",
            "MY": "Malaysia",
            "MV": "Maldives",
            "ML": "Mali",
            "MT": "Malta",
            "MH": "Marshall Islands",
            "MQ": "Martinique",
            "MR": "Mauritania",
            "MU": "Mauritius",
            "YT": "Mayotte",
            "MX": "Mexico",
            "FM": "Micronesia",
            "MD": "Moldova",
            "MC": "Monaco",
            "MN": "Mongolia",
            "ME": "Montenegro",
            "MS": "Montserrat",
            "MA": "Morocco",
            "MZ": "Mozambique",
            "MM": "Myanmar",
            "NA": "Namibia",
            "NR": "Nauru",
            "NP": "Nepal",
            "NL": "Netherlands",
            "AN": "Netherlands Antilles",
            "NC": "New Caledonia",
            "NZ": "New Zealand",
            "NI": "Nicaragua",
            "NE": "Niger",
            "NG": "Nigeria",
            "NU": "Niue",
            "NF": "Norfolk Island",
            "KP": "North Korea",
            "MP": "Northern Mariana Islands",
            "NO": "Norway",
            "OM": "Oman",
            "PK": "Pakistan",
            "PW": "Palau",
            "PS": "Palestinian Territory",
            "PA": "Panama",
            "PG": "Papua New Guinea",
            "PY": "Paraguay",
            "PE": "Peru",
            "PH": "Philippines",
            "PN": "Pitcairn",
            "PL": "Poland",
            "PT": "Portugal",
            "PR": "Puerto Rico",
            "QA": "Qatar",
            "CG": "Republic of the Congo",
            "RE": "Reunion",
            "RO": "Romania",
            "RU": "Russia",
            "RW": "Rwanda",
            "BL": "Saint Barthelemy",
            "SH": "Saint Helena",
            "KN": "Saint Kitts and Nevis",
            "LC": "Saint Lucia",
            "MF": "Saint Martin",
            "PM": "Saint Pierre and Miquelon",
            "VC": "Saint Vincent and the Grenadines",
            "WS": "Samoa",
            "SM": "San Marino",
            "ST": "Sao Tome and Principe",
            "SA": "Saudi Arabia",
            "SN": "Senegal",
            "RS": "Serbia",
            "CS": "Serbia and Montenegro",
            "SC": "Seychelles",
            "SL": "Sierra Leone",
            "SG": "Singapore",
            "SX": "Sint Maarten",
            "SK": "Slovakia",
            "SI": "Slovenia",
            "SB": "Solomon Islands",
            "SO": "Somalia",
            "ZA": "South Africa",
            "GS": "South Georgia and the South Sandwich Islands",
            "KR": "South Korea",
            "SS": "South Sudan",
            "ES": "Spain",
            "LK": "Sri Lanka",
            "SD": "Sudan",
            "SR": "Suriname",
            "SJ": "Svalbard and Jan Mayen",
            "SZ": "Swaziland",
            "SE": "Sweden",
            "CH": "Switzerland",
            "SY": "Syria",
            "TW": "Taiwan",
            "TJ": "Tajikistan",
            "TZ": "Tanzania",
            "TH": "Thailand",
            "TG": "Togo",
            "TK": "Tokelau",
            "TO": "Tonga",
            "TT": "Trinidad and Tobago",
            "TN": "Tunisia",
            "TR": "Turkey",
            "TM": "Turkmenistan",
            "TC": "Turks and Caicos Islands",
            "TV": "Tuvalu",
            "VI": "U.S. Virgin Islands",
            "UG": "Uganda",
            "UA": "Ukraine",
            "AE": "United Arab Emirates",
            "GB": "United Kingdom",
            "US": "United States",
            "UM": "United States Minor Outlying Islands",
            "UY": "Uruguay",
            "UZ": "Uzbekistan",
            "VU": "Vanuatu",
            "VA": "Vatican",
            "VE": "Venezuela",
            "VN": "Vietnam",
            "WF": "Wallis and Futuna",
            "EH": "Western Sahara",
            "YE": "Yemen",
            "ZM": "Zambia",
            "ZW": "Zimbabwe",
            # Below are not country codes but recognized as regions / TLDs
            "AC": "Ascension Island",
            "EU": "European Union",
            "SU": "Soviet Union",
            "UK": "United Kingdom",
        }

    @staticmethod
    def sanitiseInput(
        cmd: str, extra: typing.Optional[typing.List[str]] = None
    ) -> bool:
        """Verify input command is safe to execute

        Args:
            cmd (str): The command to check
            extra (list[str]): Additional characters to consider safe

        Returns:
            bool: command is "safe"
        """
        if not extra:
            extra = []

        chars = [
            "a",
            "b",
            "c",
            "d",
            "e",
            "f",
            "g",
            "h",
            "i",
            "j",
            "k",
            "l",
            "m",
            "n",
            "o",
            "p",
            "q",
            "r",
            "s",
            "t",
            "u",
            "v",
            "w",
            "x",
            "y",
            "z",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "-",
            ".",
        ]

        if extra:
            chars.extend(extra)

        for c in cmd:
            if c.lower() not in chars:
                return False

        if ".." in cmd:
            return False

        if cmd.startswith("-"):
            return False

        if len(cmd) < 3:
            return False

        return True

    @staticmethod
    def is_private_ip(ip_address_str):
        """
        Check if an IP address is private.

        Args:
            ip_address_str (str): IP address to check

        Returns:
            bool: True if the IP address is private, False otherwise
        """
        try:
            ip_obj = ipaddress.ip_address(ip_address_str)
            return ip_obj.is_private
        except Exception:
            return False

    @staticmethod
    def is_valid_local_or_loopback_ip(ip_address_str):
        """
        Check if an IP address is valid local or loopback.

        Args:
            ip_address_str (str): IP address to check

        Returns:
            bool: True if the IP address is valid local or loopback, False otherwise
        """
        try:
            ip_obj = ipaddress.ip_address(ip_address_str)
            return ip_obj.is_private or ip_obj.is_loopback
        except Exception:
            return False

    def buildGraphJson(data, root="", tooltip=None):
        """Convert supplied raw data into JSON format for graph.

        Args:
            data (list): Data to be converted
            root (str): Root node
            tooltip (str): Tooltip text

        Returns:
            str: JSON data
        """
        nodes = []
        edges = []

        for row in data:
            # Handling the nodes and edges
            source_data = row[7]
            source_type = row[6]
            child_data = row[1]
            child_type = row[2]

            if source_data not in [x["data"] for x in nodes]:
                nodes.append({"data": source_data, "type": source_type})

            if child_data not in [x["data"] for x in nodes]:
                nodes.append({"data": child_data, "type": child_type})

            edges.append(
                {"source": source_data, "target": child_data, "label": row[3]})

        return json.dumps({"nodes": nodes, "edges": edges})

    def extractLinksFromHtml(url, data):
        """Extract URLs from HTML content.

        Args:
            url (str): Base URL
            data (str): HTML content

        Returns:
            list: List of URLs
        """
        links = []

        if not data:
            return links

        try:
            soup = BeautifulSoup(data, "lxml")
            for link in soup.find_all("a"):
                href = link.get("href")
                if href:
                    absurl = urlRelativeToAbsolute(url, href)
                    if absurl:
                        links.append(absurl)
        except Exception:
            pass

        return links

    def extractPgpKeysFromText(text):
        """Extract PGP public keys from text.

        Args:
            text (str): Text to extract from

        Returns:
            list: list of PGP key blocks
        """
        if not text:
            return []

        pgp_keys = []
        pattern = r"-----BEGIN PGP PUBLIC KEY BLOCK-----(.*?)-----END PGP PUBLIC KEY BLOCK-----"

        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            pgp_keys.append(
                f"-----BEGIN PGP PUBLIC KEY BLOCK-----{match}-----END PGP PUBLIC KEY BLOCK-----"
            )

        return pgp_keys

    def loadModulesAsDict(directory, modclass):
        """Load modules from directory as a dict.

        Args:
            directory (str): Directory to load modules from
            modclass (str): Module class

        Returns:
            dict: Dictionary of module objects
        """
        modules = {}

        for filename in os.listdir(directory):
            if not filename.endswith(".py"):
                continue

            if filename == "__init__.py":
                continue

            modname = filename.split(".")[0]

            try:
                module = __import__(
                    f"modules.{modname}", globals(), locals(), [modname]
                )
                mod = getattr(module, modname)
                instance = mod()

                if modclass and modclass != instance.__module__:
                    continue

                modules[modname] = instance
            except Exception:
                pass

        return modules

    def urlRelativeToAbsolute(base_url, relative_url):
        """Convert a relative URL to an absolute URL.

        Args:
            base_url (str): Base URL
            relative_url (str): Relative URL

        Returns:
            str: Absolute URL
        """
        if not relative_url:
            return None

        if relative_url.startswith("//"):
            # Protocol-relative URL
            protocol = base_url.split(":", 1)[0]
            return f"{protocol}:{relative_url}"

        if relative_url.startswith("http://") or relative_url.startswith("https://"):
            # Already absolute
            return relative_url

        try:
            return urljoin(base_url, relative_url)
        except Exception:
            return None

    def sanitiseInput(string):
        """Sanitize input to prevent SQL injection.

        Args:
            string (str): The input string to sanitize

        Returns:
            str: The sanitized string
        """
        if not isinstance(string, str):
            string = str(string)

        if string.find("'") >= 0 or string.find('"') >= 0:
            string = string.replace("'", "").replace('"', "")
        return string

    def urlBaseDir(url):
        """Get the base directory of a URL.

        Args:
            url (str): URL to get the base directory from

        Returns:
            str: Base directory URL
        """
        if not url:
            return None

        try:
            parsed_url = urlparse(url)
            path = parsed_url.path

            # Get the directory part
            if path.endswith("/"):
                # URL already points to a directory
                directory = path
            else:
                # Get the directory containing the file
                directory = os.path.dirname(path) + "/"

            # Reconstruct the URL
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{directory}"
            return base_url
        except Exception:
            return None

    def extractUrlsFromText(text):
        """Extract URLs from text.

        Args:
            text (str): Text to extract URLs from

        Returns:
            list: List of URLs
        """
        # Simple URL regex pattern
        url_pattern = r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"

        if not text:
            return []

        urls = re.findall(url_pattern, text)
        return urls
