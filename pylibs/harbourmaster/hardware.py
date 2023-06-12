
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

    if str(file_name).startswith('~/'):
        file_name = file_name.expanduser()

    if not file_name.is_file():
        return ''

    return file_name.read_text()


def file_exists(file_name):
    return Path(file_name).exists()


def device_info():
    if HM_TESTING:
        return {
            'system': platform.system(),
            'version': platform.release(),
            'device': 'PC',
            }

    all_data = {}

    ## Get Device

    # Works on ArkOS
    config_device = safe_cat('~/.config/.DEVICE')
    if config_device != '':
        all_data.setdefault('device', config_device.strip())

    # Works on ArkOS
    plymouth = safe_cat('/usr/share/plymouth/themes/text.plymouth')
    if plymouth != '':
        for result in re.findall(r'^title=(.*?) \(([^\)]+)\)$', plymouth, re.I|re.M):
            all_data['name'] = result[0]
            all_data['version'] = result[1]

    # Works on uOS / JELOS
    sfdbm = safe_cat('/sys/firmware/devicetree/base/model')
    if sfdbm != '':
        all_data.setdefault('device', sfdbm.split(' ')[1].strip().rstrip('\0'))

    # Works on AmberELEC / uOS / JELOS
    os_release = safe_cat('/etc/os-release')
    for result in re.findall(r'^([a-z0-9_]+)="([^"]+)"$', os_release, re.I|re.M):
        if result[0] in ('NAME', 'VERSION', 'OS_NAME', 'OS_VERSION', 'HW_DEVICE', 'COREELEC_DEVICE'):
            all_data.setdefault(result[0].rsplit('_', 1)[-1].lower(), result[1].strip())

    return all_data


def hardware_features():
    device = device_info()
    hardware = {
        'analogsticks': 2,
        'resolution': '640x480',
        'device': 'unknown',
        'joystick': 'unknown',
        'hotkey': None,
        }

    if file_exists('/dev/input/by-path/platform-ff300000.usb-usb-0:1.2:1.0-event-joystick'):
        # RG351P/M
        hardware['joystick'] = "03000000091200000031000011010000"
        hardware['device'] = "anbernic"
        hardware['resolution'] = '480x320'

        if file_exists('/boot/rk3326-rg351v-linux.dtb') or safe_cat("/storage/.config/.OS_ARCH").strip().casefold() == "rg351v":
            # RG351V
            hardware['analogsticks'] = 1
            hardware['resolution'] = '640x480'

    elif file_exists('/dev/input/by-path/platform-odroidgo2-joypad-event-joystick'):
        if "190000004b4800000010000001010000" in safe_cat('/etc/emulationstation/es_input.cfg'):
            hardware['joystick'] = "190000004b4800000010000001010000"
            hardware['device'] = "oga"
            hardware['hotkey'] = "l3"
        else:
            if file_exists('/usr/lib/aarch64-linux-gnu/libSDL2-2.0.so.0.2600.2'):
                hardware['joystick'] = "19005b284b4800000010000000010000"
            else:
                hardware['joystick'] = "190000004b4800000010000000010000"

            hardware['device'] = "rk2020"

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
            hardware['device'] = safe_cat("/opt/.retrooz/device").strip().casefold()
            if "rgb10max2native" in hardware['param_device']:
                hardware['device'] = "rgb10maxnative"
            if "rgb10max2top" in hardware['param_device']:
                hardware['device'] = "rgb10max2top"

    elif file_exists('/dev/input/by-path/platform-gameforce-gamepad-event-joystick'):
        hardware['joystick'] = "19000000030000000300000002030000"
        hardware['device'] = "chi"
        hardware['hotkey'] = "l3"

    elif file_exists('/dev/input/by-path/platform-singleadc-joypad-event-joystick'):
        hardware['joystick'] = "190000004b4800000111000000010000"
        hardware['device']   = device['device'].casefold()
        if device['device'].casefold() in ('rg552'):
            hardware['resolution'] = '1920x1152'

    ## TODO: figure out features based on OS & Hardware.
    hardware['features'] = []

    return hardware


logger.debug(f'HARDWARE: {device_info()}, {hardware_features()}')

__all__ = (
    'device_info',
    'hardware_features',
    )
