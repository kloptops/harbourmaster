import functools
import gettext
import json

import sdl2
import sdl2.ext

import harbourmaster
import harbourmaster.source
import pySDL2gui

from loguru import logger


_ = gettext.gettext


## TODO: make this all a class
def extract_requirements(text, strict=False):
    if strict:
        default = None
    else:
        default = []

    if '[' not in text:
        return text, default

    if text.count('[') > 1 or not text.endswith(']'):
        logger.error(f"Bad requirement {text}")
        return text.split('[')[0] + "_bad", default

    text, requirement = text.split('[', 1)
    requirements = map(str.strip, requirement[:-1].split(','))
    return text, list(requirements)


def theme_update(target, source):
    capabilities = harbourmaster.device_info()['capabilities']

    for key, value in source.items():
        key, requirements = extract_requirements(key)
        if requirements is not None:
            if not harbourmaster.match_requirements(capabilities, requirements):
                continue

        if isinstance(value, dict):
            theme_update(target.setdefault(key, {}), value)
        elif isinstance(value, list):
            target[key] = value[:]
        else:
            target[key] = value

    return target


def theme_merge(target, source):
    temp = theme_update({}, target)
    temp = theme_update(temp, source)
    return temp


def theme_apply(gui, section_data, base_data, elements):
    new_data = {}
    capabilities = harbourmaster.device_info()['capabilities']

    for region_name, region_data in section_data.items():
        if region_name == "#base":
            base_data = theme_merge(base_data, region_data)
            continue

        elif region_name.startswith("#element:"):
            element_name = region_name.split(':', 1)[1]
            if ':' in element_name:
                element_name, region_name = element_name.split(':', 1)
            else:
                region_name = element_name

            region_name, requirements = extract_requirements(region_name)
            if not harbourmaster.match_requirements(capabilities, requirements):
                continue

            if element_name not in elements:
                logger.debug(f"Error: Unknown element {element_name}")
                continue

            new_data[region_name] = theme_merge(base_data, theme_merge(elements[element_name], region_data))
            continue

        region_name, requirements = extract_requirements(region_name, strict=True)
        if requirements is not None:
            if not harbourmaster.match_requirements(capabilities, requirements):
                continue

            new_data[region_name] = theme_merge(new_data.get(region_name, base_data), region_data)

        else:
            new_data[region_name] = theme_merge(base_data, region_data)

    return new_data


def theme_load(gui, theme_file, color_scheme=None):
    print(f"Loading theme {theme_file}")

    with open(theme_file, 'r') as fh:
        theme_data = json.load(fh)

    if theme_data is None:
        raise ValueError(f"Unable to load theme {theme_file}")

    capabilities = harbourmaster.device_info()["capabilities"]

    base_data = {}
    elements = {}
    sections = {}

    all_schemes = [
        scheme_name
        for scheme_name in theme_data.get("#schemes", {})
        if not scheme_name.startswith("#")]

    if color_scheme is None:
        color_scheme = theme_data.get("#info", {}).get("default-scheme", None)

    if color_scheme not in all_schemes:
        color_scheme = None

    if color_scheme is None:
        if len(all_schemes) > 0:
            color_scheme = all_schemes[0]

    if color_scheme is not None:
        if color_scheme not in theme_data.get("#schemes", {}):
            print(f"- Unable to find {color_scheme} in the theme_data.")
            return None

        else:
            base_scheme = theme_data["#schemes"].get("#base", {})

            for section_name, section_data in theme_data["#schemes"][color_scheme].items():
                if section_name not in ("#base", "#resources", "#pallet"):
                    continue

                theme_data[section_name] = theme_merge(base_scheme.get(section_name, {}), section_data)

    for section_name, section_data in theme_data.items():
        if section_name.startswith('#'):
            if section_name == "#base":
                print("- loading base_data")
                base_data = section_data

            elif section_name == "#resources":
                print("- loading resources:")
                for resource_name, resource_data in section_data.items():
                    resource_set_name = resource_data.get("name", resource_name)

                    if resource_name.lower().rsplit('.', 1)[-1] in ('jpg', 'png', 'svg'):
                        success = gui.images.load_data(resource_name, resource_data) is None and 'FAIL' or 'OKAY'

                        if resource_set_name != resource_name:
                            print(f"  - loading image {resource_name} as {resource_set_name} - [{success}]")
                        else:
                            print(f"  - loading image {resource_name} - [{success}]")

                    elif resource_name.lower().rsplit('.', 1)[-1] in ('ogg', 'wav', 'mp3', 'mod'):
                        success = gui.sounds.load(resource_name, resource_set_name) is None and 'FAIL' or 'OKAY'

                        if resource_set_name != resource_name:
                            print(f"  - loading sound {resource_name} as {resource_set_name} - [{success}]")
                        else:
                            print(f"  - loading sound {resource_name} - [{success}]")

            elif section_name == "#elements":
                print("- loading elements:")
                for element_name, element_data in section_data.items():
                    element_name, requirements = extract_requirements(element_name)
                    if not harbourmaster.match_requirements(capabilities, requirements):
                        continue

                    elements[element_name] = element_data

                    last_value = None
                    for element_key, element_value in element_data.items():
                        element_key, requirements = extract_requirements(element_key)
                        if element_key != 'area':
                            continue

                        if not harbourmaster.match_requirements(capabilities, requirements):
                            continue

                        last_value = element_value

                    if last_value is not None:
                        gui.default_rects.make_rect(element_data.get('parent', 'root'), element_name, last_value)

            elif section_name == "#pallet":
                print("- loading pallet:")
                for pallet_name, pallet_value in section_data.items():
                    gui.pallet[pallet_name] = pallet_value

            elif section_name == "#override":
                print("- loading override:")
                for override_name, override_value in section_data.items():
                    gui.override[override_name] = override_value

        else:
            section_name, requirements = extract_requirements(section_name, strict=True)
            if requirements is not None:
                if not harbourmaster.match_requirements(capabilities, requirements):
                    logger.debug(f"Not matched: {section_name} -> {capabilities}, {requirements}")
                    continue

                if section_name not in sections:
                    logger.error(f"{section_name} not yet defined, skipping.")
                    continue

                print(f"  - loading section {section_name}")
                sections[section_name] = theme_apply(gui, section_data, sections[section_name], elements)
            else:
                print(f"  - loading section {section_name}")
                sections[section_name] = theme_apply(gui, section_data, base_data, elements)

    if harbourmaster.HM_TESTING:
        with open('debug.json', 'w') as fh:
            json.dump(sections, fh, indent=4)

    return sections


