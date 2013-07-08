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
import sys

if sys.version[0] == '2':
    import lib2.ftplib as ftplib
else:
    import FTPSync.lib3.ftplib as ftplib

import os
import re
import time
import datetime
import locale

# workaround for http://www.gossamer-threads.com/lists/python/dev/755427
try:
    import _strptime
except ImportError:
    print("FTPSync > Failed to import _strptime")

# FTPSync libraries
try:
    from FTPSync.ftpsyncfiles import Metafile, isTextFile, viaTempfile
    # exceptions
    from FTPSync.ftpsyncexceptions import FileNotFoundException
except ImportError:
    from ftpsyncfiles import Metafile, isTextFile, viaTempfile
    # exceptions
    from ftpsyncexceptions import FileNotFoundException


# ==== Initialization and optimization =====================================================

# to extract data from FTP LIST http://stackoverflow.com/questions/2443007/ftp-list-format
re_ftpListParse = re.compile("^([d-])([rxws-]{9})\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\w{1,3}\s+\d+\s+(?:\d+:\d+|\d{2,4}))\s+(.*?)$", re.M | re.I | re.U | re.L)

# error code - first 3-digit number https://tools.ietf.org/html/rfc959#page-39
re_errorCode = re.compile("[1-5]\d\d")

# 20x ok code
re_errorOk = re.compile("2\d\d")

# trailing .
trailingDot = re.compile("/.\Z")

# trailing /
trailingSlash = re.compile("/\Z")

# whitespace
re_whitespace = re.compile("\s+")

# For FTP LIST entries with {last modified} timestamp earlier than 6 months, see http://stackoverflow.com/questions/2443007/ftp-list-format
currentYear = int(time.strftime("%Y", time.gmtime()))

# months
months = {
    'Jan': '01',
    'Feb': '02',
    'Mar': '03',
    'Apr': '04',
    'May': '05',
    'Jun': '06',
    'Jul': '07',
    'Aug': '08',
    'Sep': '09',
    'Oct': '10',
    'Nov': '11',
    'Dec': '12'
}

# List of FTP errors of interest
ftpError = {
    'fileNotAllowed': 553,
    'fileUnavailible': 550,
    'pendingInformation': 350,
    'ok': 200,
    'passive': 227
}

ftpErrors = {
    'noFileOrDirectory': 'No such file or directory',
    'cwdNoFileOrDirectory': 'No such file or directory',
    'fileNotExist': 'Sorry, but that file doesn\'t exist',
    'permissionDenied': 'Permission denied',
    'rnfrExists': 'RNFR accepted - file exists, ready for destination',
    'rntoReady': '350 Ready for RNTO',
    'disconnected': 'An established connection was aborted by the software in your host machine',
    'timeout': 'timed out',
    'typeIsNow': 'TYPE is now'
}

# SSL issue
sslErrors = {
    'badWrite': 'error:1409F07F:SSL routines:SSL3_WRITE_PENDING:bad write retry',
    'reuseRequired': 'SSL connection failed; session reuse required',
}

# Default permissions for newly created folder
defaultFolderPermissions = "755"

# Default encoding for file paths
encoding = 'utf-8'

# FTP time format, used for example for MFMT
ftpTimeFormat = '%Y%m%d%H%M%S'



# ==== Exceptions ==========================================================================

class ConnectionClosedException(Exception):
    pass

