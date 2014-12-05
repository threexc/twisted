# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.logger._legacy}.
"""

from time import time
import logging as py_logging

from zope.interface.verify import verifyObject, BrokenMethodImplementation

from twisted.trial import unittest

from twisted.python import context
from twisted.python import log as legacyLog
from twisted.python.failure import Failure

from .._levels import LogLevel
from .._observer import ILogObserver
from .._format import formatEvent
from .._legacy import LegacyLogObserverWrapper
from .._legacy import publishToNewObserver



class LegacyLogObserverWrapperTests(unittest.TestCase):
    """
    Tests for L{LegacyLogObserverWrapper}.
    """

    def test_interface(self):
        """
        L{LegacyLogObserverWrapper} is an L{ILogObserver}.
        """
        legacyObserver = lambda e: None
        observer = LegacyLogObserverWrapper(legacyObserver)
        try:
            verifyObject(ILogObserver, observer)
        except BrokenMethodImplementation as e:
            self.fail(e)


    def test_repr(self):
        """
        L{LegacyLogObserverWrapper} returns the expected string.
        """
        class LegacyObserver(object):
            def __repr__(self):
                return "<Legacy Observer>"

            def __call__(self):
                return

        observer = LegacyLogObserverWrapper(LegacyObserver())

        self.assertEquals(
            repr(observer),
            "LegacyLogObserverWrapper(<Legacy Observer>)"
        )


    def observe(self, event):
        """
        Send an event to a wrapped legacy observer.

        @param event: an event
        @type event: L{dict}

        @return: the event as observed by the legacy wrapper
        """
        events = []

        legacyObserver = lambda e: events.append(e)
        observer = LegacyLogObserverWrapper(legacyObserver)
        observer(event)
        self.assertEquals(len(events), 1)

        return events[0]


    def forwardAndVerify(self, event):
        """
        Send an event to a wrapped legacy observer and verify that its data is
        preserved.

        @param event: an event
        @type event: L{dict}

        @return: the event as observed by the legacy wrapper
        """
        # Send a copy: don't mutate me, bro
        observed = self.observe(dict(event))

        # Don't expect modifications
        for key, value in event.items():
            self.assertIn(key, observed)
            self.assertEquals(observed[key], value)

        return observed


    def test_forward(self):
        """
        Basic forwarding.
        """
        self.forwardAndVerify(dict(foo=1, bar=2))


    def test_system(self):
        """
        Translate: C{"log_system"} -> C{"system"}
        """
        event = self.forwardAndVerify(dict(log_system="foo"))
        self.assertEquals(event["system"], "foo")


    def test_pythonLogLevel(self):
        """
        Python log level is added.
        """
        event = self.forwardAndVerify(dict(log_level=LogLevel.info))
        self.assertEquals(event["logLevel"], py_logging.INFO)


    def test_message(self):
        """
        C{"message"} key is added.
        """
        event = self.forwardAndVerify(dict())
        self.assertEquals(event["message"], ())


    def test_format(self):
        """
        Formatting is translated properly.
        """
        event = self.forwardAndVerify(
            dict(log_format="Hello, {who}!", who="world")
        )
        self.assertEquals(
            legacyLog.textFromEventDict(event),
            b"Hello, world!"
        )


    def test_failure(self):
        """
        Failures are handled, including setting isError and why.
        """
        failure = Failure(RuntimeError("nyargh!"))
        why = "oopsie..."
        event = self.forwardAndVerify(dict(
            log_failure=failure,
            log_format=why,
        ))
        self.assertIdentical(event["failure"], failure)
        self.assertTrue(event["isError"])
        self.assertEquals(event["why"], why)



class PublishToNewObserverTests(unittest.TestCase):
    """
    Tests for L{publishToNewObserver}.
    """

    def setUp(self):
        self.events = []
        self.observer = self.events.append


    def legacyEvent(self, *message, **kw):
        """
        Return a basic old-style event as would be created by L{legacyLog.msg}.

        @param message: a message event value in the legacy event format

        @param kw: additional event values in the legacy event format

        @return: a legacy event
        """
        event = (context.get(legacyLog.ILogContext) or {}).copy()
        event.update(kw)
        event["message"] = message
        event["time"] = time()
        return event


    def test_observed(self):
        """
        The observer should get called exactly once.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(len(self.events), 1)


    def test_message(self):
        """
        An adapted old-style event should format as text in the same way as the
        given C{textFromEventDict} callable would format it.
        """
        def textFromEventDict(event):
            return "".join(reversed(" ".join(event["message"])))

        event = self.legacyEvent("Hello,", "world!")
        text = textFromEventDict(event)

        publishToNewObserver(self.observer, event, textFromEventDict)

        self.assertEquals(formatEvent(self.events[0]), text)


    def test_defaultLogLevel(self):
        """
        Adapted event should have log level of L{LogLevel.info}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(self.events[0]["log_level"], LogLevel.info)


    def test_isError(self):
        """
        If C{"isError"} is set to C{1} on the legacy event, the C{"log_level"}
        key should get set to L{LogLevel.critical}.
        """
        publishToNewObserver(
            self.observer, self.legacyEvent(isError=1), lambda e: u""
        )

        self.assertEquals(self.events[0]["log_level"], LogLevel.critical)


    def test_stdlibLogLevel(self):
        """
        If C{"logLevel"} is set to a standard library logging level on the
        legacy event, the C{"log_level"} key should get set to the
        corresponding level.
        """
        publishToNewObserver(
            self.observer,
            self.legacyEvent(logLevel=py_logging.WARNING),
            lambda e: u""
        )

        self.assertEquals(self.events[0]["log_level"], LogLevel.warn)


    def test_defaultNamespace(self):
        """
        Adapted event should have a namespace of C{"log_legacy"}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(self.events[0]["log_namespace"], "log_legacy")


    def test_system(self):
        """
        The C{"system"} key should get copied to C{"log_system"}.
        """
        publishToNewObserver(self.observer, self.legacyEvent(), lambda e: u"")

        self.assertEquals(
            self.events[0]["log_system"], self.events[0]["system"]
        )