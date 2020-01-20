# Copyright (c) 2020, Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.\
from argparse import ArgumentParser, HelpFormatter
import crayons as c
from typing import Iterable, Optional, TYPE_CHECKING
from textwrap import dedent

if TYPE_CHECKING:
    from argparse import Action, _ArgumentGroup

from jane.cli.log import console_handler, emoji
from jane import PRETTY_VERSION


class JaneHelpFormatter(HelpFormatter):
    def _format_action_invocation(self, action: "Action") -> str:
        return c.green(super()._format_action_invocation(action), bold=True)


parser = ArgumentParser(
    "jane",
    formatter_class=JaneHelpFormatter,
    usage=f"{c.normal('jane', bold=True)} [OPTIONS] COMMAND [ARGS]...",
    description=dedent(
        f"""
    Compile Python scripts to standalone executables with no dependency on 
    a systemwide Python installation.
    """
    ),
)
parser.add_argument(
    "--verbose",
    "-v",
    action="count",
    help="control the verbosity of the output, `-vvv` for max",
)
parser.add_argument(
    "--version", "-V", action="version", version=PRETTY_VERSION
)
parser.add_argument(
    "--emoji",
    choices=["on", "off"],
    help=f"""
    controls whether to show emoji in terminal output. can be used to 
    temporarily override the environment variable JANE_EMOJI, if set
     [default: {['off', 'on'][emoji.emoji_on]}]""",
)


def run():
    parser.parse_args()
