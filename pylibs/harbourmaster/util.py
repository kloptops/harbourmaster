
import contextlib
import datetime
import platform
import tempfile
import shutil
import json

from pathlib import Path

import loguru
import requests

from loguru import logger

from .config import *

logger = loguru.logger.opt(colors=True)

################################################################################
## Utils
def json_safe_loads(*args):
    try:
        return json.loads(*args)
    except json.JSONDecodeError as err:
        logger.error(f"Unable to load json_data <b>{err.doc}</b>:<b>{err.pos}</b>")
        return None

def json_safe_load(*args):
    try:
        return json.load(*args)
    except json.JSONDecodeError as err:
        logger.error(f"Unable to load json_data <b>{err.doc}</b>:<b>{err.pos}</b>")
        return None

def fetch(url):
    r = requests.get(url)
    if r.status_code != 200:
        logger.error(f"Failed to download <b>{url!r}</b>: <b>{r.status_code}</b>")
        return None

    return r


def fetch_data(url):
    r = fetch(url)
    if r is None:
        return None

    return r.content


def fetch_json(url):
    r = fetch(url)
    if r is None:
        return None

    return r.json()


def fetch_text(url):
    r = fetch(url)
    if r is None:
        return None

    return r.text


def nice_size(size):
    suffixes = ('B', 'KB', 'MB', 'GB')
    for suffix in suffixes:
        if size < 768:
            break

        size /= 1024

    if suffix == 'B':
        return f"{size:.0f} {suffix}"

    return f"{size:.02f} {suffix}"


def download(file_name, file_url, md5_source=None, md5_result=None):
    """
    Download a file from file_url into file_name, checks the md5sum of the file against md5_source if given.

    returns file_name if successful, otherwise None.
    """
    if md5_result is None:
        md5_result = [None]

    r = requests.get(file_url, stream=True)

    if r.status_code != 200:
        logger.error(f"Unable to download file: {file_url!r} [{r.status_code}]")
        return None

    total_length = r.headers.get('content-length')
    if total_length is None:
        total_length = None
        total_length_mb = "???? MB"
    else:
        total_length = int(total_length)
        total_length_mb = nice_size(total_length)

    md5 = hashlib.md5()

    cprint(f"Downloading <b>{file_url!r}</b> - <b>{total_length_mb}</b>")

    length = 0
    with file_name.open('wb') as fh:
        for data in r.iter_content(chunk_size=104096, decode_unicode=False):
            md5.update(data)
            fh.write(data)
            length += len(data)

            if total_length is None:
                sys.stdout.write(f"\r[{'?' * 40}] - {nice_size(length)} / {total_length_mb} ")
            else:
                amount = int(length / total_length * 40)
                sys.stdout.write(f"\r[{'|' * amount}{' ' * (40 - amount)}] - {nice_size(length)} / {total_length_mb} ")
            sys.stdout.flush()

        cprint("\n")

    md5_file = md5.hexdigest()
    if md5_source is not None:
        if md5_file != md5_source:
            zip_file.unlink()
            logger.error(f"File doesn't match the md5 file: {md5_file} != {md5_source}")
            return None
        else:
            cprint(f"<b,g,>Passed md5 check.</b,g,>")
    else:
        logger.warning(f"No md5 to check against: <b>{md5_file}</b>")

    md5_result[0] = md5_file

    return file_name


def datetime_compare(time_a, time_b=None):
    if isinstance(time_a, str):
        time_a = datetime.datetime.fromisoformat(time_a)

    if time_b is None:
        time_b = datetime.datetime.now()
    elif isinstance(time_b, str):
        time_b = datetime.datetime.fromisoformat(time_b)

    return (time_b - time_a).seconds


def add_list_unique(base_list, value):
    if value not in base_list:
        base_list.append(value)


def add_dict_list_unique(base_dict, key, value):
    if key not in base_dict:
        base_dict[key] = value
        return

    if isinstance(base_dict[key], str):
        if base_dict[key] == value:
            return

        base_dict[key] = [base_dict[key]]

    if value not in base_dict[key]:
        base_dict[key].append(value)


def get_dict_list(base_dict, key):
    if key not in base_dict:
        return []

    result = base_dict[key]
    if isinstance(result, str):
        return [result]

    if result is None:
        ## CEBION STRIKES AGAIN
        return []

    return result



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

    zip_info = PortInfo({})

    zip_info.md5 = md5_result[0]
    zip_info.source = f"url/{zip_file.name}"
    zip_info.zip_file = zip_file
    zip_info.attr['url'] = original_url

    # print(f"-- {zip_info} --")

    cprint("<b,g,>Success!</b,g,>")
    return zip_info


@contextlib.contextmanager
def make_temp_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)

    finally:
        shutil.rmtree(temp_dir)


__all__ = (
    'add_list_unique',
    'add_dict_list_unique',
    'get_dict_list',
    'fetch_data',
    'fetch_json',
    'fetch_text',
    'json_safe_load',
    'json_safe_loads',
    'make_temp_directory',
    'download',
    'datetime_compare',
    'raw_download',
    )
