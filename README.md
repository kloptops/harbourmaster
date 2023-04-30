# harbourmaster
New Portmaster Backend Engine

# Goals

Harbourmaster is the start of the eventual replacement of the [PortMaster][PortMaster] script. Currently PortMaster is a monolithic bash script that allows users to download prepackaged ports for portable linux handhelds. Currently it works well but it slowly getting more and more unweildly as more and more ports are added. Some ports are engines that allow classic games to run on newer hardware, but they have a different name from the original game. This can make discoverability hard.

The goal is to have a gui frontend that can display text/images and a description about the game, even add sorting by genre or updates available. This is the script backend that will handle listing available ports, downloading and installing/uninstalling ports.

- [x] `ports.md` generation for `PortMaster.sh`
  - [x] List by Genre
  - [ ] List by Updates
  - [x] List by Ready to Run
- [x] Download Ports
- [x] Install Ports
- [x] List ports
- [x] Detect ports installed by zip
  - [x] Have a builtin list of known ports to figure out older ports and ports installed manually.
- [x] Multiple Ports repositories
- [x] Uninstall Ports

# How it works:

## Listing available ports:

Harbourmaster has a list of sources where it fetches ports from, by default it comes with:

| Source               | Description                                                                           | Source File                  |
| -------------------- | --------------------------------------------------------------------------------------| ---------------------------- |
| PortMaster           | This draws from the default portmaster repository, it uses the PortMasterV1 protocol. | `020_portmaster.source.json` |
| PortMaster Runtimes  | This is where runtimes for different game systems live, it uses the GitHubRawReleaseV1 protocol. | `021_runtimes.source.json` |

With these two sources portmaster behaves as usual.

What makes portmaster different is it is now possible to install additional port sources, so that additional repositories of ports can be sourced.

| Source               | Description                                                                           | Source File                  |
| -------------------- | --------------------------------------------------------------------------------------| ---------------------------- |
| Kloptops             | This is a source for my own testing port releases, it uses the GitHubRepoV1 protocol. | [`050_kloptops.source.json`][KloptopsSource] |


_Note: additional sources can be added_

## Installing ports:

Harbour

## Keeping track of installed ports:

Harbourmaster maintains a record of installed ports by checking the ports folder and reading `<portname>.port.json` files. These port.json files indicate the files and directories associated with each port. If any of these files or directories are not found, the port is marked as broken. Additionally, Harbourmaster scans the files and directories in the ports folder to identify any unclaimed files. If any of these match our database of known ports, they are flagged as newly installed ports. For those ports, we create a `<portname>.port.json` file. During this process we also check all the files and directories associated with the newly found port, if any are missing it flags the port as broken.

## commands available:

| Command                                                  | Effect                                                  |
|  ------------------------------------------------------- | ------------------------------------------------------- |
| `harbourmaster update`                                   | downloads the latest ports information                  |
| `harbourmaster portsmd [filters]`                        | generate a ports.md file compatible with PortMaster.sh  |
| `harbourmaster list [filters]`                           | list available ports                                    |
| `harbourmaster ports`                                    | list installed ports, and unknown ports.                |
| `harbourmaster install <source>/<zipname>.zip`           | downloads and installs the port from available sources. |
| `harbourmaster install http[s]://<url>.zip[.md5/md5sum]` | downloads a port from the specified url. If the url ends with md5/md5sum it assumes the url without the md5 is the ports zipfile. It will check the md5 against what is downloaded. |
| `harbourmaster upgrade harbourmaster`                    | Updates harbourmaster against the latest version on github |

[PortMaster]: https://github.com/christianhaitian/PortMaster
[KloptopsSource]: https://raw.githubusercontent.com/kloptops/Portmaster-misc/main/releases/050_kloptops.source.json
