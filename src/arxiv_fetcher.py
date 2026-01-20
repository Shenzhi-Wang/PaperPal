"""
arXiv API integration module
Responsible for fetching AI-related papers from arXiv
"""

import socket
import urllib.error
from datetime import datetime, timedelta
from typing import Optional

import arxiv
from requests.exceptions import RequestException, SSLError

import config
from src.paper import Paper


class ArxivFetcher:
    """arXiv paper fetcher"""

    def __init__(self, categories: Optional[list[str]] = None):
        """
        Initialize the fetcher

        Args:
            categories: List of arXiv categories to search, defaults to AI-related categories in config
        """
        if categories:
            self.categories = categories
        else:
            from src.preference_manager import get_preference_manager

            pref_manager = get_preference_manager()
            self.categories = (
                pref_manager.get_arxiv_categories() or config.DEFAULT_ARXIV_CATEGORIES
            )
        self.client = arxiv.Client()

    # Extended categories for exhaustive search (broader but manageable)
    EXTENDED_CATEGORIES = [
        # Core AI/ML
        "cs.AI",
        "cs.LG",
        "cs.CL",
        "cs.CV",
        "cs.NE",
        "cs.RO",
        "cs.IR",
        # Other CS
        "cs.HC",
        "cs.MA",
        "cs.CR",
        "cs.DC",
        "cs.SE",
        "cs.DB",
        "cs.SI",
        # Statistics & Math
        "stat.ML",
        "stat.TH",
        "stat.ME",
        "math.OC",
        "math.ST",
        # Electrical Engineering
        "eess.AS",
        "eess.IV",
        "eess.SP",
        "eess.SY",
        # Physics (quantum computing related)
        "quant-ph",
    ]

    def _build_query(
        self,
        start_date: datetime,
        end_date: datetime,
        keywords: Optional[list[str]] = None,
        include_all: bool = False,
    ) -> str:
        """
        Build arXiv search query

        Args:
            start_date: Start date
            end_date: End date
            keywords: Optional keywords to search in title/abstract
            include_all: If True, use extended categories for broader search

        Returns:
            arXiv query string
        """
        # Build category query
        if include_all:
            # Use extended categories for exhaustive search
            categories = self.EXTENDED_CATEGORIES
        else:
            categories = self.categories

        category_query = " OR ".join([f"cat:{cat}" for cat in categories])

        # If keywords provided, add them to the query
        if keywords:
            # Search in title and abstract
            keyword_query = " OR ".join(
                [f'(ti:"{kw}" OR abs:"{kw}")' for kw in keywords]
            )
            return f"({category_query}) AND ({keyword_query})"

        return f"({category_query})"

    def fetch_papers(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = config.MAX_RESULTS,
        keywords: Optional[list[str]] = None,
        include_all: bool = False,
        on_progress: Optional[callable] = None,
    ) -> list[Paper]:
        """
        Fetch papers within specified time range

        Args:
            start_date: Start date
            end_date: End date
            max_results: Maximum number of results
            keywords: Optional keywords to search in title/abstract
            include_all: If True, search across all arXiv categories
            on_progress: Optional callback function(current_count)

        Returns:
            List of Paper objects
        """
        query = self._build_query(
            start_date, end_date, keywords, include_all=include_all
        )

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        papers = []
        raw_count = 0
        try:
            results = self.client.results(search)
            for result in results:
                raw_count += 1
                if on_progress:
                    on_progress(raw_count)

                # Check if paper updated date is within range (use updated instead of published)
                # Because we want papers that were recently submitted or updated
                pub_date = result.published.replace(tzinfo=None)
                updated_date = result.updated.replace(tzinfo=None)

                # Use the more recent date between published and updated
                relevant_date = max(pub_date, updated_date)

                if relevant_date < start_date:
                    # Since results are sorted by submitted date (descending), we can stop
                    break

                if relevant_date > end_date:
                    # Skip papers that are too new (in case of clock skew)
                    continue

                paper = Paper(
                    arxiv_id=result.entry_id.split("/")[-1],
                    title=result.title.replace("\n", " ").strip(),
                    abstract=result.summary.replace("\n", " ").strip(),
                    authors=[author.name for author in result.authors],
                    categories=[cat for cat in result.categories],
                    published=pub_date,
                    updated=updated_date,
                    pdf_url=result.pdf_url,
                    arxiv_url=result.entry_id,
                    primary_category=result.primary_category,
                )
                papers.append(paper)
        except PermissionError as e:
            raise ConnectionError(
                "Network access denied. ArXiv API connection blocked.\n"
                "Possible causes:\n"
                "  1. Firewall or security software blocking Python network access\n"
                "  2. Running in a restricted/sandboxed environment\n"
                "  3. SSL certificate permission issues\n"
                "Please run the script directly in your terminal (not in IDE sandbox)."
            ) from e
        except SSLError as e:
            error_msg = str(e)
            if "permission" in error_msg.lower():
                raise ConnectionError(
                    "SSL Permission Error when connecting to arXiv API.\n"
                    "This usually happens when:\n"
                    "  1. Running in a sandboxed/restricted environment (like Cursor IDE)\n"
                    "  2. Missing SSL certificate permissions\n"
                    "Solution: Run the script directly in your terminal:\n"
                    "  conda activate PaperPal\n"
                    "  python main.py"
                ) from e
            else:
                raise ConnectionError(
                    f"SSL/Certificate error when connecting to arXiv API.\n"
                    f"Possible solutions:\n"
                    f"  1. Check your internet connection\n"
                    f"  2. Verify SSL certificates are properly installed\n"
                    f"  3. If behind a proxy, configure HTTP_PROXY/HTTPS_PROXY\n"
                    f"Error: {error_msg}"
                ) from e
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            error_msg = str(e).lower()
            if "ssl" in error_msg or "certificate" in error_msg:
                raise ConnectionError(
                    "SSL/Certificate error when connecting to arXiv API.\n"
                    "Possible solutions:\n"
                    "  1. Check your internet connection\n"
                    "  2. Verify SSL certificates are properly installed\n"
                    "  3. If behind a proxy, configure HTTP_PROXY/HTTPS_PROXY environment variables"
                ) from e
            else:
                raise ConnectionError(
                    f"Failed to connect to arXiv API.\n"
                    f"Please check your internet connection.\n"
                    f"Error details: {str(e)}"
                ) from e
        except Exception as e:
            error_str = str(e)
            if "permission" in error_str.lower() or "ssl" in error_str.lower():
                raise ConnectionError(
                    f"Network permission or SSL error: {error_str}\n"
                    "Try running directly in your terminal instead of IDE sandbox."
                ) from e
            raise RuntimeError(
                f"An error occurred while fetching from arXiv: {str(e)}"
            ) from e

        return papers

    def fetch_all_papers(
        self,
        start_date: datetime,
        end_date: datetime,
        include_all: bool = False,
        max_results: int = 5000,
        on_progress: Optional[callable] = None,
    ) -> tuple[list[Paper], dict]:
        """
        Fetch all papers within specified time range.

        Args:
            start_date: Start date
            end_date: End date
            include_all: If True, search across all arXiv categories
            max_results: Maximum papers to fetch from API (default 5000)
            on_progress: Optional callback function(current_count)

        Returns:
            Tuple of (List of Paper objects, diagnostic info dict)
        """
        query = self._build_query(
            start_date, end_date, keywords=None, include_all=include_all
        )
        all_papers: list[Paper] = []
        raw_count = 0
        too_old_count = 0
        too_new_count = 0
        first_paper_date = None
        last_paper_date = None

        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        try:
            results = self.client.results(search, offset=0)
            for result in results:
                raw_count += 1
                if on_progress:
                    on_progress(raw_count)

                pub_date = result.published.replace(tzinfo=None)
                updated_date = result.updated.replace(tzinfo=None)
                relevant_date = max(pub_date, updated_date)

                # Track first and last paper dates for diagnostics
                if first_paper_date is None:
                    first_paper_date = relevant_date
                last_paper_date = relevant_date

                # Check if paper is too old
                if relevant_date < start_date:
                    too_old_count += 1
                    # Allow some tolerance - don't break immediately
                    # as date sorting might not be perfect
                    if too_old_count > 100:
                        break
                    continue

                if relevant_date > end_date:
                    too_new_count += 1
                    continue

                paper = Paper(
                    arxiv_id=result.entry_id.split("/")[-1],
                    title=result.title.replace("\n", " ").strip(),
                    abstract=result.summary.replace("\n", " ").strip(),
                    authors=[author.name for author in result.authors],
                    categories=[cat for cat in result.categories],
                    published=pub_date,
                    updated=updated_date,
                    pdf_url=result.pdf_url,
                    arxiv_url=result.entry_id,
                    primary_category=result.primary_category,
                )
                all_papers.append(paper)
        except PermissionError as e:
            raise ConnectionError(
                "Network access denied. ArXiv API connection blocked.\n"
                "Please run the script directly in your terminal (not in IDE sandbox)."
            ) from e
        except SSLError as e:
            error_msg = str(e)
            raise ConnectionError(
                f"SSL/Certificate error when connecting to arXiv API.\n"
                f"Try running in terminal: conda activate PaperPal && python main.py\n"
                f"Error: {error_msg}"
            ) from e
        except (urllib.error.URLError, socket.timeout, ConnectionError) as e:
            raise ConnectionError(
                f"Failed to connect to arXiv API.\n"
                f"Please check your internet connection.\n"
                f"Error details: {str(e)}"
            ) from e
        except arxiv.HTTPError as e:
            raise RuntimeError(
                f"arXiv API returned an error (HTTP {e.status}).\n"
                f"This may be temporary. Please try again in a few minutes.\n"
                f"URL: {e.url}"
            ) from e
        except Exception as e:
            error_str = str(e)
            if "HTTP" in error_str and "500" in error_str:
                raise RuntimeError(
                    f"arXiv API server error (HTTP 500).\n"
                    f"This is usually temporary. Please try again in a few minutes.\n"
                    f"Error: {error_str}"
                ) from e
            raise RuntimeError(
                f"An error occurred while fetching from arXiv: {error_str}"
            ) from e

        # Return papers and diagnostic info
        diag = {
            "raw_count": raw_count,
            "too_old_count": too_old_count,
            "too_new_count": too_new_count,
            "first_paper_date": first_paper_date,
            "last_paper_date": last_paper_date,
            "query": query,
        }
        return all_papers, diag

    def fetch_recent(
        self,
        days: int = 1,
        max_results: int = config.MAX_RESULTS,
        keywords: Optional[list[str]] = None,
    ) -> list[Paper]:
        """
        Fetch papers from recent N days

        Args:
            days: Number of days
            max_results: Maximum number of results
            keywords: Optional keywords to search in title/abstract

        Returns:
            List of Paper objects
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return self.fetch_papers(start_date, end_date, max_results, keywords)


# Helper functions
def fetch_ai_papers(
    start_date: datetime,
    end_date: datetime,
    max_results: int = config.MAX_RESULTS,
) -> list[Paper]:
    """Helper function to fetch AI-related papers"""
    fetcher = ArxivFetcher()
    return fetcher.fetch_papers(start_date, end_date, max_results)


def fetch_recent_ai_papers(
    days: int = 1, max_results: int = config.MAX_RESULTS
) -> list[Paper]:
    """Helper function to fetch recent AI-related papers"""
    fetcher = ArxivFetcher()
    return fetcher.fetch_recent(days, max_results)
