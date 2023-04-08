#!/usr/bin/env python3

import contextlib
import datetime
import fnmatch
import gzip
import hashlib
import json
import pathlib
import re
import os
import shutil
import sys
import tempfile
import textwrap
import zipfile
import subprocess

from difflib import Differ
from pathlib import Path


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


def analyse_port(file_name, zip_hash, all_data):
    # When we analyse a port, we want to look at the root directories, and the rooth scripts.
    root_scripts = []
    root_directories = []
    print(file_name)
    with zipfile.ZipFile(file_name, 'r') as zf:
        for file_info in zf.infolist():
            if file_info.filename.startswith('/'):
                continue

            if '/' in file_info.filename:
                root_directory = file_info.filename.split('/', 1)[0]
                if root_directory not in root_directories:
                    root_directories.append(root_directory)
            else:
                file_hash = hash_text(zf.read(file_info.filename))

                root_scripts.append([file_info.filename, file_info.file_size, file_hash])

    return {
        'scripts': root_scripts,
        'dirs': root_directories,
        }

def append_to_list(the_list, item):
    the_list.append(item)

def prepend_to_list(the_list, item):
    the_list.insert(0, item)

def analyse_ports(root_path, commit_id, all_data, is_old=True):
    if is_old:
        add_mode = append_to_list
    else:
        add_mode = prepend_to_list

    zip_files = {}
    print(f"Checking {root_path}")
    for sub_file in root_path.iterdir():
        if not sub_file.is_file():
            continue

        # print(sub_file, sub_file.suffix)
        if sub_file.suffix not in ('.zip', ):
            continue

        if sub_file.name.lower() == 'portmaster.zip':
            continue

        file_hash = hash_file(sub_file)

        file_size = sub_file.stat().st_size

        if file_hash in all_data['cache']:
            zip_files[sub_file.name] = all_data['cache'][file_hash]
        else:
            zip_files[sub_file.name] = temp = {
                'hash': file_hash,
                'info': analyse_port(sub_file, file_hash, all_data),
                }

            all_data['cache'][file_hash] = temp

        for script_file_name, script_file_size, script_file_hash in zip_files[sub_file.name]['info']['scripts']:
            rsl = all_data['root_script_lookup'].setdefault(script_file_name, {}).setdefault(script_file_hash, [])
            if file_hash not in rsl:
                add_mode(rsl, file_hash)

        for root_directory in zip_files[sub_file.name]['info']['dirs']:
            rdl = all_data['root_directory_lookup'].setdefault(root_directory, [])
            if sub_file.name not in rdl:
                add_mode(rdl, sub_file.name)

        zhl = all_data['zip_hash'].setdefault(sub_file.name, [])
        if file_hash not in zhl:
            add_mode(zhl, file_hash)

        hzl = all_data['hash_zip'].setdefault(file_hash, [])
        if sub_file.name not in hzl:
            add_mode(hzl, sub_file.name)

        zsl = all_data['zip_size'].setdefault(sub_file.name, {}).setdefault(str(file_size), [])
        if file_hash not in zsl:
            add_mode(zsl, file_hash)

        # print(f"{commit_id[:10]}: {sub_file.name}, {file_hash}")

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
        for i, commit_id in enumerate(commit_ids):
            subprocess.check_output(['git', 'checkout', commit_id])

            commits.append(analyse_ports(root_path, commit_id, all_data, is_old))
            print(f"Done: {i:3d} / {len(commit_ids):3d}")

    except KeyboardInterrupt:
        pass

    subprocess.check_output(['git', 'checkout', 'main'])

    return commits


def main():
    root_path = Path('../Portmaster/').absolute()
    info_file = Path('ports_info.json').absolute()
    info_file_gz = Path('ports_info.json.gz').absolute()

    cache_file_gz = Path('ports_info_cache.json.gz').absolute()

    if cache_file_gz.is_file():
        with gzip.open(cache_file_gz, 'rt') as gz:
            cache = json.load(gz)
    else:
        cache = {
            'first_run': True,
            'first_checkout': None,
            'last_checkout': None,
            }

    all_data = {
        'cache': cache,
        'hash_zip': {},
        'root_directory_lookup': {},
        'root_script_lookup': {},
        'zip_hash': {},
        'zip_size': {},
        }

    os.chdir(root_path)

    commits = git_rewind(root_path, all_data)

    del all_data['cache']
    with info_file.open('w') as fh:
        json.dump(all_data, fh, indent=4)

    with gzip.open(info_file_gz, 'wt', 9) as gz:
        json.dump(all_data, gz)

    with gzip.open(cache_file_gz, 'wt', 1) as gz:
        json.dump(cache, gz)


if __name__ == '__main__':
    main()
