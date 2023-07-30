# harbourmaster
New Portmaster Backend Engine

# Goals

Harbourmaster is the start of the eventual replacement of the [PortMaster][PortMaster] script. Currently PortMaster is a monolithic bash script that allows users to download prepackaged ports for portable linux handhelds. Currently it works well but it slowly getting more and more unweildly as more and more ports are added. Some ports are engines that allow classic games to run on newer hardware, but they have a different name from the original game. This can make discoverability hard.

The goal is to have a gui frontend that can display text/images and a description about the game, even add sorting by genre or updates available. This is the script backend that will handle listing available ports, downloading and installing/uninstalling ports.

- [x] `ports.md` generation for `PortMaster.sh`
  - [x] List by Genre
  - [ ] List by Updates
  - [x] List by Ready to Run
  - [x] Filter by device/capabilities
- [x] Download Ports
- [x] Install Ports
- [x] List ports
- [x] Detect ports installed by zip
  - [x] Have a builtin list of known ports to figure out older ports and ports installed manually.
- [x] Multiple Ports repositories
- [x] Uninstall Ports

# How it works:


## port.json

Most of what harbourmaster uses is a new file called `<portname>.port.json`, this contains all the information required for a port.

An [example annotated json file is included][example_json], however for the moment most ports do not have a `.port.json` file so harbourmaster creates them from various sources. Going forward all ports should have a `.port.json` file and will be a requirement of submission to PortMaster.

We have an [easy to use webpage][port_html] for adding `port.json` file directly to your ports zip files, it all runs locally in your webbrowser so its easy to use.


## Listing available ports:

Harbourmaster has a list of sources where it fetches ports from, by default it comes with:

| Source               | Description                                                                           | Source File                  |
| -------------------- | --------------------------------------------------------------------------------------| ---------------------------- |
| PortMaster           | This draws from the default portmaster repository, it uses the PortMasterV1 protocol. | `020_portmaster.source.json` |
| PortMaster Runtimes  | This is where runtimes for different runtimes live, it uses the GitHubRawReleaseV1 protocol. | `021_runtimes.source.json` |

With these two sources portmaster behaves as usual.

What makes portmaster different is it is now possible to install additional port sources, so that additional repositories of ports can be sourced.

| Source               | Description                                                                           | Source File                  |
| -------------------- | --------------------------------------------------------------------------------------| ---------------------------- |
| Kloptops             | This is a source for my own testing port releases, it uses the [GitHubRepoV1][GitHubRepoV1] protocol. | [`050_kloptops.source.json`][Kloptops_Source] |

[Kloptops_Source]: https://raw.githubusercontent.com/kloptops/Portmaster-misc/main/releases/050_kloptops.source.json


_**Note**: additional sources can be added, make a PR to get yours added_


## Installing ports:

Harbourmaster follows a specific process to identify and fetch the appropriate port for downloading.

Here's an overview of the steps involved:

- Port Identification: Ports are uniquely identified by their zip file names. Although this method may not be flawless, it has proven to be effective in practice.
- Source Priority: Harbourmaster fetches ports from the sources provided, considering their priority order. The tool retrieves ports from the sources in the specified sequence.
- Verification and Validation: Once a port is fetched from a source, Harbourmaster verifies its integrity. This involves checking if the downloaded port matches the supplied MD5 checksum. This verification ensures that the port is not corrupted or modified during the download process.
- Zip Content Check: After the download is validated, Harbourmaster inspects the contents of the zip file. It checks for the presence of at least one bash file and a data directory. Additionally, it scans for any unusual files that could potentially override core operating system files.
- Port Configuration: Harbourmaster ensures that a `<portname>.port.json` file exists for the port. This file contains relevant information about the port itself, which is combined with other data during the installation process to fully flesh it out.

By following this process, Harbourmaster reliably identifies, fetches, and verifies ports from the specified sources, ensuring the integrity and consistency of the downloaded files.


## Keeping track of installed ports:

Harbourmaster keeps track of installed ports by examining the ports folder and reading the `<portname>.port.json` files associated with each port. These JSON files provide information about the specific files and directories related to each port.

During this process, Harbourmaster performs the following checks and actions:

