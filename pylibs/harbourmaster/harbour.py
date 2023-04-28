
import json
import pathlib
import zipfile

from pathlib import Path
from loguru import logger

import utility

from utility import cprint, cstrip

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

    def __init__(self, config, *, tools_dir=None, ports_dir=None, temp_dir=None):
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

        self.ports = []
        self.utils = []

        if not self.cfg_dir.is_dir():
            self.cfg_dir.mkdir(0o755, parents=True)

            for source_name in HM_SOURCE_DEFAULTS:
                with (self.cfg_dir / source_name).open('w') as fh:
                    fh.write(HM_SOURCE_DEFAULTS[source_name])

        self.load_sources()

        self.load_ports()


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
                    logger.error(f"Missing key {check_key!r} in <b>{source_file}</b>.")
                    fail = True
                    break

                if check_value is not None and source_data[check_key] not in check_value:
                    logger.error(f"Unknown {check_key!r} in <b>{source_file}</b>: {source_data[check_key]}.")
                    fail = True
                    break

            if fail:
                continue

            source = HM_SOURCE_APIS[source_data['api']](self, source_file, source_data)

            self.sources[source_data['prefix']] = source


    def load_ports(self):
        """
        Find all installed ports, because ports can be installed by zips we need to recheck every time.
        """
        port_files = list(self.ports_dir.glob('*/*.port.json'))
        port_files.sort()

        self.installed_ports = []
        self.unknown_ports = []
        self.broken_ports = []
        all_items = {}
        unknown_files = []

        ports_info = None

        ## Load all the known ports with port.json files
        for port_file in port_files:
            changed = False
            port_info = port_info_load(port_file)

            # logger.info(f"Port Info: {port_info!r}")

            if port_info.get('name', None) is None:
                logger.error(f"No 'name' in {port_info!r}")
                if port_info.get('items', None) is None:
                    continue

                if ports_info is None:
                    from ports_info import ports_info

                for item in port_info['items']:
                    port_temp = ports_info['items'].get(item.casefold(), None)
                    if isinstance(port_temp, str):
                        break
                else:
                    logger.error(f"Unable to figure it out.")
                    continue

                changed = True
                port_info['name'] = port_temp[0]

            if port_info.get('items', None) is None:
                logger.error(f"No 'items' in {port_info!r}")
                if ports_info is None:
                    from ports_info import ports_info

                if port_info['name'] not in ports_info['ports']:
                    logger.error(f"Unable to figure it out.")
                    continue

                changed = True
                port_info['items'] = ports_info['ports'][port_info['name']]['items'][:]

            for item in port_info['items']:
                add_dict_list_unique(all_items, item, port_info['name'])

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
            for script_name in (item for script_name in port_info['items'] if not item.endswith('/')):
                if not (self.ports_dir / script_name).is_file():
                    bad = True
                    break

            for dir_name in (item for script_name in port_info['items'] if item.endswith('/')):
                if not (self.ports_dir / dir_name).is_dir():
                    bad = True
                    break

            if bad:
                if port_info['status']['status'] != 'Broken':
                    port_info['status']['status'] = 'Broken'
                    changed = True

                self.broken_ports.append(port_info)
            else:
                if port_info['status']['status'] != 'Installed':
                    port_info['status']['status'] = 'Installed'
                    changed = True

                self.installed_ports.append(port_info)

            with port_file.open('wt') as fh:
                json.dump(port_info, fh, indent=4)

        ## Check all files
        for file_item in self.ports_dir.iterdir():
            ## Skip these
            if file_item.name.lower() in (
                'portmaster', 'portmaster.sh',
                'thememaster', 'thememaster.sh',
                'harbourmaster',
                'images', 'videos', 'manuals',
                'gamelist.xml', 'gamelist.xml.old'):
                continue

            file_name = file_item.name
            if file_item.is_dir():
                file_name += '/'

            port_owners = get_dict_list(all_items, file_name)

            if len(port_owners) == 0:
                if file_name.lower().endswith('.sh'):
                    unknown_files.append(file_name)

        ## Find any ports that match the files we couldnt find matchting a port.json file
        ports_info = None
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

            if port_info.get('status', None) is None:
                port_info['status'] = {}

            port_info['status']['source'] = "Unknown"
            port_info['status']['md5'] = None

            if not port_json.parent.is_dir():
                ## CEBION WAS HERE!
                logger.info(f"Broken port: {port_info}")
                port_info['status']['status'] = "Broken"
                self.broken_ports.append(port_info)
                continue

            port_info['status']['status'] = "Installed"
            with port_json.open('w') as fh:
                json.dump(port_info, fh, indent=4)

            self.installed_ports.append(port_info)


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

        for installed_port in self.installed_ports:
            if installed_port['name'].endswith(port_info['name']):
                add_list_unique(attrs, 'installed')

        for broken_port in self.broken_ports:
            if broken_port['name'].endswith(port_info['name']):
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
            for port in source.ports:
                if port in ports:
                    continue

                port_info = source.port_info(port)

                if not self.match_filters(filters, port_info):
                    continue

                ports[port] = port_info

        return ports

    def install_port(self, download_info):
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
                    logger.error(f"Port <b>{download_info['name']}</b> has an illegal file {file_info.filename!r}, aborting.")
                    return 255

                if file_info.filename.startswith('../'):
                    ## Little
                    logger.error(f"Port <b>{download_info['name']}</b> has an illegal file {file_info.filename!r}, aborting.")
                    return 255

                if '/../' in file_info.filename:
                    ## Shits
                    logger.error(f"Port <b>{download_info['name']}</b> has an illegal file {file_info.filename!r}, aborting.")
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
                                logger.warning(f"Port <b>{download_info['name']}</b> has multiple port.json files.")
                                logger.warning(f"- Before: <b>{port_info_file.relative_to(self.ports_dir)!r}</b>")
                                logger.warning(f"- Now:    <b>{file_info.filename!r}</b>")

                            port_info_file = self.ports_dir / file_info.filename

                    if file_info.filename.lower().endswith('.sh'):
                        logger.warning(f"Port <b>{download_info['name']}</b> has <b>{file_info.filename}</b> inside, this can cause issues.")

                else:
                    if file_info.filename.lower().endswith('.sh'):
                        scripts.append(file_info.filename)
                        items.append(file_info.filename)
                    else:
                        logger.warning(f"Port <b>{download_info['name']}</b> contains <b>{file_info.filename}</b> at the top level, but it is not a shell script.")

            if len(dirs) == 0:
                logger.error(f"Port <b>{download_info['name']}</b> has no directories, aborting.")
                return 255

            if len(scripts) == 0:
                logger.error(f"Port <b>{download_info['name']}</b> has no scripts, aborting.")
                return 255

            ## TODO: keep a list of installed files for uninstalling?
            # At this point the port will be installed
            # Extract all the files to the specified directory
            # zf.extractall(self.ports_dir)
            cprint("<b>Extracting port.</b>")
            for file_info in zf.infolist():
                if file_info.file_size == 0:
                    compress_saving = 100
                else:
                    compress_saving = file_info.compress_size / file_info.file_size * 100

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

        return self.check_runtime(port_info)

    def check_runtime(self, port_info):
        runtime = port_info['attr'].get('runtime', None)
        if isinstance(runtime, str):
            if '/' in runtime:
                logger.error(f"Bad runtime <b>{runtime}</b>")
                return 255

            runtime_file = (self.libs_dir / runtime)
            if not runtime_file.is_file():
                for source_prefix, source in self.sources.items():
                    if runtime in source.utils:
                        cprint(f"Downloading required runtime <b>{runtime}</b>.")

                        try:
                            runtime_download = source.download(runtime, temp_dir=self.libs_dir)

                        except Exception as err:
                            ## We need to catch any errors and delete the file if it fails,
                            ## here we are not using the temp file auto deletion.
                            if runtime_file.is_file():
                                runtime_file.unlink()

                            raise err

                        return 0
                else:
                    logger.error(f"Unable to find suitable source for {runtime}.")
                    return 0
                    # return 255

    def portmd(self, port_info):
        output = []

        if 'opengl' in port_info["attr"]["reqs"]:
            output.append(f'<r>Title_F</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')
        elif 'power' in port_info["attr"]['reqs']:
            output.append(f'<r>Title_P</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')
        else:
            output.append(f'<r>Title</r>="<y>{port_info["attr"]["title"].replace(" ", "_")} .</y>"')

        output.append(f'<r>Desc</r>="<y>{port_info["attr"]["desc"]}</y>"')
        output.append(f'<r>porter</r>="<y>{port_info["attr"]["porter"]}</y>"')
        output.append(f'<r>locat</r>="<y>{port_info["name"]}</y>"')
        if port_info["attr"]['rtr']:
            output.append(f'<r>runtype</r>="<e>rtr</e>"')
        if port_info["attr"]['runtime'] == "mono-6.12.0.122-aarch64.squashfs":
            output.append(f'<r>mono</r>="<e>y</e>"')

        output.append(f'<r>genres</r>="<m>{",".join(port_info["attr"]["genres"])}</m>"')

        return ' '.join(output)
