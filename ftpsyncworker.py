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
from time import sleep


# ==== Content =============================================================================

# Command thread
class RunningCommand(threading.Thread):
    def __init__(self, command, onFinish, debug, tid):
        self.command = command
        self.onFinish = onFinish
        self.debug = bool(debug)
        self.id = int(tid)
        threading.Thread.__init__(self)

    def run(self):
        try:
            if self.debug:
                print "Executing command " + unicode(self.id)

            self.command.execute()
        except Exception:
            if self.debug:
                print "Retrying command " + unicode(self.id)

            self.command.execute()
        finally:
            if self.debug:
                print "Closing command " + unicode(self.id)

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
        self.threadId = 0

        self.makeConnection = factory
        self.makeConfig = loader

        self.freeConnections = range(1, self.limit + 1)
        self.freeConnections.reverse()

        self.debug = False


    # Enables console dumping
    def enableDebug(self):
        self.debug = True

    # Enables console dumping
    def disableDebug(self):
        self.debug = False

    # Sets a callback used for making a connection
    def setConnectionFactory(self, factory):
        self.makeConnection = factory

    # Adds a new connection to pool
    def addConnection(self, connections):
        self.connections.append(connections)

    # Adds a new command to worker
    def addCommand(self, command, config):
        if self.debug:
            print "Adding command " + self.__commandName(command)

        if len(self.commands) >= self.limit:
            if self.debug:
                print "Queuing command " + self.__commandName(command)

            self.__waitCommand(command)
        else:
            if len(self.connections) <= self.limit:
                self.addConnection(self.makeConnection(self.makeConfig(config)))

                if self.debug:
                    print "Creaing new connection #" + unicode(len(self.connections))

            self.__run(command)

    # Return whether has any scheduled commands
    def isEmpty(self):
        return len(self.commands) == 0 and len(self.waitingCommands) == 0

    # Put the command to sleep
    def __waitCommand(self, command):
        self.waitingCommands.append(command)

    # Run the command
    def __run(self, command):
        self.threadId += 1
        thread = RunningCommand(command, self.__onFinish, self.debug, self.threadId)

        while len(self.freeConnections) == 0:
            sleep(0.05)

        index = self.freeConnections.pop()

        if self.debug:
            print "Scheduling thread #" + unicode(self.threadId) + " " + self.__commandName(command) + " run, using connection " + unicode(index)

        command.setConnection(self.connections[index - 1])
        self.commands.append({
            'command': command,
            'thread': thread,
            'index': index,
            'threadId': self.threadId
        })

        thread.start()

    # Finish callback
    def __onFinish(self, command):
        # Kick from running commands and free connection
        for cmd in self.commands:
            if cmd['command'] is command:
                self.freeConnections.append(cmd['index'])
                self.commands.remove(cmd)

                if self.debug:
                    print "Removing thread #" + unicode(cmd['threadId'])

        if self.debug:
            print "Sleeping commands: " + unicode(len(self.waitingCommands))

        # Woke up one sleeping command
        if len(self.waitingCommands) > 0:
            awakenCommand = self.waitingCommands.pop()
            self.__run(awakenCommand)

    # Returns classname of given command
    def __commandName(self, command):
        return unicode(command.__class__.__name__)

    # Closes all connections
    def __del__(self):
        for connections in self.connections:
            for connection in connections:
                connection.close()

                if self.debug:
                    print "Closing connection"


