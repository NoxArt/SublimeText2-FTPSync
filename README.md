SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing.

Supports:
* Multiple named upload targets
* Ignored file regex patterns
* Secured transfer using TLS

To mark a folder and descendants for upload, insert *ftpsync.settings* file in format:

    {
    	<connection_name>: {
    		host: {string},

    		username: {null|string=null}, // null means anonymous manipulation
    		password: {null|string=""},

    		path: {string="/"}, // remote root for these files

    		port: {int=21},
    		tls: {bool=false}, // use secured transfer
    		timeout: {int=30}, // seconds to invalidate the cached connection
    		ignore: {null|string}, // regular expression, matched against file path

    		constrains: {list=[]} // * not implemented yet *
    	}
    }

You can create such file using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

Files are automatically uploaded on save.

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

**@NoxArt**