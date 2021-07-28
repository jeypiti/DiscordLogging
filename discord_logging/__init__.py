from logging import Handler, LogRecord
from time import monotonic, sleep
from typing import Optional

import requests


class DiscordWebhookHandler(Handler):
    def __init__(self, webhook_url: str, emit_interval: float = 1.0):
        """Initialize a logging handler that posts to a Discord webhook.

        :param webhook_url: URL of the webhook.
        :param emit_interval: The minimum interval between emits in seconds.
        """

        super().__init__()
        self.url = webhook_url

        self.interval = emit_interval
        self.last_emit: float = 0

        self.queue: list[LogRecord] = []

    def post_webhook(self, content: str, timeout: float = 5.0) -> bool:
        """
        Post content to the webhook, retrying on rate limit errors for a maximum
        of `timeout` seconds.

        :param content: Content to be posted to the webhook.
        :param timeout: Time in seconds after which the operation should be aborted.
        :return: Whether the post request was successful.
        :raises requests.HTTPError: If there are non-recoverable HTTP errors, most
            likely due to bad configuration.
        """

        if not content:
            return True

        # send as normal message if content length doesn't exceed Discord's limits
        # 1994 characters to account for triple backticks
        if len(content) <= 1994:
            kwargs = {"data": {"content": f"```{content}```"}}

        # send as file otherwise
        else:
            kwargs = {"files": {"file": ("content.log", content.encode())}}

        resp = requests.post(self.url, **kwargs)
        start_time = monotonic()

        # attempt retries if post wasn't successful
        while not resp.status_code < 400:

            # abort if not a transient error
            if resp.status_code not in {429, 502}:
                raise requests.HTTPError(
                    f"{resp.status_code} HTTP Error: {resp.reason} for webhook {self.url}",
                    response=resp,
                )

            sleep_duration = float(resp.headers.get("x-ratelimit-reset-after", 2))

            # return if timeout would be exceeded after sleep
            if monotonic() - start_time + sleep_duration > timeout:
                return False

            sleep(sleep_duration)
            resp = requests.post(self.url, **kwargs)

        return True

    def emit(self, record: Optional[LogRecord]) -> None:
        """
        Emits a log record. The log record can be `None`, in which case the queue will
        be flushed.

        :param record: Log record to emit or `None`.
        """

        now = monotonic()

        if record is not None and self.last_emit + self.interval > now:
            self.queue.append(record)
            return

        queue_content = "\n".join(self.format(queued_record) for queued_record in self.queue)
        record_content = self.format(record) if record is not None else ""
        success = self.post_webhook(f"{queue_content}\n{record_content}")

        self.last_emit = now
        if success:
            self.queue.clear()
        else:
            assert record is not None
            self.queue.append(record)

    def flush(self) -> None:
        if self.queue:
            # flush the queue
            self.emit(None)
