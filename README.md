SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing.

Todo:
* Need to solve multiple connections when downloading, uses the first successful one for the moment

Recent:
* **Fixed issue #7 (with ports and possibly usernames)**
* Fixed forced downloading
* More refactoring, optimizations, fixes
* Download only downloads new content or with different filesize, added _forced_ variant
* Added loaded config verification

Supports:
* Multiple named upload targets
* Ignored file regex patterns
* Secure transfer using TLS
* Manual multiple file & folder uploading (sidebar context menu)
* Manual multiple file & folder downloading (sidebar context menu)

Current focus:
* Remote vs local file _last\_updated_ detection
* Resolving downloading from more locations
* SFTP support

To mark a folder and descendants for upload insert *ftpsync.settings* file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

    {
    	<connection_name>: {
    		host: {string},

    		username: {null|string=null}, // null means anonymous manipulation
    		password: {null|string=""},

    		path: {string="/"}, // remote root for these files

            upload_on_save: true, // whether upload on save or manually

    		port: {int=21},
    		tls: {bool=false}, // use secured transfer
    		timeout: {int=30}, // seconds to invalidate the cached connection
    		ignore: {null|string}, // regular expression, matched against file path - not applied for downloading
    	} //,
        // <connection2_name>: { ... }
    }

Files are automatically uploaded on save (unless disabled by setting).

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

**@NoxArt**


Thanks [castus](https://github.com/castus), [tommymarshall](https://github.com/tommymarshall), [TotallyInformation](https://github.com/TotallyInformation), [saiori](https://github.com/saiori), [vnabet](https://github.com/vnabet) and [Jcrs](https://github.com/Jcrs) for reporting issues, ideas and fixing!


Tips
----

* **Upload different language versions to different servers of paths**

        {
        	<connection_name>: {
        		host: "ftp.host.en.com",
        		ignore: "/locale/(?!fr)\\w+/.*"
        	},
        	<connection2_name>: {
        		host: "ftp.host.cz.com",
        		ignore: "/locale/(?!cz)\\w+/.*"
        	}
        }