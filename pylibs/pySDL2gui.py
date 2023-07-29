"""
Copyright (C) 2020, Michael C Palmer <michaelcpalmer1980@gmail.com>

This file is part of pySDL2gui

pySDLgui is a simple, low level gui module that handles input and draws multiple
rectangular Regions using hardware GPU rendering. Written in python, pySDLgui
uses pySDL2, a low level SDL2 wrapper also written in pure python with no other
dependencies.

This module is designed to produce full screen GUIs for lower powered
GNU/Linux based retro handhelds using game controller style input, but it may
prove useful on other hardware.

The main building block of GUIs built with this module is the Region, which
represents a rectangular area that can display text, lists, and images. Each
Region has numerous attributes that should be defined in theme.json or
defaults.json and can be used to change the look and feel of a GUI without
change the program's code.

CLASSES:
    Image: simple class to represent and draw textures and subtexture
        regions onto a pySDL render context
    ImageManager: class to load and cache images as Image objects in
        texture memory
    Rect: class used to represent and modify Rectangular regions
    Region: draws a rectangular region with a backround, outline, image,
        lists, etc. The main building block of pySDL2gui GUIs
    SoundManager: class used to load and play sound effects and music

FUNCTIONS:
    deep_merge: used internally to merge option dicts
    deep_print: available to display nested dict items or save them to disk
    deep_update: used internally to update an options dict from a second one
    get_color_mod: get the color_mod value of a texture (not working)
    get_text_size: get the size a text string would be if drawn with given font
    range_list: generate a list of numerical values to select from in a option
        menu, similar to a slider widget
    set_color_mod: set the color_mod value of a texture (not working)

pySDL2gui is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.
pytmx is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.
You should have received a copy of the GNU Lesser General Public
License along with pySDL2gui.

If not, see <http://www.gnu.org/licenses/>.
"""

import collections
import functools
import json
import os
import pathlib
import random
import sys

from collections.abc import Mapping
from ctypes import c_int, c_ubyte, byref
from pathlib import Path

import sdl2
import sdl2.ext
import sdl2.sdlmixer


try:
    import sdl2.sdlgfx as sdlgfx
except ImportError:
    sdlgfx = False


class GUIException(Exception):
    '''
    The root of all GUI runtime exceptions.
    '''
    pass


class GUIValueError(GUIException, ValueError):
    pass


class GUIRuntimeError(GUIException, RuntimeError):
    '''
    General runtime exception.
    '''
    pass


class GUIThemeError(GUIRuntimeError):
    '''
    This is an exception that is thrown during Region creation.
    '''
    pass


class GUI:
    def __init__(self, renderer):
        self.renderer = renderer

        self.resources = ResourceManager(self)
        self.fonts = FontManager(self)
        self.text = TextManager(self)
        self.images = ImageManager(self)
        self.sounds = SoundManager(self)
        self.events = EventManager(self)
        self.pallet = {}

    def clean(self):
        '''
        Call after a frame to clean up extra textures/resources no longer needed.
        '''
        self.text.clean()

class ResourceManager:
    def __init__(self, gui):
        self.gui = gui
        self._paths = []

    def add_path(self, path):
        if isinstance(path, pathlib.PurePath):
            pass
        elif isinstance(path, str):
            path = Path(path)
        else:
            raise GUIValueError(f"Invalid {path!r}")

        if not path.is_dir():
            return

        if path not in self._paths:
            self._paths.append(path)
            self.find.cache_clear()

    def remove_path(self, path):
        if isinstance(path, pathlib.PurePath):
            pass
        elif isinstance(path, str):
            path = Path(path)
        else:
            raise GUIValueError(f"Invalid {path!r}")

        if path in self._paths:
            self._paths.remove(path)
            self.find.cache_clear()

    @functools.lru_cache(512)
    def find(self, file_name):
        if isinstance(file_name, pathlib.PurePath):
            pass

        elif isinstance(file_name, str):
            file_name = Path(file_name)

        elif file_name is None:
            return None

        else:
            raise GUIValueError(f"Invalid {file_name!r}")

        if file_name.exists():
            return file_name

        for path in reversed(self._paths):
            full_file_name = path / file_name

            if full_file_name.exists():
                return full_file_name

        return None


