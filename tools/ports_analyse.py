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

def custom_json_indent(obj, level=0, indent=4, sort_keys=True, max_length=80):
    if sort_keys is True:
        sort_fnc = lambda x: sorted(x, key=lambda y: y[0].lower())
    else:
        sort_fnc = lambda x: x

    """
    Custom function to indent JSON structure, but combine lines for elements with only a few or short items.
    """
    # Check if obj is a list or dict
    if isinstance(obj, list):
        # If obj is a list, join its elements with commas and no spaces
        items = ", ".join([custom_json_indent(item, level=level + 1, indent=indent, sort_keys=sort_keys, max_length=max_length) for item in obj])
        # If the list fits on a single line, return it on one line
        if len(items) <= (max_length - (indent * level) - 2):
            return f"[{items}]"
        # If the list spans multiple lines, indent it and add newlines
        else:
            indent_str = "\n" + (" " * (level * indent))
            items = ("," + indent_str).join([custom_json_indent(item, level=level + 1, indent=indent, sort_keys=sort_keys, max_length=max_length) for item in obj])
            return f"[{indent_str}{items}{indent_str[:-indent]}]"
    elif isinstance(obj, dict):
        # If obj is a dict, indent its keys and values and join them with commas and newlines
        items = ",".join([
            f"{json.dumps(k)}: {custom_json_indent(v, level=level + 1, indent=indent, sort_keys=sort_keys, max_length=max_length)}"
            for k, v in sort_fnc(obj.items())
            ])
        # If the dict fits on a single line, return it on one line
        if len(items) <= (max_length - (indent * level) - 2):
            return f"{{{items.strip()}}}"
        # If the dict spans multiple lines, indent it and add newlines
        else:
            indent_str = "\n" + (" " * (level * indent))
            items = ("," + indent_str).join([
                f"{json.dumps(k, sort_keys=sort_keys)}: {custom_json_indent(v, level=level + 1, indent=indent, sort_keys=sort_keys, max_length=max_length)}"
                for k, v in sort_fnc(obj.items())
                ])
            return f"{{{indent_str}{items}{indent_str[:-indent]}}}"
    else:
        # If obj is not a list or dict, return its JSON representation
        return json.dumps(obj, sort_keys=sort_keys)

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
    """
    Similar to the one in harbourmaster, but more streamlined.
    """
    __attrs__ = (
        'file', 'name', 'items', 'items_opt')

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
        self.name = info.get('name', None)
        self.items = info.get('items', None)
        self.items_opt = info.get('items_opt', None)

        if isinstance(self.items, list):
            self.items = [
                item
                for item in self.items
                if isinstance(item, str) and item != ""]

        if isinstance(self.items_opt, list):
            self.items_opt = [
                item
                for item in self.items_opt
                if isinstance(item, str) and item != ""]

            if self.items_opt == []:
                self.items_opt = None

    def merge_info(self, other):
        BLANK = object()

        if isinstance(other, (str, dict)):
            other = PortInfo(other)

        elif isinstance(other, PortInfo):
            pass

        else:
            raise ValueError(str(info))

        for attr in self.__attrs__:
            value_a = getattr(self, attr)
            value_b = getattr(other, attr, BLANK)

            if value_b is BLANK:
                continue

            if value_a is None or value_a == "" or value_a == []:
                setattr(self, attr, value_b)

            if value_b in (True, False) and value_a in (True, False, None):
                setattr(self, attr, value_b)
                continue

            if isinstance(value_b, str) and value_a in ("", None):
                setattr(self, attr, value_b)
                continue

            if isinstance(value_b, list) and value_a in ([], None):
                setattr(self, attr, value_b)
                continue

            if attr == 'attr':
                for key in value_b.keys():
                    if key not in value_a:
                        value_a[key] = value_b[key]
                        continue

                    if value_b[key] in (True, False) and value_a[key] in (True, False, None):
                        value_a[key] = value_b[key]
                        continue

                    if isinstance(value_b[key], str) and value_a[key] in ("", None):
                        value_a[key] = value_b[key]
                        continue

                    if isinstance(value_b[key], list) and value_a[key] in ([], None):
                        value_a[key] = value_b[key]
                        continue

            self.items = [
                item
                for item in self.items
                if isinstance(item, str) and item != ""]

            if isinstance(self.items_opt, list):
                self.items_opt = [
                    item
                    for item in self.items_opt
                    if isinstance(item, str) and item != ""]

                if self.items_opt == []:
                    self.items_opt = None

    def to_dict(self):
        return {
            attr: getattr(self, attr)
            for attr in self.__attrs__
            if getattr(self, attr) is not None
            }

    @property
    def dirs(self):
        return [
            item[:-1]
            for item in self.items
            if item.endswith('/')]

    @property
    def files(self):
        return [
            item
            for item in self.items
            if not item.endswith('/')]

    def __str__(self):
        return str(self.to_dict())

    def __repr__(self):
        return str(self.to_dict())

