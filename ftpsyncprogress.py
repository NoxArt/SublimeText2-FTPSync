# -*- coding: utf-8 -*-

# Copyright (c) 2012 Jiri "NoxArt" Petruzelka
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# @author Jiri "NoxArt" Petruzelka | petruzelka@noxart.cz | @NoxArt
# @copyright (c) 2012 Jiri "NoxArt" Petruzelka
# @link https://github.com/NoxArt/SublimeText2-FTPSync

# ==== Libraries ===========================================================================

# Python's built-in libraries
import math


# ==== Content =============================================================================

# Class implementing logic for progress bar
class Progress:
    def __init__(self, current=0):
        self.current = 0
        self.entries = []

    # Add unfinished entries to progress bar
    #
    # @type  self: Progress
    # @type  entries: list
    # @param entries: list of unfinished entries, usually strings
    def add(self, entries):
        for entry in entries:
            if entry not in self.entries:
                self.entries.append(entry)


    # Return number of items in the progress
    #
    # @type  self: Progress
    #
    # @return int
    def getTotal(self):
        return len(self.entries)


    # Marks a certain number of entries as finished
    #
    # @type  self: Progress
    # @type  by: integer
    # @param by: number of finished items
    def progress(self, by=1):
        self.current += int(by)

        if self.current > self.getTotal():
            self.current = self.getTotal()


    # Returns whether the process has been finished
    #
    # @type  self: Progress
    #
    # @return bool
    def isFinished(self):
        return self.current >= self.getTotal()


    # Get percentage of the progress bar, maybe rounded, see @return
    #
    # @type  self: Progress
    # @type  division: integer
    # @param division: rounding amount
    #
    # @return integer between 0 and 100 / division
    def getPercent(self, division=5):
        if division is 0:
            division = 1

        total = self.getTotal()
        if total is 0:
            total = self.current
        if total is 0:
            total = 1

        percent = int(math.ceil(float(self.current) / float(total) * 100))
        percent = math.ceil(percent / division)

        return percent