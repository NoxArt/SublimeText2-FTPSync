# -*- coding: utf8 -*-

# Test file for ../ftpsyncfiles.py
import ftpsyncfiles
import unittest
import minimock
import os


class TestFormatTimestamp(unittest.TestCase):

	def test_default(self):
		timestamp = 1345833507
		result = ftpsyncfiles.formatTimestamp(timestamp)

		self.assertEqual(result, '2012-08-24 20:38')

	def test_custom_format(self):
		timestamp = 1345833507
		format = '%H:%M.%S %d.%m. %Y'
		result = ftpsyncfiles.formatTimestamp(timestamp, format)

		self.assertEqual(result, '20:38.27 24.08. 2012')


class TestGetFolders(unittest.TestCase):

	def test_windows(self):
		path = "C:/Some/Path/With space/and čapek"
		expected = ["C:/Some/Path/With space/and čapek", "C:/Some/Path/With space", "C:/Some/Path", "C:/Some", "C:/"]
		minimock.mock('os.path.abspath', returns=path)

		result = ftpsyncfiles.getFolders(path)

		self.assertEqual(result, expected)

	def test_linux(self):
		path = "/home/Some/Path/With space/and čapek"
		expected = ["/home/Some/Path/With space/and čapek", "/home/Some/Path/With space", "/home/Some/Path", "/home/Some", "/home", "/"]
		minimock.mock('os.path.abspath', returns=path)

		result = ftpsyncfiles.getFolders(path)

		self.assertEqual(result, expected)

	def test_expand(self):
		path = "../test"
		cwd  = "C:/foo/bar/xyz"

		minimock.mock('os.path.abspath', returns="C:/foo/bar/test")

		result = ftpsyncfiles.getFolders(path)
		expected = ["C:/foo/bar/test", "C:/foo/bar", "C:/foo", "C:/"]

		self.assertEqual(result, expected)

	def tearDown(self):
		minimock.restore()


class TestFindFile(unittest.TestCase):

	def setUp(self):
		self.path = "./data/ftpsyncfiles/findFile";

	def test_returns_none_when_given_none(self):
		self.assertEqual(None, ftpsyncfiles.findFile(None, "anything"))

	def test_find(self):
		path = self.path
		file_name = "lost.txt"
		expected = os.path.abspath(os.path.join(self.path + "/foo/bar", file_name))
		result = ftpsyncfiles.findFile(path, file_name)

		print expected

		self.assertEqual(expected, result)