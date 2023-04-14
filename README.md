# harbourmaster
New Portmaster Backend Engine

# Goals

Harbourmaster is the start of the eventual replacement of the [PortMaster][PortMaster] script. Currently PortMaster is a monolithic bash script that allows users to download prepackaged ports for portable linux handhelds. Currently it works well but it slowly getting more and more unweildly as more and more ports are added. Some ports are engines that allow classic games to run on newer hardware, but they have a different name from the original game. This can make discoverability hard.

The goal is to have a gui frontend that can display text/images and a description about the game, even add sorting by genre or updates available. This is the script backend that will handle listing available ports, downloading and installing/uninstalling ports.

- [x] `ports.md` generation for `PortMaster.sh`
  - [ ] List by Genre
  - [ ] List by Updates
  - [ ] List by Ready to Run
- [ ] Download Ports
- [ ] Install Ports
- [ ] Multiple Ports repositories
- [ ] Uninstall Ports



# Ports Installed Check

Look at root scripts

- check file size / md5
- check associated directories exist
- determines which zip it comes from.


[PortMaster]: https://github.com/christianhaitian/PortMaster
