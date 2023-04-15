#!/usr/bin/env python3

import contextlib
import datetime
import fnmatch
import gzip
import hashlib
import json
import os
import pathlib
import pprint
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile


from difflib import Differ
from pathlib import Path

"""
The scripts purpose is to analyse portmaster and build up enough information to make <portname>.port.json for any older ports.

If a port has a port.json in it, it will load it.
"""

def hash_file(file):
    md5 = hashlib.md5()
    with open(file, 'rb') as fh:
        while True:
            data = fh.read(1024 * 1024)
            if len(data) == 0:
                break

            md5.update(data)

    return md5.hexdigest()


def hash_text(text):
    md5 = hashlib.md5()
    if isinstance(text, str):
        md5.update(text.encode('utf-8'))
    else:
        md5.update(text)

    return md5.hexdigest()


################################################################################
## Port Information
class PortInfo():
    __attrs__ = (
        'file', 'source', 'items', 'items_opt')

    def __init__(self, info):
        if isinstance(info, pathlib.PurePath):
            with info.open('r') as fh:
                self.from_dict(json.load(fh))

        elif isinstance(info, dict):
            self.from_dict(info)

        else:
            raise ValueError(str(info))

    def from_dict(self, info):
        self.file = info.get('file', None)
        self.source = info.get('source', None)
        self.items = info.get('items', None)
        self.items_opt = info.get('items_opt', None)

    def merge_info(self, other):
        if isinstance(other, (str, dict)):
            info = PortInfo(other)

        elif isinstance(other, PortInfo):
            pass

        else:
            raise ValueError(str(info))

        for attr in self.__attrs__:
            value_a = getattr(self, attr)
            value_b = getattr(other, attr)

            if value_a is None and value_b is not None:
                setattr(self, attr, value_b)

    def to_dict(self):
        return {
            attr: getattr(self, attr)
            for attr in self.__attrs__
            if getattr(self, attr) is not None
            }

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return str(self.to_dict())

def clean_name(file_name, attr='name'):
    if attr == 'name':
        name = file_name.name
    elif attr == 'stem':
        name = file_name.stem
    else:
        name = str(file_name)

    return name.lower().replace(" ", ".").replace("..", ".")

def add_nicely(base_dict, key, value):
    if key not in base_dict:
        base_dict[key] = value
        return

    if isinstance(base_dict[key], str):
        if base_dict[key] == value:
            return

        base_dict[key] = [base_dict[key]]

    if value not in base_dict[key]:
        base_dict[key].append(value)

def analyse_port(file_name, all_data):
    # When we analyse a port, we want to look at the root directories, and the rooth scripts.
    port_info_file = None
    items = []
    dirs = []
    scripts = []

    zip_name = clean_name(file_name)

    with zipfile.ZipFile(file_name, 'r') as zf:
        for file_info in zf.infolist():
            if file_info.filename.startswith('/'):
                ## Sneaky
                print(f"Port {zip_name} has an illegal file {file_info.filename!r}.")

            if file_info.filename.startswith('../'):
                ## Little
                print(f"Port {zip_name} has an illegal file {file_info.filename!r}.")

            if '/../' in file_info.filename:
                ## Shits
                print(f"Port {zip_name} has an illegal file {file_info.filename!r}.")

            if '/' in file_info.filename:
                parts = file_info.filename.split('/')

                if parts[0] not in dirs:
                    items.append(parts[0] + '/')
                    dirs.append(parts[0])

                if len(parts) == 2:
                    if parts[1].lower().endswith('.port.json'):
                        ## TODO: add the ability for multiple port folders to have multiple port.json files. ?
                        if port_info_file is not None:
                            print(f"Port {zip_name} has multiple port.json files.")
                            print(f"- Before: {port_info_file!r}")
                            print(f"- Now:    {file_info.filename!r}")

                        port_info_file = file_info.filename

            else:
                if file_info.filename.lower().endswith('.sh'):
                    scripts.append(file_info.filename)
                    items.append(file_info.filename)
                else:
                    print(f"Port {zip_name} contains {file_info.filename} at the top level, but it is not a shell script.")

        if port_info_file is not None:
            with zf.open(port_info_file, "r") as fh:
                port_info = PortInfo(json.loads(fh.read()))
        else:
            port_info = PortInfo({})

    ## These two are always overriden.
    port_info.items = items
    port_info.source = f"pm/{zip_name}"

    if port_info_file is None:
        port_info.file = f"{dirs[0]}/{(clean_name(file_name, 'stem') + '.port.json')}"
    else:
        port_info.file = port_info_file

    if port_info.items_opt is not None:
        for item in port_info.items_opt:
            add_nicely(all_data['items'], item, zip_name)

    for item in items:
        add_nicely(all_data['items'], item, zip_name)

    all_data['ports'][zip_name] = port_info.to_dict()


def analyse_ports(root_path, all_data):
    zip_files = {}
    print(f"Checking {root_path}")
    for sub_file in root_path.iterdir():
        if not sub_file.is_file():
            continue

        # print(sub_file, sub_file.suffix)
        if sub_file.suffix not in ('.zip', ):
            continue

        zip_name = clean_name(sub_file)

        if zip_name in ('portmaster.zip', 'fallout 1.zip'):
            continue

        if zip_name in all_data['ports']:
            continue

        analyse_port(sub_file, all_data)

    return zip_files


def git_rewind(root_path, all_data):
    commits = []

    commit_ids = []

    for line in subprocess.check_output(['git', 'log']).decode('utf-8').split('\n'):
        if not line.startswith('commit'):
            continue

        commit_id = line.split(' ', 1)[1]

        commit_ids.append(commit_id)

    try:
        for i, commit_id in enumerate(commit_ids, 1):
            subprocess.check_output(['git', 'checkout', commit_id])

            analyse_ports(root_path, all_data)
            print(f"Done: {i:3d} / {len(commit_ids):3d}")

            if i > 1:
                break

    except KeyboardInterrupt:
        pass

    subprocess.check_output(['git', 'checkout', 'main'])

def main():
    root_path = Path('../Portmaster/').absolute()
    host_path = Path('../Portmaster-Hosting/').absolute()
    info_file = Path('pylibs/ports_info.py').absolute()

    all_data = {
        'items': {},
        'ports': {},
        }

    analyse_ports(host_path, all_data)

    os.chdir(root_path)

    git_rewind(root_path, all_data)

    with info_file.open('wt') as fh:
        fh.write( "# -- Autogenerated by tools/ports_analyse.py --\n")
        fh.write(f"# -- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --\n\n")
        out_str = json.dumps(all_data, indent=4, sort_keys=True)
        fh.write(f"ports_info = {out_str}\n")


if __name__ == '__main__':
    main()
