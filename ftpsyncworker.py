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
				print ("Executing command " + unicode(self.id))

			self.command.execute()
		except Exception as e:
			if self.debug:
				print (e)
				print ("Retrying command " + unicode(self.id))

			self.command.execute()
		finally:
			if self.debug:
				print ("Ending command " + unicode(self.id))

			while self.command.isRunning():
				if self.debug:
					print ("Command " + str(self.id) + " running...")
				sleep(0.5)

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
		self.semaphore = threading.BoundedSemaphore(self.limit)

		self.makeConnection = factory
		self.makeConfig = loader
		self.freeConnections = []

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

	# Creates and adds a connection if limit allows
	def fillConnection(self, config):
		if len(self.connections) <= self.limit:
			connection = None

			try:
				connection = self.makeConnection(self.makeConfig(config), None, False)
			except Exception as e:
				if str(e).lower().find('too many connections') != -1:
					if self.debug:
						print ("FTPSync > Too many connections...")
					sleep(1.5)
				else:
					if self.debug:
						print (e)
					raise

			if connection is not None and len(connection) > 0:
				self.addConnection(connection)
				self.freeConnections.append(len(self.connections))

			if self.debug:
				print ("FTPSync > Creating new connection #" + unicode(len(self.connections)))

	# Adds a new command to worker
	def addCommand(self, command, config):
		if self.debug:
			print ("FTPSync > Adding command " + self.__commandName(command))

		if len(self.commands) >= self.limit:
			if self.debug:
				print ("FTPSync > Queuing command " + self.__commandName(command) + " (total: " + str(len(self.waitingCommands) + 1) + ")")

			self.__waitCommand(command)
		else:
			if self.debug:
				print ("FTPSync > Running command " + self.__commandName(command) + " (total: " + str(len(self.commands) + 1) + ")")

			self.__run(command, config)

	# Return whether has any scheduled commands
	def isEmpty(self):
		return len(self.commands) == 0 and len(self.waitingCommands) == 0

	# Put the command to sleep
	def __waitCommand(self, command):
		self.waitingCommands.append(command)

	# Run the command
	def __run(self, command, config):
		try:
			self.semaphore.acquire()
			self.threadId += 1

			self.fillConnection(config)
			while len(self.freeConnections) == 0:
				sleep(0.1)
				self.fillConnection(config)

			index = self.freeConnections.pop()
			thread = RunningCommand(command, self.__onFinish, self.debug, self.threadId)

			if self.debug:
				print ("FTPSync > Scheduling thread #" + unicode(self.threadId) + " " + self.__commandName(command) + " run, using connection " + unicode(index))

			command.setConnection(self.connections[index - 1])
			self.commands.append({
				'command': command,
				'config': config,
				'thread': thread,
				'index': index,
				'threadId': self.threadId
			})

			thread.start()
		except Exception as e:
			self.__onFinish(command)
			raise
		finally:
			self.semaphore.release()

	# Finish callback
	def __onFinish(self, command):
		config = None

		# Kick from running commands and free connection
		for cmd in self.commands:
			if cmd['command'] is command:
				self.freeConnections.append(cmd['index'])
				config = cmd['config']
				self.commands.remove(cmd)

				if self.debug:
					print ("FTPSync > Removing thread #" + unicode(cmd['threadId']))

		if self.debug:
			print ("FTPSync > Sleeping commands: " + unicode(len(self.waitingCommands)))

		# Woke up one sleeping command
		if len(self.waitingCommands) > 0:
			awakenCommand = self.waitingCommands.pop()
			self.__run(awakenCommand, config)

	# Returns classname of given command
	def __commandName(self, command):
		return unicode(command.__class__.__name__)

	# Closes all connections
	def __del__(self):
		for connections in self.connections:
			for connection in connections:
				connection.close()

				if self.debug:
					print ("FTPSync > Closing connection")