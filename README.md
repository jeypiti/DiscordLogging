# DiscordLogging

A lightweight handler for the logging module that emits log records to a Discord webhook.

### Installation

To install this package with `pip`, run the following command:

```shell
$ pip install git+https://github.com/jeypiti/DiscordLogging.git
```

### Usage

**Basic Usage**

Example usage to only send records of [level](https://docs.python.org/3/library/logging.html#logging-levels) `logging.ERROR` or above to the Discord webhook:

```py
import logging
import discord_logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

discord_handler = discord_logging.DiscordWebhookHandler("<webhook url>")
discord_handler.setLevel(logging.ERROR)

logger.addHandler(discord_handler)

logger.error("Test")
```

You can also attach logging [formatters](https://docs.python.org/3/library/logging.html#formatter-objects) and [filters](https://docs.python.org/3/library/logging.html#filter-objects) as usual with

```py
import logging


formatter = logging.Formatter(...)
filter = CustomFilter(...)  # self-defined filter class

discord_handler.setFormatter(formatter)
discord_handler.addFilter(filter)
```

**Rate Limits**

Discord webhooks are subject to [rate limits](https://ptb.discord.com/developers/docs/topics/rate-limits). The handler keeps track of when it last sent a request to the webhook to ensure that these limits will not be reached. This can be configured during initialization via the `min_emit_interval` argument:

```py
discord_handler = discord_logging.DiscordWebhookHandler("<webhook url>", min_emit_interval=2.0)
```

Here we would send a message to Discord at most every two seconds (default: 1 second).

The handler maintains and internal queue of records that still need to be sent out. This queue will be flushed the next time a message is sent out to the webhook.

*Note:* You may remove this artificial limitation of the send rate by setting `min_emit_interval=0.`. If the webhook quota is temporarily used up, the handler will go to sleep until quota is available again. This behavior may lead to problems depending on your use case.
