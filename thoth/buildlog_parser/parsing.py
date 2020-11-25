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
"""Thoth's build logs parser."""
import json
import logging
import re

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import yaml

_LOGGER = logging.getLogger(__name__)

# Based on micropipenv
_PIPFILE_LOCK_START = "---------------------------------- Pipfile.lock ----------------------------------"
_PIPFILE_LOCK_END = _PIPFILE_LOCK_START
# Thoth's config start string
_THOTH_CONFIG_START_STR = ">>> Thoth's configuration file after hardware and software discovery:"
_THOTH_CONFIG_END_STR = ">>> "
# Installation process start string
_INSTALLATION_START = _PIPFILE_LOCK_START
_S2I_BUILDER_IMAGE_RE = re.compile(r"Using (\S+) as the s2i builder image")
_S2I_RESULTING_IMAGE_RE = re.compile(r"Pushing image (\S+) \.\.\.")
_PUSH_SUCCESSFUL = "Push successful"
_THAMOS_VERSION_RE = re.compile(r".*Thamos version: '(\S+)'$")
_PROVENANCE_CHECK_RUN = ">>> Asking Thoth for provenance check..."
_ADVISER_RUN = ">>> Asking Thoth for advise..."
# pip's installation messages
_PIP_COLLECTING_RE = re.compile(r"^Collecting (\S+)==(\S+) \(.*")
_PIP_DOWNLOADING_RE = re.compile(r".*Downloading (\S+)( \((\S+)\))?")
_PIP_SUCCESSFULLY_INSTALLED_START_STR = "Successfully installed "
_MICROPIPENV_INSTALL_FAILED_RE = re.compile(r"Failed to install '\S+', will try in next installation round...")
_MICROPIPENV_INSTALL_FAILED_FATAL_RE = re.compile(
    r"Failed to install requirements, dependency '\S+' could not be installed"
)


def _parse_pipfile_lock(output_lines: List[str]) -> Any:
    """Parse Pipfile.lock as printed by micropipenv to stdout."""
    parsing = False
    pipfile_lock_str = ""
    for line in output_lines:
        if not parsing and line == _PIPFILE_LOCK_START:
            parsing = True
            continue

        if parsing and line == _PIPFILE_LOCK_END:
            break

        if parsing:
            pipfile_lock_str += line
    else:
        _LOGGER.warning("No Pipfile.lock found in the logs")
        return None

    if not pipfile_lock_str:
        _LOGGER.warning("Empty Pipfile.lock string representing Pipfile.lock, giving up")
        return None

    try:
        return json.loads(pipfile_lock_str)
    except Exception as exc:
        _LOGGER.warning(f"Failed to parse Pipfile.lock: {str(exc)}")
        return None


def _parse_thoth_config(output_lines: List[str]) -> Any:
    """Parse Thoth's configuration file out of the log."""
    parsing = False
    thoth_config = []
    for line in output_lines:
        if not parsing and line == _THOTH_CONFIG_START_STR:
            parsing = True
            continue

        if parsing:
            if line.startswith(_THOTH_CONFIG_END_STR):
                break

            thoth_config.append(line)
    else:
        _LOGGER.warning("No Thoth configuration file parsed out of log")
        return None

    if not thoth_config:
        _LOGGER.warning("Parsed Thoth configuration is empty")
        return None

    config = "\n".join(thoth_config)
    try:
        return yaml.safe_load(config)
    except yaml.parser.ParserError:
        _LOGGER.warning("Failed to parse Thoth's configuration as YAML")
        return config


def _parse_installation(output_lines: List[str]) -> List[Dict[str, Any]]:
    """Parse what packages were installed."""
    installed = []
    parsing = False
    lines = iter(output_lines)
    for line in lines:
        if not parsing and line == _PIPFILE_LOCK_END:
            parsing = True

        matched_collecting = _PIP_COLLECTING_RE.fullmatch(line)
        if matched_collecting:
            package_entry: Dict[str, Any] = {
                "artifact": None,
                "artifact_size": None,
                "installation_log": None,
                "is_successful": None,
                "is_wheel": None,
                "package_name": matched_collecting.group(1),
                "package_version": matched_collecting.group(2),
            }
            installation_lines = []
            while True:
                line = next(lines)
                installation_lines.append(line)

                downloading_match = _PIP_DOWNLOADING_RE.fullmatch(line)
                if downloading_match:
                    package_entry["artifact"] = downloading_match.group(1)
                    package_entry["artifact_size"] = downloading_match.group(3)
                    package_entry["is_wheel"] = package_entry["artifact"].endswith(".whl")
                    continue

                if line.startswith(_PIP_SUCCESSFULLY_INSTALLED_START_STR):
                    package_entry["is_successful"] = True
                    package_entry["installation_log"] = "\n".join(installation_lines)
                    break
                elif _MICROPIPENV_INSTALL_FAILED_RE.fullmatch(line):
                    # Recoverable failure
                    package_entry["is_successful"] = False
                    package_entry["installation_log"] = "\n".join(installation_lines)
                    break
                elif _MICROPIPENV_INSTALL_FAILED_FATAL_RE.fullmatch(line):
                    # Fatal failure
                    package_entry["is_successful"] = False
                    package_entry["installation_log"] = "\n".join(installation_lines)
                    break

            installed.append(package_entry)

    return installed


