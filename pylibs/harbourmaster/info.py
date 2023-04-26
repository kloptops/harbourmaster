
import json
import pathlib

from pathlib import Path

import utility

from utility import cprint, cstrip

from .config import *
from .util import *


################################################################################
## Port Information
PORT_INFO_ROOT_ATTRS = {
    'version': 1,
    'source': None,
    'items': None,
    'items_opt': None,
    'md5': None,
    'attr': {},
    }

PORT_INFO_ATTR_ATTRS = {
    'title': "",
    'desc': "",
    'inst': "",
    'genres': [],
    'porter': "",
    'image': {},
    'rtr': False,
    'runtime': None,
    'reqs': [],
    }


def port_info_load(raw_info, source_name=None):
    if isinstance(raw_info, pathlib.PurePath):
        source_name = str(raw_info)

        with raw_info.open('r') as fh:
            info = json_safe_load(fh)
            if info is None:
                return None

    elif isinstance(raw_info, str):
        if raw_info.strip().startswith('{') and raw_info.strip().endswith('}'):
            if source_name is None:
                source_name = "<str>"

            info = json_safe_loads(info)
            if info is None:
                return None

        elif Path(raw_info).is_file():
            source_name = raw_info

            with open(rawinfo, 'r') as fh:
                info = json_safe_load(fh)
                if info is None:
                    return None

        else:
            if source_name is None:
                source_name = "<str>"

            logger.error(f'Unable to load port_info from <b>{source_name!r}</b>: <b>{raw_info!r}</b>')
            return None

    elif isinstance(raw_info, dict):
        if source_name is None:
            source_name = "<dict>"

        info = raw_info

    else:
        logger.error(f'Unable to load port_info from <b>{source_name!r}</b>: <b>{raw_info!r}</b>')
        return None

    # This strips out extra stuff
    port_info = {}

    for attr, attr_default in PORT_INFO_ROOT_ATTRS.items():
        port_info[attr] = info.get(attr, attr_default)

    for attr, attr_default in PORT_INFO_ATTR_ATTRS.items():
        port_info['attr'][attr] = info.get('attr', {}).get(attr, attr_default)

    return port_info


def port_info_merge(port_info, other):
    if isinstance(other, (str, pathlib.PurePath)):
        other_info = port_info_parse(other)

    for attr, attr_default in PORT_INFO_ROOT_ATTRS.items():
        if attr == 'attr':
            break

        value_a = port_info[attr]
        value_b = other_info['attr']

        if value_a is None or value_a == "" or value_a == []:
            value_a[attr] = value_b
            continue

        if value_b in (True, False) and value_a in (True, False, None):
            value_a[attr] = value_b
            continue

        if isinstance(value_b, str) and value_a in ("", None):
            value_a[attr] = value_b
            continue

        if isinstance(value_b, list) and value_a in ([], None):
            value_a[attr] = value_b
            continue

    for key_b, value_b in other_info['attr'].items():
        if key_b not in port_info['attr']:
            continue

        if value_b in (True, False) and port_info['attr'][key_b] in (True, False, None):
            port_info['attr'][key_b] = value_b
            continue

        if isinstance(value_b, str) and port_info['attr'][key_b] in ("", None):
            port_info['attr'][key_b] = value_b
            continue

        if isinstance(value_b, list) and port_info['attr'][key_b] in ([], None):
            port_info['attr'][key_b] = value_b[:]
            continue

        if isinstance(value_b, dict) and port_info['attr'][key_b] in ({}, None):
            port_info['attr'][key_b] = value_b.copy()
            continue

    return port_info


__all__ = (
    'port_info_load',
    'port_info_merge',
    )
