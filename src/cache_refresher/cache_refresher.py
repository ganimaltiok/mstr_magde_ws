import logging
from typing import Iterable, Optional

from cache_refresher.full_report_refresher import refresh_full_reports

logger = logging.getLogger(__name__)


def refresh_daily_caches(report_names: Optional[Iterable[str]] = None):
    """
    Refresh Redis entries for reports configured with the ``daily`` cache policy.

    Args:
        report_names: Optional iterable of report identifiers. When omitted,
            every report flagged for daily caching is refreshed.

    Returns:
        The metadata summary returned by ``refresh_full_reports``.
    """
    scope = "selected reports" if report_names else "all daily reports"
    logger.info("Starting cache refresh for %s.", scope)
    summary = refresh_full_reports(report_names=report_names)

    if summary.get("refreshed"):
        logger.info("Refreshed %d report caches.", len(summary["refreshed"]))
    if summary.get("errors"):
        logger.warning("Encountered errors for: %s", ", ".join(summary["errors"].keys()))
    if summary.get("skipped"):
        logger.info("Skipped: %s", ", ".join(summary["skipped"].keys()))

    logger.info("Cache refresh completed for %s.", scope)
    return summary


def main() -> None:
    refresh_daily_caches()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
