
# System imports
import datetime
import json
import pathlib
import platform
import re
import zipfile

from pathlib import Path

# Included imports

from loguru import logger

# Module imports
from .config import *
from .info import *
from .util import *


def safe_cat(file_name):
    if isinstance(file_name, str):
        file_name = pathlib.Path(file_name)

    elif not isinstance(file_name, pathlib.PurePath):
        raise ValueError(file_name)

    if not file_name.is_file():
        return ''

    return file_name.read_text()


def file_exists(file_name):
    return Path(file_name).exists()

def os_info():
    if HM_TESTING:
        return {
            'OS_NAME': platform.system(),
            'OS_VERSION': platform.release(),
            'HW_DEVICE': 'PC',
            }

    all_data = {}

    plymouth = safe_cat('/usr/share/plymouth/themes/text.plymouth')
    for result in re.findall(r'^title=(.*?) \(([^\)]+)\)$', plymouth, re.I|re.M):
        all_data['OS_NAME'] = result[0]
        all_data['OS_VERSION'] = result[1]

    os_release = safe_cat('/etc/os-release')
    for result in re.findall(r'^([a-z0-9_]+)="([^"]+)"$', os_release, re.I|re.M):
        if result[0] in ('OS_NAME', 'HW_DEVICE'):
            all_data.setdefault(result[0], result[1])

    return all_data


def hardware_features():
    hardware = {
        'analogsticks': 2,
        'resolution': '640x480',
        'param_device': 'unknown',
        'device': 'unknown',
        'hotkey': None,
        }

    if file_exists('/dev/input/by-path/platform-ff300000.usb-usb-0:1.2:1.0-event-joystick'):
        # RG351P/M
        hardware['device'] = "03000000091200000031000011010000"
        hardware['param_device'] = "anbernic"
        hardware['resolution'] = '480x320'

        if file_exists('/boot/rk3326-rg351v-linux.dtb') or safe_cat("/storage/.config/.OS_ARCH").strip().casefold() == "rg351v":
            # RG351V
            hardware['analogsticks'] = 1
            hardware['resolution'] = '640x480'

    elif file_exists('/dev/input/by-path/platform-odroidgo2-joypad-event-joystick'):
        if "190000004b4800000010000001010000" in safe_cat('/etc/emulationstation/es_input.cfg'):
            hardware['device'] = "190000004b4800000010000001010000"
            hardware['param_device'] = "oga"
            hardware['hotkey'] = "l3"
        else:
            if file_exists('/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2600.2'):
                hardware['device'] = "19005b284b4800000010000000010000"
            else:
                hardware['device'] = "190000004b4800000010000000010000"

            hardware['param_device'] = "rk2020"

        hardware['resolution'] = '480x320'
        hardware['analogsticks'] = 1

    elif file_exists('/dev/input/by-path/platform-odroidgo3-joypad-event-joystick'):
        hardware['device'] = "190000004b4800000011000000010000"
        hardware['param_device'] = "ogs"

        if (
                safe_cat('/etc/emulationstation/es_input.cfg').strip().casefold() == "arkos" and
                safe_cat('/etc/emulationstation/es_input.cfg').strip().casefold() == "rgb10max"):
            hardware['hotkey'] = "guide"

        if file_exists('/opt/.retrooz/device'):
            hardware['param_device'] = safe_cat("/opt/.retrooz/device").strip().casefold()
            if "rgb10max2native" in hardware['param_device']:
                hardware['param_device'] = "rgb10maxnative"
            if "rgb10max2top" in hardware['param_device']:
                hardware['param_device'] = "rgb10max2top"

    elif file_exists('/dev/input/by-path/platform-gameforce-gamepad-event-joystick'):
        hardware['device'] = "19000000030000000300000002030000"
        hardware['param_device'] = "chi"
        hardware['hotkey'] = "l3"

    elif file_exists('/dev/input/by-path/platform-singleadc-joypad-event-joystick'):
        hardware['device'] = "190000004b4800000111000000010000"
        hardware['param_device'] = "rg552"
        hardware['resolution'] = '1920x1152'

    return hardware


logger.debug(f'HARDWARE: {os_info()}, {hardware_features()}')

__all__ = (
    'os_info',
    'hardware_features',
    )
