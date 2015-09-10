# Copyright (c) str4d <str4d@mail.i2p>
# See COPYING for details.

import os
from parsley import makeProtocol
from twisted.internet import defer, error
from twisted.python import log

from txi2p import grammar
from txi2p.address import I2PAddress
from txi2p.sam import constants as c
from txi2p.sam.base import SAMSender, SAMReceiver, SAMFactory


class SessionCreateSender(SAMSender):
    def sendSessionCreate(self, style, id, privKey=None, options={}):
        msg = 'SESSION CREATE'
        msg += ' STYLE=%s' % style
        msg += ' ID=%s' % id
        msg += ' DESTINATION=%s' % (privKey if privKey else 'TRANSIENT')
        for key in options:
            msg += ' %s=%s' % (key, options[key])
        msg += '\n'
        self.transport.write(msg)


class SessionCreateReceiver(SAMReceiver):
    def command(self):
        if not (hasattr(self.factory, 'nickname') and self.factory.nickname):
            # All tunnels in the same process use the same nickname
            # TODO is using the PID a security risk?
            self.factory.nickname = 'txi2p-%d' % os.getpid()

        self.sender.sendSessionCreate(
            self.factory.style,
            self.factory.nickname,
            self.factory.privKey,
            self.factory.options)
        self.currentRule = 'State_create'

    def create(self, result, destination=None, message=None):
        if result != c.RESULT_OK:
            self.factory.resultNotOK(result, message)
            return

        self.factory.privKey = destination
        self.sender.sendNamingLookup('ME')
        self.currentRule = 'State_naming'

    def postLookup(self, dest):
        self.factory.sessionCreated(self, dest)


# A Protocol for making a SAM session
SessionCreateProtocol = makeProtocol(
    grammar.samGrammarSource,
    SessionCreateSender,
    SessionCreateReceiver)


class SessionCreateFactory(SAMFactory):
    protocol = SessionCreateProtocol

    def __init__(self, nickname, style='STREAM', keyfile=None, options={}):
        if style != 'STREAM':
            raise error.UnsupportedSocketType()
        self.nickname = nickname
        self.style = style
        self._keyfile = keyfile
        self.options = options
        self.deferred = defer.Deferred(self._cancel)
        self.samVersion = None
        self.privKey = None
        self._writeKeypair = False

    def startFactory(self):
        if self._keyfile:
            try:
                f = open(self._keyfile, 'r')
                self.privKey = f.read()
                f.close()
            except IOError:
                log.msg('Could not load private key from %s' % self._keyfile)
                self._writeKeypair = True

    def sessionCreated(self, proto, pubKey):
        if self._writeKeypair:
            try:
                f = open(self._keyfile, 'w')
                f.write(self.privKey)
                f.close()
            except IOError:
                log.msg('Could not save private key to %s' % self._keyfile)
        # Now continue on with creation of SAMSession
        self.deferred.callback((self.samVersion, self.style, self.nickname, proto, pubKey))


# Dictionary containing all active SAM sessions
_sessions = {}


class SAMSession(object):
    def __init__(self, nickname, samEndpoint, samVersion, style, id, proto, autoClose):
        # User-assigned nickname, can be None
        self.nickname = nickname
        self.samEndpoint = samEndpoint
        self.samVersion = samVersion
        self.style = style
        # SAM Session ID, autogenerated if nickname is None, else nickname
        self.id = id
        self.address = None
        self.proto = proto
        self._autoClose = autoClose
        self._closed = False
        self._streams = []

    def addStream(self, stream):
        if self._closed:
            raise error.ConnectionDone
        self._streams.append(stream)

    def removeStream(self, stream):
        if self._closed:
            raise error.ConnectionDone
        # Streams are only added once they have been established
        if stream in self._streams:
            self._streams.remove(stream)
        if not self._streams and self._autoClose:
            # No more streams, close the session
            self.close()

    def close(self):
        self._closed = True
        self._streams = []
        self.proto.sender.transport.loseConnection()
        del _sessions[self.nickname]


def getSession(nickname, samEndpoint=None, autoClose=False, **kwargs):
    if _sessions.has_key(nickname):
        return defer.succeed(_sessions[nickname])

    if not samEndpoint:
        raise ValueError('A new session cannot be created without an API Endpoint')

    def createSession((samVersion, style, id, proto, pubKey)):
        s = SAMSession(nickname, samEndpoint, samVersion, style, id, proto, autoClose)
        s.address = I2PAddress(pubKey)
        _sessions[nickname] = s
        return s

    sessionFac = SessionCreateFactory(nickname, **kwargs)
    d = samEndpoint.connect(sessionFac)
    # Force caller to wait until the session is actually created
    d.addCallback(lambda proto: sessionFac.deferred)
    d.addCallback(createSession)
    return d
