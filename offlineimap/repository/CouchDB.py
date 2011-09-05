# CouchDB repository support
# Copyright (C) 
#    Francois Serman 
#    Theodore Biadala
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program; if not, write to the Free Software
#    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

from dbus import SystemBus
from Base import BaseRepository
from offlineimap import folder
from offlineimap.ui import getglobalui
from couchdb import Server
import time 

class CouchDBRepository(BaseRepository):
    def __init__(self, reposname, account):
        BaseRepository.__init__(self, reposname, account)
        self.reposname = reposname
        self.accountname = account.getname()
        self.dbname = self.getconf("dbname")
        server = Server(self.getconf("server"))
        if self.dbname in server:
            self.db = server[self.dbname]
        else:
            self.db = server.create(self.dbname)

    def getfoldertype(self):
        return folder.CouchDB.CouchDBFolder
    
    def getfolders(self):
        """Returns a list of ALL folders on this server."""
        if not self.accountname in self.db:
          account = {'_id' : self.accountname, 'type' : 'config', 'folders' : ['INBOX']}
          self.db.save(account)
        return [self.getfolder(f) for f in self.db[self.accountname]['folders']]

    def getsep(self):
        return "/"

    def forgetfolders(self):
        """Forgets the cached list of folders, if any.  Useful to run
        after a sync run."""
        pass

    def makefolder(self, foldername):
        account = self.db[self.accountname]
        account['folders'].append(foldername)
        self.db.save(account)
        pass

    def deletefolder(self, foldername):
        account = self.db[self.accountname]
        index = account['folders'].index(foldername)
        del account['folders'][index]
        self.db.save(account)
        pass

    def getfolder(self, foldername):
        return folder.CouchDB.CouchDBFolder(self.db, foldername, self, self.accountname, self.config)
