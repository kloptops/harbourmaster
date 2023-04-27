
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
    'version': 2,
    'name': None,
    'items': None,
    'items_opt': None,
    'attr': {},
    'status': None,
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


def port_info_load(raw_info, source_name=None, do_default=False):
    if isinstance(raw_info, pathlib.PurePath):
        source_name = str(raw_info)

        with raw_info.open('r') as fh:
            info = json_safe_load(fh)
            if info is None:
                if do_default:
                    info = {}
                else:
                    return None

    elif isinstance(raw_info, str):
        if raw_info.strip().startswith('{') and raw_info.strip().endswith('}'):
            if source_name is None:
                source_name = "<str>"

            info = json_safe_loads(info)
            if info is None:
                if do_default:
                    info = {}
                else:
                    return None

        elif Path(raw_info).is_file():
            source_name = raw_info

            with open(rawinfo, 'r') as fh:
                info = json_safe_load(fh)
                if info is None:
                    if do_default:
                        info = {}
                    else:
                        return None

        else:
            if source_name is None:
                source_name = "<str>"

            logger.error(f'Unable to load port_info from <b>{source_name!r}</b>: <b>{raw_info!r}</b>')
            if do_default:
                info = {}
            else:
                return None

    elif isinstance(raw_info, dict):
        if source_name is None:
            source_name = "<dict>"

        info = raw_info

    else:
        logger.error(f'Unable to load port_info from <b>{source_name!r}</b>: <b>{raw_info!r}</b>')
        if do_default:
            info = {}
        else:
            return None

    if info.get('version', None) == 1 or 'source' in info:
        info = info.copy()
        info['name'] = info['source'].rsplit('/', 1)[-1]
        del info['source']
        info['version'] = 2

        if info.get('md5', None) is not None:
            info['status'] = {
                'source': "Unknown",
                'md5': info['md5'],
                'status': "Unknown",
                }

    # This strips out extra stuff
    port_info = {}

    for attr, attr_default in PORT_INFO_ROOT_ATTRS.items():
        if attr_default == {}:
            attr_default = {}

        port_info[attr] = info.get(attr, attr_default)

    for attr, attr_default in PORT_INFO_ATTR_ATTRS.items():
        port_info['attr'][attr] = info.get('attr', {}).get(attr, attr_default)

    return port_info


def port_info_merge(port_info, other):
    if isinstance(other, (str, pathlib.PurePath)):
        other_info = port_info_parse(other)
    elif isinstance(other, dict):
        other_info = other
    else:
        logger.error(f"Unable to merge {other!r}")
        return None

    for attr, attr_default in PORT_INFO_ROOT_ATTRS.items():
        if attr == 'attr':
            break

        value_a = port_info[attr]
        value_b = other_info[attr]

        if value_a is None or value_a == "" or value_a == []:
            port_info[attr] = value_b
            continue

        if value_b in (True, False) and value_a in (True, False, None):
            port_info[attr] = value_b
            continue

        if isinstance(value_b, str) and value_a in ("", None):
            port_info[attr] = value_b
            continue

        if isinstance(value_b, list) and value_a in ([], None):
            port_info[attr] = value_b[:]
            continue

        if isinstance(value_b, dict) and value_a in ({}, None):
            port_info[attr] = value_b.copy()
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
