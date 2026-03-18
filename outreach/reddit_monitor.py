"""Reddit monitor for PortfolioForge outreach opportunities.

Watches r/fiaustralia, r/AusFinance, r/AusPropertyChat for posts about SMSF CGT.
Stores matches for manual review — no AI scoring needed, no Anthropic API required.

Workflow:
  1. python -m outreach.reddit_monitor          -- scan and store matches
  2. python -m outreach.reddit_monitor --review  -- review stored matches

Rules (enforced manually):
  - Always answer their question first. Mention PortfolioForge only if directly relevant.
  - Never pitch. Be helpful. Under 150 words.
  - Human approval before posting anything.

Required env: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
"""

from __future__ import annotations

import sys
import time

from loguru import logger
from rich.console import Console
from rich.panel import Panel

from outreach import config, db

SUBREDDITS = ["fiaustralia", "AusFinance", "AusPropertyChat"]

SEARCH_TERMS = [
    "SMSF CGT",
    "capital gains SMSF",
    "CGT calculator",
    "SMSF tax",
    "self managed super capital gains",
    "SMSF capital gains tax",
]

console = Console()


class RedditMonitor:
    def __init__(self) -> None:
        try:
            import praw
        except ImportError:
            raise SystemExit("praw not installed. Run: pip install praw")

        creds = config.reddit_credentials()
        if not creds:
            raise SystemExit(
                "Reddit credentials not set. Add REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, "
                "REDDIT_USERNAME, REDDIT_PASSWORD to .env"
            )

        import praw
        self._reddit = praw.Reddit(
            client_id=creds["client_id"],
            client_secret=creds["client_secret"],
            username=creds["username"],
            password=creds["password"],
            user_agent="PortfolioForge:monitor:v1.0 (by /u/{})".format(creds["username"]),
        )

    def scan(self) -> int:
        """Scan subreddits for relevant posts. Returns count of new matches stored."""
        new_count = 0

        for sub_name in SUBREDDITS:
            subreddit = self._reddit.subreddit(sub_name)

            for term in SEARCH_TERMS:
                try:
                    posts = list(subreddit.search(term, limit=10, sort="new", time_filter="week"))
                except Exception as exc:
                    logger.warning("Reddit search failed '{}' in r/{}: {}", term, sub_name, exc)
                    continue

                for post in posts:
                    url = f"https://reddit.com{post.permalink}"

                    with db.get_conn() as conn:
                        if db.reddit_opportunity_exists(conn, url):
                            continue

                    title = post.title or ""
                    body = getattr(post, "selftext", "") or ""

                    # Store for manual review — no AI scoring
                    with db.get_conn() as conn:
                        db.insert_reddit_opportunity(
                            conn,
                            subreddit=sub_name,
                            post_title=title,
                            post_body=body[:2000],
                            post_url=url,
                            author=str(post.author) if post.author else "unknown",
                            relevance_score=0.0,  # filled in manually during review
                            draft_reply="",  # filled in manually
                        )

                    logger.info("Stored Reddit post from r/{}: {}", sub_name, title[:70])
                    new_count += 1
                    time.sleep(0.5)

        return new_count


def show_reddit_drafts() -> None:
    """Display stored Reddit matches for manual review."""
    with db.get_conn() as conn:
        drafts = db.get_reddit_drafts(conn)

    if not drafts:
        console.print("\n[green]No Reddit posts awaiting review.[/]")
        return

    console.print(f"\n[bold]{len(drafts)} Reddit post(s) to review.[/]")
    console.print("[dim]Bring interesting ones into Claude Code to draft a reply, then post manually.[/]\n")

    for i, opp in enumerate(drafts, 1):
        console.print()
        console.rule(f"[bold cyan]Post {i}/{len(drafts)}[/]")
        console.print(f"[dim]r/{opp['subreddit']}[/]  by u/{opp['author']}")
        console.print(f"\n[bold]{opp['post_title']}[/]")
        if opp["post_body"]:
            console.print(Panel(opp["post_body"][:600], border_style="dim"))
        console.print(f"\n[link={opp['post_url']}]{opp['post_url']}[/link]")

        if opp["draft_reply"]:
            console.print(Panel(opp["draft_reply"], title="Draft Reply", border_style="blue"))

        choice = input("\n[k] keep for later  [r] reject  [q] quit > ").strip().lower()
        with db.get_conn() as conn:
            if choice == "r":
                db.update_reddit_status(conn, opp["id"], "REJECTED")
                console.print("[red]Rejected.[/]")
            elif choice == "q":
                break
            # 'k' leaves it as DRAFT


def run() -> int:
    """Entry point for daily runner. Returns count of new matches found."""
    config.load_env()
    db.init_db()
    try:
        monitor = RedditMonitor()
    except SystemExit as exc:
        logger.warning("Reddit monitor not configured: {}", exc)
        return 0
    return monitor.scan()


if __name__ == "__main__":
    from loguru import logger as _log
    _log.remove()
    _log.add(sys.stderr, level="INFO")
    config.load_env()
    db.init_db()

    if "--review" in sys.argv:
        show_reddit_drafts()
    else:
        try:
            monitor = RedditMonitor()
            n = monitor.scan()
            print(f"\n{n} new Reddit posts stored for review")
            if n > 0:
                print("Run with --review to go through them")
        except SystemExit as exc:
            print(f"Not configured: {exc}")
