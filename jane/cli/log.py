# Copyright (c) 2020, Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import logging
import crayons
import sys

SUCCESS = logging.INFO + 5
logging.addLevelName(SUCCESS, "SUCCESS")

LOG_COLORS = {
    logging.CRITICAL: lambda msg: crayons.red(msg, bold=True),
    logging.ERROR: crayons.red,
    logging.WARNING: crayons.yellow,
    SUCCESS: lambda msg: crayons.green(msg, bold=True),
    logging.INFO: crayons.white,
    logging.DEBUG: crayons.blue,
}


class JaneLogger(logging.Logger):
    def success(self, msg, *args, **kwargs):
        if self.isEnabledFor(SUCCESS):
            self._log(SUCCESS, msg, args, **kwargs)


logging.setLoggerClass(JaneLogger)


class ColorFormatter(logging.Formatter):
    def format(self, record: "logging.LogRecord") -> str:
        formatted = super(ColorFormatter, self).format(record)
        return f"{LOG_COLORS[record.levelno](record.levelname)}{formatted}"


console_handler = logging.StreamHandler()
console_handler.setFormatter(ColorFormatter)
logging.root.addHandler(console_handler)


class _EmojiFilter:
    def __init__(self):
        self.emoji_on = sys.platform == "darwin"

    def __call__(self, em: str) -> str:
        return em if self.emoji_on else ""


emoji = _EmojiFilter()