- Detection of Broken Ports: Harbourmaster verifies the presence of the files and directories indicated in the `<portname>.port.json` files for each installed port. If any of these files or directories are not found, it indicates that the port is broken or incomplete.
- Identification of Unclaimed Files: Harbourmaster scans the files and directories within the ports folder to identify any files that have not been associated with a known port. These unclaimed files are then processed further.
- Detection of Newly Installed Ports: Among the unclaimed files, Harbourmaster compares them against its database of known ports. If a match is found, indicating that a new port has been installed, Harbourmaster flags it as such.
- Creation of `<portname>.port.json` File: For newly installed ports, Harbourmaster creates a corresponding `<portname>.port.json` file. This file contains the necessary information about the port, enabling Harbourmaster to manage and track it effectively.
- Validation of Newly Found Ports: While processing newly found ports, Harbourmaster checks all associated files and directories. If any of these files or directories are missing, it identifies the port as broken or incomplete.

By performing these checks and actions, Harbourmaster maintains an accurate record of installed ports, identifies broken ports, detects newly installed ports, and ensures the integrity of the associated files and directories. This also allows Harbourmaster to work with ports that are manually unzipped into the ports folder.


## Known Ports:

Some ports, because of their nature, cannot or do not exist on PortMaster. So that harbourmaster can work as intended, we create a `.port.json` for them in the [known-ports][known_ports] directory. Please create a PR for any that you come across that we don't know about.

## Commands available:


| Command                                                   | Effect                                                     |
|  -------------------------------------------------------- | ---------------------------------------------------------- |
| `harbourmaster update`                                    | downloads the latest ports information                     |
| `harbourmaster portsmd [filters]`                         | generate a ports.md file compatible with PortMaster.sh     |
| `harbourmaster list [filters]`                            | list available ports                                       |
| `harbourmaster ports`                                     | list installed, broken, and unknown ports.                 |
| `harbourmaster install http[s]://<url>.zip[.md5/md5sum]`  | downloads a port from the specified url. If the url ends with md5/md5sum it assumes the url without the md5 is the ports zipfile. It will check the md5 against what is downloaded. |
| `harbourmaster install [source/]<portname>.zip`           | downloads and installs the port from available sources.    |
| `harbourmaster uninstall <portname>.zip`                  | Uninstall specified port.                                  |
| `harbourmaster runtimes_list`                             | List available runtime environments                        |
| `harbourmaster runtimes_check <runtime>`                  | Installs the specified runtime if it is not installed      |
| `harbourmaster upgrade harbourmaster`                     | Updates harbourmaster against the latest version on github |


## Python libraries used:

- [ansimarkup][ansimarkup]
- [certifi][certifi]
- [colorama][colorama]
- [fastjsonschema][fastjsonschema]
- [idna][idna]
- [loguru][loguru]
- [port_gui][port_gui] - used as pySDL2gui
- [pypng][pypng]
- [pyqrcode][pyqrcode]
- [PySDL2][pysdl2]
- [requests][requests]
- [typing-extensions][typing_extensions]
- [urllib3][urllib3]


[PortMaster]: https://github.com/christianhaitian/PortMaster
[GitHubRepoV1]: https://github.com/kloptops/harbourmaster/tree/main/tools

[example_json]: https://github.com/kloptops/harbourmaster/blob/main/data/example.port.json
[port_html]: https://kloptops.github.io/harbourmaster/port.html
[known_ports]: https://github.com/kloptops/harbourmaster/tree/main/known-ports

[ansimarkup]: https://pypi.org/project/ansimarkup/
[certifi]: https://pypi.org/project/certifi/
[colorama]: https://pypi.org/project/colorama/
[fastjsonschema]: https://pypi.org/project/fastjsonschema/
[idna]: https://pypi.org/project/idna/
[loguru]: https://pypi.org/project/loguru/
[port_gui]: https://github.com/mcpalmer1980/port_gui
[pypng]: https://pypi.org/project/pypng/
[pyqrcode]: https://pypi.org/project/qrcode/
[pysdl2]: https://pypi.org/project/PySDL2/
[requests]: https://pypi.org/project/requests/
[typing_extensions]: https://pypi.org/project/typing-extensions/
[urllib3]: https://pypi.org/project/urllib3/
