#!/bin/bash

md5sum harbourmaster | cut -f 1 -d ' ' > harbourmaster.md5
md5sum pylibs.zip | cut -f 1 -d ' ' > pylibs.zip.md5
