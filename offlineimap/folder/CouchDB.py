# CouchDB db support
# Copyright (C)
#    Theodore Biadala
#    Francois Serman
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

from Base import BaseFolder
from time import time
from base64 import b64encode

class CouchDBFolder(BaseFolder):
    def __init__(self, db, name, repository, accountname, config):
        self.db = db
        self.name = name
        self.repository = repository
        self.accountname = accountname
        self.config = config
        self.messagelist = None
        self.cachemessagelist()
        BaseFolder.__init__(self)

    def mailToCouch(self, uid, content, flags, mailbox, account):
        message = {
            "type": "email",
            "meta": {
                "uid": uid,
                "account": account,
                "mailbox": mailbox,
                "fetched": time(),
                "flags": flags
            },
            "_attachments": {
                "raw.eml": {
                    "content_type": "message/rfc822",
                    "data": b64encode(content)
                }
            }
        }
        return message

    def getaccountname(self):
        return self.accountname

    def getuidvalidity(self):
        """Maildirs have no notion of uidvalidity, so we just return a magic
        token."""
        return 42

    def quickchanged(self, statusfolder):
        """Returns True if the list has changed"""
        self.cachemessagelist()
        # Folder has different uids than statusfolder => TRUE
        if sorted(self.getmessageuidlist()) != \
                sorted(statusfolder.getmessageuidlist()):
            return True
        # Also check for flag changes, it's quick on a Maildir
        for (uid, message) in self.getmessagelist().iteritems():
            if message["meta"]['flags'] != statusfolder.getmessageflags(uid):
                return True
        return False  #Nope, nothing changed

    def cachemessagelist(self):
        tmpList = {}
        if self.messagelist is None:
            msgList = self._couchdbview(self.name)

            for row in msgList:
              tmpList[row["value"]["uid"]] = row["value"]
            self.messagelist = tmpList

    def getmessagelist(self):
        return self.messagelist

    def _couchdbview(self, name):
        if not "_design/CouchDBFolder" in self.db:
            view = {
                "_id" : "_design/CouchDBFolder",
                "views": {
                    "messagelist" : {
                        "map":
"""function(doc) {
    if (doc.type === "email") {
        emit([doc.meta.account, doc.meta.mailbox], {
            "_id": doc._id,
            "uid": doc.meta.uid,
            "flags": doc.meta.flags.sort()
        });
    }
}"""
                    }
                }
            }
            self.db.save(view)
        view = self.db.view("CouchDBFolder/messagelist", key=[self.accountname, name])
        return view

    def getmessage(self, uid):
        attachment = self.db.get_attachment(self.messagelist[uid]['_id'], 'raw.eml')
        return attachment.read()

    def getmessagetime(self, uid):
        try:
            message = self.db[self.messagelist[uid]['_id']]
            rtime = message["meta"]["last_modified"]
        except:
            rtime = None
        return rtime

    def savemessage(self, uid, content, flags, rtime):
        self.ui.debug('couchdb', 'savemessage: called to write with flags %s and uid %s' % \
                 (repr(flags), repr(uid)))

        if uid < 0:
            # We cannot assign a new uid.
            return uid
        if uid in self.messagelist or content == None:
            # We already have it.
            self.savemessageflags(uid, flags)
            return uid

        message = self.mailToCouch(uid, content, flags, self.name, self.accountname)
        self.db.save(message)
        self.messagelist[uid] = {
            'uid': uid,
            '_id': message['_id'],
            'flags': flags
        }
        return uid

    def getmessageflags(self, uid):
        return self.messagelist[uid]['flags']

    def savemessageflags(self, uid, flags):
        doc = self.db.get(self.messagelist[uid]['_id'])
        doc["meta"]["flags"] = flags
        doc["meta"]["last_modified"] = time.time()
        self.db.save(doc)

    def deletemessage(self, uid):
        if not uid in self.messagelist:
            return
        doc = self.db.get(self.messagelist[uid]['_id'])
        self.db.delete(doc)
        del self.messagelist[uid]
