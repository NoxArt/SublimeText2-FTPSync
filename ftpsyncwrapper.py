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
import ftplib
import os
import re
import time

# FTPSync libraries
from ftpsyncfiles import Metafile, isTextFile


# ==== Initialization and optimization =====================================================

# to extract data from FTP LIST http://stackoverflow.com/questions/2443007/ftp-list-format
re_ftpListParse = re.compile("^([d-])[rxws-]{9}\s+\d+\s+[\w\d]+\s+[\w\d]+\s+(\d+)\s+(\w{1,3}\s+\d+\s+(?:\d+:\d+|\d{2,4}))\s+(.*?)$", re.M | re.I | re.U | re.L)

# error code - first 3-digit number https://tools.ietf.org/html/rfc959#page-39
re_errorCode = re.compile("[1-5]\d\d")

# For FTP LIST entries with {last modified} timestamp earlier than 6 months, see http://stackoverflow.com/questions/2443007/ftp-list-format
currentYear = int(time.strftime("%Y", time.gmtime()))

# List of FTP errors of interest
ftpError = {
    'fileNotAllowed': 553,
    'fileUnavailible': 550,
    'pendingInformation': 350,
    'ok': 200
}

ftpErrors = {
    'noFileOrDirectory': 'No such file or directory',
    'cwdNoFileOrDirectory': 'No such file or directory',
    'fileNotExist': 'Sorry, but that file doesn\'t exist',
    'permissionDenied': 'Permission denied',
    'rnfrExists': 'RNFR accepted - file exists, ready for destination',
    'disconnected': 'An established connection was aborted by the software in your host machine',
    'timeout': 'timed out',
    'typeIsNow': 'TYPE is now'
}

# SSL issue
sslErrors = {
    'badWrite': 'error:1409F07F:SSL routines:SSL3_WRITE_PENDING:bad write retry',
}

# Default permissions for newly created folder
defaultFolderPermissions = "755"



# ==== Exceptions ==========================================================================

class ConnectionClosedException(Exception):
    pass


# ==== Content =============================================================================

# Factory function - returns and instance of a proper class based on the configuration
# currently differs between FTP(S) and SFTP
#
# SFTP currently not implemented
#
# @type config: dict
# @type name: string
# @param name: user-defined name of a connection
#
# @return AbstractConnection
def CreateConnection(config, name):
    if 'private_key' in config and config['private_key'] is not None:
        raise NotImplementedError
    else:
        return FTPSConnection(config['connections'][name], config, name)


# Base class for all connection classes
class AbstractConnection:

    # Return server path for the uploaded file relative to specified path
    #
    # @example:
    #   file_path: /user/home/NoxArt/web/index.php
    #   config['path']: /www/
    #   config['file_path']: /user/home/NoxArt/
    #
    #   result: /www/web/index.php
    #
    # @type self: AbstractConnection
    # @type file_path: string
    #
    # @return string remote file path
    def _getMappedPath(self, file_path):
        config = os.path.dirname(self.config['file_path'])
        fragment = os.path.relpath(file_path, config)
        return self._postprocessPath(os.path.join(self.config['path'], fragment))

    # Tweaks a remote path before using it
    #
    # @type self: AbstractConnection
    # @type file_path: string
    #
    # @return string remote file path
    def _postprocessPath(self, path):
        path = path.replace('\\\\', '\\')
        path = path.replace('\\', '/')
        path = path.replace('//','/')
        return path


