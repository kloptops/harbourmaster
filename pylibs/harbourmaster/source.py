
# System imports
import datetime
import json
import re

from pathlib import Path
from urllib.parse import urlparse, urlunparse

# Included imports

from loguru import logger
from utility import cprint, cstrip

# Module imports
from .config import *
from .info import *
from .util import *

################################################################################
## APIS
class BaseSource():
    VERSION = 0

    def __init__(self, hm, file_name, config):
        pass


class GitHubRawReleaseV1(BaseSource):
    VERSION = 2

    def __init__(self, hm, file_name, config):
        self._hm = hm
        self._file_name = file_name
        self._config = config
        self._prefix = config['prefix']
        self._did_update = False
        self._wants_update = None

        if config['version'] != self.VERSION:
            self._wants_update = "Cache out of date."

        elif self._config['last_checked'] is None:
            self._wants_update = "First check."

        elif datetime_compare(self._config['last_checked']) > HM_UPDATE_FREQUENCY:
            self._wants_update = "Auto Update."

        if not self._hm.config['no-check']:
            self.auto_update()
        else:
            self.load()

    def auto_update(self):
        if self._wants_update is not None:
            cprint(f"<b>{self._config['name']}</b>: {self._wants_update}")
            self.update()
            self._wants_update = None

        else:
            self.load()

    def load(self):
        self._data = self._config.setdefault('data', {}).setdefault('data', {})
        self.ports = self._config.setdefault('data', {}).setdefault('ports', [])
        self.utils = self._config.setdefault('data', {}).setdefault('utils', [])
        self._load()

    def save(self):
        with self._file_name.open('w') as fh:
            json.dump(self._config, fh, indent=4)

    def clean_name(self, text):
        return text.casefold()

    def _load(self):
        """
        Overload to add additional loading.
        """
        ...

    def _update(self):
        """
        Overload to add additional loading.
        """
        ...

    def _clear(self):
        """
        Overload to add additional loading.
        """
        ...

    def update(self):
        cprint(f"<b>{self._config['name']}</b>: updating")
        self._clear()
        self._data = {}
        self.ports = []
        self.utils = []

        if self._did_update:
            cprint(f"- <b>{self._config['name']}</b>: up to date already.")
            return

        cprint(f"- <b>{self._config['name']}</b>: Fetching latest ports")
        data = fetch_json(self._config['url'])
        if data is None:
            return

        ## Load data from the assets.
        for asset in data['assets']:
            result = {
                'name': asset['name'],
                'size': asset['size'],
                'url': asset['browser_download_url'],
                }

            self._data[self.clean_name(asset['name'])] = result

            if asset['name'].lower().endswith('.squashfs'):
                self.utils.append(self.clean_name(asset['name']))

        self._update()

        self._config['version'] = self.VERSION

        self._config['data']['ports'] = self.ports
        self._config['data']['utils'] = self.utils
        self._config['data']['data']  = self._data

        self._config['last_checked'] = datetime.datetime.now().isoformat()

        self.save()
        self._did_update = True
        cprint(f"- <b>{self._config['name']}:</b> Done.")

    def download(self, port_name, temp_dir=None, md5_result=None):
        if md5_result is None:
            md5_result = [None]

        if port_name not in self._data:
            logger.error(f"Unable to find port {port_name}")
            return None

        if temp_dir is None:
            temp_dir = self._hm.temp_dir

        if (port_name + '.md5') in self._data:
            md5_file = port_name + '.md5'
        elif (port_name + '.md5sum') in self._data:
            md5_file = port_name + '.md5sum'
        else:
            logger.error(f"Unable to find md5 for {port_name}")
            return None

        md5_source = fetch_text(self._data[md5_file]['url'])
        if md5_source is None:
            logger.error(f"Unable to download md5 file: {self._data[port_name + '.md5']['url']!r}")
            return None

        md5_source = md5_source.strip().split(' ', 1)[0]

        zip_file = download(temp_dir / port_name, self._data[port_name]['url'], md5_source)

        if zip_file is not None:
            cprint("<b,g,>Success!</b,g,>")

        md5_result[0] = md5_source

        return zip_file

    def port_info(self, port_name):
        port_name = self.clean_name(port_name)

        if port_name not in getattr(self, '_info', {}):
            return {}

        return self._info[port_name]


