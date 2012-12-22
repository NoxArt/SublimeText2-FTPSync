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
import threading


# ==== Content =============================================================================

# Command thread
class RunningCommand(threading.Thread):
    def __init__(self, command, onFinish):
        self.command = command
        self.onFinish = onFinish
        threading.Thread.__init__(self)

    def run(self):
        self.command.execute()
        self.onFinish(self.command)


# Class handling concurrent commands
class Worker(object):

    def __init__(self, limit, factory, loader):
        self.limit = int(limit)
        self.connections = []
        self.commands = []
        self.waitingCommands = []
        self.threads = []
        self.index = 0
        self.makeConnection = factory
        self.makeConfig = loader
        self.freeConnections = range(1, self.limit + 1)
        self.freeConnections.reverse()

    def setConnectionFactory(self, factory):
        self.makeConnection = factory

    def addConnection(self, connections):
        self.connections.append(connections)

    def addCommand(self, command, config):
        if len(self.commands) >= self.limit:
            self.__waitCommand(command)
        else:
            if len(self.connections) < self.limit:
                self.addConnection(self.makeConnection(self.makeConfig(config)))

            self.__run(command)

    def isEmpty(self):
        return len(self.commands) == 0 and len(self.waitingCommands) == 0

    def __waitCommand(self, command):
        self.waitingCommands.append(command)

    def __run(self, command):
        thread = RunningCommand(command, self.__onFinish)

        index = self.freeConnections.pop()

        command.setConnection(self.connections[index - 1])
        self.commands.append({
            'command': command,
            'thread': thread,
            'index': index
        })

        thread.start()

    def __onFinish(self, command):
        for cmd in self.commands:
            if cmd['command'] is command:
                self.freeConnections.append(cmd['index'])
                self.commands.remove(cmd)

        if len(self.waitingCommands) > 0:
            awakenCommand = self.waitingCommands.pop()
            self.__run(awakenCommand)

    def __del__(self):
        for connections in self.connections:
            for connection in connections:
                connection.close()

