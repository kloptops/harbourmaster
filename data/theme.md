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


## Element overrides

You can override values in elements based on hardware by specifying a hardware capabilities on an attribute:

```json

    "#base": {
        "font": "DejaVuSans.ttf",
        "font-scale[hires]": 2.0,
        "font-scale[5:3,hires]": 3.0
    },

```

You can override entire elements based on hardware capabilities:

```json

        "ports_list": {
            "area": [0.0, 0.1, 0.4, 0.95],
            "border-x": 16,
            "roundness": 10,
            "font-size": 14,
            "font-color": "list_text",
            "select-color": "list_selected",
            "text-clip": true,
            "text-wrap": false,
            "autoscroll": "slide",
            "scroll-speed": 30,
            "scroll-delay-start": 500,
            "scroll-delay-end":   500
        },
        "ports_list[hires]": {
            "area": [0.0, 0.1, 0.3, 0.95]
        },
```

Since this uses the capabilities system used in ports you can add them together and or not them.



Currently the capabilities are:

- `hires`: devices with a screen resolution greater than 640:480
- `lowres`: devices with a screen resolution smaller then 640:480
- `power`: any device above an `rk3326` cpu.
- `opengl`: any device with `OpenGL`, not OpenGLES.
- `3:2`: aspect ratio of 3:2
- `4:3`: aspect ratio of 4:3
- `5:3`: aspect ratio of 5:3
- `16:9`: aspect ratio of 16:9
- `427:240`: aspect ratio of 427:240 (ogs/ogu & friends)
- `wide`: any aspect ratio above 4:3

You can combine them like so:

- `!lowres|hires`: must be exactly 640:480


## Scenes

Scenes can define their own `#base` element, which will cause all elements in that scene to inherit from.

Currently there are the following scenes:

- `main_menu`: The main menu
- `option_menu`: Options screen
- `ports_list`: The list of ports
- `port_info`: Detailed port information.
- `message_window`: A scrolling list of messages, used during downloading, installation, and fetching the latest ports information.
- `message_box`: An alert box
- `filter_list`: Available filters

### Scene: main_menu

This is the main menu scene, it requires the `option_list` element. It is the first scene to load and if backed out of will quit the program.

```json
    "option_list": {
        "list": [
            "All Ports",
            "Ready to Run Ports",
            "Uninstall Ports",
            "Option Menu",
            "Exit"
        ],
        "option": [
            "install",
            "install-rtr",
            "uninstall",
            "option",
            "exit"
        ]
    }
```

The option_list can contain whatever text you feel is most appropriate, the actual option that gets called is the same option in the `option` list.

Currently the supported options for the main menu are as listed, more can be added as necessary.

### Scene: options_menu

This is the options menu scene, it requires the `option_list` element. It is loaded from main-menu via.

```json
    "option_list": {
        "list": [
            "Update ports",
            "Back"
        ],
        "option": [
            "update-ports",
            "back"
        ]
    }
```

The option_list can contain whatever text you feel is most appropriate, the actual option that gets called is the same option in the `option` list.

Currently the supported options for the main menu are as listed, more will be added as necessary.


### Scene: options_menu

This is the options menu scene, it requires the `option_list` element. It is loaded from main-menu via.

```json
    "option_list": {
        "list": [
            "Update ports",
            "Back"
        ],
        "option": [
            "update-ports",
            "back"
        ]
    }
```

The option_list can contain whatever text you feel is most appropriate, the actual option that gets called is the same option in the `option` list.

Currently the supported options for the main menu are as listed, more will be added as necessary.


## Elements

### The basics

Elements are always rectangles, they must always have an `area` parameter. This can be pixels specifically, or a percentage of the parent area.

If you specify negative pixels for the width/height it subtracts it from the width/height of the parent area.

If you specify the coordinates in pixels it is in thef format: `x, y, width, height`

If you specify it as a percentage of the parent area it is as: `top-left-x, top-left-y, bottom-right-x, bottom-right-y`

```json

    "get_rect_perc": {
        // 25%, 25% to 75%, 75%
        "area": [0.25, 0.25, 0.75, 0.75]
    },

    "get_rect_px": {
        // same as above on a 640x480 display
        "area": [160, 120, 320, 240]
    },

    "get_rect_inset": {
        // same as above on a 640x480 display
        "area": [160, 120, -160, -120]
    },

```

As hinted to above, you can specify a parent element to use as the basis of the calculating element positions.


