"""Temporary network connectivity checks for DEV troubleshooting."""

import logging
import subprocess


logger = logging.getLogger(__name__)


POSTGRES_TEST_HOST = (
    "phpadgenaidbdev.postgres.database.azure.com"
)

POSTGRES_TEST_PORT = 5432


def run_postgres_telnet_check() -> None:
    """Run a temporary telnet check against the PostgreSQL server."""

    logger.info(
        "Starting PostgreSQL telnet connectivity check. "
        "host=%s port=%s",
        POSTGRES_TEST_HOST,
        POSTGRES_TEST_PORT,
    )

    try:
        result = subprocess.run(
            [
                "timeout",
                "5",
                "telnet",
                POSTGRES_TEST_HOST,
                str(POSTGRES_TEST_PORT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        output = (
            (result.stdout or "")
            + (result.stderr or "")
        ).strip()

        logger.info(
            "PostgreSQL telnet check completed. "
            "host=%s port=%s return_code=%s output=%s",
            POSTGRES_TEST_HOST,
            POSTGRES_TEST_PORT,
            result.returncode,
            output,
        )

    except FileNotFoundError as exc:
        logger.error(
            "Unable to run PostgreSQL telnet check. "
            "Required command is missing: %s",
            exc,
        )

    except Exception:
        logger.exception(
            "Unexpected error while running PostgreSQL telnet check."
        )
