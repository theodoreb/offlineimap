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
        # reponame, nom du depot dans le fichier de conf
        self.reposname = reposname
        self.account = account
        self.account_name = account.getname()
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
        if not self.account_name in self.db:
          account = {'_id' : self.account_name, 'type' : 'config', 'folders' : ['INBOX']}
          self.db.save(account)
        return [self.getfolder(f) for f in self.db[self.account_name]['folders']]

    def getsep(self):
        return "/"

    def forgetfolders(self):
        """Forgets the cached list of folders, if any.  Useful to run
        after a sync run."""
        pass

    def makefolder(self, foldername):
        account = self.db[self.account_name]
        account['folders'].append(foldername)
        self.db.save(account)
        pass

    def deletefolder(self, foldername):
        account = self.db[self.account_name]
        index = account['folders'].index(foldername)
        del account['folder'][index]
        self.db.save(account)
        pass

    def getfolder(self, foldername):
        return folder.CouchDB.CouchDBFolder(self.db, foldername, self, self.account_name, self.config)
        
    def getmessage(self, uid):
        mail = self.db.get(uid)
        return mail

    def savemessage(self, message):
        self.db.save(message)

    def savemessageflags(self, uid, flags):
        doc = self.db.get(uid)
        doc["meta"]["flags"] = flags
        doc["meta"]["last_modified"] = time.time()
        self.db.save(doc)

    def deletemessage(self, uid):
        doc = self.db.get(uid)
        self.db.delete(doc)

    def messagelist(self, name):
        if not "_design/CouchDBFolder" in self.db:
            view = {
                "_id" : "_design/CouchDBFolder",
                "views": { "messagelist" : {
                    "map": "function(doc) {  emit([doc.meta.account, doc.meta.mailbox], {uid: doc.meta.uid, \"_id\": doc._id, \"message_id\": doc.message_id, flags: doc.meta.flags.sort()});}"} 
                }
            }
            self.db.save(view)
        view = self.db.view("CouchDBFolder/messagelist", key=[self.account_name, name])
        return view