class Theme:
    def __init__(self, theme_dir):
        self.theme_dir = theme_dir

        self.theme_file = theme_dir / "theme.json"

        if not self.theme_file.is_file():
            raise ValueError(f"{self.theme_file} not found.")

        with open(self.theme_file, 'r') as fh:
            self.theme_data = json.load(fh)

        self.__screenshot = None

    @property
    def name(self):
        return self.theme_data.get("#info", {}).get("name", None)

    @property
    def creator(self):
        return self.theme_data.get("#info", {}).get("creator", None)

    @property
    def screenshot(self):
        if self.__screenshot is not None:
            return self.__screenshot

        for screenshot_name in ("screenshot.png", "screenshot.jpg"):
            screenshot_file = self.theme_dir / screenshot_name
            if screenshot_file.is_file():
                self.__screenshot = screenshot_file
                return screenshot_file

        return None

    @property
    def schemes(self):
        return [
            scheme_name
            for scheme_name in self.theme_data.get("#schemes", {})
            if not scheme_name.startswith('#')]


    def gui_init(self, gui, color_scheme=None):
        gui.resources.add_path(self.theme_dir)
        return theme_load(gui, self.theme_file, color_scheme)


class ThemeDownloader(harbourmaster.source.GitHubRawReleaseV1):
    DEFAULT_DATA = {
        "prefix": "thm",
        "api": "GitHubRawReleaseV1",
        "name": "PortMaster Themes",
        "url": "https://api.github.com/repos/PortsMaster/PortMaster-Themes/releases/latest",
        "last_checked": None,
        "version": 1,
        "data": {}
        }

    def __init__(self, gui):
        ## BROKEN :D
        self.gui = gui
        config_file = self.gui.hm.cfg_dir / "themes.json"
        if config_file.is_file():
            with open(config_file, 'r') as fh:
                config_data = json.load(fh)

        else:
            config_data = self.DEFAULT_DATA.copy()

        super().__init__(self.gui.hm, config_file, config_data)


class ThemeEngine:
    def __init__(self, gui):
        self.gui = gui

    def get_pm_config(self):
        cfg_dir = harbourmaster.HM_TOOLS_DIR / "PortMaster"
        cfg_file = cfg_dir / "config" / "config.json"
        cfg_data = {}

        if self.gui.hm is None:
            if cfg_file.is_file():
                with open(cfg_file, 'r') as fh:
                    cfg_data = json.load(fh)
        else:
            cfg_data = self.gui.hm.cfg_data

        return cfg_data

    def get_current_theme(self):
        """
        Returns the name of the current theme
        """

        cfg_data = self.get_pm_config()

        cfg_data.setdefault("theme", "default_theme")
        if not self.get_theme_dir(cfg_data["theme"]).is_dir():
            logger.error(f"Unable to find theme '{cfg_data['theme']}', setting to 'default_theme'")
            cfg_data["theme"] = "default_theme"

        elif not (self.get_theme_dir(cfg_data["theme"]) / "theme.json").is_file():
            logger.error(f"Unable to find theme '{cfg_data['theme']}', setting to 'default_theme'")
            cfg_data["theme"] = "default_theme"

        return cfg_data["theme"]

    def get_current_theme_scheme(self):
        """
        Returns the colour scheme of the current theme
        """

        cfg_data = self.get_pm_config()
        return cfg_data.setdefault("theme-scheme", None)

    def get_theme_dir(self, theme_name):
        cfg_dir = harbourmaster.HM_TOOLS_DIR / "PortMaster"

        if theme_name == "default_theme":
            return PYLIB_PATH / theme_name

        else:
            return cfg_dir / "themes" / theme_name

    def get_theme(self, theme_name):
        return Theme(self.get_theme_dir(theme_name))

    def get_themes_list(self):
        cfg_dir = harbourmaster.HM_TOOLS_DIR / "PortMaster"

        themes = {
            "default_theme": self.get_theme("default_theme"),
            }

        for theme_file in (cfg_dir / "themes").glob("*/theme.json"):
            theme_name = theme_file.parent.name
            theme_data = self.get_theme(theme_name)

            themes[theme_name] = theme_data

        return themes

    def get_theme_schemes_list(self, theme_name=None):
        if theme_name is None:
            theme_name = self.gui.hm.cfg_data.get("theme", "default_theme")

        theme = self.get_theme(theme_name)

        return theme.schemes

    def gui_init(self):
        theme = self.get_theme(self.get_current_theme())
        scheme = self.get_current_theme_scheme()
        return theme.gui_init(self.gui, scheme)
