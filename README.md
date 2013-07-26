FTPSync
====================
*Addon for Sublime Text 2 and Sublime Text 3*

Simple and free plugin for FTP synchronization. Just hit the _save_ as usual and it's upped.

What's there for you?
* Multiple named upload targets
* Ignored file regex patterns
* Secure transfer using TLS
* Downloading via temporary file (better stability)
* Determining newer remote files, overwrite protection
* Manual multiple file & folder up/downloading (sidebar context menu)
* Multithreaded uploading and downloading
* Local&remote renaming and deleting
* Progress bar for multiple up/download
* Remote browsing and manipulating via file list

**Now Sublime Text 3 compatible**, base commit by Dmitry Loktev!

For more info look into [Wiki](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/_pages)


How to use
----------

To mark a folder and descendants for upload insert **ftpsync.settings** file in following format. Don't worry - the skeleton can be simply inserted using *Preferences > Package Settings > FTPSync > Setup FTPSync in this folder* or using context menu in Side bar or using Control/CMD+Shift+P.

Sample settings file with minimum of options:  
( *does not contain all options* )

     {
        'primary': {
            host: 'ftp.mywebsite.com',
            username: 'johnsmith',
            password: 'secretpassword',
            path: '/www/',

            upload_on_save: true,
            tls: true
        }
    }

Set password to `null` (don't use quotes) if you do not want to store password in a file and set in manually (FTPSync will request the password in such case).

[All connection settings »](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/All-settings)

Files are automatically uploaded **on save** (unless disabled by _upload\_on\_save_=false setting). In your newly created settings file some options are preceded with `//`, this means they are commented out (and default value from global settings file is used) - remove the `//` to enable the entry.


Drawbacks and notes
---------------------

* FTPS is not supported at the moment and is not planned in near future (you can use [SFTP](http://wbond.net/sublime_packages/sftp) or [Mote](https://github.com/SublimeText/Mote) plugins)
* SSL/TLS is not supported for servers that enforce SSL_REUSE
* Does not support continuous watching and syncing, only (after) manual action
* Does not support proxy connections
* Does not support remote diff at the moment


About
-----

Done by **@NoxArt** ~ [Twitter](https://twitter.com/NoxArt)

Released under **MIT licence**.

You can buy me a snack so I have energy for further improvements :)

**[Support FTPSync page](http://ftpsync.noxart.cz/donate.html)**

Feel free to add [issues, ideas](https://github.com/NoxArt/SublimeText2-FTPSync/issues), pull requests...

Thanks to [castus](https://github.com/castus), [tommymarshall](https://github.com/tommymarshall), [TotallyInformation](https://github.com/TotallyInformation), [saiori](https://github.com/saiori), [vnabet](https://github.com/vnabet), [Jcrs](https://github.com/Jcrs), [ItayXD](https://github.com/ItayXD), [bibimij](https://github.com/bibimij), [digitalmaster](https://github.com/digitalmaster), [alfaex](https://github.com/alfaex), [seyDoggy](https://github.com/seyDoggy), Nuno, [mikedoug](https://github.com/mikedoug), [stevether](https://github.com/stevether), [zaus](https://github.com/zaus), [noAlvaro](https://github.com/noAlvaro), [zofie86](https://github.com/zofie86), [fma965](https://github.com/fma965), [PixelVibe](https://github.com/PixelVibe), [Kaisercraft](https://github.com/Kaisercraft), [benkaiser](https://github.com/benkaiser), [anupdebnath](https://github.com/anupdebnath), [sy4mil](https://github.com/sy4mil), [leek](https://github.com/leek), [surfac](https://github.com/surfac), [mitsurugi](https://github.com/mitsurugi), [MonoSnippets](https://github.com/MonoSnippets), [Zegnat](https://github.com/Zegnat), [cwhittl](https://github.com/cwhittl), [shadowsdweller](https://github.com/shadowsdweller), [adiulici01](https://github.com/adiulici01), [tablatronix](https://github.com/tablatronix), [bllim](https://github.com/bllim), [Imaulle](https://github.com/Imaulle), [friskfly](https://github.com/friskfly), [lysenkobv](https://github.com/lysenkobv), [nosfan1019](https://github.com/nosfan1019), [smoochieboochies](https://github.com/smoochieboochies), [Dmitry Loktev](https://github.com/unknownexception), [fedesilvaponte](https://github.com/fedesilvaponte), [fedegonzaleznavarro](https://github.com/fedegonzaleznavarro), [camilstaps](https://github.com/camilstaps), [maknapp](https://github.com/maknapp), [certainlyakey](https://github.com/certainlyakey), [victorhqc](https://github.com/victorhqc), [eniocarv](https://github.com/eniocarv), [molokoloco](https://github.com/molokoloco), [tq0fqeu](https://github.com/tq0fqeu), [Arachnoid](https://github.com/Arachnoid)
for reporting issues, ideas and fixing!

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/NoxArt/SublimeText2-FTPSync/trend.png)](https://bitdeli.com/free "Bitdeli Badge")



Tips
----

* **Set key bindings (hotkeys) for frequent actions you use**

Please edit only `Key Bindings - User`, open using:  
`Preferences > Package Control > FTPSync > Key Bindings - User`  
You can use the contents of `Key Bindings - Default` as a template and copy it there. If you edit `Key Bindings - Default` (either Sublime's or FTPSync's), your changes will be lost on update.  
[More info](https://github.com/NoxArt/SublimeText2-FTPSync/wiki/Key-bindings)

* **Renaming and deleting**

Please keep in mind that for deleting and renaming on server you need to use `FTPSync > Rename` respectively `FTPSync > Delete` features, not those in Sublime Text 2 or SideBarEnhancements.

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