def _parse_adviser_id(output_lines: List[str]) -> Optional[str]:
    """Parse adviser id out of the log."""
    for line in output_lines:
        if line.startswith("adviser-"):
            return line

    _LOGGER.warning("No adviser id found")
    return None


def _parse_s2i_builder_image(output_lines: List[str]) -> Optional[Dict[str, Any]]:
    """Parse s2i builder image from the log."""
    for line in output_lines:
        matched = _S2I_BUILDER_IMAGE_RE.fullmatch(line)
        if matched:
            parts = matched.group(1).split("@sha256:", maxsplit=1)
            return {
                "image": parts[0],
                "sha256": parts[1] if len(parts) == 2 else None,
            }

    _LOGGER.warning("No s2i builder image found")
    return None


def _parse_thamos_version(output_lines: List[str]) -> Optional[str]:
    """Parse Thamos version out of the log file."""
    for line in output_lines:
        matched = _THAMOS_VERSION_RE.match(line)
        if matched:
            return matched.group(1)

    _LOGGER.warning("No Thamos version identifier found")
    return None


def _parse_push_destination(output_lines: List[str]) -> Optional[Dict[str, Any]]:
    """Parse the resulting image stream where the image is pushed to."""
    for line in reversed(output_lines):
        match = _S2I_RESULTING_IMAGE_RE.fullmatch(line)
        if match:
            parts = match.group(1).rsplit(":", maxsplit=1)
            result = {
                "image": parts[0],
                "tag": None,
            }

            if "/" not in parts[1]:
                result["tag"] = parts[1]

            return result

    return None


def _parse_push_successful(output_lines: List[str]) -> bool:
    """Check if the given build was successful."""
    for line in reversed(output_lines):
        if line == _PUSH_SUCCESSFUL:
            return True

    return False


def _parse_provenance_check_run(output_lines: List[str]) -> bool:
    """Check if the provenance checks were run."""
    for line in reversed(output_lines):
        if line == _PROVENANCE_CHECK_RUN:
            return True

    return False


def _parse_adviser_run(output_lines: List[str]) -> bool:
    """Check if the adviser was run."""
    for line in output_lines:
        if line == _ADVISER_RUN:
            return True

    return False


def _parse_info(output_lines: List[str]) -> Dict[str, Any]:
    """Parse various metadata out of the build log."""
    return {
        "push_destination": _parse_push_destination(output_lines),
        "push_successful": _parse_push_successful(output_lines),
        "s2i_builder_image": _parse_s2i_builder_image(output_lines),
        "thamos_version": _parse_thamos_version(output_lines),
        "provenance_check_run": _parse_provenance_check_run(output_lines),
        "adviser_run": _parse_adviser_run(output_lines),
    }


def _post_process_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Post-process parsed result, extract relevant information for easy data mining."""
    failures = []
    seen = set()  # Make sure we preserve order across multiple runs.
    for entry in result["installation"]:
        if not entry["is_successful"]:
            failures.append(entry["package_name"])
            seen.add(entry["package_name"])

    recovered = []
    failed = []
    for failure in failures:
        for entry in result["installation"]:
            if failure == entry["package_name"] and entry["is_successful"]:
                recovered.append(failure)
                break
        else:
            failed.append(failure)

    result["recovered"] = recovered
    result["failed"] = failed
    result["installation_successful"] = not failed

    if failed and result["info"]["push_successful"]:
        _LOGGER.error(
            "The container image was pushed even thought there were detected dependencies that were not installed: %r",
            failed,
        )

    return result


def parse(output: str) -> Dict[str, Any]:
    """Parse the given build log."""
    output_lines = output.splitlines()
    result = {
        "failed": [],
        "info": _parse_info(output_lines),
        "installation": _parse_installation(output_lines),
        "installation_successful": None,
        "pipfile_lock": _parse_pipfile_lock(output_lines),
        "recovered": [],
        "thoth_config": _parse_thoth_config(output_lines),
    }
    return _post_process_result(result)
