
# System imports
import datetime
import json
import re
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
        Called on after a port is uninstalled, this can be used clean up special files.
        """
        logger.debug(f"{self.__class__.__name__}: PortMaster Install")


class PlatformUOS(PlatformBase):
    ...


class PlatformJELOS(PlatformBase):
    ...


class PlatformArkOS(PlatformBase):
    MOVE_PM_BASH = True


class PlatformAmberELEC(PlatformBase):
    ...


HM_PLATFORMS = {
    'jelos': PlatformJELOS,
    'arkos': PlatformArkOS,
    'amberelec': PlatformAmberELEC,
    'unofficialos': PlatformUOS,
    'default': PlatformBase,
    }


__all__ = (
    'PlatformBase',
    'HM_PLATFORMS',
    )

