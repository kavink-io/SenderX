from app.engine.retry_manager import RetryManager


for retry_count in range(4):

    result = RetryManager.get_retry_status(retry_count)

    print(result)