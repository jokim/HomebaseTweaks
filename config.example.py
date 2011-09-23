#!/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2011 Joakim Hovlandsvåg <joakim.hovlandsvag@gmail.com>
#
# This file is part of HomebaseTweaks.
# 
# HomebaseTweaks is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# HomebaseTweaks is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with HomebaseTweaks. If not, see <http://www.gnu.org/licenses/>.
"""
Example configuration for HomebaseTweaks. Make a copy of this to config.py.
"""

# Logon credentials
username = 'username'
password = 'password'

# The default number of days to get the programs from
days = 1.0

# Selectors for recording series.
# If any element in this list matches a program, it will be set to record.
series = (
        # This records any program that is named 'Boardwalk Empire':
        {'title': 'Boardwalk Empire', },
        # This records a program on the tv channel 'nrktv1':
        {'title': 'Boardwalk Empire', 'channel': 'nrktv1'},

        # Selector arguments
        # title:    [string]
        #           The exact title of the program.
        #
        # channel:  [string]
        #           The exact name of the channel the program should be going.
        #
        # dow:      [int]
        #           The day of the week the program should be going before it is
        #           recorded. Goes from 0 (sunday) to 6 (saturday).

        # TODO: give examples for specifying:
        # - time of day (from - to)
        # - regexp for the program name
)