# FTP(S) connection
#
# uses Python's ftplib
#
# because of FTP_TLS added in v2.7 FTPSync uses imported library from v2.7.1
# shipped with the plugin
class FTPSConnection(AbstractConnection):

    # Constructor
    #
    # @type self: FTPSConnection
    # @type config: dict
    # @param config: only the connection part of config
    # @type name: string
    # @param name: connection name from config
    def __init__(self, config, generic_config, name):
        self.config = config
        self.generic_config = generic_config
        self.name = name
        self.isClosed = False

        if self.config['tls'] is True:
            self.connection = ftplib.FTP_TLS()
        else:
            self.connection = ftplib.FTP()


    # Destructor, closes connection
    #
    # @type self: FTPSConnection
    def __del__(self):
        if hasattr(self, 'connection'):
            self.close()


    # Connects to remote server
    #
    # @type self: FTPSConnection
    def connect(self):
        self.connection.connect(self.config['host'], int(self.config['port']), int(self.config['timeout']))
        self.connection.set_pasv(self.config['passive'])


    # Authenticates if necessary
    #
    # @type self: FTPSConnection
    #
    # @return bool whether the authentication happened or not
    def authenticate(self):
        if self.config['tls'] is True:
            self.connection.auth()
            self.connection.prot_p()
            return True

        return False


    # Logs into the remote server
    #
    # @type self: FTPSConnection
    def login(self):
        self.connection.login(self.config['username'], self.config['password'])


    # Send an empty/keep-alive message to server
    #
    # @type self: FTPSConnection
    def keepAlive(self):
        self.connection.voidcmd("NOOP")


    # Returns whether the connection is active
    #
    # @type self: FTPSConnection
    #
    # @return bool
    def isAlive(self):
        return self.isClosed is False and self.connection.sock is not None and self.connection.file is not None


    # Uploads a file to remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    def put(self, file_path, new_name = None, failed=False):

        def action():
            remote_file = file_path
            if new_name is not None:
                remote_file = self._postprocessPath(os.path.join(os.path.split(file_path)[0], new_name))

            path = self._getMappedPath(remote_file)

            if os.path.isdir(file_path):
                return self.__ensurePath(path, True)

            command = "STOR " + path
            uploaded = open(file_path, "rb")

            try:
                self.connection.storbinary(command, uploaded)
            except Exception, e:
                if self.__isErrorCode(e, 'fileNotAllowed') and failed is False:
                    self.__ensurePath(path)
                    self.put(file_path, new_name, True)
                else:
                    raise e
            finally:
                uploaded.close()

        return self.__execute(action)


    # Downloads a file from remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    def get(self, file_path):

        def action():
            path = self._getMappedPath(file_path)
            command = "RETR " + path
            downloaded = open(file_path, "wb")

            downloaded = open(file_path, "wb")
            try:
                self.connection.retrbinary(command, lambda data: downloaded.write(data))
            finally:
                downloaded.close()

        return self.__execute(action)


    # Renames a file on remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    # @type new_name: string
    #
    # @global ftpErrors
    def rename(self, file_path, new_name):

        def action():
            is_dir = os.path.isdir(file_path)
            dirname = os.path.dirname(file_path)
            path = self._getMappedPath(dirname)
            base = os.path.basename(file_path)

            try:
                self.cwd(path)
            except Exception, e:
                if self.__isErrorCode(e, 'fileUnavailible'):
                    self.__ensurePath(path)
                else:
                    raise e

            try:
                self.connection.voidcmd("RNFR " + base)
            except Exception, e:
                if self.__isError(e, 'rnfrExists'):
                    self.connection.voidcmd("RNTO " + new_name)
                    return
                elif self.__isError(e, 'cwdNoFileOrDirectory') or self.__isError(e, 'fileNotExist'):
                    if is_dir:
                        self.__ensurePath( path + '/' + new_name, True )
                    else:
                        self.put(file_path, new_name)
                    return
                else:
                    raise e

            try:
                self.connection.voidcmd("RNFR " + base)
            except Exception, e:
                if self.__isError(e, 'rnfrExists') and str(e).find('Aborting previous'):
                    self.connection.voidcmd("RNTO " + new_name)
                    return
                else:
                    raise e

            self.connection.voidcmd("RNTO " + new_name)

        return self.__execute(action)


    # Changes a current path on remote server
    #
    # @type self: FTPSConnection
    # @type path: string
    def cwd(self, path):
        self.connection.cwd(path)


    # Returns a list of content of a given path
    #
    # @type self: FTPSConnection
    # @type file_path: string
    #
    # @return list<Metafile>
    def list(self, file_path):

        def action():
            path = self._getMappedPath(file_path)
            contents = []
            result = []
            self.connection.dir(path, lambda data: contents.append(data))

            for content in contents:
                try:
                    if self.config['debug_extras']['print_list_result'] is True:
                        print "FTPSync <debug> LIST line: " + str(content)
                except KeyError:
                    pass

                split = re_ftpListParse.search(content)

                if split is None:
                    continue

                isDir = split.group(1) == 'd'
                filesize = split.group(2)
                lastModified = split.group(3)
                name = split.group(4)

                data = Metafile(name, isDir, self.__parseTime(lastModified), filesize)

                if name != "." and name != "..":
                    result.append(data)

            return result

        return self.__execute(action)


    # Closes a connection
    #
    # @type self: FTPSConnection
    # @type connections: dict<hash => list<connection>
    # @type hash: string
    def close(self, connections=[], hash=None):
        try:
            self.connection.quit()
        except:
            self.connection.close()
        finally:
            self.isClosed = True

        if len(connections) > 0 and hash is not None:
            try:
                connections[hash].remove(self)
            except ValueError:
                return


    # Changes permissions for a remote file
    #
    # @type self: FTPSConnection
    # @type filename: string
    # @type permissions: string
    def chmod(self, filename, permissions):
        command = "SITE CHMOD " + str(permissions) + " " + str(filename)

        self.connection.voidcmd(command)


    # Executes an action while handling common errors
    #
    # @type self: FTPSConnection
    # @type callback: callback
    #
    # @return unknown
    def __execute(self, callback):
        try:
            return callback()
        except Exception, e:

            # bad write - repeat command
            if str(e).find(sslErrors['badWrite']) is True:
                return callback()
            # disconnected - close itself to be refreshed
            elif self.__isError(e, 'disconnected') is True:
                self.close()
                raise e
            # timeout - retry
            elif self.__isError(e, 'timeout') is True:
                return callback()
            # only informative message
            elif self.__isErrorCode(e, 'ok') is True:
                return
            # other exception
            else:
                raise e


    # Throws exception if closed
    #
    # @type self: FTPSConnection
    def __checkClosed(self):
        if self.isClosed is True:
            raise ConnectionClosedException


    # Parses string time
    #
    # @see http://stackoverflow.com/questions/2443007/ftp-list-format
    #
    # @type self: FTPSConnection
    # @type: time_val: string
    #
    # @return unix timestamp
    def __parseTime(self, time_val):
        if time_val.find(':') is -1:
            struct = time.strptime(time_val + str(" 00:00"), "%b %d %Y %H:%M")
        else:
            struct = time.strptime(str(currentYear) + " " + time_val, "%Y %b %d %H:%M")

        return time.mktime(struct)


    # Integer code error comparison
    #
    # @type self: FTPSConnection
    # @type exception: Exception
    # @type error: string
    # @param error: key of ftpError dict
    #
    # @return boolean
    #
    # @global ftpError
    # @global re_errorCode
    def __isErrorCode(self, exception, error):
        code = re_errorCode.search(str(exception))

        if code is None:
            return False

        return int(code.group(0)) == ftpError[error]


    # Textual error comparison
    #
    # @type self: FTPSConnection
    # @type exception: Exception
    # @type error: string
    # @param error: key of ftpErrors dict
    #
    # @return boolean
    #
    # @global ftpErrors
    def __isError(self, exception, error):
        return str(exception).find(ftpErrors[error]) != -1


    # Ensures the given path is existing and accessible
    #
    # @type self: FTPSConnection
    # @type path: string
    def __ensurePath(self, path, isFolder=False):
        self.connection.cwd(self.config['path'])

        relative = os.path.relpath(path, self.config['path'])

        folders = self._postprocessPath(relative)
        folders = folders.split("/")

        index = 0
        for folder in folders:
            index += 1

            try:
                if index < len(folders) or (isFolder and index <= len(folders)):
                    self.connection.cwd(folder)
            except Exception, e:
                if self.__isErrorCode(e, 'fileUnavailible'):

                    try:
                        # create folder
                        self.connection.mkd(folder)
                    except Exception, e:
                        if self.__isErrorCode(e, 'fileUnavailible'):
                            # exists, but not proper permissions
                            self.chmod(folder, self.config['default_folder_permissions'])
                        else:
                            raise e

                    # move down
                    self.connection.cwd(folder)
                else:
                    raise e


#class SSHConnection():
