#!/usr/bin/env python3
# thoth-buildlog-parser
# Copyright(C) 2020 Fridolin Pokorny
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
# type: ignore

"""Thoth's build logs."""

import logging
import sys
import time

import click
from thoth.analyzer import print_command_result
from thoth.common import init_logging

from thoth.buildlog_parser import __version__ as analyzer_version
from thoth.buildlog_parser import __title__ as analyzer_name
from thoth.buildlog_parser import parse as do_parse

init_logging()

_LOGGER = logging.getLogger("thoth.build_logs")


def _print_version(ctx: click.Context, _, value: str):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return

    click.echo(analyzer_version)
    ctx.exit()


@click.group()
@click.pass_context
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    envvar="THOTH_BUILDLOG_PARSER_DEBUG",
    help="Be verbose about what's going on.",
)
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    callback=_print_version,
    expose_value=False,
    help="Print adviser version and exit.",
)
@click.option(
    "--metadata",
    type=str,
    envvar="THOTH_BUILDLOG_PARSER_METADATA",
    help="Metadata in a form of a JSON which are used for carrying additional context in Thoth deployment.",
)
def cli(ctx=None, verbose=False, metadata=None):
    """Thoth's build log command line interface."""
    if ctx:
        ctx.auto_envvar_prefix = "THOTH_BUILDLOG_PARSER"

    if verbose:
        _LOGGER.setLevel(logging.DEBUG)

    _LOGGER.debug("Debug mode is on")
    _LOGGER.info("Version: %s", analyzer_version)

    # This value is unused here, but is reported from click context.
    metadata = metadata


@cli.command()
@click.pass_context
@click.option(
    "--input",
    "-i",
    "input_stream",
    type=str,
    envvar="THOTH_BUILDLOG_PARSER_INPUT",
    required=False,
    default="-",
    show_default=True,
    help="A build log to be analyzed.",
)
@click.option("--no-pretty", "-P", is_flag=True, help="Do not print results nicely.")
@click.option(
    "--output",
    "-o",
    type=str,
    envvar="THOTH_BUILDLOG_PARSER_OUTPUT",
    default="-",
    show_default=True,
    help="Output file or remote API to print results to, in case of URL a POST request is issued.",
    metavar="OUTPUT",
)
def parse(
    click_ctx: click.Context, *, output: str, no_pretty: bool = False, input_stream: str,
):
    """Parse the given build log and extract relevant information out of it."""
    parameters = locals()
    parameters.pop("click_ctx")

    if input_stream == "-":
        input_text = sys.stdin.read()
    else:
        with open(input_stream, "r") as input_f:
            input_text = input_f.read()

    duration = time.monotonic()
    result = do_parse(input_text)
    duration = time.monotonic() - duration

    print_command_result(
        click_ctx=click_ctx,
        analyzer=analyzer_name,
        analyzer_version=analyzer_version,
        output=output,
        pretty=not no_pretty,
        duration=duration,
        result=result,
    )

    click_ctx.exit(0)


__name__ == "__main__" and cli()
