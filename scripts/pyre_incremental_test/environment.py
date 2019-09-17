# pyre-strict

import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Container


LOG: logging.Logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CommandOutput:
    return_code: int
    stdout: str
    stderr: str


class EnvironmentException(Exception):
    pass


class Environment(ABC):
    @abstractmethod
    def run(self, working_directory: Path, command: str) -> CommandOutput:
        ...

    def checked_run(
        self,
        working_directory: Path,
        command: str,
        expected_return_codes: Container[int] = (0,),
    ) -> CommandOutput:
        output = self.run(working_directory, command)
        if output.return_code not in expected_return_codes:
            message = (
                f'Running command "{command}" '
                f"under {working_directory} "
                f"returns {output.return_code}.\n"
                f"Stdout = {output.stdout}\n"
                f"Stderr = {output.stderr}"
            )
            raise EnvironmentException(message)
        return output


class SubprocessEnvironment(Environment):
    def run(self, working_directory: Path, command: str) -> CommandOutput:
        LOG.debug(f"Invoking subprocess `{command}` at `{working_directory}`")
        result = subprocess.run(
            command.split(),
            cwd=working_directory,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return CommandOutput(
            return_code=result.returncode, stdout=result.stdout, stderr=result.stderr
        )
