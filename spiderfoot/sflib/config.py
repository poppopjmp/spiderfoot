# -*- coding: utf-8 -*-
# -------------------------------------------------------------------------------
# Name:         Modular SpiderFoot SFLib Module
# Purpose:      Common functions for working with the database back-end.
#
# Author:      Agostino Panico @poppopjmp
#
# Created:     30/06/2025
# Copyright:   (c) Agostino Panico 2025
# Licence:     MIT
# -------------------------------------------------------------------------------
from copy import deepcopy

def configSerialize(opts: dict, filterSystem: bool = True):
    if not isinstance(opts, dict):
        raise TypeError(f"opts is {type(opts)}; expected dict()")
    storeopts = dict()
    if not opts:
        return storeopts
    for opt in list(opts.keys()):
        if not isinstance(opt, str):
            continue
        if opt.startswith('__') and filterSystem:
            continue
        if isinstance(opts[opt], (int, str)):
            storeopts[opt] = opts[opt]
        if isinstance(opts[opt], bool):
            storeopts[opt] = 1 if opts[opt] else 0
        if isinstance(opts[opt], list):
            storeopts[opt] = ','.join(str(x) for x in opts[opt])
    if '__modules__' not in opts:
        return storeopts
    if not isinstance(opts['__modules__'], dict):
        raise TypeError(f"opts['__modules__'] is {type(opts['__modules__'])}; expected dict()")
    for mod in opts['__modules__']:
        mod_opts = opts['__modules__'][mod].get('opts', {})
        if not isinstance(mod_opts, dict):
            continue
        for opt in mod_opts:
            if not isinstance(opt, str):
                continue
            if opt.startswith('_') and filterSystem:
                continue
            mod_opt = f"{mod}:{opt}"
            mod_opt_val = mod_opts[opt]
            if isinstance(mod_opt_val, (int, str)):
                storeopts[mod_opt] = mod_opt_val
            if isinstance(mod_opt_val, bool):
                storeopts[mod_opt] = 1 if mod_opt_val else 0
            if isinstance(mod_opt_val, list):
                storeopts[mod_opt] = ','.join(str(x) for x in mod_opt_val)
    return storeopts

def configUnserialize(opts: dict, referencePoint: dict, filterSystem: bool = True):
    if not isinstance(opts, dict):
        raise TypeError(f"opts is {type(opts)}; expected dict()")
    if not isinstance(referencePoint, dict):
        raise TypeError(f"referencePoint is {type(referencePoint)}; expected dict()")
    returnOpts = deepcopy(referencePoint)
    for opt in list(referencePoint.keys()):
        if opt.startswith('__') and filterSystem:
            continue
        if opt not in opts:
            continue
        if isinstance(referencePoint[opt], bool):
            returnOpts[opt] = True if opts[opt] == "1" else False
            continue
        if isinstance(referencePoint[opt], str):
            returnOpts[opt] = str(opts[opt])
            continue
        if isinstance(referencePoint[opt], int):
            returnOpts[opt] = int(opts[opt])
            continue
        if isinstance(referencePoint[opt], list):
            if isinstance(referencePoint[opt][0], int):
                returnOpts[opt] = [int(x) for x in str(opts[opt]).split(",")]
            else:
                returnOpts[opt] = str(opts[opt]).split(",")
    if '__modules__' not in referencePoint:
        return returnOpts
    if not isinstance(referencePoint['__modules__'], dict):
        raise TypeError(f"referencePoint['__modules__'] is {type(referencePoint['__modules__'])}; expected dict()")
    if '__modules__' in referencePoint:
        if '__modules__' not in returnOpts:
            returnOpts['__modules__'] = dict()
        for modName in referencePoint['__modules__']:
            if modName not in returnOpts['__modules__']:
                returnOpts['__modules__'][modName] = dict()
            if 'opts' in referencePoint['__modules__'][modName]:
                if 'opts' not in returnOpts['__modules__'][modName]:
                    returnOpts['__modules__'][modName]['opts'] = dict()
                for opt in referencePoint['__modules__'][modName]['opts']:
                    returnOpts['__modules__'][modName]['opts'][opt] = referencePoint['__modules__'][modName]['opts'][opt]
            else:
                returnOpts['__modules__'][modName]['opts'] = dict()
    for modName in referencePoint['__modules__']:
        if 'opts' not in referencePoint['__modules__'][modName]:
            continue
        for opt in referencePoint['__modules__'][modName]['opts']:
            if opt.startswith('_') and filterSystem:
                continue
            if modName + ":" + opt in opts:
                ref_mod = referencePoint['__modules__'][modName]['opts'][opt]
                if isinstance(ref_mod, list) and len(ref_mod) == 0:
                    continue
                if isinstance(ref_mod, bool):
                    returnOpts['__modules__'][modName]['opts'][opt] = True if opts[modName + ":" + opt] == "1" else False
                    continue
                if isinstance(ref_mod, str):
                    returnOpts['__modules__'][modName]['opts'][opt] = str(opts[modName + ":" + opt])
                    continue
                if isinstance(ref_mod, int):
                    returnOpts['__modules__'][modName]['opts'][opt] = int(opts[modName + ":" + opt])
                    continue
                if isinstance(ref_mod, list):
                    if isinstance(ref_mod[0], int):
                        returnOpts['__modules__'][modName]['opts'][opt] = [int(x) for x in str(opts[modName + ":" + opt]).split(",")]
                    else:
                        returnOpts['__modules__'][modName]['opts'][opt] = str(opts[modName + ":" + opt]).split(",")
    return returnOpts
