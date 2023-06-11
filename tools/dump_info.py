#!/usr/bin/env python3

import pathlib
from pathlib import Path

def safe_cat(file_name):
    if isinstance(file_name, str):
        file_name = pathlib.Path(file_name)

    elif not isinstance(file_name, pathlib.PurePath):
        raise ValueError(file_name)

    if str(file_name).startswith('~/'):
        file_name = file_name.expanduser()

    if not file_name.is_file():
        return ''

    return file_name.read_text()


def safe_ls(path_name):
    if isinstance(path_name, str):
        path_name = pathlib.Path(path_name)

    elif not isinstance(path_name, pathlib.PurePath):
        raise ValueError(path_name)

    if str(path_name).startswith('~/'):
        path_name = path_name.expanduser()

    if not path_name.is_dir():
        return []

    return [
        str(file_name)
        for file_name in path_name.iterdir()]


if __name__ == '__main__':
    files = [
        '/etc/os-release',
        '/opt/.retrooz/device',
        '~/.config/.OS_ARCH',
        '~/.config/.DEVICE',
        '~/.config/.OS',
        '/usr/share/plymouth/themes/text.plymouth',
        '/sys/firmware/devicetree/base/model',
        '/sys/firmware/devicetree/base/compatible',
        '/sys/class/dmi/id/sys_vendor',
        '/sys/class/dmi/id/product_name',
        ]

    dirs = [
        '/dev/input/by-path',
        '/boot/',
        ]

    print("-- HARDWARE INFO --")

    print("-" * 30)
    for file in files:
        print(f"{file}:")
        print(safe_cat(file))
        print("-" * 30)

    for dir in dirs:
        print(f"{dir}:")
        print('\n'.join(safe_ls(dir)))
        print("-" * 30)