def clean_name(file_name, attr='name'):
    if attr == 'name':
        name = file_name.name
    elif attr == 'stem':
        name = file_name.name
        if '.' in name:
            name = name.split('.', 1)[0]
    else:
        name = str(file_name)

    name = re.sub(r'[^a-zA-Z0-9, _\-\.]+', '', name.strip().casefold())
    return re.sub(r'[ \.]+', '.', name)

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


def analyse_known_port(file_name, all_data):
    """
    These are for special ports. Which won't ever be on PortMaster, but we know about.
    """

    with file_name.open('r') as fh:
        port_data = json.load(fh)


    port_info = PortInfo(port_data)
    zip_name = f"{clean_name(file_name, 'stem')}.zip"

    ## These two are always overriden.
    port_info.name = zip_name

    port_info.file = f"{port_info.dirs[0]}/{(clean_name(file_name, 'stem') + '.port.json')}"

    if port_info.items_opt is not None:
        for item in port_info.items_opt:
            add_nicely(all_data['items'], item, zip_name)

    for item in port_info.items:
        add_nicely(all_data['items'], item, zip_name)

    all_data['ports'][zip_name] = port_info.to_dict()


def analyse_known_ports(root_path, all_data, state):
    # print(f"Checking {root_path}")
    for sub_file in root_path.glob('*.port.json'):
        zip_name = clean_name(sub_file, 'stem') + '.zip'

        if zip_name in ('portmaster.zip', 'fallout.1.zip', 'alephone.zip'):
            continue

        # if zip_name in all_data['ports']:
        #     continue

        md5sum = hash_file(sub_file)
        if md5sum in state['seen']:
            continue

        print(f"Scanning {zip_name}")
        analyse_known_port(sub_file, all_data)
        state['seen'][md5sum] = zip_name


def analyse_port(file_name, all_data, state):
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
                print(f"- illegal file {file_info.filename!r}.")
                continue

            if file_info.filename.startswith('../'):
                ## Little
                print(f"- illegal file {file_info.filename!r}.")
                continue

            if '/../' in file_info.filename:
                ## Shits
                print(f"- illegal file {file_info.filename!r}.")
                continue

            if '/./' in file_info.filename:
                ## Not too bad I suppose.
                print(f"- illegal file {file_info.filename!r}.")
                continue

            if '/' in file_info.filename:
                parts = file_info.filename.split('/')

                if parts[0] not in dirs:
                    items.append(parts[0] + '/')
                    dirs.append(parts[0])

                if len(parts) == 2:
                    if parts[1].lower().endswith('.port.json'):
                        ## TODO: add the ability for multiple port folders to have multiple port.json files. ?
                        if port_info_file is not None:
                            print(f"- multiple port.json files.")
                            print(f"  - Before: {port_info_file!r}")
                            print(f"  - Now:    {file_info.filename!r}")

                        port_info_file = file_info.filename

                if file_info.filename.lower().endswith('.sh'):
                    print(f"- extra script {file_info.filename!r}, this can cause issues.")

            else:
                if file_info.filename.lower().endswith('.sh'):
                    scripts.append(file_info.filename)
                    items.append(file_info.filename)
                else:
                    print(f"- extra file at root level thats not a script: {file_info.filename!r}")

        for script in scripts:
            with zf.open(script, "r") as fh:
                md5sum = hash_text(fh.read())
                # print(script, md5sum)
                if md5sum not in all_data['md5']:
                    all_data['md5'][md5sum] = script

        if port_info_file is not None:
            with zf.open(port_info_file, "r") as fh:
                port_info = PortInfo(json.loads(fh.read()))
        else:
            port_info = PortInfo({})

    if zip_name in all_data['ports']:
        return

    ## These two are always overriden.
    port_info.items = items
    port_info.name = zip_name

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