class Point:
    __slots__ = ('x', 'y')

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Rect:
    POINTS = (
        'topleft',
        'midtop',
        'topright',
        'midleft',
        'center',
        'midright',
        'bottomleft',
        'midbottom',
        'bottomright',
        )

    __slots__ = ('x', 'y', 'width', 'height')

    def __init__(self, x, y, width, height):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)

    def __repr__(self):
        return f'Rect({self.x}, {self.y}, {self.width}, {self.height})'

    def __mul__(self, v):
        'Scale by v keeping center in position'
        cx, cy = self.center
        r = Rect(self.x, self.y, self.width, self.height)
        r.width = int(r.width * v)
        r.height = int(r.height * v)
        r.center = cx, cy
        return r

    def copy(self):
        'Returns a copy of the called Rect object'
        return Rect(self.x, self.y, self.width, self.height)

    def fit(self, other):
        'Move and resize myself to fill other rect maintaining aspect ratio'
        r = self.fitted(other)
        self.x = r.x
        self.y = r.y
        self.width = r.width
        self.height = r.height

    def fitted(self, other):
        '''
        Return new Rect with other centered and resized to fill self.
        Aspect ration is retained
        '''
        xr = self.width / other.width
        yr = self.height / other.height
        mr = max(xr, yr)

        w = int(self.width / mr)
        h = int(self.height / mr)
        x = int(other.x + (other.width - w) / 2)
        y = int(other.y + (other.height - h) / 2)
        return Rect(x, y, w, h)

    @staticmethod
    def from_corners(x, y, x2, y2):
        '''
        Creat a new rect using bottom and right coordinates instead
        of width and height
        '''
        return Rect(x, y, x2 - x, y2 - y)

    @staticmethod
    def from_sdl(r):
        '''
        Create a new rect based on the position and size of an sdl_rect
        object'''
        return Rect(r.x, r.y, r.w, r.h)

    def inflate(self, x, y=None):
        '''
        Add x to width and y to height of rect, or x to both.
        The rect will remain centered around the same point
        '''
        if y is None:
            y = x

        self.x -= x // 2
        self.y -= y // 2
        self.width += x
        self.height += y

    def inflated(self, x, y=None):
        '''
        Return a copy of self with x added to the width and y to the
        height of rect, or x to both. The rect will remain centered
        around the same point
        '''
        if y is None:
            y = x

        nx = self.x - x // 2
        ny = self.y - y // 2
        nw = self.width + x
        nh = self.height + y
        return Rect(nx, ny, nw, nh)

    def move(self, x, y):
        '''
        Move self by x/y pixels
        '''
        self.x += x
        self.y += y

    def moved(self, x, y):
        '''
        Return copy of self moved by x/y pixels
        '''
        return Rect(
            self.x + x, self.y + y,
            self.width, self.height)

    def sdl(self):
        '''
        Return my value as an sdl_rect
        '''
        return sdl2.SDL_Rect(self.x, self.y, self.width, self.height)

    def tuple(self):
        '''
        Return my value as a 4-tuple
        '''
        return self.x, self.y, self.width, self.height

    def update(self, x, y, w, h):
        '''
        Update myself with new position and size
        '''
        self.x = x
        self.y = y
        self.width = w
        self.height = h

    def clip(self, other):
        '''
        Return copy of self cropped to fit inside other Rect
        '''
        # LEFT
        if self.x >= other.x and self.x < (other.x + other.width):
            x = self.x
        elif other.x >= self.x and other.x < (self.x + self.width):
            x = other.x
        else:
            return Rect(self.x, self.y, 0, 0)

        # RIGHT
        if (self.x + self.width) > other.x and (self.x + self.width) <= (other.x + other.width):
            w = self.x + self.width - x
        elif (other.x + other.width) > self.x and (other.x + other.width) <= (self.x + self.width):
            w = other.x + other.width - x
        else:
            return Rect(self.x, self.y, 0, 0)

        # TOP
        if self.y >= other.y and self.y < (other.y + other.height):
            y = self.y
        elif other.y >= self.y and other.y < (self.y + self.height):
            y = other.y
        else:
            return Rect(self.x, self.y, 0, 0)

        # BOTTOM
        if (self.y + self.height) > other.y and (self.y + self.height) <= (other.y + other.height):
            h = self.y + self.height - y
        elif other.y + other.height > self.y and (other.y + other.height) <= (self.y + self.height):
            h = other.y + other.height - y
        else:
            return Rect(self.x, self.y, 0, 0)

        return Rect(x, y, w, h)

    @property
    def w(self):
        return self.width

    @w.setter
    def w(self, v):
        self.width = v
        self.x -= v // 2

    @property
    def h(self):
        return self.height

    @h.setter
    def h(self, v):
        self.height = v
        self.y -= v // 2

    # EDGES
    @property
    def top(self):
        return self.y

    @top.setter
    def top(self, v):
        self.y = v

    @property
    def bottom(self):
        return self.y + self.height

    @bottom.setter
    def bottom(self, v):
        self.y = v - self.height

    @property
    def left(self):
        return self.x

    @left.setter
    def left(self, v):
        self.x = v

    @property
    def right(self):
        return self.x + self.width

    @right.setter
    def right(self, v):
        self.x = v - self.width

    @property
    def centerx(self):
        return self.x + (self.width // 2)

    @centerx.setter
    def centerx(self, v):
        self.x = v - (self.width // 2)

    @property
    def centery(self):
        return self.y + (self.height // 2)

    @centery.setter
    def centery(self, v):
        self.y = v - (self.height // 2)

    # FIRST ROW
    @property
    def topleft(self):
        return self.x, self.y

    @topleft.setter
    def topleft(self, v):
        x, y = v
        self.x = x
        self.y = y

    @property
    def midtop(self):
        return self.x + (self.width // 2), self.y

    @midtop.setter
    def midtop(self, v):
        x, y = v
        self.x = x - (self.width // 2)
        self.y = y

    @property
    def topright(self):
        return self.x + self.width, self.y

    @topright.setter
    def topright(self, v):
        x, y = v
        self.x = x - self.width
        self.y = y

    # SECOND ROW
    @property
    def midleft(self):
        return self.x, self.y + (self.height // 2)

    @midleft.setter
    def midleft(self, v):
        x, y = v
        self.x = x
        self.y = y - (self.height // 2)

    @property
    def center(self):
        return self.x + (self.width // 2), self.y + (self.height // 2)

    @center.setter
    def center(self, v):
        x, y = v
        self.x = x - (self.width // 2)
        self.y = y - (self.height // 2)

    @property
    def midright(self):
        return self.x + self.width, self.y + (self.height // 2)

    @midright.setter
    def midright(self, v):
        x, y = v
        self.x = x - self.width
        self.y = y - (self.height // 2)

    # THIRD ROW
    @property
    def bottomleft(self):
        return self.x, self.y + self.height

    @bottomleft.setter
    def bottomleft(self, v):
        x, y = v
        self.x = x
        self.y = y - self.height

    @property
    def midbottom(self):
        return self.x + (self.width // 2), self.y + self.height

    @midbottom.setter
    def midbottom(self, v):
        x, y = v
        self.x = x - (self.width // 2)
        self.y = y - self.height

    @property
    def bottomright(self):
        return self.x + self.width, self.y + self.height

    @bottomright.setter
    def botomright(self, v):
        x, y = v
        self.x = x - self.width
        self.y = y - self.height

    @property
    def size(self):
        return self.width, self.height

    @size.setter
    def size(self, v):
        cx, cy = self.center
        self.width, self.height = v
        self.center = cx, cy

    def __getitem__(self, i):
        return (self.x, self.y, self.width, self.height)[i]


class Texture:
    '''
    The Texture class is a base texture class used within pySDL2gui.

    The texture can be a subtexture by using srcrect.
    '''
    def __init__(self, gui, texture, size=None, parent=None, srcrect=None):
        self.gui = gui
        self.renderer = gui.renderer
        self.parent = parent
        self.texture = texture
        self.children = []
        self.__in_delete = False

        if isinstance(size, Rect):
            self.size = size
        elif isinstance(size, (list, tuple)) and len(size) == 4:
            self.size = Rect(*size)
        elif isinstance(size, (sdl2.SDL_Rect)):
            self.size = Rect.from_sdl(size)
        elif size is None:
            self.size = Rect(0, 0, *texture.size)
        else:
            raise GUIValueError('srcrect not a supported type')

        if parent is not None:
            parent.children.append(self)
        # else:
        #     self.gui.textures.append(self)

        if isinstance(srcrect, Rect):
            self.srcrect = srcrect.sdl()
        elif isinstance(srcrect, (list, tuple)) and len(srcrect) == 4:
            self.srcrect = sdl2.SDL_Rect(*srcrect)
        elif isinstance(srcrect, (sdl2.SDL_Rect)):
            self.srcrect = srcrect
        elif srcrect is None:
            self.srcrect = sdl2.SDL_Rect(0, 0, *texture.size)
        else:
            raise GUIValueError('srcrect not a supported type')

    def __del__(self):
        if self.__in_delete:
            return

        self.__in_delete = True

        if self.parent is not None:
            if self in self.parent.children:
                self.parent.children.remove(self)

        # else:
        #     if self in self.gui.textures:
        #         self.gui.textures.remove(self)

        children = self.children
        self.children = []
        for child in self.children:
            del child

        self.texture.destroy()

    def draw(self):
        self.renderer.copy(self.texture, self.srcrect, dstrect=self.size.sdl())

    def draw_at(self, x, y):
        '''
        Draw image with topleft corner at x, y and at the original size.

        x: x position to draw at
        y: y position to draw at
        '''

        self.renderer.copy(self.texture, self.srcrect, dstrect=(x, y))

    def draw_in(self, dest, fit=False, clip=False):
        '''
        Draw image inside given Rect region (may squish or stretch image)

        dest: Rect area to draw the image into
        fit: set true to fit the image into dest without changing its aspect
             ratio
        clip: set true to clip the image into the dest.
        '''

        if fit:
            dest = self.size.fitted(dest)
            self.renderer.copy(self.texture, self.srcrect, dstrect=dest.sdl())

        elif clip:
            destrect = Rect(*dest)

            # Calculate the scaling factors for width and height
            width_scale = self.size.width / self.srcrect.w
            height_scale = self.size.height / self.srcrect.h

            # Calculate the clipped size
            clipped_width = min(self.size.width, destrect.width)
            clipped_height = min(self.size.height, destrect.height)

            # Calculate the source rectangle within the texture
            srcrect_x = self.srcrect.x + (destrect.x - self.size.x) / width_scale
            srcrect_y = self.srcrect.y + (destrect.y - self.size.y) / height_scale
            srcrect_x = self.srcrect.x + max(0, (destrect.x - self.size.x)) / width_scale
            srcrect_y = self.srcrect.y + max(0, (destrect.y - self.size.y)) / height_scale

            srcrect_width = clipped_width / width_scale
            srcrect_height = clipped_height / height_scale

            # Calculate the destination rectangle
            # destrect_x = destrect.x
            # destrect_y = destrect.y
            destrect_x = destrect.x + max(0, (self.size.x - destrect.x))
            destrect_y = destrect.y + max(0, (self.size.y - destrect.y))

            destrect_width = clipped_width
            destrect_height = clipped_height

            self.renderer.copy(self.texture, (srcrect_x, srcrect_y, srcrect_width, srcrect_height),
                               dstrect=(destrect_x, destrect_y, destrect_width, destrect_height))

        else:
            self.renderer.copy(self.texture, self.srcrect, dstrect=dest.sdl())


class Image:
    renderer = None
    '''
    The Image class represents an image with its position, angle,
    and flipped(x/y) status. An image references a Texture and
    has a srcrect(Rect) to define which part of the Texture to
    draw
    '''

    def __init__(self, texture, srcrect=None, renderer=None):
        '''
        Create a new Image from a texture and a source Rect.

        :param texture: a sdl2.ext.Texture object to draw the image from
        :param srcrect: a gui.Rect object defining which part of the
            texture to draw
        :param renderer: a sdl2.ext.Renderer context to draw into
        '''

        renderer = renderer or Image.renderer
        if renderer is None:
            raise GUIRuntimeError('No renderer context provided')

        if Image.renderer is None:
            Image.renderer = renderer  # set default

        self.texture = texture
        if isinstance(srcrect, Rect):
            self.srcrect = srcrect.sdl()
        elif isinstance(srcrect, (list, tuple)) and len(srcrect) == 4:
            self.srcrect = sdl2.SDL_Rect(*srcrect)
        elif isinstance(srcrect, (sdl2.SDL_Rect)):
            self.srcrect = srcrect
        elif srcrect is None:
            self.srcrect = sdl2.SDL_Rect(0, 0, *texture.size)
        else:
            raise GUIValueError('srcrect not a supported type')

        self.x = self.y = 0
        self.flip_x = self.flip_y = 0
        self.angle = 0
        self.center = None

        # default dest rect is fitted to full screen
        self.dstrect = Rect.from_sdl(self.srcrect).fitted(
            Rect(0, 0, *self.renderer.logical_size)).sdl()

    def draw_at(self, x, y, angle=0, flip_x=None, flip_y=None, center=None):
        '''
        Draw image with topleft corner at x, y and at the original size.

        x: x position to draw at
        y: y position to draw at
        angle: optional angle to rotate image
        flip_x: optional flag to flip image horizontally
        flip_y: optional flag to flip image vertically
        center: optional point to rotate the image around if angle provided
        '''
        center = center or self.center
        angle = angle or self.angle

        if flip_x is None and flip_y is None:
            flip = 1 * bool(self.flip_x) | 2 * bool(self.flip_y)
        else:
            flip = 1 * bool(flip_x) | 2 * bool(flip_y)

        self.renderer.copy(
            self.texture,
            self.srcrect,
            dstrect=(x, y),
            angle=angle,
            flip=flip,
            center=center,
            )

    def draw_in(self, dest, angle=0, flip_x=None, flip_y=None,
                center=None, fit=False, color=None):
        '''
        Draw image inside given Rect region (may squish or stretch image)

        dest: Rect area to draw the image into
        angle: optional angle to rotate image
        flip_x: optional flag to flip image horizontally
        flip_y: optional flag to flip image vertically
        center: optional point to rotate the image around if angle provided
        fit: set true to fit the image into dest without changing its aspect
             ratio
        '''
        center = center or self.center
        angle = angle or self.angle

        if fit:
            dest = self.srcrect.fitted(dest)
        if flip_x is None and flip_y is None:
            flip = 1 * bool(self.flip_x) | 2 * bool(self.flip_y)
        else:
            flip = 1 * bool(flip_x) | 2 * bool(flip_y)

        set_color_mod(self.texture, (255, 255, 255))
        self.renderer.copy(self.texture, self.srcrect,
            dstrect=dest, angle=angle, flip=flip, center=center)

    def draw(self):
        ''''Draw image to its current destrect(Rect region), which defaults to
        full screen maintaining aspect ratio'''
        flip = 1 * bool(self.flip_x) | 2 * bool(self.flip_y)
        self.renderer.copy(self.texture, self.srcrect,
            dstrect=self.dstrect, angle=self.angle,
            flip=flip, center=self.center)


class ImageManager():
    '''
    The ImageManager class loads images into Textures and caches them for later use
    '''
    MAX_IMAGES = 100 # maximum number of images to cache
    def __init__(self, gui, max_images=None):
        '''
        Create a new Image manager that can load images into textures

        gui.renderer: sdl2.ext.Renderer context that the image will draw
            into. A renderer must be provided to create new Texture
            objects.
        max: maximum number of images to cach before old ones are
            unloaded. Defaults to ImageManager.MAX_IMAGES(20)
        '''
        if max_images is None:
            self.max_images = self.MAX_IMAGES
        else:
            self.max_images = max_images

        self.gui = gui
        self.renderer = gui.renderer
        self.images = {}
        self.textures = {}
        self.cache = []

    def load(self, filename):
        '''
        Load an image file into a Texture or receive a previously cached
        Texture with that name.

        :param filename: filename(str) to load
        :rvalue gui.Image: reference to the image just loaded or from cache
        '''
        if filename in self.cache:
            i = self.cache.index(filename)
            self.cache.insert(0, self.cache.pop(i))
            return self.images[filename]

        elif filename in self.images:
            return self.images[filename]

        else:
            res_filename = self.gui.resources.find(filename)

            if res_filename is None:
                return None

            surf = sdl2.ext.image.load_img(res_filename)

            texture = sdl2.ext.renderer.Texture(self.renderer, surf)
            self.textures[filename] = texture
            self.images[filename] = Image(texture, renderer=self.renderer)
            self.cache.insert(0, filename)
            self._clean()
            return self.images[filename]

    def load_atlas(self, filename, atlas):
        '''
        Load image filename, create Images from an atlas dict, and create
        a named shortcut for each image in the atlas.

        This does not use the cache.

        :param filename: (str) filename of image to load into a texture
        :param atlas: a dict representing each image in the file
        :rvalue {}: dict of gui.Images in {name: Image} format

        example atlas:
        atlas = {
            'str_name': (x, y, width, height),
            'another_img: (32, 0, 32, 32)
        }
        '''
        images = {}

        res_filename = self.gui.resources.find(filename)

        if res_filename is None:
            return None

        surf = sdl2.ext.image.load_img(res_filename)

        texture = sdl2.ext.renderer.Texture(self.renderer, surf)

        for name, item in atlas.items():
            r = item[:4]
            flip_x, flip_y, angle, *_ = list(item[4:] + [0, 0, 0])

            im = Image(texture, r, renderer=self.renderer)
            im.flip_x = flip_x
            im.flip_y = flip_y
            im.angle = angle

            # Cant happen if using a dict ?
            # if name in images:
            #     raise Exception('Image names must be unique')

            self.images[name] = im
            images[name] = im

        return images

    def load_static(self, filename):
        '''
        Load image with filename.

        This does not get removed from the cache.

        :param filename: (str) filename of image to load into a texture
        :rvalue gui.Image: image loaded from filename

        '''
        res_filename = self.gui.resources.find(filename)

        if res_filename is None:
            return None

        surf = sdl2.ext.image.load_img(res_filename)

        texture = sdl2.ext.renderer.Texture(self.renderer, surf)

        image = Image(texture, renderer=self.renderer)

        self.images[filename] = image

        return image

    def _clean(self):
        'Remove old images when max_images is reached'
        for filename in self.cache[self.max_images:]:
            texture = self.textures.pop(filename)
            image = self.images.pop(filename)
            # image.destroy()
            texture.destroy()
        self.cache = self.cache[:self.max_images]


def get_text_size(font, text=''):
    '''
    Calculate the size of given text using the given font, or if
    no text is provided, then return the font's height instead

    font: an existing sdl2.ext.FontTTF object
    text: optional text string to generate size of
    :rvalue (int, int) or int: (width(int), height(int)) if text provided,
            or height(int) otherwise
    '''
    text_w, text_h = c_int(0), c_int(0)
    f = font.get_ttf_font()
    sdl2.sdlttf.TTF_SizeText(f, text.encode(), byref(text_w), byref(text_h))
    if not text:
        return text_h.value
    return text_w.value, text_h.value


class FontTTF(sdl2.ext.FontTTF):
    """
    Adds quick_render to sdl2.ext.FontTTF
    """
    def line_height(self, size, color=(0, 0, 0)):
        style_key = f"{size},{color}"
        if style_key not in self._styles:
            self.add_style(style_key, size, color)

        return self._get_line_size("", style_key)[1]

    def quick_render(self, text, size, color, width=None, align='left'):
        """Renders a string of text to a new surface.

        Uses render_text to render text to a new surface.

        It adds a style that matches what we need if it doesnt exist,
        """
        style_key = f"{size},{color}"
        if style_key not in self._styles:
            self.add_style(style_key, size, color)

        return self.render_text(text, style_key, width=width, align=align)


class TextManager:
    MAX_TEXTURES = 100

    def __init__(self, gui):
        self.gui = gui
        self.renderer = gui.renderer
        self._textures = {}
        self._texture_list = collections.deque([])
        self.fonts = {}

    def add_font(self, font_name, font_file):
        if font_name not in self.fonts:
            self.fonts[font_name] = FontTTF(str(font_file), 22, (0, 0, 0, 255))

    def clean(self):
        """
        Call at the end of a frame to clean up any of the oldest textures.
        """

        while len(self._texture_list) > self.MAX_TEXTURES:
            key = self._texture_list.pop()
            del self._textures[key]

    def line_height(self, font_name, size):
        if font_name not in self.fonts:
            font_file = self.gui.resources.find(font_name)
            if font_file is None:
                raise GUIValueError(f"Unknown font {font_name}.")

            self.add_font(font_name, font_file)

        font = self.fonts[font_name]

        return font.line_height(size)

    def render_text(self, text, font_name, size, color, *, width=None, align="left"):
        if font_name not in self.fonts:
            font_file = self.gui.resources.find(font_name)
            if font_file is None:
                raise GUIValueError(f"Unknown font {font_name}.")

            self.add_font(font_name, font_file)

        font = self.fonts[font_name]

        key = f"{font.family_name}:{size!r}:{color!r}:{width}:{align}:{text}"
        if key not in self._textures:
            surface = font.quick_render(text, size, color, width=width, align=align)
            texture = self._textures[key] = Texture(
                self.gui,
                sdl2.ext.Texture(self.renderer, surface))
            sdl2.SDL_FreeSurface(surface)
            self._texture_list.appendleft(key)
            return texture

        self._texture_list.remove(key)
        self._texture_list.appendleft(key)
        return self._textures[key]


char_map = ''' ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,?!-:'"_=+&<^>~@/\\|(%)*'''
class FontManager():
    '''
    The FontManager class loads ttf TODO (otf?) fonts, caches them, and draws text
    into a sdl2.ext.Renderer context.
    '''
    def __init__(self, gui):
        '''
        Initialize FontManager for use with pySDL2.ext.Renderer context

        :param gui.renderer: pySDL2.ext.Renderer to draw on
        '''
        self.gui = gui
        self.renderer = gui.renderer
        self.fonts = {}
        self.cmaps = {}
        self.cache = {}

    def __del__(self):
        for t, h in self.fonts.values():
            t.destroy()

    def load(self, filename, size=None):
        '''
        Load a font for later rendering

        :param filename: path to a ttf or otf format font file
        :param size: int point size for font or 'XXpx' for pixel height
        :rvalue tuple: a (filename, size) 2-tuple representing the font in
            future draw() calls
        '''
        if not size:
            filename, cache = filename

        if (filename, size) in self.fonts:
            self.texture, self.height = self.fonts[(filename, size)]
            self.cmap = self.cmaps[(filename, size)]
            self.blank = self.cmap[' ']
            return filename, size

        res_filename = self.gui.resources.find(filename)

        if res_filename is None:
            return None

        font = sdl2.ext.FontTTF(str(res_filename), size, (255, 255, 255))
        self.cmap = {}
        tot = 0

        for c in char_map:
            tot += get_text_size(font, c)[0]

        if tot > 1024: # prevent overly wide textures
            width = 1024
            rows = int(tot // 1024) + 1
        else:
            width = tot
            rows = 1
        self.height = get_text_size(font)

        y = 0
        surface = sdl2.SDL_CreateRGBSurface(sdl2.SDL_SWSURFACE, width, self.height *rows,
                32, 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000)
        tot = x = 0

        for c in char_map:
            rend = font.render_text(c)
            wi, hi = rend.w, rend.h
            if x + wi > 1024: # limit texture width
                x = 0
                y += self.height +1
            sdl2.SDL_BlitSurface(rend, None, surface,
                    sdl2.SDL_Rect(x, y, wi, hi))

            self.cmap[c] = Rect(x, y, wi, self.height)
            tot += wi
            x += wi
        self.blank = self.cmap[' ']
        self.texture = sdl2.ext.renderer.Texture(self.renderer, surface)
        self.fonts[(filename, size)] = self.texture, self.height
        self.cmaps[(filename, size)] = self.cmap
        sdl2.SDL_FreeSurface(surface)
        return filename, size

    def draw(self, text, x, y, color=None, alpha=None,
            align='topleft', clip=None, wrap=None, linespace=0, font=None, outline=None):
        '''
        Draw text string onto pySDL2.ext.Renderer context

        :param text: string to draw
        :param x: x coordinate to draw at
        :param y: y coordinate to draw at
        :param color: (r, g, b) color tuple
        :param alpha: alpha transparency value
        :param align: choose one of: topleft, midtop, topright, midleft, center, midright,
                bottomleft, midbottom, or bottomright
        :param clip: clip text to Rect
        :param wrap: #TODO wrap text over multiple lines, using clip Rect
        :param font: (filename, size) tuple for font, defaults to last_loaded
        :param outline: (color, thickness) or None
        :rvalue rect: actual area drawn into
        '''


        if font in self.fonts: # load texture if argument is in cache
            texture, height = self.fonts[font]
            cmap = self.cmaps[font]
        else:
            texture, height = self.texture, self.height
            cmap = self.cmap

        if wrap and not clip: # must have a clip if wrapping
            w = self.renderer.logical_size[0] - x
            h = self.renderer.logical_size[1] - y
            clip = Rect(x, y, w, h)
        if isinstance(clip, int): # convert clip width into clip rect
            clip = Rect(x, y, clip, self.height)

        if wrap:
            wrapped_text = self._split_lines(text, clip)
            lines = len(wrapped_text)
            if lines > 1:
                if align in ('midleft', 'center', 'midright'):
                    y -= (self.height * lines) // 2 + (linespace * (lines / 2))
                elif align in ('bottomleft', 'midbottom', 'bottomright'):
                    y -= (self.height) * lines + linespace * lines

                for line in wrapped_text:
                    self.draw(line, x, y, color, alpha, align, clip)
                    y += self.height + linespace
                    if y + self.height + linespace > clip.bottom:
                        break
            return clip

        out_rect = Rect(0, 0, self.width(text), self.height)
        dx, dy = getattr(out_rect, align, (0, 0))
        dest = Rect(x - dx, y - dy, 1, self.height)
        out_rect.topleft = dest.topleft

        sdl2.SDL_SetTextureAlphaMod(texture.tx, alpha or 255)
        color = color or (255, 255, 255)
        sdl2.SDL_SetTextureColorMod(texture.tx, *color[:3])

        for c in text:
            src = cmap.get(c, self.blank)
            dest.width = src.width
            if clip and dest.right > clip.right:
                break

            if outline:
                sdl2.SDL_SetTextureColorMod(texture.tx, *outline[0])
                self.renderer.copy(texture, src.sdl(), dest.inflated(outline[1]).sdl())
                sdl2.SDL_SetTextureColorMod(texture.tx, *color[:3])
                self.renderer.copy(texture, src.sdl(), dest.inflated(-outline[1]).sdl())
            else:
                self.renderer.copy(texture, src.sdl(), dest.sdl())
            #self.renderer.draw_rect(dest.tuple(), (255, 255, 255, 255))
            dest.x += src.width
        return out_rect

    def width(self, text, scale=1):
        '''
        Calculate width of given text not including motion or scaling effects
        Uses currently loaded font

        :param text: text string to calculate width of
        :rvalue int: width of string in pixels
        '''
        w = 0
        for c in text:
            w += self.cmap.get(c, self.blank).width * scale
        return w

    def find_max_letters(self, text, max_width, scale=1):
        '''
        return a string of letters that will fit within max_width

        :param text: text string to calculate width of
        :param max_width: maximum width of the word
        :rvalue int: width of string in pixels
        '''
        ## TODO: make it split words on non word characters
        current_width = 0
        current_word = []

        for letter in text:
            width = self.cmap.get(letter, self.blank).width * scale

            if (width + current_width) > max_width:
                return ''.join(current_word)

            current_word.append(letter)
            current_width += width

        return ''.join(current_word)

    def _split_lines(self, text, dest, scale=1):
        '''
        Create a series of lines that will fit in the provided rectangle.

        :param text: a text string
        :param dest: a Rect object to wrap the text into
        :param scale: scalar to multiply font size by, unused so far
        :rvalue []: list of strings that fit within given area
        '''
        final_lines = []

        max_height = dest.height
        width = dest.width
        requested_lines = text.splitlines()

        for requested_line in requested_lines:
            if self.width(requested_line, scale) > width:
                line_words = collections.deque(requested_line.split(' '))
                words = []

                # if any of our words are too long to fit, return.
                while len(line_words) > 0:
                    word = line_words.popleft()

                    if self.width(word, scale) >= width:
                        # TODO force wrap long words
                        new_word = self.find_max_letters(word, width, scale)
                        line_words.appendleft(word[len(new_word):])
                        words.append(new_word)
                        continue

                    words.append(word)

                # Start a new line
                accumulated_line = ""
                for word in words:
                    test_line = accumulated_line + word + " "
                    # Build the line while the words fit.
                    if self.width(test_line, scale) < width:
                        accumulated_line = test_line
                    else:
                        final_lines.append(accumulated_line)
                        accumulated_line = word + " "
                final_lines.append(accumulated_line)
            else:
                final_lines.append(requested_line)

        #line_count = len(final_lines)
        #line_height = self.height()
        #total_height = line_height * line_count
        return final_lines


class EventManager:
    ## TODO: add deadzone code

    BUTTON_MAP = {
        sdl2.SDL_CONTROLLER_BUTTON_A: 'A',
        sdl2.SDL_CONTROLLER_BUTTON_B: 'B',
        sdl2.SDL_CONTROLLER_BUTTON_X: 'X',
        sdl2.SDL_CONTROLLER_BUTTON_Y: 'Y',

        sdl2.SDL_CONTROLLER_BUTTON_LEFTSHOULDER: 'L1',
        sdl2.SDL_CONTROLLER_BUTTON_RIGHTSHOULDER: 'R1',
        # sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT:    'L2',
        # sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT:   'R2',
        sdl2.SDL_CONTROLLER_BUTTON_LEFTSTICK:    'L3',
        sdl2.SDL_CONTROLLER_BUTTON_RIGHTSTICK:   'R3',

        sdl2.SDL_CONTROLLER_BUTTON_DPAD_UP:      'UP',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_DOWN:    'DOWN',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_LEFT:    'LEFT',
        sdl2.SDL_CONTROLLER_BUTTON_DPAD_RIGHT:   'RIGHT',

        sdl2.SDL_CONTROLLER_BUTTON_START:        'START',
        sdl2.SDL_CONTROLLER_BUTTON_GUIDE:        'GUIDE',
        sdl2.SDL_CONTROLLER_BUTTON_BACK:         'BACK',
        }

    KEY_MAP = {
        sdl2.SDLK_UP:       'UP',
        sdl2.SDLK_DOWN:     'DOWN',
        sdl2.SDLK_LEFT:     'LEFT',
        sdl2.SDLK_RIGHT:    'RIGHT',

        sdl2.SDLK_KP_ENTER: 'START',
        sdl2.SDLK_RETURN:   'START',
        sdl2.SDLK_ESCAPE:   'SELECT',

        sdl2.SDLK_SPACE:    'A',
        sdl2.SDLK_z:        'A',
        sdl2.SDLK_x:        'B',
        sdl2.SDLK_a:        'X',
        sdl2.SDLK_s:        'Y',
        sdl2.SDLK_LCTRL:    'L',
        sdl2.SDLK_LALT:     'R',
        }

    AXIS_MAP = {
        sdl2.SDL_CONTROLLER_AXIS_LEFTX: 'LX',
        sdl2.SDL_CONTROLLER_AXIS_LEFTY: 'LY',
        sdl2.SDL_CONTROLLER_AXIS_RIGHTX: 'RX',
        sdl2.SDL_CONTROLLER_AXIS_RIGHTY: 'RY',
        sdl2.SDL_CONTROLLER_AXIS_TRIGGERLEFT: 'L2',
        sdl2.SDL_CONTROLLER_AXIS_TRIGGERRIGHT: 'R2',
        }

    AXIS_TO_BUTTON = {
        'LX': ('L_LEFT', None, 'L_RIGHT'),
        'LY': ('L_UP',   None, 'L_DOWN'),
        'RX': ('R_LEFT', None, 'R_RIGHT'),
        'RY': ('R_UP',   None, 'R_DOWN'),
        'L2': (None,    None, 'L2'),
        'R2': (None,    None, 'R2'),
        }

    REPEAT_MAP = [
        'UP',
        'DOWN',
        'LEFT',
        'RIGHT',

        'L_UP',
        'L_DOWN',
        'L_LEFT',
        'L_RIGHT',

        'R_UP',
        'R_DOWN',
        'R_LEFT',
        'R_RIGHT',
        ]

    # Wait 1.5 seconds
    REPEAT_DELAY = 800
    # Trigger every 1 second
    REPEAT_RATE = 300

    ANALOG_MIN = 2048
    TRIGGER_MIN = 1024

    def __init__(self, gui):
        self.gui = gui
        sdl2.ext.init(controller=True)

        self.running = True
        self.buttons = {
            key: False
            for key in self.BUTTON_MAP.values()}

        self.buttons.update({
            key: False
            for key in self.AXIS_TO_BUTTON.keys()})

        self.axis = {
            key: 0.0
            for key in self.AXIS_MAP.values()}

        self.axis_button = {
            key: None
            for key in self.AXIS_MAP.values()}

        self.repeat = {
            key: None
            for key in self.REPEAT_MAP}

        self.last_buttons = {}
        self.last_buttons.update(self.buttons)

        self.controller = None
        self.trigger_min = self.TRIGGER_MIN
        self.analog_min = self.ANALOG_MIN
        self.ticks = sdl2.SDL_GetTicks()

        ## Change this to handle other controllers.
        for i in range(sdl2.SDL_NumJoysticks()):
            if sdl2.SDL_IsGameController(i) == sdl2.SDL_TRUE:
                self.controller = sdl2.SDL_GameControllerOpen(i)

    def _axis_map(self, axis, limit):
        if abs(axis) < limit:
            return 1

        if axis < 0:
            return 0

        return 2

    def handle_events(self):
        # To handle WAS pressed do: 
        #    self.buttons['UP'] and not self.last_buttons['UP']
        self.last_buttons.update(self.buttons)

        ticks_now = sdl2.SDL_GetTicks64()

        for event in sdl2.ext.get_events():
            if event.type == sdl2.SDL_QUIT:
                self.running = False

            elif event.type == sdl2.SDL_KEYDOWN:
                if event.key.keysym.sym == sdl2.SDLK_ESCAPE:
                    self.running = False
                    break

                key = self.KEY_MAP.get(event.key.keysym.sym, None)
                if key is not None:
                    # print(f'PRESSED {key}')
                    self.buttons[key] = True

                    if key in self.repeat:
                        self.repeat[key] = ticks_now + self.REPEAT_DELAY

            elif event.type == sdl2.SDL_KEYUP:
                key = self.KEY_MAP.get(event.key.keysym.sym, None)
                if key is not None:
                    # print(f'RELEASED {key}')
                    self.buttons[key] = False

                    if key in self.repeat:
                        self.repeat[key] = None

            elif event.type == sdl2.SDL_CONTROLLERBUTTONDOWN:
                key = self.BUTTON_MAP.get(event.cbutton.button, None)
                if key is not None:
                    # print(f'PRESSED {key}')
                    self.buttons[key] = True

                    if key in self.repeat:
                        self.repeat[key] = ticks_now + self.REPEAT_DELAY

            elif event.type == sdl2.SDL_CONTROLLERBUTTONUP:
                key = self.BUTTON_MAP.get(event.cbutton.button, None)
                if key is not None:
                    # print(f'RELEASED {key}')
                    self.buttons[key] = False

                    if key in self.repeat:
                        self.repeat[key] = None

            elif event.type == sdl2.SDL_CONTROLLERAXISMOTION:
                if event.caxis.axis in self.AXIS_MAP:
                    key = self.AXIS_MAP[event.caxis.axis]
                    # print(f'MOVED {key} {event.caxis.value}')
                    self.axis[key] = event.caxis.value

                    last_axis_key = self.axis_button[key]
                    axis_key = self.AXIS_TO_BUTTON[key][self._axis_map(event.caxis.value, self.analog_min)]

                    if axis_key is not None:
                        if last_axis_key is None:
                            # print(f"PRESSED {axis_key}")
                            self.buttons[axis_key] = True

                            if axis_key in self.repeat:
                                self.repeat[axis_key] = ticks_now + self.REPEAT_DELAY
                        elif last_axis_key != axis_key:
                            # print(f"RELEASED {last_axis_key}")
                            self.buttons[last_axis_key] = True
                            if last_axis_key in self.repeat:
                                self.repeat[last_axis_key] = None

                    elif axis_key is None:
                        if last_axis_key is not None:
                            # print(f"RELEASED {last_axis_key}")
                            self.buttons[last_axis_key] = True
                            if last_axis_key in self.repeat:
                                self.repeat[last_axis_key] = None

                    self.axis_button[key] = axis_key

        for key in self.repeat.keys():
            next_repeat = self.repeat[key]
            if next_repeat is not None and next_repeat <= ticks_now:
                # Trigger was_pressed state
                self.last_buttons[key] = False
                # print(f'REPEAT {key} {ticks_now - next_repeat}')
                self.repeat[key] = ticks_now + self.REPEAT_RATE


    def was_pressed(self, button):
        return self.buttons.get(button, False) and not self.last_buttons.get(button, False)

    def was_released(self, button):
        return not self.buttons.get(button, False) and self.last_buttons.get(button, False)


class SoundManager():
    '''
    The SoundManager class loads and plays sound files.
    '''
    def __init__(self, gui):
        self.gui = gui
        self.sounds = {}
        self.song = None
        self.is_init = False
        self.init_failed = False

        self.init()

    def init(self):
        '''
        Initialize the sound system
        '''
        if not self.is_init and not self.init_failed:
            if sdl2.SDL_Init(sdl2.SDL_INIT_AUDIO) != 0:
                print("Cannot initialize audio system: {}".format(SDL_GetError()))
                self.init_failed = True
                return

            if sdl2.sdlmixer.Mix_OpenAudio(44100, sdl2.sdlmixer.MIX_DEFAULT_FORMAT, 2, 1024):
                print(f'Cannot open mixed audio: {sdlmixer.Mix_GetError()}')
                self.init_failed = True
                return

            self.is_init = True

    def load(self, filename, name=None, volume=1):
        '''
        Load a given sound file into the Sound Manager

        :param filename: filename for sound file to load
        :param name: alternate name to use to play the sound instead of its filename
        :param volume: default volume level to play the sound at, from 0.0 to 1.0
        '''
        if not self.is_init:
            return None

        res_filename = self.gui.resources.find(filename)

        if res_filename is None:
            return None

        sample = sdl2.sdlmixer.Mix_LoadWAV(
                sdl2.ext.compat.byteify(str(res_filename), 'utf-8'))

        if name is None:
            name = res_filename.name

        if sample is None:
            return None
            # raise GUIRuntimeError(f'Cannot open audio file: {sdl2.Mix_GetError()}')

        sdl2.sdlmixer.Mix_VolumeChunk(sample, int(128 * volume))
        self.sounds[name] = sample
        return name

    def music(self, filename, loops=-1, volume=1):
        '''
        Loads a music file and plays immediately plays it

        :param filename: path to music file to load and play
        :param loops: number of times to play song, or loop forever by default
        :param volume: volume level to play music, between 0.0 and 1.0
        '''
        if not self.is_init:
            return None

        res_filename = self.gui.resources.find(filename)

        if res_filename is None:
            return None

        sdl2.sdlmixer.Mix_VolumeMusic(int(volume * 128))
        music = sdl2.sdlmixer.Mix_LoadMUS(
                    sdl2.ext.compat.byteify(str(res_filename), 'utf-8'))

        if music is None:
            return None
            # raise GUIRuntimeError(f'Cannot open audio file: {sdl2.Mix_GetError()}')

        sdl2.sdlmixer.Mix_PlayMusic(music, loops)
        if self.song:
            sdl2.sdlmixer.Mix_FreeMusic(self.song)

        self.song = music
        return self.song

    @property
    def volume(self):
        if not self.is_init:
            return

        return sdl2.sdlmixer.Mix_MasterVolume(-1) / 128

    @volume.setter
    def volume(self, v):
        'Set master volume level between 0.0 and 1.0'
        if not self.is_init:
            return

        sdl2.sdlmixer.Mix_MasterVolume(int(v * 128))

    def play(self, name, volume=1):
        '''
        Play a loaded sound with the given name

        :param name: name of sound, either the filename(without extension) or
            an alternate name provided to the load() method
        :param volume: volume to play sound at, from 0.0 to 1.
        '''
        if not self.is_init:
            return

        sample = self.sounds.get(name)
        if sample:
            channel = sdl2.sdlmixer.Mix_PlayChannel(-1, sample, 0)
            if channel == -1:
                raise GUIRuntimeError(
                    f'Cannot play sample {name}: {sdl2.sdlmixer.Mix_GetError()}')
            sdl2.sdlmixer.Mix_Volume(channel, int(volume * 128))

    def __del__(self):
        if not self.is_init:
            return

        for s in self.sounds.values():
            sdl2.sdlmixer.Mix_FreeChunk(s)

        if self.song:
            sdl2.sdlmixer.Mix_FreeMusic(self.song)

        sdl2.sdlmixer.Mix_CloseAudio()
        sdl2.SDL_Quit(sdl2.SDL_INIT_AUDIO)
        print('SoundManager closed')


'''
TODO
    Fix image/text confusion in bars
    Text horiz scrolling
    Text animation (rotation, scaling, color changing)
    Tiled image rendering
    Deque the cache list
    Alpha colors for fill and outline
    Alpha for images
'''

class Region:
    '''
    The Region class is the primary building block of pySDL2gui interfaces.
    It represents a rectangular region, defines its attributes, handles
    user interaction, and draws itself onto the screen. Each region may
    have a fill color, outline, and image, as well as scrolling text, an
    interactive list, or a horizontal toolbar. These attributes are loaded
    from a json file and then passed to the class as a standard dict.

    FILL AND OUTLINE
    area: 4-tuple representing a rectangular area for the region, defined in (left, top, right, bottom) format, not in (x, y, width, height) format like a normal Rect object. It can be in pixels (10, 10, 200, 400), or in screen percent (0.1, 0.1, 0.5, 0.9).
    fill: 3-tuple rgb fill color
    outline: 3-tuple rgb outline color
    thickness: int outline thickness,
    roundness: int radius to draw the region as a rounded rectangle
    border: int border around all sides of text, or use borderx and bordery instead
    borderx: int left/right border around text
    bordery: int top/bottom border around text

    IMAGE RENDERING
    image: filename for an image to draw in the region
    imagesize: an 2-tuple of ints (width, height) to draw image at a specific size
    imagemode: draw mode for the image can be 'fit', 'stretch', or 'repeat'
    imagealign: string options to align the image include: topleft, topright, midtop,
    midleft, center, midright, bottomleft, midbottom, and bottomright
    patch: a 4-tuple of ints (left, top, right, bottom) that defines the size of
    non-stretched portions of the image when drawing as a 9-patch, or None to
    render it normally
    pattern: (TODO) if True the image attribute is loaded as a base64 string value
    pimage: filename or image to use for patch rendering if different than image

    TEXT RENDERING
    align: string options to align the text include: topleft, topright, midtop,
    midleft, center, midright, bottomleft, midbottom, and bottomright
    autoscroll: number of rendered frames (update calls) between each line of auto
    scrolling for the text, or 0 to disable auto-scrolling (default)
    font: filename for the font to draw with
    fontsize: int size of font to draw with
    fontcolor: 3-tuple rgb color used to draw text
    fontoutline: 2-tuple (RGB 3-tuple color, int outline thickness)
    linespace: int extra space between each line of wrapped text
    scrollable: bool that allows up/down events to scroll wrapped text when set to True
    text: text string to draw, which may include newlines
    wrap: set True to allow multiline text wrapping

    LIST RENDERING
    list: a list of items to be displayed and selected from
    itemsize: the height that each list item is drawn with
    select: a 3-tuple rgb color for the selected item, or a Region for rendering it
    selectable: a list including the index for each item of the list that may be selected by the user
    selected: the currently selected list item, which will be drawn using the color or Region referenced by the select attribute

    BARS (toolbars)
    bar: a list that may include strings, Image objects, and image filenames. They will be drawn as a horizontal bar. A single null value will split the bar into 2 sides, the first one left aligned and the second one right aligned
    barspace: additional space between each bar item beyond its natural size
    barwidth: the minimum width for each bar item
    selectablex: TODO a list indluding the index for each item in the bar that may be selected by the user
    selectedx: the currently selected list item, or -1 if nothing is selected.
    The selected item will be drawn in the color of or with the Region referenced by the select attribute.
    '''
    SCROLL_START_PAUSE, SCROLL_FORWADS, SCROLL_BACKWARDS, SCROLL_END_PAUSE = (
        'SCROLL_START_PAUSE', 'SCROLL_FORWADS', 'SCROLL_BACKWARDS', 'SCROLL_END_PAUSE')

    SCROLL_FSM = {
        None: {
            SCROLL_START_PAUSE: SCROLL_START_PAUSE,
            },
        'slide': {
            SCROLL_START_PAUSE: SCROLL_FORWADS,
            SCROLL_FORWADS: SCROLL_END_PAUSE,
            SCROLL_END_PAUSE: SCROLL_FORWADS,
            },
        'marquee': {
            SCROLL_START_PAUSE: SCROLL_FORWADS,
            SCROLL_FORWADS: SCROLL_END_PAUSE,
            SCROLL_END_PAUSE: SCROLL_BACKWARDS,
            SCROLL_BACKWARDS: SCROLL_START_PAUSE,
            },
        }

    DATA = {}

    def __init__(self, data, gui):
        'Create a new Region for future drawing.'
        self._dict = deep_merge(self.DATA, data)

        self.gui = gui
        self.renderer = gui.renderer
        self.images = gui.images
        self.fonts = gui.fonts
        self.texts = gui.text
        self.pallet = gui.pallet

        self.z_index = self._verify_int('z-index', default=None, optional=True)
        self.visible = self._verify_bool('visible', default=True, optional=True)

        self.area = self._verify_rect('area')
        self.fill = self._verify_color('fill', optional=True)
        self.outline = self._verify_color('outline', optional=True)
        self.thickness = self._verify_int('thickness', 0)
        self.roundness = self._verify_int('roundness', 0)
        self.borderx = self._verify_int('border', 0)
        self.bordery = self._verify_int('border-y', self.borderx) or 0
        self.borderx = self._verify_int('border-x', self.borderx)

        self.image = self.images.load(self._dict.get('image'))
        self.imagesize = self._verify_ints('image-size', 2, None, optional=True)
        self.imagemode = self._verify_option('image-mode',
                ('fit', 'stretch', 'repeat', None), 'fit')
        self.imagealign = self._verify_option('image-align', Rect.POINTS, None)
        self.patch = self._verify_ints('patch', 4, optional=True)
        self.pimage = self.images.load(self._dict.get('pimage'))
        if self.patch and not self.pimage:
            self.pimage = self.image
            self.image = None

        self.pattern = False

        # TODO figure out how to use default/system fonts
        self.font = self._verify_file('font', optional=True)
        self.fontsize = self._verify_int('font-size', 30)
        self.fontcolor = self._verify_color('font-color', (255, 255, 255))
        self.fontoutline = self._verify_outline('font-outline', None, optional=True)
        self._text = self._verify_text('text', optional=True)
        self.textclip = self._verify_bool('text-clip', True, optional=True)
        self.textwrap = self._verify_bool('text-wrap', False, optional=True)
        self.linespace = self._verify_int('linespace', 0, optional=True)
        self.align = self._verify_option('align', Rect.POINTS, 'topleft')

        self.list = self._verify_list('list', optional=True)
        self.selectable = None
        self.imagelist = 0 ## TODO
        self.ilistalign = 0 ## TODO
        self.itemsize = self._verify_int('item-size', None, optional=True)
        self.select = self._verify_color('select-color', optional=True)

        self.click_sound = self._verify_text('click_sound', optional=True)
        self.cancel_sound = self._verify_text('cancel_sound', optional=True)

        self.scrollable = self._verify_bool('scrollable', False, True)

        self.autoscroll = self._verify_option('autoscroll', (None, 'slide', 'marquee'), None)
        self.scroll_speed = self._verify_int('scroll-speed', 30, True)
        self.scroll_direction = self._verify_option(
            'scroll-direction',
            ('vertical', 'horizontal'),
            self.textwrap and 'vertical' or 'horizontal')

        self.scroll_delay_start = self._verify_int('scroll-delay-start', 1000, True)
        self.scroll_delay_end = self._verify_int('scroll-delay-end', 1000, True)
        self.scroll_state = self.SCROLL_START_PAUSE

        self.barspace = self._verify_int('barspace', 4)
        self.barwidth = self._verify_int('barwidth', 0, optional=True)
        self._bar = self._verify_bar('bar', optional=True)

        if self._text and self.list:
            raise GUIThemeError('Cannot define text and a list')

        self.scroll_pos = 0
        self.scroll_max = 10
        self.scroll_last_update = sdl2.SDL_GetTicks64()

        self.selected = 0
        self.selectedx = -1

        self.info = self._verify_list('info', optional=True)
        self.option = self._verify_list('option', optional=True)

        if self._text is not None:
            # Trigger text setting code
            self.text = self._text

    def draw(self, area=None, text=None, image=None):
        '''
        Draw all features of this Region

        area: override Region's area, used internally
        text: override Region's text and list, used internally
        image: override Region's image, used internally
        '''

        area = area or self.area.copy()
        image = image or self.image
        # screen.blendmode = sdl2.SDL_BLENDMODE_BLEND

        # FILL AND OUTLINE
        if self.patch:
            self._draw_patch(area, self.pimage)
            area = Rect.from_corners(
                area.x + self.patch[0], area.y + self.patch[1],
                area.right - self.patch[2], area.bottom - self.patch[3])

        elif self.fill and self.outline:
            if self.roundness and sdlgfx:
                sdlgfx.roundedBoxRGBA(self.renderer.sdlrenderer,
                    area.x, area.y, area.right, area.bottom,
                    self.roundness, *self.outline)
            area.inflate(-self.thickness)
            if self.roundness and sdlgfx:
                sdlgfx.roundedBoxRGBA(self.renderer.sdlrenderer,
                    area.x, area.y, area.right, area.bottom,
                    self.roundness, *self.fill)

            else:
                self.renderer.fill(area.sdl(), self.outline)
                area.inflate(-self.thickness)
                self.renderer.fill(area.sdl(), self.fill)

        elif self.fill:
            if self.roundness and sdlgfx:
                sdlgfx.roundedBoxRGBA(self.renderer.sdlrenderer,
                    area.x, area.y, area.right, area.bottom,
                    self.roundness, *self.fill)
            else:
                # print(self.fill)
                self.renderer.fill(area.sdl(), self.fill)

        elif self.outline:
            r = area.sdl()
            for _ in range(self.thickness - 1):
                if self.roundness and sdlgfx:
                    sdlgfx.roundedRectangleRGBA(self.renderer.sdlrenderer,
                        r.x, r.y, r.x + r.w, r.y + r.h,
                        self.roundness, *self.outline)
                else:
                    self.renderer.draw_rect(r, self.outline)
                r.x += 1; r.w -= 2
                r.y += 1; r.h -= 2
            area.size = area.w - self.thickness, area.h - self.thickness

        # RENDER IMAGE
        if self.image and not self.patch:
            image = self.image #s.load(self.image)
            dest = Rect.from_sdl(image.srcrect)
            if self.imagesize:
                dest.size = self.imagesize

            if self.imagemode == 'fit':
                dest.fit(area)
                if self.imagealign:
                    w = getattr(area, self.imagealign)
                    setattr(dest, self.imagealign, w)
                image.draw_in(dest.tuple())
            elif self.imagemode == 'stretch':
                image.draw_in(area.tuple())
            elif self.imagemode == 'repeat':
                pass # TODO

            else:
                dest.topleft = area.topleft
                image.draw_in(dest.clip(area).tuple())

        text_area = area.inflated(-self.borderx * 2, -self.bordery * 2)

        if self.font and self.fontsize:
            self.fonts.load(self.font, self.fontsize)
        else:
            return

        # RENDER BAR (toolbarish)
        align_to_textalign = {
            'center': 'center',
            'topleft': 'left',
            'midleft': 'left',
            'bottomleft': 'left',
            'topcenter': 'center',
            'topcenter': 'center',
            'bottomcenter': 'center',
            'topright': 'right',
            'midright': 'right',
            'bottomright': 'right',
            }

        if self._bar:
            self._draw_bar(text_area, self._bar)

        # RENDER TEXT
        elif text:
            x, y = getattr(text_area, self.align, text_area.topleft)
            self.fonts.draw(text, x, y, self.fontcolor, 255, self.align,
                    text_area, outline=self.fontoutline).height + self.linespace

        elif self._text:
            if text_area.width > 0 and text_area.height > 0:
                if self.textwrap:
                    texture = self.texts.render_text(
                        self._text,
                        self.font, self.fontsize, self.fontcolor,
                        width=text_area.width, align=align_to_textalign[self.align])
                else:
                    texture = self.texts.render_text(
                        self._text,
                        self.font, self.fontsize, self.fontcolor, align=align_to_textalign[self.align])

                # x, y = getattr(text_area, self.align, text_area.topleft)
                x, y, self.scroll_max = autoscroll_text(
                    texture.size,
                    text_area,
                    self.align,
                    self.scroll_pos,
                    self.scroll_direction == 'vertical')

                setattr(texture.size, self.align, (x, y))

                if self.autoscroll:
                    if self.scroll_state == self.SCROLL_FORWADS:
                        if self.scroll_pos >= self.scroll_max:
                            self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                            self.scroll_last_update = sdl2.SDL_GetTicks64()
                    elif self.scroll_state == self.SCROLL_BACKWARDS:
                        if self.scroll_pos <= 0:
                            self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                            self.scroll_last_update = sdl2.SDL_GetTicks64()

                if self.textclip:
                    texture.draw_in(text_area, clip=True)
                else:
                    texture.draw_in(text_area, fit=True)

            # pos = self.scroll_pos % len(self._text)

            # x, y = getattr(text_area, self.align, text_area.topleft)
            # #y += self.linespace // 2
            # for l in self._text[pos:]:
            #     if y + self.fonts.height > text_area.bottom:
            #         break

            #     y += self.fonts.draw(l, x, y, self.fontcolor, 255, self.align,
            #             text_area, outline=self.fontoutline).height + self.linespace

        # RENDER LIST
        elif self.list:
            if self.itemsize is not None:
                itemsize = self.itemsize  # + self.bordery
            else:
                itemsize = self.texts.line_height(self.font, self.fontsize)  # + self.bordery

            self.page_size = area.height // itemsize
            self.selected = self.selected % len(self.list)

            # self.fonts.load(self.font, self.fontsize)
            if len(self.list) > self.page_size:
                start = max(0, min(self.selected - self.page_size // 3,
                        len(self.list) -self.page_size))
            else:
                start = 0

            irect = text_area.copy()
            irect.height = itemsize
            i = start
            for t in self.list[start: start + self.page_size]:
                if isinstance(t, (list, tuple)):
                    bar = self._verify_bar(None, t, irect)

                    if i == self.selected and self.selectedx >= 0:
                        x = self.selectedx
                    else:
                        x = None

                    self._draw_bar(irect, bar, x)

                elif self.selected == i:
                    ## Not sure what this is used for.
                    #
                    # if isinstance(self.select, Region):
                    #     r = irect.inflated(self.borderx * 2, self.bordery * 2)
                    #     self.select.draw(irect, t)
                    #     self.fonts.load(self.font, self.fontsize)
                    # else:
                    texture = self.texts.render_text(
                        t,
                        self.font, self.fontsize, self.select, align=align_to_textalign[self.align])

                    x, y, self.scroll_max = autoscroll_text(
                        texture.size,
                        irect,
                        self.align,
                        self.scroll_pos,
                        self.scroll_direction == 'vertical')

                    setattr(texture.size, self.align, (x, y))

                    if self.autoscroll:
                        if self.scroll_state == self.SCROLL_FORWADS:
                            if self.scroll_pos >= self.scroll_max:
                                self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                                self.scroll_last_update = sdl2.SDL_GetTicks64()
                        elif self.scroll_state == self.SCROLL_BACKWARDS:
                            if self.scroll_pos <= 0:
                                self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                                self.scroll_last_update = sdl2.SDL_GetTicks64()

                    if self.textclip:
                        texture.draw_in(irect, clip=True)
                    else:
                        texture.draw_in(irect, fit=True)

                else:
                    texture = self.texts.render_text(
                        t,
                        self.font, self.fontsize, self.fontcolor, align=align_to_textalign[self.align])

                    x, y = getattr(irect, self.align, irect.topleft)
                    setattr(texture.size, self.align, (x, y))

                    if self.textclip:
                        texture.draw_in(irect, clip=True)
                    else:
                        texture.draw_in(irect, fit=True)

                irect.y += itemsize
                i += 1

    def update(self):
        '''
        Update current region based on given input and autoscrolling parameters

        inp: reference to an gui.InputHandler to receive input
        RETURNS: True if screen should redraw, otherwise False
        '''
        updated = False
        current_time = sdl2.SDL_GetTicks64()

        if self.autoscroll:
            scroll_change = False
            scroll_dt = (current_time - self.scroll_last_update)
            # print(f"{self.autoscroll} -> {self.scroll_state} -> {scroll_dt} -> {self.scroll_pos} / {self.scroll_max}")
            if self.scroll_state == self.SCROLL_FORWADS:
                if scroll_dt >= self.scroll_speed:
                    self.scroll_pos += 1
                    self.scroll_last_update = current_time

            elif self.scroll_state == self.SCROLL_BACKWARDS:
                if scroll_dt >= self.scroll_speed:
                    self.scroll_pos -= 1
                    self.scroll_last_update = current_time

            elif self.scroll_state == self.SCROLL_START_PAUSE:
                if scroll_dt >= self.scroll_delay_start:
                    self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                    self.scroll_last_update = current_time
                    scroll_change = True

            elif self.scroll_state == self.SCROLL_END_PAUSE:
                if scroll_dt >= self.scroll_delay_end:
                    self.scroll_state = self.SCROLL_FSM[self.autoscroll][self.scroll_state]
                    self.scroll_last_update = current_time
                    scroll_change = True

            if scroll_change:
                if self.scroll_state == self.SCROLL_FORWADS:
                    self.scroll_pos = 0
                if self.scroll_state == self.SCROLL_BACKWARDS:
                    self.scroll_pos = self.scroll_max

        if self.text and self.scrollable:
            if self.gui.events.was_pressed('UP'):
                updated = True
                self.scroll_pos -= 1

            elif self.gui.events.was_pressed('DOWN'):
                self.scroll_pos += 1
                updated = True
            self.scroll_pos = min(max(0, self.scroll_pos), len(self.text) - 1)

        elif self.list:
            l = len(self.list)
            selectable = self.selectable or range(l)
            selected = self.selected

            if self.gui.events.was_pressed('UP'):
                selected = (selected - 1) % l
                while (selected) % l not in selectable:
                    selected = (selected - 1) % l
                self.gui.sounds.play(self.click_sound)
                updated = True

            elif self.gui.events.was_pressed('DOWN'):
                selected = (selected + 1) % l
                while (selected) % l not in selectable:
                    selected = (selected + 1) % l

                self.gui.sounds.play(self.click_sound)
                updated = True

            if updated:
                self.selected = selected
                if self.autoscroll:
                    self.scroll_state = self.SCROLL_START_PAUSE
                    self.scroll_last_update = current_time

        return updated

    @property
    def text(self):
        return self._text
    @text.setter
    def text(self, val):
        'Process text for proper wrapping when user changes it.'
        if self.textwrap:
            self._text = val
            self.scroll_state = self.SCROLL_START_PAUSE
            self.scroll_pos = 0
            self.scroll_last_update = sdl2.SDL_GetTicks64()
        else:
            self._text = val
        #print(f'text set to:\n{self._text}')

    @property
    def bar(self):
        return self._bar
    @bar.setter
    def bar(self, val):
        self._bar = self._verify_bar(None, val)

    def _verify_bar(self, name, default=None, area=None, optional=True):
        '''
        Process bar list for future display and selection. Used internally.

        name: key for Region dict to read bar list from
        default: default value is None
        area: override Region's area, used internally
        '''
        vals = self._dict.get(name, default)
        if vals is None and optional: return None

        if not isinstance(vals, (list, tuple)):
            raise GUIThemeError("bar is not a list")
        vals = [None if v == '' else v for v in vals]
        if vals.count('None') > 1:
            raise GUIThemeError('bar has more than one null value separator')

        if not area:
            area = self.area
            if self.patch:
                area = Rect.from_corners(
                    area.x + self.patch[0], area.y + self.patch[1],
                    area.right - self.patch[2], area.bottom - self.patch[3])
            else:
                area = area.inflated(-self.borderx * 2, -self.bordery * 2)

        self.fonts.load(self.font, self.fontsize)
        x = area.x
        y = area.centery

        items = left = []; right = []
        for i, v in enumerate(vals):
            im = v if isinstance(v, Image) else self.images.load(v)
            if im:
                dest = Rect.from_sdl(im.srcrect).fitted(area)
                dest.x = x
                dest.width = max(dest.w, self.barwidth)
                x = dest.right + self.barspace
                items.append((dest, im))
            elif isinstance(v, str):
                w = self.fonts.width(v)
                dest = Rect(x, y, max(w, self.barwidth), self.fonts.height)
                dest.centery = area.centery
                x = dest.right + self.barspace
                items.append((dest, v))
            elif v is None:
                items = right
            else:
                raise GUIThemeError(f'bar item {i}({v}) not valid type')
        x = area.right
        for dest, item in right:
            dest.right = x
            x -= dest.width + self.barspace

        return left + right

    def _draw_bar(self, area, bar, selected=None):
        '''
        Draw bar in given area. Used internally
        '''
        #mode, self.renderer.blendmode = self.renderer.blendmode, sdl2.SDL_BLENDMODE_BLEND
        #self.fonts.load(self.font, self.fontsize)

        for i, (dest, item) in enumerate(bar):
            if i == selected:
                if isinstance(self.select, Region):
                    if isinstance(item, Image):
                        image = item; text = None
                    else:
                        color = None
                        text = item; image = None
                    r = dest.inflated(self.borderx * 2, self.bordery * 2)
                    self.select.draw(dest, text, image)
                    self.fonts.load(self.font, self.fontsize)

                else:
                    #self.renderer.fill(dest.tuple(), [0, 0, 255, 100])

                    if isinstance(item, Image):
                        item.draw_in(Rect.from_sdl(item.srcrect).fitted(dest).tuple())
                    else:
                        x, y = dest.center
                        self.fonts.draw(item, x, y,
                                self.select, 255, 'center', area,
                                outline=self.fontoutline)

            elif isinstance(item, Image):
                item.draw_in(Rect.from_sdl(item.srcrect).fitted(dest).tuple())
            else:
                x, y = dest.center
                self.fonts.draw(item, x, y, self.fontcolor, 255, 'center',
                        area, outline=self.fontoutline)
        #self.renderer.blendmode = mode

    def _verify_outline(self, name, default, optional):
        # print(name, default)
        val = self._dict.get(name, default)
        if val is None and optional: return None

        # print(val)
        if isinstance(val, (list, tuple)) and len(val) == 2:
            color = self._verify_color(None, val[0])
            thickness = self._verify_int(None, val[1])
            if color and thickness:
                return color, thickness

        else:
            raise GUIThemeError(f'fontoutline is not a 2-tuple')

        if not isinstance(val, int):
            raise GUIThemeError(f'{name} is not an int')
        #print(f'{name}: {val}')
        return None

    def _draw_patch(self, area, image):
        '''
        Draw 9-patch image in given area
        '''
        target = area.copy()
        bounds = Rect.from_sdl(image.srcrect)
        texture = image.texture

        self.renderer.copy(texture,  # TOP
                srcrect=(bounds.left, bounds.top, self.patch[0], self.patch[1]),
                dstrect=(target.left, target.top, self.patch[0], self.patch[1]))
        self.renderer.copy(texture,  # LEFT
            srcrect=(bounds.left, bounds.top + self.patch[1], self.patch[0],
                    bounds.height - self.patch[1] - self.patch[3]),
            dstrect=(target.left, target.top + self.patch[1], self.patch[0],
                    target.height - self.patch[1] - self.patch[3]))
        self.renderer.copy(texture,  # BOTTOM-LEFT
            srcrect=(bounds.left, bounds.bottom - self.patch[3],
                    self.patch[0], self.patch[3]),
            dstrect=(target.left, target.bottom - self.patch[3],
                    self.patch[0], self.patch[3]))

        self.renderer.copy(texture, # TOP -RIGHT
            srcrect=(bounds.right - self.patch[2], bounds.top,
                    self.patch[2], self.patch[1]),
            dstrect=(target.right - self.patch[2], target.top,
                    self.patch[2], self.patch[1]))
        self.renderer.copy(texture, # RIGHT
            srcrect=(bounds.right - self.patch[2], bounds.top + self.patch[1],
                    self.patch[2], bounds.height - self.patch[3] - self.patch[1]),
            dstrect=(target.right - self.patch[2], target.top + self.patch[1],
                    self.patch[2], target.height - self.patch[3] - self.patch[1]))
        self.renderer.copy(texture, # BOTTOM-RIGHT
            srcrect=(bounds.right - self.patch[2], bounds.bottom - self.patch[3],
                    self.patch[2], self.patch[3]),
            dstrect=(target.right - self.patch[2], target.bottom - self.patch[3],
                    self.patch[2], self.patch[3]))

        self.renderer.copy(texture, # TOP
            srcrect=(bounds.left + self.patch[0], bounds.top,
                    bounds.width - self.patch[0] - self.patch[2], self.patch[1]),
            dstrect=(target.left + self.patch[0], target.top,
                    target.width - self.patch[0] - self.patch[2], self.patch[1]))
        self.renderer.copy(texture, # CENTER
            srcrect=(bounds.left + self.patch[0], bounds.top + self.patch[1],
                    bounds.width - self.patch[2] - self.patch[0],
                    bounds.height - self.patch[1] - self.patch[3]),
            dstrect=(target.left + self.patch[0], target.top + self.patch[1],
                    target.width - self.patch[2] - self.patch[0],
                    target.height - self.patch[1] - self.patch[3]))
        self.renderer.copy(texture, # BOTTOM
            srcrect=(bounds.left + self.patch[0], bounds.bottom - self.patch[3],
                    bounds.width - self.patch[0] - self.patch[2], self.patch[3]),
            dstrect=(target.left + self.patch[0], target.bottom - self.patch[3],
                    target.width - self.patch[0] - self.patch[2], self.patch[3]))


    def _verify_rect(self, name, default=None, optional=False):
        'Verify that value of self._dict[name] is a usable Rect'

        val = self._dict.get(name, default)
        if val is None and optional: return None

        try:
            if len(val) != 4:
                raise GUIThemeError('Region area incorrect length')

        except TypeError:
            print('Region area not iterable')
            raise

        for i, p in enumerate(val):
            if not isinstance(p, (int, float)):
                raise GUIThemeError(f'point {i}{p} is not a number')

            if type(p)==float and 0 < p <= 1:
                val[i] = p * self.renderer.logical_size[i % 2]

        val = Rect.from_corners(*val)
        #print(f'{name}: {val}')
        return val

    def _verify_color(self, name, default=None, optional=False):
        'verify that value of self._dict[name] is valid RGB 3-tuple color'
        ## Added support for a colour pallet.

        val = self._dict.get(name, default)
        if val is None and optional: return None

        if isinstance(val, str):
            val = self.pallet.get(val, [0, 0, 0, 255])

        try:
            if len(val) == 3:
                val = tuple(val) + (255, )

            elif len(val) != 4:
                raise GUIThemeError('color incorrect length')

        except TypeError:
            # print('color not iterable')
            ## TODO: fix this
            raise

        for i, p in enumerate(val):
            if not isinstance(p, (int)):
                raise GUIThemeError(f'{i}, {p} - invalid color type')

            if p<0 or p>255:
                raise GUIThemeError(f'{i}, {p} - invalid color value')
        #print(f'{name}: {val}')
        return val

    def _verify_int(self, name, default=0, optional=False):
        'verify that value of self._dict[name] is valid int value'

        val = self._dict.get(name, default)
        if val is None and optional:
            return None

        if not isinstance(val, int):
            raise GUIThemeError(f'{name} is not an int')
        #print(f'{name}: {val}')
        return val

    def _verify_file(self, name, default=None, optional=False):
        ''''
        verify that value of self._dict[name] is valid relative path,
        absolute path, or RESOURCES asset
        '''
        val = self._dict.get(name, default)
        if val is None and optional:
            return None

        if not isinstance(val, str):
            raise GUIThemeError(f'{name} is not a string')

        if not self.gui.resources.find(val):
            raise GUIThemeError(f'{name} is not a file')

        #print(f'{name}: {val}')
        return val

    def _verify_bool(self, name, default=None, optional=False):
        'verify that value of self._dict[name] is valid bool value'

        val = self._dict.get(name, default)
        if val is None and optional:
            return None

        if val in (True, False, 0, 1):
            val = True if val else False
            #print(f'{name}: {val}')
            return val
        else:
            raise GUIThemeError(f'{name} is not BOOL')

    def _verify_option(self, name, options, default=None, optional=False):
        'verify that value of self._dict[name] is in given options list'

        val = self._dict.get(name, default)
        if val is None and optional: return None

        if val not in options:
            val = default
        return val

    def _verify_text(self, name, default=None, optional=False):
        'verify that value of self._dict[name] is valid str of text'

        val = self._dict.get(name, default)
        if val is None and optional: return None

        if isinstance(val, str):
            #print(f'{name}: {val}')
            return val
        else:
            raise(f'{name} is not text')

    def _verify_list(self, name, default=None, optional=False):
        'verify that value of self._dict[name] is valid list'

        val = self._dict.get(name, default)
        if val is None and optional: return None

        if not isinstance(val, (list, tuple)):
            raise GUIThemeError(f'{name} is not a list')

        for i, v in enumerate(val):
            if isinstance(v, (list, tuple)):
                self._verify_bar(None, v, Rect(0, 0, 100, 100))

            elif not isinstance(v, str):
                raise GUIThemeError(f'{name}[{i}] == {v}, not a string')

        return val

    def _verify_ints(self, name, count, default=None, optional=False):
        'verify that value of self._dict[name] is valid list of ints'

        val = self._dict.get(name, default)
        if val is None and optional: return None

        if not isinstance(val, (list, tuple)):
            raise GUIThemeError(f'{name} is not a list')

        elif len(val) != count:
            raise GUIThemeError(f'{name} must have {count} int values')

        for i, v in enumerate(val):
            if not isinstance(v, int):
                raise GUIThemeError(f'{name}[{i}] == {v}, not an int')

        return val


def deep_update(d, u, r=False):
    '''
    Add contents of dict u into dict d. This will change the provided
    d parameter dict

    :param d: dict to add new values to
    :param u: dict with values to add into d
    :rvalue dict: the updated dict, same as d
    '''
    o = d
    for k, v in u.items():
        if not isinstance(d, Mapping):
            o = u

        elif isinstance(v, Mapping):
            r = deep_update(d.get(k, {}), v, True)
            o[k] = r

        else:
            o[k] = u[k]

    return o

def deep_merge(d, u, r=False):
    '''
    Add contents of dict u into a copy of dict d. This will not change the
    provided d parameter dict, only return a new copy.

    :param d: dict to add new values to
    :param u: dict with values to add into d
    :rvalue dict: the new dict with u merged into d
    '''
    n = deep_update({}, d)
    return deep_update(n, u)

def deep_print(d, name=None, l=0, file=None):
    '''
    Pretty print a dict recursively, included all child dicts

    :param d: dict to pring
    :param name: name of dict to use in printing
    :param l: used internaly
    :param file: open file to print into instead of to the console
    '''
    if name: print(f'{"  " * l}{name}', file=file)
    for k, v in d.items():
        if isinstance(v, Mapping):
            deep_print(v, k, l + 1, file)

        else:
            print(f'{"  " * (l + 1)}{k}: {v}', file=file)


def range_list(start, low, high, step):
    '''
    Creates a list of strings representing numbers within a given
    range. Meant for use with gui.options_menu as an alternative to
    a slider widget. The values will be a listin numerical order, but
    rotated to have the start value first.

    :param start: the value to start at (first value)
    :param low: lowest value for list
    :param hight: highest value for list
    :param step: the numerical value between each item in the list
    :rvalue list: a list of numerical values, rotate to have start value
            first

    example: range_list(50, 0, 100, 10) ->
            [50, 60, 70, 80, 90, 100, 0, 10, 20, 30, 40]
    '''
    return [str(i) for i in range(start, high + 1, step)] + [
            str(i) for i in reversed(range(start - step, low - 1, -step))]


def get_color_mod(texture):
    '''
    Get color_mod value of a texture as an RGB 3-tuple
    NOT WORKING
    '''
    r, g, b = c_ubyte(0), c_ubyte(0), c_ubyte(0)
    sdl2.SDL_GetTextureColorMod(texture.tx, byref(r), byref(g), byref(b))
    print('inside get', r.value, g.value, b.value)
    return  r.value, g.value, b.value

def set_color_mod(texture, color):
    '''
    Set color_mod value of a texture using an RGB 3-tuple
    NOT WORKING
    '''
    r, g, b = c_ubyte(color[0]), c_ubyte(color[1]), c_ubyte(color[2])
    sdl2.SDL_SetTextureColorMod(texture.tx, r, g, b)


def autoscroll_text(text_rect, area_rect, alignment, scroll_amount, is_vertical=True):
    # Calculate the fitted rect for the text within the area
    x, y = getattr(area_rect, alignment, area_rect.topleft)

    if is_vertical:
        max_scroll = max(0, text_rect.height - area_rect.height)
        scroll_amount = min(scroll_amount, max_scroll)

        if 'top' in alignment:
            y -= scroll_amount

        elif 'bottom' in alignment:
            y += scroll_amount

    else:
        max_scroll = max(0, text_rect.width - area_rect.width)
        scroll_amount = min(scroll_amount, max_scroll)

        if 'left' in alignment:
            x -= scroll_amount

        elif 'right' in alignment:
            x += scroll_amount

    return x, y, max_scroll


'''
## Not used.
def init():
    with open('theme.json') as inp:
        config = json.load(inp)
    if os.path.isfile('defaults.json'):
        with open('defaults.json') as inp:
            defaults = json.load(inp)
        config = deep_update(defaults, config)
    deep_print(config, 'config')

    logical_size = config.get('options', {}).get('logical_size', DEFAULT_SIZE)
    sdl2.ext.init()
    mode = sdl2.ext.displays.DisplayInfo(0).current_mode
    if 'window' in sys.argv:
        screen_size = config['options'].get('screen_size') or logical_size
        flags = None
    else:
        screen_size = config['options'].get('screen_size') or mode.w, mode.h
        flags = sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP # TODO should not use fullscreen_desktop on actual device
    print(f'Current display mode: {mode.w}x{mode.h}@{mode.refresh_rate}Hz')
    print(f'Logical Size: {logical_size}, Screen Size: {screen_size}')

    window = sdl2.ext.Window("Harbour Master",
            size=screen_size, flags=flags)
    screen = sdl2.ext.renderer.Renderer(window,
            flags=sdl2.SDL_RENDERER_ACCELERATED, logical_size=logical_size)
    screen.clear((0, 0, 0))
    sdl2.ext.renderer.set_texture_scale_quality('linear') #nearest, linear, best

    Image.renderer = screen
    images = ImageManager(screen)
    fonts = FontManager(screen)
    inp = InputHandler()
    window.show()

    if 'sounds' in config:
        sounds.init()
        for k, v in config['sounds'].items():
            print('loading sound: ', v)
            sounds.load(v, k)
    if config['options'].get('music'):
        sounds.init()
        sounds.music(config['options']['music'], volume=.3)

    defaults = config.get('defaults', {})
    print('Defaults:', defaults)
    Region.set_defaults(defaults, screen, images, fonts)

    gui.set_globals(config, screen, images, fonts, inp)
    utility.set_globals(config, screen, images, fonts, inp)

    return config, screen, fonts, images, inp
'''
