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

# Doc comment syntax inspired by http://stackoverflow.com/a/487203/387503


# ==== Libraries ===========================================================================

# Python's built-in libraries
import os
import sys

# FTPSync libraries
if sys.version < '3':
    from ftpsyncfiles import gatherMetafiles, getChangedFiles
else:
    from FTPSync.ftpsyncfiles import gatherMetafiles, getChangedFiles


# ==== Exceptions ==========================================================================

class WatcherClosedException(RuntimeError):
	pass

class NotPreparedException(Exception):
	pass


# ==== Content =============================================================================

class FileWatcher(object):

	def __init__(self, config_file_path, config):
		self.config_file_path = config_file_path
		self.config = config
		self.prepared = False
		self.afterwatch = {
			'before': {},
			'after': {}
		}


	# Scans watched paths for watched files, creates metafiles
	#
	# @type event: string
	# @param event: 'before', 'after'
	# @type name: string
	# @param name: connection name
	def scanWatched(self, event, name):
		if event is 'before' and name in self.afterwatch['before'] and len(self.afterwatch['before'][name]) > 0:
			return

		root = os.path.dirname(self.config_file_path)
		properties = self.config[name]
		watch = properties['after_save_watch']
		self.afterwatch[event][name] = {}

		if type(watch) is list and len(watch) > 0 and properties['upload_delay'] > 0:
			for folder, filepattern in watch:
				# adds contents to dict
				self.afterwatch[event][name].update(gatherMetafiles(filepattern, os.path.join(root, folder)).items())


	# ???
	#
	# @type event: string
	# @param event: 'before', 'after'
	# @type name: string
	# @param name: connection name
	# @type data: ???
	# @param data: ???
	def setScanned(self, event, name, data):
		if type(self.afterwatch) is not dict:
			self.afterwatch = {}

		if event not in self.afterwatch or type(self.afterwatch[event]) is not dict:
			self.afterwatch[event] = {}

		self.afterwatch[event][name] = data


	# Goes through all connection configs and scans all the requested paths
	def prepare(self):
		if self.prepared:
			raise WatcherClosedException

		for name in self.config:
			if self.config[name]['after_save_watch']:
				self.scanWatched('before', name)

				if self.config[name]['debug_extras']['after_save_watch']:
					print ("FTPSync <debug> dumping pre-scan")
					print (self.afterwatch['before'])

		self.prepared = True


	# Returns files that got changed
	#
	# @type connectionName: string
	#
	# @return Metafile[]
	def getChangedFiles(self, connectionName):
		if self.prepared is False:
			raise NotPreparedException

		self.afterwatch['after'][connectionName] = {}
		self.scanWatched('after', connectionName)
		if self.config[connectionName]['debug_extras']['after_save_watch']:
			print ("FTPSync <debug> dumping post-scan")
			print (self.afterwatch['before'])
		changed = getChangedFiles(self.afterwatch['before'][connectionName], self.afterwatch['after'][connectionName])
		if self.config[connectionName]['debug_extras']['after_save_watch']:
			print ("FTPSync <debug> dumping changed files")
			print ("COUNT: " + str(len(changed)))
			for change in changed:
				print ("Path: " + change.getPath() + " | Name: " + change.getName())

		return changed



