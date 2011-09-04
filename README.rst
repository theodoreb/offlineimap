.. -*- coding: utf-8 -*-


Description
===========

This is a fork to implement a CouchDB backend for offlineimap. 

To use it you need a couchdb server and python-couch v0.8+

The configuration is as follow ::

  [general]
  accounts = TestCouchDB

  [Account TestCouchDB]
  localrepository = Local
  remoterepository = Remote

  [Repository Local]
  type = CouchDB
  dbname = offlineimap
  server = http://localhost:5984/

  [Repository Remote]
  type = IMAP
  remotehost = examplehost
  remoteuser = jgoerzen

You can put several "Account" in the same couchdb database. The view is 
filtered by account name. If you have auth enabled use something like 
`http://user:pass@server:5984` for the `server` variable. DesktopCouch 
support is on the way.

The `CouchDB` type can be used for local or remote repository.

Please refer to upstream for proper documentation on everything else.