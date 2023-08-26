# PortMaster - Public Beta

PortMaster is a convenient script designed to facilitate the downloading and installation of ports for handheld devices. As the number of available ports has increased, the original interface has become progressively cumbersome. For the past few months we have been developing a new GUI.

We are delighted to present the first public beta the new PortMaster GUI.

# Features (it has them)

- Completely custom GUI using Python SDL2 bindings
- Small size, only 3.8mb!
- Port previews, we can really showcase the ports.
- Cancellable downloads, accidentally started a 300mb download? Get out of here.
- Filter ports by genre/porter/runtime
- Localizations (We currently have English, Italian, French, and German), translators welcome!
- **Themes:**
  - Since it was possible with the custom GUI, we went for it.
  - We have a few themes at launch, but contributions are more than welcome.
    - *Default Theme*: comes in both light mode and dark mode
    - *Zelda*: LTTP Inspired theme
    - *FF VII*: A beautifully done FF7 theme
    - *Basic Theme*: A super barebones theme so you can get started designing your own!
  - Colour Schemes, themes can support multiple colour schemes for darkmode / lightmode / different colour ways.
  - Builtin theme downloader!

# Nerdy features

- **Custom Sources**: want to control your own ports repository? no worries!
- **Platform Hooks**: PortMaster on raspberry pi? Lets gooooo.


# Installation

[Download](https://github.com/kloptops/harbourmaster/releases/latest)

To install the beta download the PortMaster.zip from the link above, unzip it and place it in the appropriate folder for your CFW.

| CFW          | Location               |
|--------------|------------------------|
| AmberElec    | /storage/roms/ports/   |
| ArkOS        | /roms(or roms2)/tools/ |
| JELOS        | /storage/roms/ports/   |
| TheRA        | /opt/tools/            |
| UnofficialOS | /storage/roms/ports/   |

If your CFW is not listed above, it will most likely be in one of the above locations.

# Things to know

There are a few bugs, which we are looking to fix.

- ArkOS has no volume control, so it is disabled for now.
- Some resolutions of the themes need some work, but for the most part are good.
- The options menus need a bit of reworking.

# Things still to do

We are still using the old `ports.md` file to store information about ports, which is limited. Once the gui is live we will transition to the new `ports.json` format and that will mean reworking most of the port descriptions and adding installation instructions. This will allow PortMaster to know if there is updates available, filter by runtimes, and lots of other quality of life features.

# Feedback

Please direct all feedback to the [PortMaster Public Beta](https://discord.com/channels/1122861252088172575/1144846802701520997) channel in the [PortMaster discord server](https://discord.gg/SbVcUM4qFp).

# Thanks

I want to thank everyone on the PortMaster crew who have helped, but a special thanks to:

- [christianhaitian](https://github.com/christianhaitian)
- [cebion](https://github.com/cebion)
- [christopher-roelofs](https://github.com/christopher-roelofs)
- [tekkenfede](https://github.com/tekkenfede)
