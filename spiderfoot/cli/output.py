"""
Output formatting and color utilities for SpiderFoot CLI.
"""

class bcolors:
    GREYBLUE = '\x1b[38;5;25m'
    GREY = '\x1b[38;5;243m'
    DARKRED = '\x1b[38;5;124m'
    DARKGREEN = '\x1b[38;5;30m'
    BOLD = '\033[1m'
    ENDC = '\033[0m'
    GREYBLUE_DARK = '\x1b[38;5;24m'


def format_colored(msg, color=None, bold=False, prefix=None):
    out = ""
    if color:
        out += color
    if bold:
        out += bcolors.BOLD
    if prefix:
        out += prefix + " "
    out += msg
    if color or bold:
        out += bcolors.ENDC
    return out


def pretty_table(data, titlemap=None):
    if not data:
        return ""
    out = list()
    maxsize = dict()
    if isinstance(data[0], dict):
        cols = list(data[0].keys())
    else:
        cols = list(map(str, list(range(0, len(data[0])))))
    if titlemap:
        nc = [c for c in cols if c in titlemap]
        cols = nc
    spaces = 2
    for r in data:
        for i, c in enumerate(r):
            cn = c if isinstance(r, dict) else str(i)
            v = str(r[c]) if isinstance(r, dict) else str(c)
            if len(v) > maxsize.get(cn, 0):
                maxsize[cn] = len(v)
    if titlemap:
        for c in maxsize:
            if len(titlemap.get(c, c)) > maxsize[c]:
                maxsize[c] = len(titlemap.get(c, c))
    for i, c in enumerate(cols):
        t = titlemap.get(c, c) if titlemap else c
        out.append(t)
        sdiff = maxsize[c] - len(t) + 1
        out.append(" " * spaces)
        if sdiff > 0 and i < len(cols) - 1:
            out.append(" " * sdiff)
    out.append('\n')
    for i, c in enumerate(cols):
        out.append("-" * ((maxsize[c] + spaces)))
        if i < len(cols) - 1:
            out.append("+")
    out.append("\n")
    for r in data:
        i = 0
        di = 0
        tr = type(r)
        for c in r:
            cn = c if tr == dict else str(i)
            v = str(r[c]) if tr == dict else str(c)
            if cn not in cols:
                i += 1
                continue
            out.append(v)
            lv = len(v)
            sdiff = (maxsize[cn] - lv) + spaces if di == 0 else (maxsize[cn] - lv) + spaces - 1
            if di < len(cols) - 1:
                out.append(" " * sdiff)
            if di < len(cols) - 1:
                out.append("| ")
            di += 1
            i += 1
        out.append("\n")
    return ''.join(out)
