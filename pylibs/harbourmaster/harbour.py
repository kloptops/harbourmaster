
# System imports
import fnmatch
import json
import pathlib
import shutil
import subprocess
import zipfile

from pathlib import Path

# Included imports
import utility

from loguru import logger
from utility import cprint

# Module imports
from .config import *
from .hardware import *
from .util import *
from .info import *
from .source import *


################################################################################
## Config loading
class HarbourMaster():
    __PORTS_INFO = None

    CONFIG_VERSION = 1
    DEFAULT_CONFIG = {
        'version': CONFIG_VERSION,
        'first_run': True,
        }

    def __init__(self, config, *, tools_dir=None, ports_dir=None, temp_dir=None, callback=None):
        """
        config = load_config()
        """

        if tools_dir is None:
            tools_dir = HM_TOOLS_DIR

        if ports_dir is None:
            ports_dir = HM_PORTS_DIR

        if isinstance(tools_dir, str):
            tools_dir = Path(tools_dir)
        elif not isinstance(tools_dir, pathlib.PurePath):
            raise ValueError('tools_dir')

        if isinstance(ports_dir, str):
            ports_dir = Path(ports_dir)
        elif not isinstance(ports_dir, pathlib.PurePath):
            raise ValueError('ports_dir')

        if callback is None:
            callback = Callback()

        self.temp_dir  = temp_dir
        self.tools_dir = tools_dir
        self.cfg_dir   = tools_dir / "PortMaster" / "config"
        self.libs_dir  = tools_dir / "PortMaster" / "libs"
        self.ports_dir = ports_dir
        self.sources = {}
        self.config = {
            'no-check': config.get('no-check', False),
            'offline': config.get('offline', False),
            'quiet': config.get('quiet', False),
            'debug': config.get('debug', False),
            }

        self.device = device_info()

        self.callback = callback
        self.ports = []
        self.utils = []

        with self.callback.enable_messages():
            self.callback.message("Loading...")

            if not self.cfg_dir.is_dir():
                self.cfg_dir.mkdir(0o755, parents=True)

                for source_name in HM_SOURCE_DEFAULTS:
                    with (self.cfg_dir / source_name).open('w') as fh:
                        fh.write(HM_SOURCE_DEFAULTS[source_name])

            self.load_sources()

            self.load_ports()

    @timeit
    def __ports_info(self):
        if self.__PORTS_INFO is None:
            from ports_info import ports_info
            self.__PORTS_INFO = ports_info

        return self.__PORTS_INFO

    @timeit
    def load_sources(self):
        source_files = list(self.cfg_dir.glob('*.source.json'))
        source_files.sort()

        self.callback.message("- Loading Sources.")

        check_keys = {'version': None, 'prefix': None, 'api': HM_SOURCE_APIS, 'name': None, 'last_checked': None, 'data': None}
        for source_file in source_files:
            with source_file.open() as fh:
                source_data = json_safe_load(fh)

            if source_data is None:
                continue

            fail = False
            for check_key, check_value in check_keys.items():
                if check_key not in source_data:
                    logger.error(f"Missing key {check_key!r} in {source_file}.")
                    fail = True
                    break

                if check_value is not None and source_data[check_key] not in check_value:
                    logger.error(f"Unknown {check_key!r} in {source_file}: {source_data[check_key]}.")
                    fail = True
                    break

            if fail:
                continue

            source = HM_SOURCE_APIS[source_data['api']](self, source_file, source_data)

            self.sources[source_data['prefix']] = source


    def _get_pm_signature(self, file_name):
        """
        Returns (file_name, original_file_name, port_name)

        This handles files being renamed, hopefully.
        """
        if not str(file_name).lower().endswith('.sh'):
            return None

        # See if the file has a signature
        pm_signature = load_pm_signature(file_name)

        if pm_signature is None:
            ports_info = self.__ports_info()

            # If not look it up by name
            port_owners = get_dict_list(ports_info['items'], file_name.name)
            if len(port_owners) > 0:
                add_pm_signature(file_name, [port_owners[0], file_name.name])
                return (file_name.name, file_name.name, port_owners[0])

            # Finally try by the md5sum of the file
            md5 = hash_file(file_name)
            if md5 in ports_info['md5']:
                other_name = ports_info['md5'][md5]

                port_owners = get_dict_list(ports_info['items'], other_name)

                if len(port_owners) > 0:
                    add_pm_signature(file_name, [port_owners[0], other_name])
                    return (other_name, file_name.name, port_owners[0])

            return (file_name.name, file_name.name, None)

        return (file_name.name, pm_signature[1], pm_signature[0])

    def _load_port_info(self, port_file):
        """
        Loads a <blah>.port.json file.

        It will try its best to recover the data into a usable state.

        returns None if it is unusuable.
        """
        port_info = port_info_load(port_file, do_default=True)

        ports_info = self.__ports_info()
        changed = False

        # Its possible for the port_info to be in a bad way, lets try and fix it.
        if port_info.get('name', None) is None:
            # No name, check the items and see if it matches our internal database, we can get the port name from a script.
            logger.error(f"No 'name' in {port_file!r}")
            if port_info.get('items', None) is None:
                # Can't do shit if the items is empty. :(
                logger.error(f"Unable to load {port_file}, missing 'name' and 'items' keys.")
                return None

            for item in port_info['items']:
                port_temp = ports_info['items'].get(item.casefold(), None)
                if isinstance(port_temp, str):
                    break
            else:
                # Couldn't find the port.
                logger.error(f"Unable to load {port_file}, unknown items.")
                return None

            changed = True
            port_info['name'] = name_cleaner(port_temp[0])

        # Force the port_info['name'] to be lowercase/casefolded.
        if port_info['name'] != name_cleaner(port_info['name']):
            port_info['name'] = name_cleaner(port_info['name'])
            changed = True

        if port_info.get('items', None) is None:
            # This shouldn't happen, but we can restore it.
            logger.error(f"No 'items' in {port_info!r} for {port_file}")

            if port_info['name'] not in ports_info['ports']:
                # Sorry, cant work it out.
                logger.error(f"Unable to figure it out, unknown port {port_info['name']}")
                return None

            changed = True
            port_info['items'] = ports_info['ports'][port_info['name']]['items'][:]

        if port_info['attr']['title'] in ("", None):
            for item in port_info['items']:
                if item.casefold().endswith('.sh'):
                    port_info['attr']['title'] = item[:-3]
                    changed = True
                    break

        if port_info.get('status', None) is None:
            changed = True
            port_info['status'] = {
                'source': 'Unknown',
                'md5': None,
                'status': 'Unknown',
                }

        port_info['changed'] = changed

        return port_info

    @timeit
    def load_ports(self):
        """
        Find all installed ports, because ports can be installed by zips we need to recheck every time.
        """
        port_files = list(self.ports_dir.glob('*/*.port.json'))
        port_files.sort()

        self.installed_ports = {}
        self.broken_ports = {}
        self.unknown_ports = []
        all_items = {}
        unknown_files = []

        all_ports = {}
        ports_files = {}
        file_renames = {}

        ports_info = self.__ports_info()

        self.callback.message("- Loading Ports.")

        """
        This is a bit of a heavy function but it does the following.

        Phase 1:
        - Load all *.port.json files, fix any issues with them
    
        Phase 2:
        - Check all files/dirs in the ports_dir, see if they are "owned" by a port, find any renamed files.

        Phase 3:
        - Find any new ports, create the port.json files as necessary.

        Phase 4:
        - Finalise any data, figure out if the ports are broken etc.

        DONE.

        """

        ## Phase 1: Load all the known ports with port.json files
        for port_file in port_files:
            port_info = self._load_port_info(port_file)

            if port_info is None:
                continue

            # The files attribute keeps track of file renames.
            if port_info.get('files', None) is None:
                port_info['files'] = {
                    'port.json': str(port_file.relative_to(self.ports_dir)),
                    }
                port_info['changed'] = True

            # Add all the root dirs/scripts in the port
            for item in port_info['items']:
                add_dict_list_unique(all_items, item, port_info['name'])

                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)
                        port_info['changed'] = True

            # And any optional ones.
            for item in get_dict_list(port_info, 'items_opt'):
                add_dict_list_unique(all_items, item, port_info['name'])

                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)
                        port_info['changed'] = True

            all_ports[port_info['name']] = port_info
            ports_files[port_info['name']] = port_file

        ## Phase 2: Check all files
        for file_item in self.ports_dir.iterdir():
            ## Skip these
            if file_item.name.casefold() in (
                    'gamelist.xml',
                    'gamelist.xml.old',
                    'harbourmaster',
                    'images',
                    'manuals',
                    'portmaster',
                    'portmaster.sh',
                    'thememaster',
                    'thememaster.sh',
                    'videos',
                    ):
                continue

            file_name = file_item.name
            if file_item.is_dir():
                file_name += '/'

            elif file_item.suffix.casefold() not in ('.sh', ):
                # Ignore non bash files.
                continue

            port_owners = get_dict_list(all_items, file_name)

            if len(port_owners) > 0:
                # We know what port this file belongs to.
                # Add signature to files
                if file_item.suffix.casefold() in ('.sh', ):
                    pm_signature = load_pm_signature(file_item)

                    if pm_signature is None:
                        logger.debug(f"add_pm_signature({file_item!r}, [{port_owners[0]!r}, {file_name!r}])")
                        add_pm_signature(file_item, [port_owners[0], file_name])
                        continue

                    if pm_signature[0] in all_ports:
                        port_info = all_ports[pm_signature[0]]
                        # print(file_name, pm_signature)
                        if file_name not in get_dict_list(port_info['files'], pm_signature[1]):
                            add_dict_list_unique(port_info['files'], pm_signature[1], file_name)
                            print("added")
                            port_info["changed"] = True

                continue

            if not file_name.endswith('/'):
                # See if the file has been renamed, thanks Christian!
                pm_signature = self._get_pm_signature(file_item)
                if pm_signature is None:
                    # Shouldn't happen
                    unknown_files.append(file_name)
                    continue

                if pm_signature[0] != pm_signature[1]:
                    # We atleast know the file is renamed.
                    file_renames[pm_signature[1]] = pm_signature[0]

                if pm_signature[2] is None:
                    # Unknown port?
                    unknown_files.append(file_name)
                    continue

                if pm_signature[2] in all_ports:
                    port_info = all_ports[pm_signature[2]]
                    add_dict_list_unique(all_items, pm_signature[0], pm_signature[2])

                    if pm_signature[0] not in get_dict_list(port_info['files'], pm_signature[1]):
                        add_dict_list_unique(port_info['files'], pm_signature[1], pm_signature[0])
                        port_info["changed"] = True

                    continue

            unknown_files.append(file_name)

        # from pprint import pprint
        # pprint(all_items)
        # pprint(file_renames)
        # pprint(unknown_files)

        ## Create new ports.
        new_ports = []
        for unknown_file in unknown_files:
            port_owners = get_dict_list(ports_info['items'], unknown_file)

            if len(port_owners) == 1:
                add_list_unique(new_ports, port_owners[0])

            elif len(port_owners) == 0:
                if unknown_file.casefold().endswith('.sh'):
                    re_name = file_renames.get(unknown_file, None)
                    if re_name is not None:
                        port_owners = get_dict_list(ports_info['items'], re_name)

                        if len(port_owners) == 1:
                            if port_owners[0] in all_ports:
                                port_info = all_ports[port_owners[0]]
                                if unknown_file not in get_dict_list(port_info['files'], re_name):
                                    add_dict_list_unique(port_info['files'], re_name, unknown_file)
                                    port_info['changed'] = True

                            else:
                                add_list_unique(new_ports, port_owners[0])

                            continue

                    ## Keep track of unknown bash scripts.
                    logger.info(f"Unknown port: {unknown_file}")
                    self.unknown_ports.append(unknown_file)

        ## Create new port.json files for any new ports, these only contain the most basic of information.
        for new_port in new_ports:
            port_info_raw = ports_info['ports'][new_port]

            port_info = port_info_load(port_info_raw)

            port_file = self.ports_dir / port_info_raw['file']

            ## Load extra info
            for source in self.sources.values():
                port_name = source.clean_name(port_info['name'])

                if port_name in source.ports:
                    port_info_merge(port_info, source.port_info(port_name))
                    break

            if port_info['attr']['title'] in ("", None):
                for item in port_info['items']:
                    if item.casefold().endswith('.sh'):
                        port_info['attr']['title'] = item[:-3]
                        break

            if port_info.get('status', None) is None:
                port_info['status'] = {}

            port_info['name'] = port_info['name'].casefold()

            port_info['status']['source'] = "Unknown"
            port_info['status']['md5'] = None
            port_info['status']['status'] = "Unknown"

            port_info['files'] = {
                'port.json': port_info_raw['file'],
                }

            # Add all the root dirs/scripts in the port
            for item in port_info['items']:
                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)
                        port_info['changed'] = True

                if item in file_renames:
                    item_rename = file_renames[item]
                    if (self.ports_dir / item_rename).exists():
                        if item_rename not in get_dict_list(port_info['files'], item):
                            add_dict_list_unique(port_info['files'], item, item_rename)
                            port_info['changed'] = True

            # And any optional ones.
            for item in get_dict_list(port_info, 'items_opt'):
                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)
                        port_info['changed'] = True

                if item in file_renames:
                    item_rename = file_renames[item]
                    if (self.ports_dir / item_rename).exists():
                        if item_rename not in get_dict_list(port_info['files'], item):
                            add_dict_list_unique(port_info['files'], item, item_rename)
                            port_info['changed'] = True

            port_info['changed'] = True

            all_ports[port_info['name']] = port_info
            ports_files[port_info['name']] = port_file

        for port_name in all_ports:
            port_info = all_ports[port_name]

            bad = False
            for port_file in list(port_info['files']):
                file_names = get_dict_list(port_info['files'], port_file)

                for file_name in list(file_names):
                    if not (self.ports_dir / file_name).exists():
                        remove_dict_list(port_info['files'], port_file, file_name)
                        port_info['changed'] = True

            for item in port_info['items']:
                if len(get_dict_list(port_info['files'], item)) == 0:
                    logger.error(f"Port {port_name} missing {item}.")
                    bad = True

            if bad:
                if port_info['status'].get('status', 'Unknown') != 'Broken':
                    port_info['status']['status'] = 'Broken'
                    port_info['changed'] = True

                self.broken_ports[port_name] = port_info
            else:
                if port_info['status'].get('status', 'Unknown') != 'Installed':
                    port_info['status']['status'] = 'Installed'
                    port_info['changed'] = True

                self.installed_ports[port_name] = port_info

            changed = port_info['changed']
            del port_info['changed']

            if changed:
                if ports_files[port_name].parent.is_file():
                    logger.debug(f"Dumping {str(ports_files[port_name])}: {port_info}")
                    with ports_files[port_name].open('wt') as fh:
                        json.dump(port_info, fh, indent=4)
                else:
                    logger.debug(f"Unable to dump {str(ports_files[port_name])}: {port_info}")

    def port_info_attrs(self, port_info):
        runtime_fix = {
            'frt':  'godot',
            'mono': 'mono',
            'jdk11': 'jre',
            }

        attrs = []
        runtime = port_info.get('attr', {}).get('runtime', None)
        if runtime is not None:
            for runtime_key, runtime_attr in runtime_fix.items():
                if runtime_key in runtime:
                    add_list_unique(attrs, runtime_attr)

        for genre in port_info.get('attr', {}).get('genres', None):
            add_list_unique(attrs, genre.casefold())

        rtr = port_info.get('attr', {}).get('rtr', False)
        if rtr:
            add_list_unique(attrs, 'rtr')

        if port_info['name'].casefold() in self.installed_ports:
            add_list_unique(attrs, 'installed')

        if port_info['name'].casefold() in self.broken_ports:
            add_list_unique(attrs, 'installed')
            add_list_unique(attrs, 'broken')

        return attrs

    def match_filters(self, port_filters, port_info):
        port_attrs = self.port_info_attrs(port_info)

        for port_filter in port_filters:
            if port_filter.casefold() not in port_attrs:
                return False

        return True

    def match_requirements(self, port_info):
        """
        Matches hardware capabilities to port requirements.
        """

        capabilities = self.device['capabilities']

        requirements = port_info.get('attr', {}).get('reqs', [])
        if len(requirements) == 0:
            return True

        passed = True
        for requirement in requirements:
            match_not = True

            if requirement.startswith('!'):
                match_not = False
                requirement = requirement[1:]

            if '|' in requirement:
                passed = any(
                    req in capabilities
                    for req in requirement.split('|')) == match_not

            else:
                if requirement in capabilities:
                    passed = match_not
                else:
                    passed = not match_not

            if not passed:
                break

        return passed

    def list_ports(self, filters=[]):
        ## Filters can be genre, runtime

        ports = {}

        for source_prefix, source in self.sources.items():
            for port_name in source.ports:
                if port_name.casefold() in ports:
                    continue

                port_info = source.port_info(port_name)

                if not self.match_filters(filters, port_info):
                    continue

                if not self.match_requirements(port_info):
                    continue

                ports[port_name.casefold()] = port_info

        if 'installed' in filters:
            for port_name, port_info in self.installed_ports.items():
                if port_name.casefold() in ports:
                    continue

                if not self.match_filters(filters, port_info):
                    continue

                ports[port_name.casefold()] = port_info

            for port_name, port_info in self.broken_ports.items():
                if port_name.casefold() in ports:
                    continue

                if not self.match_filters(filters, port_info):
                    continue

                ports[port_name.casefold()] = port_info

        return ports

    def port_images(self, port_name):
        for source_prefix, source in self.sources.items():
            if name_cleaner(port_name) in source.images:
                return {
                    image_type: (source._images_dir / image_file)
                    for image_type, image_file in source.images[name_cleaner(port_name)].items()}

        return None

    def port_info(self, port_name, installed=False):
        if installed:
            if port_name in self.installed_ports:
                return self.installed_ports[name_cleaner(port_name)]

            if port_name in self.broken_ports:
                return self.broken_ports[name_cleaner(port_name)]

        for source_prefix, source in self.sources.items():
            if source.clean_name(port_name) in source.ports:
                return source.port_info(port_name)

        return None

    def port_download_size(self, port_name):
        for source_prefix, source in self.sources.items():
            if source.clean_name(port_name) not in source.ports:
                if source.clean_name(port_name) not in source.utils:
                    continue

            return source.port_download_size(port_name)

        return 0

    def _fix_permissions(self):
        path_fs = get_path_fs(self.ports_dir)
        logger.debug(f"path_fs={path_fs}")
        if path_fs not in ('ext4', 'ext3'):
            return

        try:
            logger.info(f"Fixing permissions for {self.ports_dir}.")
            subprocess.check_output(['chmod', '-R', '777', str(self.ports_dir)])

        except subprocess.CalledProcessError as err:
            logger.error(f"Failed to fix permissions: {err}")
            return

    def _install_port(self, download_info):
        """
        Installs a port.

        We collect a list of top level scripts/directories, this is added to the port.json file.
        """

        port_info_file = None
        items = []
        dirs = []
        scripts = []

        undo_data = []
        is_successs = False

        try:
            with zipfile.ZipFile(download_info['zip_file'], 'r') as zf:
                for file_info in zf.infolist():
                    if file_info.filename.startswith('/'):
                        ## Sneaky
                        logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting.")
                        self.callback.message_box(f"Port {download_info['name']} has an illegal file, aborting installation.")
                        return 255

                    if file_info.filename.startswith('../'):
                        ## Little
                        logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting installation.")
                        self.callback.message_box(f"Port {download_info['name']} has an illegal file, aborting installation.")
                        return 255

                    if '/../' in file_info.filename:
                        ## Shits
                        logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting.")
                        self.callback.message_box(f"Port {download_info['name']} has an illegal file, aborting installation.")
                        return 255

                    if '/' in file_info.filename:
                        parts = file_info.filename.split('/')

                        if parts[0] not in dirs:
                            items.append(parts[0] + '/')
                            dirs.append(parts[0])

                        if len(parts) == 2:
                            if parts[1].lower().endswith('.port.json'):
                                ## TODO: add the ability for multiple port folders to have multiple port.json files. ?
                                if port_info_file is not None:
                                    logger.warning(f"Port {download_info['name']} has multiple port.json files.")
                                    logger.warning(f"- Before: {port_info_file.relative_to(self.ports_dir)!r}")
                                    logger.warning(f"- Now:    {file_info.filename!r}")

                                port_info_file = self.ports_dir / file_info.filename

                        if file_info.filename.lower().endswith('.sh'):
                            logger.warning(f"Port {download_info['name']} has {file_info.filename} inside, this can cause issues.")

                    else:
                        if file_info.filename.lower().endswith('.sh'):
                            scripts.append(file_info.filename)
                            items.append(file_info.filename)
                        else:
                            logger.warning(f"Port {download_info['name']} contains {file_info.filename} at the top level, but it is not a shell script.")

                if len(dirs) == 0:
                    logger.error(f"Port {download_info['name']} has no directories, aborting.")
                    self.callback.message_box(f"Port {download_info['name']} has no directories, aborting installation.")

                    return 255

                if len(scripts) == 0:
                    logger.error(f"Port {download_info['name']} has no scripts, aborting.")
                    self.callback.message_box(f"Port {download_info['name']} has no scripts, aborting installation.")

                    return 255

                ## TODO: keep a list of installed files for uninstalling?
                # At this point the port will be installed
                # Extract all the files to the specified directory
                # zf.extractall(self.ports_dir)
                cprint("<b>Extracting port.</b>")
                self.callback.message(f"Installing {download_info['name']}.")

                for file_info in zf.infolist():
                    if file_info.file_size == 0:
                        compress_saving = 100
                    else:
                        compress_saving = file_info.compress_size / file_info.file_size * 100

                    self.callback.message(f"- {file_info.filename}")

                    dest_file = path=self.ports_dir / file_info.filename

                    if not file_info.filename.endswith('/'):
                        if not dest_file.parent.is_dir():
                            add_list_unique(undo_data, dest_file.parent)

                    if not dest_file.exists():
                        add_list_unique(undo_data, dest_file)

                    cprint(f"- <b>{file_info.filename!r}</b> <d>[{nice_size(file_info.file_size)} ({compress_saving:.0f}%)]</d>")
                    zf.extract(file_info, path=self.ports_dir)

            if port_info_file is not None:
                port_info = port_info_load(port_info_file)
            else:
                port_info = port_info_load({})

            # print(f"Port Info: {port_info}")
            # print(f"Download Info: {download_info}")

            port_info_merge(port_info, download_info)

            ## These two are always overriden.
            port_info['name'] = name_cleaner(download_info['zip_file'].name)
            port_info['items'] = items
            port_info['status'] = download_info['status'].copy()
            port_info['status']['status'] = 'Installed'

            if port_info_file is None:
                port_info_file = self.ports_dir / dirs[0] / (port_info['name'].rsplit('.', 1)[0] + '.port.json')

            port_info['files'] = {
                'port.json': str(port_info_file.relative_to(self.ports_dir)),
                }

            # Add all the root dirs/scripts in the port
            for item in port_info['items']:
                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)

                    if item.casefold().endswith('.sh'):
                        add_pm_signature(self.ports_dir / item, [port_info['name'], item])

            # And any optional ones.
            for item in get_dict_list(port_info, 'items_opt'):
                if (self.ports_dir / item).exists():
                    if item not in get_dict_list(port_info['files'], item):
                        add_dict_list_unique(port_info['files'], item, item)

                    if item.casefold().endswith('.sh'):
                        add_pm_signature(self.ports_dir / item, [port_info['name'], item])
            # print(f"Merged Info: {port_info}")

            if not port_info_file.is_file():
                add_list_unique(undo_data, port_info_file)

            with open(port_info_file, 'w') as fh:
                json.dump(port_info, fh, indent=4)

            is_successs = True

        finally:
            if not is_successs and len(undo_data) > 0:
                logger.error("Installation failed, removing installed files.")
                self.callback.message(f"Installation failed, removing files...")

                for undo_file in undo_data[::-1]:
                    logger.debug(f"Removing {undo_file.relative_to(self.ports_dir)}")
                    self.callback.message(f"- {str(undo_file.relative_to(self.ports_dir))}")

                    if undo_file.is_file():
                        undo_file.unlink()

                    elif undo_file.is_dir():
                        shutil.rmtree(undo_file)

                self.callback.message_box(f"Port {download_info['name']} installed failed.")

        self._fix_permissions()

        logger.debug(port_info)
        if port_info['attr'].get('runtime', None) is not None:
            return self.check_runtime(port_info['attr']['runtime'])

        self.callback.message_box(f"Port {download_info['name']} installed successfully.")

        return 0

    def check_runtime(self, runtime, port_name=None):
        if isinstance(runtime, str):
            if '/' in runtime:
                self.callback.message_box(f"Port {runtime} contains a bad runtime, game may not run correctly.")

                logger.error(f"Bad runtime {runtime}")
                return 255

            if not self.libs_dir.is_dir():
                self.libs_dir.mkdir(0o777)

            runtime_file = (self.libs_dir / runtime)
            if not runtime_file.is_file():

                if self.config['offline']:
                    cprint(f"Unable to download {runtime} when offline")
                    return 0

                for source_prefix, source in self.sources.items():
                    if runtime not in source.utils:
                        continue

                    cprint(f"Downloading required runtime <b>{runtime}</b>.")

                    self.callback.message(f"Downloading runtime {runtime}.")

                    try:
                        with self.callback.enable_cancellable(True):
                            runtime_download = source.download(runtime, temp_dir=self.libs_dir)

                        if self.callback.was_cancelled:
                            if runtime_file.is_file():
                                runtime_file.unlink()

                            self.callback.message_box(f"Unable to download {runtime}, game may not run correctly.")

                    except Exception as err:
                        ## We need to catch any errors and delete the file if it fails,
                        ## here we are not using the temp file auto deletion.
                        if runtime_file.is_file():
                            runtime_file.unlink()

                        logger.error(err)

                        self.callback.message_box(f"Unable to download {runtime}, game may not run correctly.")
                        return 255

                    self.callback.message_box(f"Successfully downloaded {runtime}.")
                    return 0
                else:
                    self.callback.message(f"Unable to find a download for {runtime}.")

                    logger.error(f"Unable to find suitable source for {runtime}.")
                    return 255

    def install_port(self, port_name):
        # Special HTTP download code.
        if port_name.startswith('http'):
            if self.config['offline']:
                cprint(f"Unable to download {port_name} when offline")
                return 255

            download_info = raw_download(self.temp_dir, port_name, callback=self.callback)

            if download_info is None:
                return 255

            with self.callback.enable_cancellable(False):
                return self._install_port(download_info)

        # Special case for a local file.
        if port_name.startswith('./') or port_name.startswith('../') or port_name.startswith('/'):
            port_file = Path(port_name)
            if not port_file.is_file():
                logger.error(f"Unable to find local file {port_name} for installation.")
                return 255

            md5_result = hash_file(port_file)
            port_info = port_info_load({})

            port_info['name'] = name_cleaner(port_file.name)
            port_info['zip_file'] = port_file
            port_info['status'] = {
                'source': 'file',
                'md5': md5_result,
                'status': 'downloaded',
                }

            with self.callback.enable_cancellable(False):
                return self._install_port(port_info)

        if '/' in port_name:
            repo, port_name = port_name.split('/', 1)
        else:
            repo = '*'

        # Otherwise:
        for source_prefix, source in self.sources.items():
            if not fnmatch.fnmatch(source_prefix, repo):
                continue

            if source.clean_name(port_name) not in source.ports:
                continue

            if self.config['offline']:
                cprint(f"Unable to download {port_name} when offline")
                return 255

            download_info = source.download(source.clean_name(port_name))

            if download_info is None:
                return 255

            # print(f"Download Info: {download_info.to_dict()}")
            with self.callback.enable_cancellable(False):
                return self._install_port(download_info)

        self.callback.message_box(f"Unable to find a source for {port_name}")

        cprint(f"Unable to find a source for <b>{port_name}</b>")
        return 255

    def uninstall_port(self, port_name):
        port_info = self.installed_ports.get(port_name.casefold(), None)
        port_loc = self.installed_ports

        if port_info is None:
            port_info = self.broken_ports.get(port_name.casefold(), None)
            port_loc = self.broken_ports

            if port_info is None:
                self.callback.message_box(f"Unknown port {port_name}")
                logger.error(f"Unknown port {port_name}")
                return 255

        all_items = {}

        # We need to build up a list of all associated files
        # so we only delete the ones that will no longer be associaed with any ports.
        for item_name, item_info in self.installed_ports.items():
            # Add all the root dirs/scripts in the port
            for item in item_info['files']:
                if item in ('port.json', ):
                    continue

                for name in get_dict_list(item_info['files'], item):
                    add_dict_list_unique(all_items, name, item_name)

        for item_name, item_info in self.broken_ports.items():
            # Add all the root dirs/scripts in the port
            for item in item_info['files']:
                if item in ('port.json', ):
                    continue

                for name in get_dict_list(item_info['files'], item):
                    add_dict_list_unique(all_items, name, item_name)

        # from pprint import pprint
        # pprint(all_items)

        # cprint(f"{all_items}")
        cprint(f"Uninstalling <b>{port_name}</b>")
        self.callback.message(f"Removing {port_name}")

        all_port_items = []
        for port_file in port_info['files']:
            all_port_items.extend(get_dict_list(port_info['files'], port_file))

        ports_dir = self.ports_dir

        if not ports_dir.is_absolute():
            ports_dir = ports_dir.resolve()

        for item in all_port_items:
            # Only delete files/scripts with only 1 owner.
            item_owners = get_dict_list(all_items, item)
            if len(item_owners) > 1:
                continue

            item_path = self.ports_dir / item

            if item_path.exists():
                cprint(f"- removing {item}")
                self.callback.message(f"- removing {item}")

                if item_path.is_dir():
                    shutil.rmtree(item_path)

                elif item_path.is_file():
                    item_path.unlink()

        self.callback.message_box(f"Successfully uninstalled {port_name}")

        del port_loc[port_name.casefold()]
        return 0

    def portmd(self, port_info):
        def nice_value(value):
            if value is None:
                return ""
            if value == "None":
                return ""
            return value

        output = []

        if 'opengl' in port_info["attr"]["reqs"]:
            output.append(f'<r>Title_F</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')
        elif 'power' in port_info["attr"]['reqs']:
            output.append(f'<r>Title_P</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')
        else:
            output.append(f'<r>Title</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')

        output.append(f'<r>Desc</r>="<y>{nice_value(port_info["attr"]["desc"])}</y>"')
        output.append(f'<r>porter</r>="<y>{nice_value(port_info["attr"]["porter"])}</y>"')
        output.append(f'<r>locat</r>="<y>{nice_value(port_info["name"])}</y>"')
        if port_info["attr"]['rtr']:
            output.append(f'<r>runtype</r>="<e>rtr</e>"')
        if port_info["attr"]['runtime'] == "mono-6.12.0.122-aarch64.squashfs":
            output.append(f'<r>mono</r>="<e>y</e>"')

        output.append(f'<r>genres</r>="<m>{",".join(port_info["attr"]["genres"])}</m>"')

        return ' '.join(output)

__all__ = (
    'HarbourMaster',
    )