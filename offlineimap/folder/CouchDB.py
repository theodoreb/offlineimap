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

import socket
import time
import re
import os
import sys, mimetypes
import email
from Base import BaseFolder
from email.Header import decode_header
from email.Parser import Parser as EmailParser
from email.utils import parseaddr, getaddresses
from base64 import b64decode, b64encode
from StringIO import StringIO
from datetime import datetime
import json


def parse_attachment(message_part, idx):
    content_disposition = message_part.get("Content-Disposition", None)
    if content_disposition:
        dispositions = content_disposition.strip().split(";")
        if bool(content_disposition and dispositions[0].lower() in ["attachment", "inline"]):

            content_type = message_part.get_content_type()
            data = message_part.get_payload(decode=True)

            filename = message_part.get_filename()

            if not filename:
              ext = mimetypes.guess_extension(content_type)
              if not ext:
                ext = ".bin"
              filename = "part-%03d%s" % (idx, ext)

            if data:
              return {
                  "filename" : filename,
                  "data" : {
                    "content_type" : content_type,
                    "data" : b64encode(data)
                    }
                }
    return None

def get_headers(msg):
    fields = {
      "from" : None,
      "subject" : None,
    }
    keys = [s.lower() for s in set(msg.keys())]
    emailaddr = ["to", "cc", "bcc"]
    decode = ["from", "sender", "reply-to", "date", "subject", "message_id"]
    for key in keys:
        if key in emailaddr:
          fields[key] = map(header_decode, msg.get_all(key, []))
        elif key in decode:
          fields[key] = header_decode(msg.get(key, ""))
    return fields

def header_decode(raw):
    decodefrag = decode_header(raw)
    subj_fragments = []
    for s, enc in decodefrag:
        s = unicode(s, enc or 'ascii', 'replace').encode('utf8', 'replace')
        subj_fragments.append(s)
    return " ".join(subj_fragments)
           
def parseToCouch(content, flags, rtime):
    msgobj = email.message_from_string(content)
    headers = get_headers(msgobj)

    if msgobj["Message-id"] is not None:
      msgid = msgobj["Message-id"]
    else:
      msgid = email.utils.make_msgid()
    msgid = msgid[1:-1]

    message = {
      "message_id" : msgid,
      "type" : "email",
      "meta" : {
        "tags" : [],
        "fetched" : time.time(),
        "last_modified" : time.time(),
        "flags" : flags
      }
    }
    
    filename = "%s.eml" % msgid
    # ajoute le mail original
    attachments = {
        filename : {
            "content_type" : "message/rfc822",
            "data" : b64encode(content)
        }
    }
    body = None
    html = None
    counter = 1
    for part in msgobj.walk():
        attachment = parse_attachment(part, counter)
        if attachment:
            attachments[attachment["filename"]] = attachment["data"]
            counter += 1
        elif part.get_content_type() == "text/plain":
            if body is None:
                body = ""
            body += unicode(
                part.get_payload(decode=True),
                part.get_content_charset() or 'ascii',
                'replace'
            ).encode('utf8','replace')
        elif part.get_content_type() == "text/html":
            if html is None:
                html = ""
            html += unicode(
                part.get_payload(decode=True),
                part.get_content_charset(),
                'replace'
            ).encode('utf8','replace')

    message["_attachments"] = attachments
    message["text"] = {
      "plain" : body,
      "html" : html
    }
    headers.update(message)
    return headers

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
        print repr(mail['message_id'])
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
        self.ui.debug('maildir', 'savemessage: returning uid %s' % message['_id'])
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