```json
        "left_pane": {
            // [0, 0, 192, 480] on 640x480 display
            "area": [ 0.0, 0.0, 0.3, 1.0 ]
        },
        "right_pane": {
            // [192, 0, 448, 480] on 640x480 display
            "area": [ 0.3, 0.0, 1.0, 1.0 ]
        },
        "port_info_image_area": {
            // [202, 10, 236, 230] using the above right_pane as the basis
            "parent": "right_pane",
            "area": [ 10, 10, -10, 0.5 ]
        },
        "port_info_text_area": {
            // [202, 240, 236, 230] using the above right_pane as the basis
            "parent": "right_pane",
            "area": [ 10, 0.5, -10, -10 ]
        },
```

By mixing and matching these you can build very powerful layouts.

You can also use the element overrides to further customise for different screen sizes.

```json
        "left_pane": {
            "area": [ 0.0, 0.0, 0.3, 1.0 ],
            "area[wide]": [ 0.0, 0.0, 0.4, 1.0 ]
        },
        "right_pane": {
            "area": [ 0.3, 0.0, 1.0, 1.0 ],
            "area[wide]": [ 0.4, 0.0, 1.0, 1.0 ]
        },
```


Elements can be themed by setting a `fill`, `outline`, `thickness`, and `roundness`:

- `fill`: the color to fill in the elements rect
- `outline`: the color of the outline for the elements rect
- `thickness`: how thick the stroke of the outline is
- `roundess`: if sdlGFX is available, it will make a roundrect with x pixels of roundness in the corners.
- `progress-fill`: this is a special fill colour, used for the progress bar.



### Displaying Text

Currently there are a few ways of displaying text.

To display text at a minimum you need a `font`, `font-size`, `font-color`, and `text`.

```json
    "text_element": {
        "area": [0.25, 0.25, 0.75, 0.75],
        "text": "Text to be displayed!",
        "font": "DejaVuSans.ttf",
        "font-size": 20,
        "font-color": [0, 0, 0]
    }
```

A special option is `font-scale` which should be used to broadly scale fonts across multiple elements or scenes using the element overrides.

```json
    "#base": {
        "font-scale[hires]": 2.0,
    }
```

You can align text to different positions of the element.

- `topleft`
- `topcenter`
- `topright`
- `midleft`
- `center`
- `midright`
- `bottomleft`
- `bottomcenter`
- `bottomright`

You can control the way text is displayed with word wrapping, automatic scrolling, clipping, and scaling.

- shrink/grow the text to fill the region: `"text-clip": false`
- clip the text and just show what is visible: `"text-clip": true`
- word wrap the text if it is too wide for the area provided: `"text-wrap": true`

It also supports text auto-scrolling if it doesnt fit within the area it is displayed. It will horizontally scroll if the text is wider (word wrap is off), and vertically scroll if it is too tall (word-wrap is on).

```json
    "element_name": {
        // Other element bits and bobs here.

        "text-clip": true,          // This must be true for scrolling to work
        "text-wrap": false,         // If text-wrap is false, it will default to a horizontal scroll, otherwise it defaults to a vertical scroll

        "autoscroll": "slide",      // null does nothing, "slide" scrolls down then resets, "marquee" scrolls back and forth

        "scroll-speed": 30,         // How many miliseconds between each scrolling step
        "scroll-delay-start": 500,  // How many miliseconds to wait before starting to scroll
        "scroll-delay-end":   500,   // How many miliseconds to wait at the end of scrolling

        "scroll-direction": "horizontal" // override the defaults assumed based on text-wrap
    }

```

## Text Template System

### System tags

- system.time_24hr
- system.time_12hr
- system.free_space
- system.used_space
- system.cfw_name
- system.cfw_version
- system.device_name
- system.battery_level

- system.progress_text
- system.progress_amount

### Port info tags

- port_info.title
- port_info.description
- port_info.instructions
- port_info.genres
- port_info.porter
- port_info.ready_to_run
- port_info.download_size
- port_info.runtime
- port_info.runtime_status



### Control flow of PortMaster

```
Main:
  -> Install Menu
  -> Uninstall Menu -> Port List [Installed filter]
  -> Options
  -> Quit

Install Menu:
  -> All Ports    -> Port List [No filter]
  -> Ready To Run -> Port List [RTR filter]

  -> Lists 1      -> Custom List
  -> Lists 2      -> Custom List
  -> Lists 3      -> Custom List
  -> Lists 4      -> Custom List

  -> Back

Port List:
  -> List of Ports
    -> Inspect
    -> Back

Options:
  -> TBD.
  -> Back

Inspect:
  -> Install/Re-Install or Uninstall
  -> Back

Install/Uninstall:
  -> Message Screen
  -> Back
```
