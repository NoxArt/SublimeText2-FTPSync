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

class Pubsub:

	_instance = None

	@staticmethod
	def instance():
		if Pubsub._instance is None:
			Pubsub._instance = Pubsub()

		return Pubsub._instance

	def __init__(self):
		self.handlers = {}

	def subscribe(self, event, handler):
		if not self.has(event):
			self.handlers[event] = []

		self.handlers[event].append(handler)

	def publish(self, event, args = []):
		if not self.has(event):
			return

		for handler in self.handlers[event]:
			handler(*args)

	def has(self, event):
		return event in self.handlers


if __name__ == '__main__':
	import unittest

	class PubsubTest(unittest.TestCase):
		def test_hasEvent(self):
			p = Pubsub()
			self.assertFalse(p.has('test_hasEvent'))
			p.subscribe('test_hasEvent', None)
			self.assertTrue(p.has('test_hasEvent'))

		def test_basic(self):
			p = Pubsub()

			result = {
				'success': False,
				'failure': False
			}

			def setSuccess():
				result['success'] = True
			def setFailure():
				result['failure'] = True

			p.subscribe('success', setSuccess)
			p.publish('success')

			self.assertTrue(result['success'])
			self.assertFalse(result['failure'])

		def test_args(self):
			p = Pubsub()

			result = {
				'result': None
			}
			def multiply(a, b):
				result['result'] = a * b

			p.subscribe('test', multiply)
			p.publish('test', [2, 7])

			self.assertEquals(14, result['result'])

		def test_instance(self):
			p = Pubsub.instance()
			self.assertTrue( isinstance(p, Pubsub) )


	unittest.main()


