"""Tests for MPQueueHandler - multiprocessing-safe queue handler."""

import logging
import sys
from multiprocessing import Queue
from unittest.mock import MagicMock

import pytest

from appinfra.log.mp import MPQueueHandler


@pytest.fixture
def queue():
    """Create a multiprocessing queue for testing."""
    return Queue()


@pytest.fixture
def handler(queue):
    """Create an MPQueueHandler for testing."""
    return MPQueueHandler(queue)


@pytest.fixture
def log_record():
    """Create a basic log record for testing."""
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/test/file.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
    )


@pytest.mark.unit
class TestMPQueueHandlerInit:
    """Test MPQueueHandler initialization."""

    def test_basic_initialization(self, queue):
        """Test handler initializes with queue."""
        handler = MPQueueHandler(queue)
        assert handler.queue is queue

    def test_inherits_from_handler(self, handler):
        """Test handler inherits from logging.Handler."""
        assert isinstance(handler, logging.Handler)


@pytest.mark.unit
class TestMPQueueHandlerEmit:
    """Test MPQueueHandler.emit() method."""

    def test_emit_puts_record_on_queue(self, handler, queue, log_record):
        """Test emit puts prepared record on queue."""
        handler.emit(log_record)

        result = queue.get(timeout=1)
        assert result.name == "test.logger"
        assert result.levelno == logging.INFO
        assert result.msg == "Test message"

    def test_emit_handles_exception_gracefully(self, handler, log_record):
        """Test emit handles queue errors without raising."""
        handler.queue = MagicMock()
        handler.queue.put_nowait.side_effect = Exception("Queue full")

        # Should not raise
        handler.emit(log_record)

    def test_emit_formats_message_args(self, handler, queue):
        """Test emit formats message with args."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=1,
            msg="Value: %s",
            args=("hello",),
            exc_info=None,
        )

        handler.emit(record)
        result = queue.get(timeout=1)

        assert result.msg == "Value: hello"
        assert result.args is None


@pytest.mark.unit
class TestMPQueueHandlerPrepare:
    """Test MPQueueHandler._prepare() method."""

    def test_prepare_clears_exc_info(self, handler, log_record):
        """Test prepare clears exc_info after formatting."""
        try:
            raise ValueError("test error")
        except ValueError:
            log_record.exc_info = sys.exc_info()

        prepared = handler._prepare(log_record)

        assert prepared.exc_info is None
        assert prepared.exc_text is not None
        assert "ValueError" in prepared.exc_text
        assert "test error" in prepared.exc_text

    def test_prepare_formats_infra_extra_exception(self, handler, log_record):
        """Test prepare handles exception in __infra__extra."""
        try:
            raise RuntimeError("extra exception")
        except RuntimeError as e:
            setattr(log_record, "__infra__extra", {"exception": e, "key": "value"})

            prepared = handler._prepare(log_record)
            extra = getattr(prepared, "__infra__extra")

            assert "exception" not in extra
            assert "exception_formatted" in extra
            assert "RuntimeError" in extra["exception_formatted"]
            assert extra["key"] == "value"

    def test_prepare_preserves_other_infra_attrs(self, handler, log_record):
        """Test prepare preserves __infra__pathnames and __infra__linenos."""
        setattr(log_record, "__infra__pathnames", ["/a.py", "/b.py"])
        setattr(log_record, "__infra__linenos", [10, 20])
        setattr(log_record, "__infra__extra", {"key": "value"})

        prepared = handler._prepare(log_record)

        assert getattr(prepared, "__infra__pathnames") == ["/a.py", "/b.py"]
        assert getattr(prepared, "__infra__linenos") == [10, 20]

    def test_prepare_handles_getMessage_failure(self, handler, log_record):
        """Test prepare handles getMessage failure gracefully."""
        log_record.msg = "Format: %s %s"
        log_record.args = ("only_one",)  # Missing argument

        # Should not raise, just clear args
        prepared = handler._prepare(log_record)
        assert prepared.args is None


@pytest.mark.unit
class TestMPQueueHandlerFormatException:
    """Test exception formatting methods."""

    def test_format_exc_info_with_traceback(self, handler):
        """Test _format_exc_info formats full traceback."""
        try:
            raise ValueError("test")
        except ValueError:
            exc_info = sys.exc_info()
            result = handler._format_exc_info(exc_info)

            assert "ValueError" in result
            assert "test" in result
            assert "Traceback" in result

    def test_format_exc_info_with_none(self, handler):
        """Test _format_exc_info with None exc_info."""
        result = handler._format_exc_info((None, None, None))
        assert result == ""

    def test_format_exception_in_context_current_exception(self, handler):
        """Test _format_exception_in_context with current exception."""
        try:
            raise TypeError("context error")
        except TypeError as e:
            result = handler._format_exception_in_context(e)

            assert "TypeError" in result
            assert "context error" in result
            assert "Traceback" in result

    def test_format_exception_in_context_not_current(self, handler):
        """Test _format_exception_in_context with non-current exception."""
        old_exc = ValueError("old error")

        # No exception context
        result = handler._format_exception_in_context(old_exc)

        assert result == "ValueError: old error"
        assert "Traceback" not in result


@pytest.mark.unit
class TestMPQueueHandlerClose:
    """Test MPQueueHandler.close() method."""

    def test_close_calls_parent_close(self, handler):
        """Test close calls parent class close."""
        handler.close()
        # Should not raise


@pytest.mark.unit
class TestLoggerWithQueue:
    """Test Logger.with_queue() class method."""

    def test_with_queue_creates_logger(self, queue):
        """Test with_queue creates a logger with queue handler."""
        from appinfra.log import Logger

        lg = Logger.with_queue(queue, name="test.worker")

        assert lg.name == "test.worker"
        assert len(lg.handlers) == 1
        assert isinstance(lg.handlers[0], MPQueueHandler)

    def test_with_queue_sets_level(self, queue):
        """Test with_queue sets the log level."""
        from appinfra.log import Logger

        lg = Logger.with_queue(queue, name="test.worker", level="debug")

        assert lg.level == logging.DEBUG

    def test_with_queue_level_string(self, queue):
        """Test with_queue accepts string level."""
        from appinfra.log import Logger

        lg = Logger.with_queue(queue, name="test", level="warning")

        assert lg.level == logging.WARNING

    def test_with_queue_logs_to_queue(self, queue):
        """Test logger created with_queue sends records to queue."""
        from appinfra.log import Logger

        lg = Logger.with_queue(queue, name="test.queue")
        lg.info("test message")

        record = queue.get(timeout=1)
        assert record.msg == "test message"


@pytest.mark.integration
class TestMPQueueHandlerIntegration:
    """Integration tests for MPQueueHandler."""

    def test_full_logging_flow(self, queue):
        """Test complete logging flow through queue handler."""
        logger = logging.getLogger("test.mp.handler")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        handler = MPQueueHandler(queue)
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        logger.info("Test info message")
        logger.warning("Test warning")

        record1 = queue.get(timeout=1)
        record2 = queue.get(timeout=1)

        assert record1.msg == "Test info message"
        assert record1.levelno == logging.INFO
        assert record2.msg == "Test warning"
        assert record2.levelno == logging.WARNING

    def test_exception_logging_flow(self, queue):
        """Test exception is properly captured and formatted."""
        logger = logging.getLogger("test.mp.exc")
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        handler = MPQueueHandler(queue)
        logger.addHandler(handler)

        try:
            raise KeyError("missing key")
        except KeyError:
            logger.exception("Error occurred")

        record = queue.get(timeout=1)

        assert record.exc_info is None  # Cleared
        assert record.exc_text is not None  # Formatted
        assert "KeyError" in record.exc_text
        assert "missing key" in record.exc_text
