
class RetryManager:

    MAX_RETRIES = 3
    BASE_DELAY_SECONDS = 5
    MAX_DELAY_SECONDS = 60

    @classmethod
    def can_retry(cls, retry_count):
        return retry_count < cls.MAX_RETRIES

    @classmethod
    def is_retryable_error(cls, error):

        # Provider errors carry an explicit retry classification.
        if hasattr(error, "retryable"):
            return error.retryable is True

        # Common temporary network errors.
        if isinstance(error, (TimeoutError, ConnectionError)):
            return True

        # Unknown errors are not automatically retried.
        return False

    @classmethod
    def get_retry_delay(cls, retry_count, retry_after=None):
        if retry_after is not None:
            try:
                val = int(retry_after)
                if val > 0:
                    return min(val, cls.MAX_DELAY_SECONDS)
            except (ValueError, TypeError):
                pass

        delay = cls.BASE_DELAY_SECONDS * (2 ** retry_count)
        return min(delay, cls.MAX_DELAY_SECONDS)

    @classmethod
    def get_retry_status(cls, retry_count, retry_after=None):

        if cls.can_retry(retry_count):
            return {
                "success": True,
                "status": "RETRYING",
                "retry_count": retry_count + 1,
                "delay": cls.get_retry_delay(retry_count, retry_after=retry_after)
            }

        return {
            "success": False,
            "status": "DEAD",
            "message": "Maximum retry attempts reached"
        }