class PortMasterV1(GitHubRawReleaseV1):
    VERSION = 2

    def _load(self):
        self._info = self._config.setdefault('data', {}).setdefault('info', {})

    def _clear(self):
        self._info = {}

    def _update(self):

        cprint(f"- <b>{self._config['name']}</b>: Fetching info")
        # portsmd_url = "https://raw.githubusercontent.com/kloptops/PortMaster/main/ports.md"
        portsmd_url = self._data['ports.md']['url']
        for line in fetch_text(portsmd_url).split('\n'):
            line = line.strip()
            if line == '':
                continue

            port_info = self._portsmd_to_portinfo(line)

            self._info[port_info['name']] = port_info

            self.ports.append(port_info['name'])

        self._config['data']['info']  = self._info

    def _portsmd_to_portinfo(self, text):
        # Super jank
        raw_info = {
            'title': '',
            'desc': '',
            'locat': '',
            'porter': '',
            'reqs': [],
            'rtr': False,
            'runtime': None,
            'genres': [],
            }

        for key, value in re.findall(r'(?:^|\s)(\w+)=\"(.+?)"(?=\s+\w+=|$)', text.strip()):
            key = key.casefold()
            if key == 'title_f':
                raw_info['reqs'].append('opengl')
                key = 'title'
            elif key == 'title_p':
                raw_info['reqs'].append('power')
                key = 'title'

            if key == 'title':
                value = value[:-2].replace('_', ' ')

            # Zips with spaces in their names get replaced with '.'
            if '%20' in value:
                value = value.replace('%20', '.')
                value = value.replace('..', '.')

            # Special keys
            if key == 'runtype':
                key, value = "rtr", True
            elif key == "mono":
                key, value = "runtime", "mono-6.12.0.122-aarch64.squashfs"
            elif key == "genres":
                value = value.split(',')

            raw_info[key] = value

        port_info = port_info_load({})

        port_info['name'] = self.clean_name(raw_info['locat'])
        ## SUPER JANK --
        from ports_info import ports_info

        port_info['items'] = ports_info['ports'].get(port_info['name'], {'items': []})['items']
        port_info['attr']['title']   = raw_info['title']
        port_info['attr']['porter']  = raw_info['porter']
        port_info['attr']['desc']    = raw_info['desc']
        port_info['attr']['rtr']     = raw_info['rtr']
        port_info['attr']['reqs']    = raw_info['reqs']
        port_info['attr']['runtime'] = raw_info['runtime']
        port_info['attr']['genres']  = raw_info['genres']

        return port_info

    def download(self, port_name, temp_dir=None):
        md5_result = [None]
        zip_file = super().download(port_name, temp_dir, md5_result)

        if zip_file is None:
            return None

        if port_name in self.utils:
            ## Utils
            return zip_file

        zip_info = port_info_load({})

        zip_info['name'] = port_name
        zip_info['status'] = {
            'source': self._config['name'],
            'md5':    md5_result[0],
            'status': 'downloaded',
            }
        zip_info['zip_file'] = zip_file

        port_info = self.port_info(port_name)
        port_info_merge(zip_info, port_info)

        return zip_info


