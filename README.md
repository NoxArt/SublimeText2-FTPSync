SublimeText2-FTPSync
====================

Simple and free plugin for FTP syncing. Just hit the _save_ as usual and it's upped.

What's there for you?
* Multiple named upload targets
* Ignored file regex patterns
* Secure transfer using TLS
* Determining newer remote files, overwrite protection
* Manual multiple file & folder up/downloading (sidebar context menu)
* Local&remote renaming
* Progress bar for multiple up/download

Recently
* Mutlithreaded upload and download for much better speed (only used for more files); limit of threads `max_threads = 5` is global and applies to one process
* Added empty shortcuts [wiki entry](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/Key-bindings)
* Fixed Renaming feature
* Added Delete feature (confirm dialogue inspired by [SideBarEnhancements](https://github.com/titoBouzout/SideBarEnhancements))
* Improved dialog features
* Remebered overwrite cancelled state
* Working on handling special characters in file path

**I apologize for slower development at the moment, have a little time spare due to school and work duties.** Trying to fix the bugs though. The project is of course open so anyone is free to contribute improvements/fixes.

For more info look into [Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/_pages)


How to use
----------

To mark a folder and descendants for upload insert *ftpsync.settings* file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

Format:

    {
    	<connection_name>: {
    		host: {string},

    		username: {null|string=null}, // null means anonymous manipulation
    		password: {null|string=""},

    		path: {string="/"}, // your project's root path on the _server_

            upload_on_save: true, // whether upload on save or manually
            download_on_open: false, // checks whether there's a newer remote file on opening a file
            overwrite_newer_prevention: true, // overwrite protection when remote file is newer
            upload_delay: {int=0}, // delays [seconds] upload triggered by upload_on_save

    		port: {int=21}, // remote port, pretty much always 21, unless SFTP
    		tls: {bool=false}, // set true to use secured transfer, recommended! (server needs to support)
            passive: {bool=true}, // whether to use passive or active connection
    		timeout: {int=30}, // [seconds] to invalidate the cached connection
    		ignore: {null|string}, // regular expression, matched against file path - not applied for downloading
            time_offset: {int=0}, // [seconds] to adjust for a different timezone of server

            after_save_watch: {null|list<list<subfolder, filepatter>>=null} // after save watch
            // example: [ [ "code/assets/css", "*.css" ], [ "code/assets/", "*.jpg, *.png, *.gif" ] ]
            // more in Wiki

    	} //,
        // <connection2_name>: { ... }
    }

Files are automatically uploaded **on save** (unless disabled by _upload\_on\_save_=false setting). In your newly created settings file some options are preceded with `//`, this means they are commented out (and default value from global settings file is used) - remove the `//` to enable the entry.



About
-----

Done by **@NoxArt** ~ [Twitter](https://twitter.com/#!/NoxArt)

Released under MIT licence.

Feel free to add issues, ideas, pull requests...

Thanks to [castus](https://github.com/castus), [tommymarshall](https://github.com/tommymarshall), [TotallyInformation](https://github.com/TotallyInformation), [saiori](https://github.com/saiori), [vnabet](https://github.com/vnabet), [Jcrs](https://github.com/Jcrs), [ItayXD](https://github.com/ItayXD), [bibimij](https://github.com/bibimij), [digitalmaster](https://github.com/digitalmaster), [alfaex](https://github.com/alfaex), [seyDoggy](https://github.com/seyDoggy), Nuno, [mikedoug](https://github.com/mikedoug), [stevether](https://github.com/stevether), [zaus](https://github.com/zaus), [noAlvaro](https://github.com/noAlvaro), [zofie86](https://github.com/zofie86), [fma965](https://github.com/fma965), [PixelVibe](https://github.com/PixelVibe), [Kaisercraft](https://github.com/Kaisercraft) and [benkaiser](https://github.com/benkaiser) for reporting issues, ideas and fixing!



Tips
----

* **Renaming and deleting**

Please keep in mind that for deleting and renaming on server you need to use `FTPSync > Rename` and `FTPSync > Delete` features, not those in Sublime Text 2 or SideBarEnhancements.

* **Working from more places? Or in team?**

You can either use *download_on_open=true* to check files upon openning or *FTPSync: Check current file* command to see whether you have the same version as is on all servers. Using *overwrite_newer_prevention* is also recommended (it's actually enabled by default).

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

* **Using file compilation? Want to upload as well?**

You can use *after_save_watch* option to setup files to be watched for change after uploading on save. [Learn how to use in Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/Why-and-how-to-use-afterwatch).