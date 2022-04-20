from logging import Handler, LogRecord
from time import monotonic, sleep
from typing import Final

import requests


class DiscordWebhookHandler(Handler):
    def __init__(self, webhook_url: str, emit_interval: float = 1.0, timeout: float = 5.0):
        """Initialize a logging handler that posts to a Discord webhook.

        :param webhook_url: URL of the webhook.
        :param emit_interval: The minimum interval between emits in seconds.
        :param timeout: The duration after which the webhook requests time out.
        """

        super().__init__()
        self.url: Final[str] = webhook_url

        self.interval: Final[float] = emit_interval
        self.timeout: Final[float] = timeout
        self.last_emit: float = 0

        self.queue: list[LogRecord] = []

    def post_webhook(self, content: str) -> bool:
        """
        Post content to the webhook, retrying on rate limit errors for a maximum
        of `timeout` seconds.

        :param content: Content to be posted to the webhook.
        :return: Whether the post request was successful.
        :raises requests.HTTPError: If there are non-recoverable HTTP errors, most
            likely due to bad configuration.
        """

        if not content:
            return True

        start_time = monotonic()

        # send as normal message if content length doesn't exceed Discord's limits
        # 1994 characters to account for triple backticks
        if len(content) <= 1994:
            kwargs = {"data": {"content": f"```{content}```"}}

        # send as file otherwise
        else:
            kwargs = {"files": {"file": ("content.log", content.encode())}}

        try:
            resp = requests.post(self.url, timeout=self.timeout, **kwargs)
        except (requests.ConnectionError, requests.Timeout):
            return False

        # attempt retries if post wasn't successful
        while resp.status_code != 204:

            # abort if not a transient error
            if resp.status_code not in {429, 502}:
                raise requests.HTTPError(
                    f"{resp.status_code} HTTP Error: {resp.reason} for webhook {self.url}",
                    response=resp,
                )

            sleep_duration = float(resp.headers.get("x-ratelimit-reset-after", 2))

            # return if timeout would be exceeded after sleep
            if monotonic() - start_time + sleep_duration > self.timeout:
                return False

            sleep(sleep_duration)
            try:
                resp = requests.post(self.url, timeout=self.timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                return False

        return True

    def emit(self, record: LogRecord) -> None:
        """
        Handles emission of log records. If no record has been emitted within the
        interval specified at handler initialization, attempt to post queue contents
        and current record to webhook. Otherwise append record to internal queue.

        If the post times out, leave queue intact and carry on.

        :param record: Log record to emit.
        """

        now = monotonic()

        if self.last_emit + self.interval > now:
            self.queue.append(record)
            return

        queue_content = "\n".join(self.format(queued_record) for queued_record in self.queue)
        success = self.post_webhook(f"{queue_content}\n{self.format(record)}")

        self.last_emit = now
        if success:
            self.queue.clear()
        else:
            self.queue.append(record)

    def flush(self) -> None:
        """Post queue contents to the webhook and clear queue if successful."""
        queue_content = "\n".join(self.format(queued_record) for queued_record in self.queue)
        success = self.post_webhook(queue_content)

        if success:
            self.queue.clear()
