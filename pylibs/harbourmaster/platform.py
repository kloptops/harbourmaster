
# System imports
import datetime
import json
import os
import re
import shutil
import zipfile

from gettext import gettext as _
from pathlib import Path

# Included imports

from loguru import logger
from utility import cprint, cstrip

# Module imports
from .config import *
from .hardware import *
from .util import *


class PlatformBase():
    MOVE_PM_BASH = False

    def __init__(self, hm):
        self.hm = hm

    def first_run(self):
        """
        Called on first run, this can be used to add custom sources for your platform.
        """
        logger.debug(f"{self.__class__.__name__}: First Run")

    def port_install(self, port_name, port_info, port_files):
        """
        Called on after a port is installed, this can be used to check permissions, possibly augment the bash scripts.
        """
        logger.debug(f"{self.__class__.__name__}: Port Install {port_name}")

    def runtime_install(self, runtime_name, runtime_files):
        """
        Called on after a port is installed, this can be used to check permissions, possibly augment the bash scripts.
        """
        logger.debug(f"{self.__class__.__name__}: Runtime Install {runtime_name}")

    def port_uninstall(self, port_name, port_info, port_files):
        """
        Called on after a port is uninstalled, this can be used clean up special files.
        """
        logger.debug(f"{self.__class__.__name__}: Port Uninstall {port_name}")

    def portmaster_install(self):
        """
        Called on after portmaster is updated, this can be used clean up special files.
        """
        logger.debug(f"{self.__class__.__name__}: PortMaster Install")

    def set_gcd_mode(self, mode=None):
        logger.debug(f"{self.__class__.__name__}: Set GCD Mode {mode}")

    def get_gcd_modes(self):
        return tuple()

    def get_gcd_mode(self):
        logger.debug(f"{self.__class__.__name__}: Get GCD Mode")
        return None


class PlatformGCD_PortMaster:
    """
    gamecontrollerdb standard / xbox mode
    """
    def set_gcd_mode(self, gcd_mode=None):
        gamecontroller_file = self.hm.tools_dir / "PortMaster" / "gamecontrollerdb.txt"
        mode_files = {
            'standard': self.hm.tools_dir / "PortMaster" / ".Backup" / "donottouch.txt",
            'xbox': self.hm.tools_dir / "PortMaster" / ".Backup" / "donottouch_x.txt",
            }

        logger.debug(f"{self.__class__.__name__}: Set GCD Mode: {gcd_mode}")

        if gcd_mode:
            if gcd_mode not in mode_files:
                logger.debug(f"Unknown gcd_mode {gcd_mode}")
                return

            if not mode_files[gcd_mode].is_file():
                logger.debug(f"Unknown gcd_mode {gcd_mode} file.")
                return

            shutil.copy(mode_files[gcd_mode], gamecontroller_file)

            self.hm.cfg_data['gcd-mode'] = gcd_mode
            self.hm.save_config()

        else:
            logger.debug(f"Weird {gcd_mode}")

    def get_gcd_modes(self):
        return ('standard', 'xbox')

    def get_gcd_mode(self):
        gamecontroller_file = self.hm.tools_dir / "PortMaster" / "gamecontrollerdb.txt"

        gcd_mode = self.hm.cfg_data.get('gcd-mode', None)

        if gcd_mode not in self.get_gcd_modes():
            gcd_mode = None

        if gcd_mode is None:
            if gamecontroller_file.is_file():
                if "# Xbox 360 Layout" in gamecontroller_file.read_text():
                    gcd_mode = 'xbox'

            if gcd_mode is None:
                gcd_mode = 'standard'

            self.hm.cfg_data['gcd-mode'] = gcd_mode
            self.hm.save_config()

        logger.debug(f"{self.__class__.__name__}: Get GCD Mode: {gcd_mode}")
        return gcd_mode


class PlatformUOS(PlatformGCD_PortMaster, PlatformBase):
    ...


class PlatformJELOS(PlatformBase):
    def first_run(self):
        self.portmaster_install()

    def portmaster_install(self):
        """
        Copy JELOS PortMaster files here.
        """
        shutil.copy("/storage/.config/PortMaster/control.txt", "/storage/roms/ports/PortMaster/control.txt")
        shutil.copy("/storage/.config/PortMaster/gptokeyb", "/storage/roms/ports/PortMaster/gptokeyb")
        shutil.copy("/storage/.config/PortMaster/gamecontrollerdb.txt", "/storage/roms/ports/PortMaster/gamecontrollerdb.txt")
        shutil.copy("/storage/.config/PortMaster/mapper.txt", "/storage/roms/ports/PortMaster/mapper.txt")
        for oga_control in Path("/storage/.config/PortMaster/").glob("oga_controls*"):
            shutil.copy(oga_control, Path("/storage/roms/ports/PortMaster") / oga_control.name)


class PlatformArkOS(PlatformGCD_PortMaster, PlatformBase):
    MOVE_PM_BASH = True


class PlatformAmberELEC(PlatformGCD_PortMaster, PlatformBase):
    ...


HM_PLATFORMS = {
    'jelos': PlatformJELOS,
    'arkos': PlatformArkOS,
    'amberelec': PlatformAmberELEC,
    'unofficialos': PlatformUOS,
    'default': PlatformBase,
    # 'default': PlatformAmberELEC,
    }


__all__ = (
    'PlatformBase',
    'HM_PLATFORMS',
    )

