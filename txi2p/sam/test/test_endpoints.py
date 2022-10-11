# Copyright (c) str4d <str4d@mail.i2p>
# See COPYING for details.

from twisted.internet.error import ConnectionLost, ConnectionRefusedError
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.interfaces import IStreamServerEndpoint
from twisted.python import failure
from twisted.test import proto_helpers
from twisted.trial import unittest

from txi2p.sam import endpoints
from txi2p.sam.session import SAMSession
from txi2p.test.util import FakeEndpoint, FakeFactory, fakeSession


connectionLostFailure = failure.Failure(ConnectionLost())
connectionRefusedFailure = failure.Failure(ConnectionRefusedError())


def sessionOptionsFromNew(cls, **kwargs):
    """
    Create a new session factory and return the value of its ``options``
    attribute.

    :param cls: A class like ``endpoints.SAMI2PStreamClientEndpoint``.

    :return: A ``Deferred`` that fires with the ``options`` value.
    """
    samEndpoint = FakeEndpoint(failure=connectionRefusedFailure)
    endpoint = cls.new(samEndpoint, '', **kwargs)
    if IStreamServerEndpoint.providedBy(endpoint):
        f = endpoint.listen
    else:
        f = endpoint.connect
    d = f(Factory.forProtocol(Protocol))
    d.addErrback(lambda err: err.trap(ConnectionRefusedError))
    d.addCallback(lambda ignored: samEndpoint.factory.options)
    return d


class SAMI2PStreamClientEndpointTestCase(unittest.TestCase):
    """
    Tests for I2P client Endpoint backed by the SAM API.
    """
    endpointClass = endpoints.SAMI2PStreamClientEndpoint

    def test_newWithOptions(self):
        """
        If ``SAMI2PStreamClientEndpoint.new`` is called options then
        ``SessionCreateFactory`` is created with those options.
        """
        options = {'inbound.length': 5, 'outbound.length': 5}
        d = sessionOptionsFromNew(self.endpointClass, options=options)
        self.assertEqual(self.successResultOf(d), options)

    def test_newWithoutOptions(self):
        """
        If ``SAMI2PStreamClientEndpoint.new`` is called without options then
        ``SessionCreateFactory`` is created with an empty options dictionary.
        """
        d = sessionOptionsFromNew(self.endpointClass)
        self.assertEqual(self.successResultOf(d), {})

    def test_samConnectionFailed(self):
        samEndpoint = FakeEndpoint(failure=connectionRefusedFailure)
        endpoint = endpoints.SAMI2PStreamClientEndpoint.new(samEndpoint, '')
        d = endpoint.connect(Factory.forProtocol(Protocol))
        self.failureResultOf(d, ConnectionRefusedError)

    def test_streamConnect(self):
        samEndpoint = FakeEndpoint()
        session = SAMSession()
        session.nickname = 'foo'
        session.samEndpoint = samEndpoint
        session.samVersion = '3.1'
        session.id = 'foo'
        session._autoClose = True
        endpoint = endpoints.SAMI2PStreamClientEndpoint(session, 'foo.i2p')
        endpoint.connect(None)
        self.assertSubstring('HELLO VERSION', samEndpoint.transport.value().decode('utf-8'))



class SAMI2PStreamServerEndpointTestCase(unittest.TestCase):
    """
    Tests for I2P server Endpoint backed by the SAM API.
    """
    endpointClass = endpoints.SAMI2PStreamServerEndpoint

    def test_newWithOptions(self):
        """
        If ``SAMI2PStreamServerEndpoint.new`` is called options then
        ``SessionCreateFactory`` is created with those options.
        """
        options = {'inbound.length': 5, 'outbound.length': 5}
        d = sessionOptionsFromNew(self.endpointClass, options=options)
        self.assertEqual(self.successResultOf(d), options)

    def test_newWithoutOptions(self):
        """
        If ``SAMI2PStreamServerEndpoint.new`` is called without options then
        ``SessionCreateFactory`` is created with an empty options dictionary.
        """
        d = sessionOptionsFromNew(self.endpointClass)
        self.assertEqual(self.successResultOf(d), {})

    def test_samConnectionFailed(self):
        samEndpoint = FakeEndpoint(failure=connectionRefusedFailure)
        endpoint = endpoints.SAMI2PStreamServerEndpoint.new(samEndpoint, '')
        d = endpoint.listen(Factory.forProtocol(Protocol))
        self.failureResultOf(d, ConnectionRefusedError)

    def test_streamListen(self):
        samEndpoint = FakeEndpoint()
        session = SAMSession()
        session.nickname = 'foo'
        session.samEndpoint = samEndpoint
        session.samVersion = '3.1'
        session.id = 'foo'
        session._autoClose = True
        endpoint = endpoints.SAMI2PStreamServerEndpoint(session)
        endpoint.listen(None)
        self.assertSubstring('HELLO VERSION', str(samEndpoint.transport.value()))