def analyse_ports(root_path, all_data, state):
    # print(f"Checking {root_path}")
    for sub_file in root_path.glob('*.zip'):
        zip_name = clean_name(sub_file)

        if zip_name in ('portmaster.zip', 'fallout.1.zip', 'alephone.zip'):
            continue

        md5sum = hash_file(sub_file)
        if md5sum in state['seen']:
            continue

        # if zip_name in all_data['ports']:
        #     continue

        print(f"Scanning {zip_name}")
        analyse_port(sub_file, all_data, state)
        state['seen'][md5sum] = zip_name


def git_rewind(root_path, all_data, state):
    month_to_num = {
        'jan': 1,
        'feb': 2,
        'mar': 3,
        'apr': 4,
        'may': 5,
        'jun': 6,
        'jul': 7,
        'aug': 8,
        'sep': 9,
        'oct': 10,
        'nov': 11,
        'dec': 12,
        }
    commits = []

    commit_ids = []

    for line in subprocess.check_output(['git', 'log']).decode('utf-8').split('\n'):
        if not line.startswith('commit'):
            continue

        commit_id = line.split(' ', 1)[1]

        commit_ids.append(commit_id)

    all_zips = set()

    try:
        counter = 0
        for i, commit_id in enumerate(commit_ids, 1):

            if commit_id in state['git']:
                continue

            subprocess.check_output(['git', 'checkout', commit_id], stderr=subprocess.STDOUT)

            counter += 1
            analyse_ports(root_path, all_data, state)
            print(f"Done: {counter:3d} -- {i:3d} / {len(commit_ids):3d}")

            state['git'][commit_id] = True

            ## This seems to work well enough.
            # if counter > 100:
            #     break

    except KeyboardInterrupt:
        pass

    subprocess.check_output(['git', 'checkout', 'main'])

    for sub_file in root_path.glob('*.zip'):
        first_date = None
        last_date = None

        zip_name = clean_name(sub_file)

        if zip_name in ('portmaster.zip', 'fallout.1.zip', 'alephone.zip'):
            continue

        for line in subprocess.check_output(['git', 'log', '--', sub_file.name]).decode('utf-8').split('\n'):
            match = re.match(r'Date:\s+\w+ (\w+) (\d+) \d+:\d+:\d+ (\d+)', line, re.I)
            if not match:
                continue

            first_date = f"{match.group(3)}-{month_to_num[match.group(1).casefold()]:02d}-{int(match.group(2)):02d}"
            if last_date is None:
                last_date = first_date

        print(f"{zip_name}: {first_date} - {last_date}")
        all_data['ports'][zip_name]['date'] = [first_date, last_date]

def main():
    ## The local portmaster repo
    root_path   = Path('../Portmaster/').absolute()
    ## Portmaster-Hosting folder, download as new large files are added.
    host_path   = Path('../Portmaster-Hosting/').absolute()
    ## Special ports.
    known_ports = Path('known-ports/').absolute()

    info_file   = Path('pylibs/ports_info.py').absolute()

    state_file   = Path('tools/state.json').absolute()

    state = {
        'git': {},
        'seen': {},
        }

    all_data = {
        'items': {},
        'ports': {},
        'md5': {},
        }

    if state_file.is_file():
        with state_file.open('rt') as fh:
            state = json.load(fh)

    if info_file.is_file():
        check = 'ports_info = '
        all_text = info_file.read_text()
        print("Loading port_info data.")
        if check in all_text:
            data = all_text[(all_text.index(check) + len(check)):]
            # print((all_text.index(check) + len(check)), data[:32])
            all_data = json.loads(data)

    if 'md5' not in all_data:
        all_data['md5'] = {}

    analyse_known_ports(known_ports, all_data, state)

    analyse_ports(host_path, all_data, state)

    os.chdir(root_path)

    git_rewind(root_path, all_data, state)

    ## Dump it using a custom json dumper.
    with state_file.open('wt') as fh:
        out_str = custom_json_indent(state, level=1, indent=2, sort_keys=True)
        fh.write(out_str)

    with info_file.open('wt') as fh:
        fh.write( "# -- Autogenerated by tools/ports_analyse.py --\n")
        fh.write(f"# -- {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} --\n\n")
        out_str = custom_json_indent(all_data, level=1, indent=2, sort_keys=True)
        fh.write(f"ports_info = {out_str}\n")


if __name__ == '__main__':
    main()
