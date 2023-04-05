#!/usr/bin/env python3

import hashlib
import json
import pathlib
import re
import sys
import textwrap
import zipfile
import datetime

from difflib import Differ
from pathlib import Path

## Insert our extra modules.
sys.path.insert(0, str(Path(__file__).parent / 'libs'))

import requests

################################################################################
## Override this for custom config folder, otherwise it will reside in `SCRIPT_DIRECTORY/config`
CONFIG_PATH=None
PORTS_PATH=None

SOURCE_DEFAULT_PORTMASTER = """
{
    "api": "PortMasterV1",
    "name": "PortMaster",
    "url": "https://api.github.com/repos/PortsMaster/PortMaster-Releases/releases/latest",
    "last_checked": null,
    "data": {}
}
""".strip()

################################################################################
## Default CONFIG_PATH

if CONFIG_PATH is None:
    CONFIG_PATH = Path(__file__).parent / 'config'
elif isinstance(CONFIG_PATH, str):
    CONFIG_PATH = Path(__file__)
elif isinstance(config_dir, pathlib.PurePath):
    # This is good.
    pass
else:
    print(f"Error: {CONFIG_PATH!r} is set to something weird.")
    exit(255)

## Default PORTS_PATH
if PORTS_PATH is None:
    PORTS_PATH = Path(__file__).parent.parent
elif isinstance(CONFIG_PATH, str):
    PORTS_PATH = Path(__file__)
elif isinstance(config_dir, pathlib.PurePath):
    # This is good.
    pass
else:
    print(f"Error: {PORTS_PATH!r} is set to something weird.")
    exit(255)

################################################################################
## 
def fetch(url):
    r = requests.get(url)
    if r.status_code != 200:
        print(f"Failed to download {r.status_code}")
        return None

    return r

def fetch_json(url):
    r = fetch(url)
    if r is None:
        return None

    return r.json()

def fetch_text(url):
    r = fetch(url)
    if r is None:
        return None

    return r.text


################################################################################
## APIS

class BaseSource():
    def __init__(self):
        pass

    def add_ports(self, port_list):
        raise NotImplementedError()


class PortMasterV1(BaseSource):
    def __init__(self, file_name, config):
        self._file_name = file_name
        self._config = config

        if len(self._config['data']) == 0:
            self._update()
        else:
            self._data = self._config['data']['data']
            self._ports = self._config['data']['ports']
            self._info = self._config['data']['info']

    def _update(self):
        data = fetch_json(self._config['url'])

        self._data = {}
        self._ports = []
        self._info = {}

        ## Load data from the assets.
        for asset in data['assets']:
            result = {
                'name': asset['name'],
                'size': asset['size'],
                'url': asset['browser_download_url'],
                }

            self._data[asset['name']] = result

            if asset['name'].lower().endswith('.zip'):
                self._ports.append(asset['name'])

        for line in fetch_text(self._data['ports.md']['url']).split('\n'):
            line = line.strip()
            if line == '':
                continue

            info = self._parse_port_info(line)
            if info['file'] not in self._ports:
                print(f'Found port {info["file"]} in `ports.md` but not in github list')

            self._info[info['file']] = info

        self._config['data']['data']  = self._data
        self._config['data']['ports'] = self._ports
        self._config['data']['info']  = self._info

        self._save()

    def _save(self):
        with self._file_name.open('w') as fh:
            json.dump(self._config, fh, indent=4)

    def _parse_port_info(self, text):
        # Super jank
        keys = {
            'title_f': 'title',
            'title_p': 'title',
            'locat': 'file',
            }

        info = {
            'title': '',
            'desc': '',
            'porter': '',
            'opengl': False,
            'power': False,
            'rtr': False,
            }

        for key, value in re.findall(r'(?:^|\s)(\w+)=\"([^"]+)"', text):
            if key.lower() == 'title_f':
                info['opengl'] = True

            if key.lower() == 'title_p':
                info['power'] = True

            key = keys.get(key.lower(), key.lower())
            if key == 'title':
                value = value[:-2]

            # Zips with spaces in their names get replaced with '.'
            value = value.replace('%20', '.')

            if key == 'runtype':
                key, value = 'rtr', True

            info[key] = value

        return info

    def add_ports(self, port_list):
        ## TODO
        pass


SOURCE_APIS = {
    'PortMasterV1': PortMasterV1,
    }

################################################################################
## Config loading
def load_config():
    """
    config = load_config()
    """

    if not CONFIG_PATH.is_dir():
        CONFIG_PATH.mkdir(0o755)

        with (CONFIG_PATH / '000_portmaster.source.json').open('w') as fh:
            fh.write(SOURCE_DEFAULT_PORTMASTER)

        with (CONFIG_PATH / 'config.json').open('w') as fh:
            fh.write('{"first_run": true}')


    source_files = list(CONFIG_PATH.glob('*.source.json'))
    source_files.sort()

    config = {
        'config_dir': CONFIG_PATH,
        'ports_dir': PORTS_PATH,
        'sources': [],
        'ports': [],
        }

    for source_file in source_files:
        with source_file.open() as fh:
            source_data = json.load(fh)

            assert 'api' in source_data, f'Missing key "api" in {source_file}.'
            assert 'name' in source_data, f'Missing key "name" in {source_file}.'
            assert 'last_checked' in source_data, f'Missing key "last_checked" in {source_file}.'
            assert 'data' in source_data, f'Missing key "data" in {source_file}.'
            assert source_data['api'] in SOURCE_APIS, f'Unknown api {source_data["api"]}.'

        source = SOURCE_APIS[source_data['api']](source_file, source_data)

        config['sources'].append(source)

        source.add_ports(config['ports'])

    return config


################################################################################
## Commands
def do_update(config, argv):
    """
    Update available ports, checks for new releases.
    """

    return 0



def do_help(config, argv):
    """
    Shows general help or help for a particular command.

    {command} help
    {command} help list
    """
    command = sys.argv[0]

    if len(argv) > 0:
        if argv[0].lower() not in all_commands:
            print(f"Error: unknown help command {argv[0]!r}")
            do_help(config, build_configs, [])
            return

        print(textwrap.dedent(all_commands[argv[0].lower()].__doc__.format(command=command)).strip())
        return

    print(f"{command} <update> [source/all] ")
    print(f"{command} <install/upgrade> [source/]<port_name> ")
    print(f"{command} <uninstall> [source/]<port_name> ")
    print(f"{command} <list> [source/all] [... filters]")
    print(f"{command} <help> <command>")
    print()
    print("All available commands: " + (', '.join(all_commands.keys())))


all_commands = {
    'update': do_update,
    'help': do_help,
    }

def main(argv):

    config = load_config()

    if len(argv) == 1:
        all_commands['help'](config, [])
        return 1

    if argv[1].lower() not in all_commands:
        print(f'Command {argv[1]!r} not found.')
        all_commands['help'](config, [])
        return 2

    return all_commands[argv[1].lower()](config, argv[2:])


if __name__ == '__main__':
    exit(main(sys.argv))
