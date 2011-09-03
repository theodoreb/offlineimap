# CouchDB db support
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

import time
import os
import email
from Base import BaseFolder
from base64 import b64decode, b64encode

def parseToCouch(content, flags, rtime):
    msgobj = email.message_from_string(content)

    if msgobj["Message-id"] is not None:
      msgid = msgobj["Message-id"]
    else:
      msgid = email.utils.make_msgid()
    msgid = msgid[1:-1]

    message = {
      "message_id" : msgid,
      "type" : "email",
      "meta" : {
        "fetched" : time.time(),
        "flags" : flags
      }
    }
    
    filename = "%s.eml" % msgid
    # ajoute le mail original
    message["_attachments"] = {
        filename : {
            "content_type" : "message/rfc822",
            "data" : b64encode(content)
        }
    }
    return message

class CouchDBFolder(BaseFolder):
    def __init__(self, db, name, repository, accountname, config):
        self.name = name
        self.config = config
        self.messagelist = None
        self.repository = repository
        self.db = db
        self.accountname = accountname
        self.cachemessagelist()
        BaseFolder.__init__(self)

    def getaccountname(self):
        return self.accountname

    def getfullname(self):
        return os.path.join(self.getroot(), self.getname())

    def getuidvalidity(self):
        """Maildirs have no notion of uidvalidity, so we just return a magic
        token."""
        return 42

    def quickchanged(self, statusfolder):
        """Returns True if the Maildir has changed"""
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
            msgList = self.repository.messagelist(self.name)

            for row in msgList:
              tmpList[row["value"]["uid"]] = row["value"]
            self.messagelist = tmpList
            
    def getmessagelist(self):
        return self.messagelist

    def getmessage(self, uid):
        _id = self.messagelist[uid]['_id']
        mail = self.db.get(_id)
        attachment = self.db.get_attachment(mail, '%s.eml' % mail['message_id'])
        return attachment.read()

    def getmessagetime(self, uid):
        messageid = self.messagelist[uid]['_id']
        rec = self.repository.getmessage(messageid)
        try:
            rtime = rec["meta"]["last_modified"]
        except:
            rtime = None 
        return rtime

    def savemessage(self, uid, content, flags, rtime):
        self.ui.debug('couchdb', 'savemessage: called to write with flags %s and content %s' % \
                 (repr(flags), repr(content)))
        
        if uid < 0:
            # We cannot assign a new uid.
            return uid
        if uid in self.messagelist or content == None:
            # We already have it.
            self.savemessageflags(uid, flags)
            return uid

        message = parseToCouch(content, flags, rtime)
        message["_id"] = "%d-%s-%s" % (uid, self.name, message['message_id'])
        message['meta']['uid'] = uid
        message['meta']['mailbox'] = self.name
        message['meta']['account'] = self.accountname
        
        self.repository.savemessage(message)

        self.messagelist[uid] = {'uid': uid, '_id': message['_id'], 'message_id': message['message_id'], 'flags': flags}
        self.ui.debug('couchdb', 'savemessage: returning uid %s' % message['_id'])
        return uid
        
    def getmessageflags(self, uid):
        return self.messagelist[uid]['flags']

    def savemessageflags(self, uid, flags):
        messageid = self.messagelist[uid]['_id']
        self.repository.savemessageflags(messageid, flags)

    def deletemessage(self, uid):
        if not uid in self.messagelist:
            return
        self.repository.deletemessage(self.messagelist[uid]['_id'])
        del(self.messagelist[uid])
