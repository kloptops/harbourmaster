## PortMaster Theme Specification

PortMasters new gui has a flexible theme system build around a `theme.json` file.

This is currently a WIP documenting the theme format.

## Scene Format

The theme has a few different sections:

- `#info`: Info about the theme
- `#base`: The base element, which every gui element in the theme inherits from
- `#pallet`: Predefined colours for the theme.
- `#resources`: Images the theme uses, can either be an atlas or individual images.
- `#elements`: Reusable elements that different scenes in your theme can use.
- **scenes**: Scenes that the gui uses

It also uses a template system for the text, so that the gui elements automatically update as the text changes.


## Element Inheritence Order:

The order that elemets get their values is defined as:

element -> scene `#base` -> global `#base`


If you use a reusable element the order is:

element -> element `#element` -> scene `#base` -> global `#base`


## Scenes

Scenes can define their own `#base` element, which will cause all elements in that scene to inherit from.

Currently there are the following scenes:

- `main_menu`: The main menu
- `option_menu`: Options screen
- `ports_list`: The list of ports
- `port_info`: Detailed port information.
- `message_window`: A scrolling list of messages, used during installation, downloading the latest ports information.
- `message_box`: An alert box
- `filter_list`: Available filters

### Scene: main_menu


## Element theming

### Auto Scrolling Text

```json
    "text-clip": true,          // This must be true for scrolling to work
    "text-wrap": false,         // If text-wrap is false, it will default to a horizontal scroll, otherwise it defaults to a vertical scroll

    "autoscroll": "slide",      // null does nothing, "slide" scrolls down then resets, "marquee" scrolls back and forth

    "scroll-speed": 30,         // How many miliseconds between each scrolling step
    "scroll-delay-start": 500,  // How many miliseconds to wait before starting to scroll
    "scroll-delay-end":   500   // How many miliseconds to wait at the end of scrolling

    "scroll-direction": "horizontal", // override the defaults by text-wrap
```


## Text Template System

### System specific tags

- system.time_24hr
- system.time_12hr
- system.free_space
- system.used_space
- system.cfw_name
- system.cfw_version
- system.device_name
- system.battery_level

### Port specific tags

- port_info.title
- port_info.description
- port_info.instructions
- port_info.genres
- port_info.porter
- port_info.ready_to_run
- port_info.download_size
- port_info.runtime
- port_info.runtime_status