class TargetAlreadyExists(Exception):
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
        self.feat = None

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


    # Sets passive connection if configured to do so
    #
    # @type self: FTPSConnection
    def _makePassive(self):
        if self.config['passive']:
            self.connection.voidcmd("PASV")


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
        self.voidcmd("NOOP")


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
    # @type new_name: string
    # @param new_name: uploads a file under a different name
    # @type failed: bool
    # @param failed: retry flag
    # @type blockCallback: callback
    # @param blockCallback: callback called on every block transferred
    def put(self, file_path, new_name = None, failed = False, blockCallback = None):

        def action():
            remote_file = file_path
            if new_name is not None:
                remote_file = self._postprocessPath(os.path.join(os.path.split(file_path)[0], new_name))

            path = self._getMappedPath(remote_file)

            if os.path.isdir(file_path):
                return self.__ensurePath(path, True)

            command = "STOR " + path
            uploaded = open(file_path, "rb")

            def perBlock(data):
                if blockCallback is not None:
                    blockCallback()

            try:
                self.connection.storbinary(command, uploaded, callback = perBlock)
            except Exception as e:
                if self.__isErrorCode(e, ['ok', 'passive']) is True:
                    pass
                elif self.__isErrorCode(e, 'fileUnavailible') and failed is False:
                    self.__ensurePath(path)
                    self.put(file_path, new_name, True)
                elif self.__isErrorCode(e, 'fileNotAllowed') and failed is False:
                    self.__ensurePath(path)
                    self.put(file_path, new_name, True)
                else:
                    raise
            finally:
                uploaded.close()

            if self.config['set_remote_lastmodified'] and self.__hasFeat("MFMT") :
                try:
                    self.voidcmd("MFMT " + self.__encodeTime(os.path.getmtime(file_path)) + " " + path)
                except Exception as e:
                    if self.__isDebug():
                        try:
                            print ("Failed to set lastModified <Exception: " + str(e) + ">")
                        except:
                            pass

        return self.__execute(action)


    # Downloads a file from remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    # @type blockCallback: callback
    # @type blockCallback: callback called on every block transferred
    def get(self, file_path, blockCallback):

        def action():
            path = self._getMappedPath(file_path)
            command = "RETR " + self.__encode(path)

            if self.config['debug_extras']['debug_remote_paths']:
                print ("FTPSync <debug> get path " + file_path + " => " + str(self.__encode(path)))

            def download(tempfile):

                def perBlock(data):
                    tempfile.write(data)

                    if blockCallback is not None:
                        blockCallback()

                try:
                    self.connection.retrbinary(command, perBlock)
                except Exception as e:
                    if self.__isErrorCode(e, ['ok', 'passive']):
                        self.connection.retrbinary(command, perBlock)
                    elif self.__isErrorCode(e, 'fileUnavailible'):
                        raise FileNotFoundException
                    else:
                        raise

            existsLocally = os.path.exists(file_path)

            if self.config['use_tempfile']:
                viaTempfile(file_path, download, self.config['default_folder_permissions'])
            else:
                with open(file_path, 'wb') as destination:
                    download(destination)

            if existsLocally is False or self.config['always_sync_local_permissions']:
                try:
                    if self.config['default_local_permissions'] is not None and sys.platform != 'win32' and sys.platform != 'cygwin':
                        if self.config['default_local_permissions'] == "auto":
                            metadata = self.list(file_path)

                            if type(metadata) is list and len(metadata) > 0:
                                os.chmod(file_path, int(metadata[0].getPermissionsNumeric(),8))
                        else:
                            os.chmod(file_path, int(self.config['default_local_permissions'], 8))
                except Exception as e:
                    print ("FTPSync > Error setting local chmod [Exception: " + str(e) + "]")

        return self.__execute(action)



    # Deletes a file from remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    def delete(self, file_path, remote=False):

        def action():
            isDir = os.path.isdir(file_path)
            dirname = os.path.dirname(file_path)

            if remote is False:
                path = self._getMappedPath(dirname)
            else:
                path = dirname

            path = trailingDot.sub("", path)
            base = os.path.basename(file_path)

            try:
                if isDir:
                    for entry in self.list(file_path):
                        self.__delete(path + '/' + base, entry)

                    self.cwd(path)
                    self.voidcmd("RMD " + base)
                else:
                    self.cwd(path)
                    self.voidcmd("DELE " + base)
            except Exception as e:
                if str(e).find('No such file'):
                    raise FileNotFoundException
                else:
                    raise

        return self.__execute(action)



    # Deletes a file purely from remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    def __delete(self, root, metafile):
        if metafile is None:
            return

        name = self.__basename(metafile.getName())
        if name is None:
            return

        if type(name) is not str:
            name = name.decode('utf-8')

        path = root + '/' + name

        if metafile.isDirectory():
            self.cwd(path)
            for entry in self.list(path, True):
                self.__delete(path, entry)

            self.cwd(root)
            try:
                self.voidcmd("RMD " + name)
            except Exception as e:
                if self.__isErrorCode(e, 'fileUnavailible'):
                    return False
                else:
                    raise
        else:
            self.voidcmd("DELE " + name)



    # Renames a file on remote server
    #
    # @type self: FTPSConnection
    # @type file_path: string
    # @type new_name: string
    #
    # @global ftpErrors
    def rename(self, file_path, new_name, forced=False):

        try:
            is_dir = os.path.isdir(file_path)
            dirname = os.path.dirname(file_path)
            path = self._getMappedPath(dirname)
            base = os.path.basename(file_path)

            try:
                self.cwd(path)
            except Exception as e:
                if self.__isErrorCode(e, 'fileUnavailible'):
                    self.__ensurePath(path)
                else:
                    raise

            if not forced and self.fileExists(new_name):
                raise TargetAlreadyExists("Remote target {" + new_name + "} already exists")

            try:
                self.voidcmd("RNFR " + base)
            except Exception as e:
                if self.__isError(e, 'rnfrExists') or self.__isError(e, 'rntoReady'):
                    self.voidcmd("RNTO " + new_name)
                    return
                elif self.__isError(e, 'cwdNoFileOrDirectory') or self.__isError(e, 'fileNotExist'):
                    if is_dir:
                        self.__ensurePath( path + '/' + new_name, True )
                    else:
                        self.put(file_path, new_name)
                    return
                else:
                    raise

            try:
                self.voidcmd("RNFR " + base)
            except Exception as e:
                if (self.__isError(e, 'rnfrExists') and str(e).find('Aborting previous')) or self.__isError(e, 'rntoReady'):
                    self.voidcmd("RNTO " + new_name)
                    return
                else:
                    raise

            self.voidcmd("RNTO " + new_name)

        except Exception as e:

            # disconnected - close itself to be refreshed
            if self.__isError(e, 'disconnected') is True:
                self.close()
                raise
            # other exception
            else:
                raise


    # Changes a current path on remote server
    #
    # @type self: FTPSConnection
    # @type path: string
    def cwd(self, path):
        self._makePassive()
        self.connection.cwd((path))


    # Returns whether it provides true last modified mechanism
    def hasTrueLastModified(self):
        return self.__hasFeat("MFMT")


    # Void command without return
    #
    # Passivates if configured to do so
    #
    # @type self: FTPSConnection
    # @type path: string
    def voidcmd(self, command):
        self._makePassive()
        self.connection.voidcmd(self.__encode(command))


    # Plain command with return
    #
    # Passivates if configured to do so
    #
    # @type self: FTPSConnection
    # @type path: string
    def sendcmd(self, command):
        self._makePassive()
        return self.connection.sendcmd(self.__encode(command))


    # Returns whether file or folder info
    #
    # @type self: FTPSConnection
    # @type path: string
    def fileExists(self, path):
        try:
            self._makePassive()
            self.voidcmd("SIZE " + path)

            return True
        except Exception as e:
            if self.__isErrorCode(e, 'fileUnavailible'):
                return False
            else:
                raise


    # Returns a list of content of a given path
    #
    # @type self: FTPSConnection
    # @type file_path: string
    # @type mapped: bool
    # @param mapped: whether it's remote path (True) or not
    #
    # @return list<Metafile>|False
    def list(self, file_path, mapped=False,all=False):

        def action():
            if mapped:
                path = file_path
            else:
                path = self._getMappedPath(file_path)

            path = self.__encode(path)

            if self.config['debug_extras']['debug_remote_paths']:
                print ("FTPSync <debug> list path " + file_path + " => " + str(path))

            contents = []
            result = []

            try:
                self.connection.dir(path, lambda data: contents.append(data))
            except Exception as e:
                if self.__isErrorCode(e, ['ok', 'passive']):
                    self.connection.dir(path, lambda data: contents.append(data))
                elif str(e).find('No such file'):
                    raise FileNotFoundException
                else:
                    raise

            for content in contents:
                try:
                    if self.config['debug_extras']['print_list_result'] is True:
                        print ("FTPSync <debug> LIST line: " + str(content).encode('utf-8'))
                except KeyError:
                    pass

                split = re_ftpListParse.search(content)

                if split is None:
                    continue

                isDir = split.group(1) == 'd'
                permissions = split.group(2)
                filesize = split.group(3)
                lastModified = split.group(4)
                name = split.group(5)

                if all is True or (name != "." and name != ".."):
                    data = Metafile(name, isDir, self.__parseTime(lastModified) + int(self.config['time_offset']), filesize, os.path.normpath(path).replace('\\', '/'), permissions)
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

        self.voidcmd(command)


    # Returns local path for given remote path
    def getLocalPath(self, remotePath, localRoot):
        if remotePath[-1] == '.':
            remotePath = remotePath[0:-1]
        remotePath = remotePath.replace('//', '/')

        path = os.path.join(localRoot, os.path.relpath(remotePath, self.config['path']))

        return os.path.normpath(path)


    # Returns normalized path in unix style
    def getNormpath(self, path):
        return os.path.normpath(path).replace('\\', '/').replace('//', '/')


    # Encodes a (usually filename) string
    #
    # @type self: FTPSConnection
    # @type filename: string
    #
    # @return encoded string
    def __encode(self, string):
        if sys.version[0] == '3':
            if hasattr(string, 'decode'):
                return string.decode('utf-8')
            else:
                return string

        if self.config['encoding'].lower() == 'auto':
            if self.__hasFeat("UTF8"):
                return string.encode('utf-8')
            else:
                return string
        else:
            return string.encode(self.config['encoding'])


    # Loads availible features
    #
    # @type self: FTPSConnection
    def __loadFeat(self):
        try:
            feats = self.connection.sendcmd("FEAT").split("\n")
            self.feat = []
            for feat in feats:
                if feat[0] != '2':
                    self.feat.append( feat.strip() )
        except Exception as e:
            self.feat = []


    # Returns whether server supports a certain feature
    #
    # @type self: FTPSConnection
    def __hasFeat(self, feat):
        if self.feat is None:
            self.__loadFeat()

        return (feat in self.feat)


    # Executes an action while handling common errors
    #
    # @type self: FTPSConnection
    # @type callback: callback
    #
    # @return unknown
    def __execute(self, callback):
        result = None
        try:
            result = callback()
            return result
        except Exception as e:

            # bad write - repeat command
            if re_errorOk.search(str(e)) is not None:
                print ("FTPSync > " + str(e))
                return result
            elif str(e).find(sslErrors['badWrite']) != -1:
                return callback()
            # disconnected - close itself to be refreshed
            elif self.__isError(e, 'disconnected') is True:
                self.close()
                raise
            # timeout - retry
            elif self.__isError(e, 'timeout') is True:
                return callback()
            # other exception
            else:
                raise


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
        for month in months:
            time_val = time_val.replace(month, months[month])

        if time_val.find(':') is -1:
            time_val = time_val + str(" 00:00")
            time_val = re_whitespace.sub(" ", time_val)
            struct = time.strptime(time_val, "%m %d %Y %H:%M")
        else:
            time_val = str(currentYear) + " " + time_val
            time_val = re_whitespace.sub(" ", time_val)
            struct = time.strptime(time_val, "%Y %m %d %H:%M")

        return time.mktime(struct)


    # Unix timestamp to FTP time
    #
    # @type self: FTPSConnection
    # @type: timestamp: integer
    #
    # @return formatted time
    def __encodeTime(self, timestamp):
        time = datetime.datetime.fromtimestamp(timestamp)
        return time.strftime(ftpTimeFormat)


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

        if type(error) is list:
            for err in error:
                if int(code.group(0)) == ftpError[err]:
                    return True
            return False
        else:
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


    # Whether in debug mode
    #
    # @type self: FTPSConnection
    #
    # @return boolean
    def __isDebug(self):
        return True


    # Returns base name
    #
    # @type self: FTPSConnection
    # @type remote_path: string
    # @param remote_path: remote file path
    #
    # @return string
    #
    # @global trailingSlash
    def __basename(self, remote_path):
        if remote_path is None:
            return

        return trailingSlash.sub("", remote_path).split("/")[-1]


    # Ensures the given path is existing and accessible
    #
    # @type self: FTPSConnection
    # @type path: string
    def __ensurePath(self, path, isFolder=False):
        self.connection.cwd(self.config['path'])

        relative = os.path.relpath(path, self.config['path'])
        relative = self._postprocessPath(relative)

        folders = relative.split("/")
        if 'debug_extras' in self.config and 'print_ensure_folders' in self.config['debug_extras'] and self.config['debug_extras']['print_ensure_folders'] is True:
            print (relative, folders)

        index = 0
        for folder in folders:
            index += 1

            try:
                if index < len(folders) or (isFolder and index <= len(folders)):
                    self.cwd(folder)
            except Exception as e:
                if self.__isErrorCode(e, 'fileUnavailible'):

                    try:
                        # create folder
                        self.connection.mkd(self.__encode(folder))
                    except Exception as e:
                        if self.__isErrorCode(e, 'fileUnavailible'):
                            # not proper permissions
                            self.chmod(folder, self.config['default_folder_permissions'])
                        else:
                            raise

                    # move down
                    self.cwd(folder)
                else:
                    raise

        self.cwd(self.config['path'])

