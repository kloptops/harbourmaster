
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
from .util import *
from .info import *
from .source import *


################################################################################
## Config loading
class HarbourMaster():
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


        self.temp_dir  = temp_dir
        self.tools_dir = tools_dir
        self.cfg_dir   = tools_dir / "PortMaster" / "config"
        self.libs_dir  = tools_dir / "PortMaster" / "libs"
        self.ports_dir = ports_dir
        self.sources = {}
        self.config = {
            'no-check': config.get('no-check', False),
            'quiet': config.get('quiet', False),
            'debug': config.get('debug', False),
            }

        self.callback = callback
        self.ports = []
        self.utils = []

        if not self.cfg_dir.is_dir():
            self.cfg_dir.mkdir(0o755, parents=True)

            for source_name in HM_SOURCE_DEFAULTS:
                with (self.cfg_dir / source_name).open('w') as fh:
                    fh.write(HM_SOURCE_DEFAULTS[source_name])

        self.load_sources()

        self.load_ports()

    @timeit
    def load_sources(self):
        source_files = list(self.cfg_dir.glob('*.source.json'))
        source_files.sort()

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

        ports_info = None

        ## Load all the known ports with port.json files
        for port_file in port_files:
            changed = False
            port_info = port_info_load(port_file, do_default=True)

            # logger.info(f"Port Info: {port_info!r}")

            # Its possible for the port_info to be in a bad way, lets try and fix it.
            if port_info.get('name', None) is None:
                # No name, check the items and see if it matches our internal database, we can get the port name from a script.
                logger.error(f"No 'name' in {port_info!r}")
                if port_info.get('items', None) is None:
                    # Can't do shit if the items is empty. :(
                    continue

                if ports_info is None:
                    from ports_info import ports_info

                for item in port_info['items']:
                    port_temp = ports_info['items'].get(item.casefold(), None)
                    if isinstance(port_temp, str):
                        break
                else:
                    # Couldn't find the port.
                    logger.error(f"Unable to figure it out.")
                    continue

                changed = True
                port_info['name'] = port_temp[0]

            if port_info.get('items', None) is None:
                # This shouldn't happen, but we can restore it.
                logger.error(f"No 'items' in {port_info!r}")

                if ports_info is None:
                    from ports_info import ports_info

                if port_info['name'] not in ports_info['ports']:
                    # Sorry, cant work it out.
                    logger.error(f"Unable to figure it out.")
                    continue

                changed = True
                port_info['items'] = ports_info['ports'][port_info['name']]['items'][:]

            if port_info['attr']['title'] in ("", None):
                for item in port_info['items']:
                    if item.casefold().endswith('.sh'):
                        port_info['attr']['title'] = item[:-3]
                        changed = True
                        break

            # Add all the root dirs/scripts in the port
            for item in port_info['items']:
                add_dict_list_unique(all_items, item, port_info['name'])

            # And any optional ones.
            for item in get_dict_list(port_info, 'items_opt'):
                add_dict_list_unique(all_items, item, port_info['name'])

            if port_info.get('status', None) is None:
                changed = True
                port_info['status'] = {
                    'source': 'Unknown',
                    'md5': None,
                    'status': 'Unknown'
                    }

            bad = False
            for item in port_info['items']:
                if not (self.ports_dir / item).exists():
                    logger.info(f"Port {port_info['name']} missing file: {item}")
                    bad = True
                    break

            if bad:
                if port_info['status'].get('status', 'Unknown') != 'Broken':
                    port_info['status']['status'] = 'Broken'
                    changed = True

                self.broken_ports[port_info['name'].casefold()] = port_info
            else:
                if port_info['status'].get('status', 'Unknown') != 'Installed':
                    port_info['status']['status'] = 'Installed'
                    changed = True

                self.installed_ports[port_info['name'].casefold()] = port_info

            if changed:
                with port_file.open('wt') as fh:
                    json.dump(port_info, fh, indent=4)

        ## Check all files
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

            port_owners = get_dict_list(all_items, file_name)

            if len(port_owners) == 0:
                unknown_files.append(file_name)

        ## Find any ports that match the files we couldnt find matchting a port.json file
        new_ports = []
        for unknown_file in unknown_files:
            if ports_info is None:
                from ports_info import ports_info

            port_owners = get_dict_list(ports_info['items'], unknown_file)

            if len(port_owners) == 1:
                add_list_unique(new_ports, port_owners[0])

            elif len(port_owners) == 0:
                if unknown_file.endswith('.sh'):
                    ## Keep track of unknown bash scripts.
                    logger.info(f"Unknown port: {unknown_file}")
                    self.unknown_ports.append(unknown_file)

        ## Create new port.json files for any new ports, these only contain the most basic of information.
        for new_port in new_ports:
            if ports_info is None:
                from ports_info import ports_info

            port_info_raw = ports_info['ports'][new_port]

            port_info = port_info_load(port_info_raw)

            port_json = self.ports_dir / port_info_raw['file']

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

            port_name = port_info['name'].casefold()

            port_info['status']['source'] = "Unknown"
            port_info['status']['md5'] = None

            if not port_json.parent.is_dir():
                ## CEBION WAS HERE!
                if port_name in self.installed_ports:
                    del self.installed_ports[port_name]

                logger.info(f"Broken port: {port_info}")
                port_info['status']['status'] = "Broken"
                self.broken_ports[port_info['name'].casefold()] = port_info
                continue

            bad = False
            for item in port_info['items']:
                if not (self.ports_dir / item).exists():
                    logger.info(f"Port {port_info['name']} missing file: {item}")
                    bad = True

            if bad:
                if port_name in self.installed_ports:
                    del self.installed_ports[port_name]

                if port_info['status'].get('status', 'Unknown') != 'Broken':
                    port_info['status']['status'] = 'Broken'

                self.broken_ports[port_name] = port_info
            else:
                if port_name in self.broken_ports:
                    del self.broken_ports[port_name]

                if port_info['status'].get('status', 'Unknown') != 'Installed':
                    port_info['status']['status'] = 'Installed'

                self.installed_ports[port_name] = port_info

            with port_json.open('w') as fh:
                json.dump(port_info, fh, indent=4)

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
            if port_name.casefold() in source.images:
                return {
                    image_type: (source._image_dir / image_file)
                    for image_type, image_file in source.images[port_name.casefold()]
                    }

        return None

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

        with zipfile.ZipFile(download_info['zip_file'], 'r') as zf:
            for file_info in zf.infolist():
                if file_info.filename.startswith('/'):
                    ## Sneaky
                    logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting.")
                    if self.callback is not None:
                        self.callback.message_box(f"Port {download_info['name']} has an illegal file, aborting installation.")
                    return 255

                if file_info.filename.startswith('../'):
                    ## Little
                    logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting installation.")
                    if self.callback is not None:
                        self.callback.message_box(f"Port {download_info['name']} has an illegal file, aborting installation.")
                    return 255

                if '/../' in file_info.filename:
                    ## Shits
                    logger.error(f"Port {download_info['name']} has an illegal file {file_info.filename!r}, aborting.")
                    if self.callback is not None:
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
                if self.callback is not None:
                    self.callback.message_box(f"Port {download_info['name']} has no directories, aborting installation.")

                return 255

            if len(scripts) == 0:
                logger.error(f"Port {download_info['name']} has no scripts, aborting.")
                if self.callback is not None:
                    self.callback.message_box(f"Port {download_info['name']} has no scripts, aborting installation.")

                return 255

            ## TODO: keep a list of installed files for uninstalling?
            # At this point the port will be installed
            # Extract all the files to the specified directory
            # zf.extractall(self.ports_dir)
            cprint("<b>Extracting port.</b>")
            if self.callback is not None:
                self.callback.message(f"Installing {download_info['name']}.")

            for file_info in zf.infolist():
                if file_info.file_size == 0:
                    compress_saving = 100
                else:
                    compress_saving = file_info.compress_size / file_info.file_size * 100

                if self.callback is not None:
                    self.callback.message(f"- {file_info.filename}")

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
        port_info['items'] = items
        port_info['status'] = download_info['status'].copy()
        port_info['status']['status'] = 'Installed'

        if port_info_file is None:
            port_info_file = self.ports_dir / dirs[0] / (download_info['zip_file'].stem + '.port.json')

        # print(f"Merged Info: {port_info}")

        with open(port_info_file, 'w') as fh:
            json.dump(port_info, fh, indent=4)

        self._fix_permissions()

        if port_info['attr'].get('runtime', None) is not None:
            return self.check_runtime(port_info['attr']['runtime'])

        if self.callback is not None:
            self.callback.message_box(f"Port {download_info['name']} installed successfully.")

        return 0

    def check_runtime(self, runtime):
        if isinstance(runtime, str):
            if '/' in runtime:
                if self.callback is not None:
                    self.callback.message_box(f"Port {runtime} contains a bad runtime, game may not run correctly.")

                logger.error(f"Bad runtime {runtime}")
                return 255

            runtime_file = (self.libs_dir / runtime)
            if not runtime_file.is_file():
                for source_prefix, source in self.sources.items():
                    if runtime not in source.utils:
                        continue

                    cprint(f"Downloading required runtime <b>{runtime}</b>.")

                    if self.callback is not None:
                        self.callback.message(f"Downloading runtime {runtime}.")

                    try:
                        runtime_download = source.download(runtime, temp_dir=self.libs_dir, callback=self.callback)

                    except Exception as err:
                        ## We need to catch any errors and delete the file if it fails,
                        ## here we are not using the temp file auto deletion.
                        if runtime_file.is_file():
                            runtime_file.unlink()

                        if self.callback is not None:
                            self.callback.message_box(f"Unable to download {runtime}, game may not run correctly.")
                            return 255

                        raise err

                    return 0
                else:
                    logger.error(f"Unable to find suitable source for {runtime}.")
                    return 255

    def install_port(self, port_name):
        # Special HTTP download code.
        if port_name.startswith('http'):
            download_info = raw_download(self.temp_dir, port_name, callback=self.callback)

            if download_info is None:
                return 255

            return self._install_port(download_info)

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

            download_info = source.download(source.clean_name(port_name), callback=self.callback)

            if download_info is None:
                return 255

            # print(f"Download Info: {download_info.to_dict()}")
            return self._install_port(download_info)

        if self.callback is not None:
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
                if self.callback is not None:
                    self.callback.message_box(f"Unknown port {port_name}")
                logger.error(f"Unknown port {port_name}")
                return 255

        all_items = {}

        # We need to build up a list of all associated files
        # so we only delete the ones that will no longer be associaed with any ports.
        for item_name, item_info in self.installed_ports.items():
            # Add all the root dirs/scripts in the port
            for item in item_info['items']:
                add_dict_list_unique(all_items, item, item_info['name'])

            # And any optional ones.
            for item in get_dict_list(item_info, 'items_opt'):
                add_dict_list_unique(all_items, item, item_info['name'])

        for item_name, item_info in self.broken_ports.items():
            # Add all the root dirs/scripts in the port
            for item in item_info['items']:
                add_dict_list_unique(all_items, item, item_info['name'])

            # And any optional ones.
            for item in get_dict_list(item_info, 'items_opt'):
                add_dict_list_unique(all_items, item, item_info['name'])

        # cprint(f"{all_items}")
        cprint(f"Uninstalling <b>{port_name}</b>")
        if self.callback is not None:
            self.callback.message(f"Removing {port_name}")
        all_port_items = port_info['items'][:]
        if port_info.get('items_opt', None) is not None:
            all_port_items.extend(port_info['items_opt'])

        ports_dir = self.ports_dir

        if not ports_dir.is_absolute():
            ports_dir = ports_dir.resolve()

        for item in all_port_items:
            # Only delete files/scripts with only 1 owner.
            item_owners = get_dict_list(all_items, item)
            if len(item_owners) != 1:
                continue

            # Sneaky shits
            if (item.startswith('/') or item.startswith('../') or '/../' in item):
                if self.callback is not None:
                    self.callback.message_box(f"Possible bad files in port_info for {port_name}.")
                    return 255
                logger.error(f"- Possible bad files in port_info: {item}, skipping for safety.")
                continue

            item_path = self.ports_dir / item
            # Stop it! >:O
            if not hasattr(item_path, 'is_relative_to'):
                ## Fix for older versions of python which don't have is_relative_to.
                try:
                    item_path.relative_to(ports_dir)
                except ValueError:
                    if self.callback is not None:
                        self.callback.message_box(f"Possible bad files in port_info for {port_name}.")
                        return 255

                    logger.error(f"- Trying to get outside of the ports folder: {item_path!r}, skipping.")
                    continue
            else:
                if not item_path.is_relative_to(ports_dir):
                    if self.callback is not None:
                        self.callback.message_box(f"Possible bad files in port_info for {port_name}.")
                        return 255

                    logger.error(f"- Trying to get outside of the ports folder: {item_path!r}, skipping.")
                    continue

            if item_path.exists():
                cprint(f"- removing {item}")
                if self.callback is not None:
                    self.callback.message(f"- removing {item}")

                if item_path.is_dir():
                    shutil.rmtree(item_path)

                elif item_path.is_file():
                    item_path.unlink()

        if self.callback is not None:
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