class GitHubRepoV1(GitHubRawReleaseV1):
    VERSION = 2

    def _load(self):
        """
        Overload to add additional loading.
        """
        self._info = self._config.setdefault('data', {}).setdefault('info', {})

    def update(self):
        cprint(f"<b>{self._config['name']}</b>: updating")
        if self._did_update:
            cprint(f"- <b>{self._config['name']}</b>: up to date already.")
            return

        self._clear()
        self._data = {}
        self._info = {}
        self.ports = []
        self.utils = []

        user_name = self._config['config']['user_name']
        repo_name = self._config['config']['repo_name']
        branch_name = self._config['config']['branch_name']
        sub_folder = self._config['config']['sub_folder']

        git_url = f"https://api.github.com/repos/{user_name}/{repo_name}/git/trees/{branch_name}?recursive=true"

        cprint(f"- <b>{self._config['name']}</b>: Fetching latest ports")
        git_info = fetch_json(git_url)
        if git_info is None:
            return None

        ports_json_file = None

        for item in git_info['tree']:
            path = item["path"]
            if not path.startswith(sub_folder):
                continue

            name = path.rsplit('/', 1)[1]

            if not (path.endswith('.zip') or
                    path.endswith('.md5') or
                    path.endswith('.squashfs') or
                    path.endswith('.md5sum') or
                    name == 'ports.json'):
                continue

            result = {
                'name': name,
                'size': item['size'],
                'url': f"https://github.com/{user_name}/{repo_name}/raw/{branch_name}/{path}",
                }

            name = self.clean_name(name)
            self._data[name] = result

            if name.endswith('.squashfs'):
                self.utils.append(self.clean_name(asset['name']))

            if name == 'ports.json':
                ports_json_file = name

        if ports_json_file is not None:
            cprint(f"- <b>{self._config['name']}:</b> Fetching info.")
            ports_json = fetch_json(self._data[ports_json_file]['url'])

            for port_info in ports_json['ports']:
                port_name = port_info['name']

                port_name = self.clean_name(port_name)

                self._info[port_name] = port_info

                self.ports.append(port_name)

        self._config['version'] = self.VERSION

        self._config['data']['ports'] = self.ports
        self._config['data']['utils'] = self.utils
        self._config['data']['data']  = self._data
        self._config['data']['info']  = self._info

        self._config['last_checked'] = datetime.datetime.now().isoformat()

        self.save()
        self._did_update = True
        cprint(f"- <b>{self._config['name']}:</b> Done.")

    def download(self, port_name, temp_dir=None):
        md5_result = [None]
        zip_file = super().download(port_name, temp_dir, md5_result)

        if zip_file is None:
            return None

        if port_name in self.utils:
            ## Utils
            return zip_file

        zip_info = port_info_load({})

        zip_info['name'] = port_name
        zip_info['status'] = {
            'source': self._config['name'],
            'md5':    md5_result[0],
            'status': 'downloaded',
            }
        zip_info['zip_file'] = zip_file

        port_info = self.port_info(port_name)
        port_info_merge(zip_info, port_info)

        return zip_info


################################################################################
## Raw Downloader

def raw_download(save_path, file_url):
    """
    This is a bit of a hack, this acts as a source of ports, but for raw urls.
    This only supports downloading so not bothering to add it as a full blown source.
    """
    original_url = file_url
    url_info = urlparse(file_url)
    file_name = url_info.path.rsplit('/', 1)[1]

    if file_name.endswith('.md5') or file_name.endswith('.md5sum'):
        ## If it is an md5 file, we assume the actual zip is sans the md5/md5sum
        md5_source = fetch_text(file_url)
        if md5_source is None:
            logger.error(f"Unable to download file: {file_url!r} [{r.status_code}]")

        md5_source = md5_source.strip().split(' ', 1)[0]

        file_name = file_name.rsplit('.', 1)[0]
        file_url = urlunparse(url_info._replace(path=url_info.path.rsplit('.', 1)[0]))
    else:
        md5_source = None

    if not file_name.endswith('.zip'):
        logger.error(f"Unable to download file: {file_url!r} [doesn't end with '.zip']")
        return None

    file_name = file_name.replace('%20', '.').replace('+', '.').replace('..', '.')

    md5_result = [None]
    zip_file = download(save_path / file_name, file_url, md5_source, md5_result)

    if zip_file is None:
        return None

    zip_info = port_info_load({})

    zip_info['name'] = zip_file.name
    zip_info['zip_file'] = zip_file
    zip_info['status'] = {
        'source': 'url',
        'md5': md5_result[0],
        'url': original_url,
        'status': 'downloaded',
        }

    # print(f"-- {zip_info} --")

    cprint("<b,g,>Success!</b,g,>")
    return zip_info


HM_SOURCE_APIS = {
    'GitHubRawReleaseV1': GitHubRawReleaseV1,
    'PortMasterV1': PortMasterV1,
    'GitHubRepoV1': GitHubRepoV1,
    }

__all__ = (
    'BaseSource',
    'raw_download',
    'HM_SOURCE_APIS',
    )

