"""
Gmail SMTP sender for PortfolioForge outreach.

Uses Gmail App Password (no OAuth needed).
Generate one at: myaccount.google.com/apppasswords

Usage:
  python send_outreach.py --preview              # show all initial emails
  python send_outreach.py --preview-followup     # show all follow-up emails
  python send_outreach.py --send 1,3,5           # send initial emails numbered 1, 3, 5
  python send_outreach.py --send all             # send all initial emails
  python send_outreach.py --followup 2,3,4       # send follow-up emails by ID
  python send_outreach.py --followup all         # send all follow-up emails
  python send_outreach.py --preview-susan        # preview Susan reply
  python send_outreach.py --send-susan           # send Susan reply

Set env vars before running:
  export GMAIL_USER="you@gmail.com"
  export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
"""

import argparse
import imaplib
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

DEMO_URL = "https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/"


def get_credentials() -> tuple[str, str]:
    user = os.environ.get("GMAIL_USER")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not password:
        raise SystemExit(
            "Set GMAIL_USER and GMAIL_APP_PASSWORD environment variables first.\n"
            "Generate an app password at: myaccount.google.com/apppasswords"
        )
    return user, password


def send_via_smtp(from_addr: str, password: str, to: str, subject: str, body: str) -> bytes:
    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = smtplib.email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(body, "plain"))
    raw = msg.as_bytes()

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as conn:
        conn.login(from_addr, password)
        conn.sendmail(from_addr, to, raw)

    return raw


def save_to_sent(from_addr: str, password: str, raw_msg: bytes) -> None:
    with imaplib.IMAP4_SSL("imap.gmail.com") as imap:
        imap.login(from_addr, password)
        imap.append("[Gmail]/Sent Mail", "\\Seen", imaplib.Time2Internaldate(time.time()), raw_msg)


# ---------------------------------------------------------------------------
# Initial emails (already sent 2026-03-11)
# ---------------------------------------------------------------------------

EMAILS = [
    {
        "id": 1,
        "firm": "Susan O'Connor Accounting",
        "principal": "Susan",
        "to": "susan@susanoconnoraccounting.com.au",
        "subject": "Australian CGT software built specifically for SMSF accountants",
        "body": """Hi Susan,

I came across your practice while researching SMSF specialists in Perth — 25 years of experience and a Limited AFSL is a rare combination.

I've built a tool called PortfolioForge specifically for accountants like you who spend hours manually calculating CGT for SMSF clients. It ingests broker CSVs directly from CommSec, SelfWealth, Stake, and IBKR, then produces a fully ATO-validated CGT schedule in seconds. FIFO cost basis, 45-day franking rule, SMSF 33.33% discount (ATO s.115-100), and cross-year loss carry-forward.

Output is a clean Word document ready to attach to the client file or lodge with the SMSF annual return.

I validated the engine against the ATO's own published CGT worked examples (Sonya, Mei-Ling, and the multi-parcel FIFO fixture) before I'd trust it near a real client.

I'm currently working with the first few SMSF accountants at $150/portfolio/year.

Would you be open to a 20-minute demo this week?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 2,
        "firm": "The SMSF Accountant",
        "principal": "Diana",
        "to": "diana@thesmsfaccountant.com.au",
        "subject": "CGT calculation tool for SMSF practices — ATO-validated",
        "body": """Hi Diana,

I noticed The SMSF Accountant has been running fixed-fee SMSF services since 2010. That model requires being efficient with time from day one.

I've built PortfolioForge to make CGT compliance faster for exactly that kind of practice. It takes a broker CSV (CommSec, SelfWealth, Stake, IBKR), applies the correct SMSF CGT rules (33.33% discount, mandatory 45-day rule, FIFO with partial lot splitting), and produces a Word document ready for the client file in under a minute.

The engine is validated against ATO published examples, not just "looks about right". Currently pricing at $150/portfolio/year for early-access accountants.

Worth a 20-minute look?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 3,
        "firm": "Grow SMSF",
        "principal": "Kris",
        "to": "contact@growsmsf.com.au",
        "subject": "PortfolioForge — CGT automation for SMSF specialists",
        "body": """Hi Kris,

Your work at Grow SMSF came up while I was looking for people doing serious SMSF-only practices in Australia. Twenty years in the space is a long time.

I've built a tool that tackles CGT calculation directly. PortfolioForge ingests broker CSVs, runs the full SMSF CGT calculation (33.33% discount under ATO s.115-100, 45-day rule always enforced, FIFO cost basis with proper partial lot handling), and exports a clean Word report. The franking credit calculation uses the ATO formula exactly.

I validated it against the ATO's own published fixtures before trusting it near a real fund.

I'm at the stage of working with a small number of SMSF accountants to stress-test it against real portfolios. Happy to offer the first year at no cost in exchange for a proper working session.

Would that be worth 20 minutes of your time?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 4,
        "firm": "A.H. Law Accounting & SMSF Auditing",
        "principal": "Adrian",
        "to": "adrian@law-smsf.com.au",
        "subject": "Automated CGT schedules for SMSF auditors",
        "body": """Hi Adrian,

I found your practice through the Auditors Institute directory. Combining accounting and SMSF auditing in the same firm gives you a sharp view of where CGT errors actually originate.

I've built PortfolioForge to address that upstream problem. It takes broker trade history CSVs and produces a fully auditable CGT schedule: FIFO cost basis, 45-day franking rule, 33.33% SMSF discount, cross-year loss carry-forward, and a line-by-line disposal log. Output is a Word document a trustee or auditor can review directly.

I validated the engine against the ATO's published CGT examples including the multi-parcel FIFO fixture that catches most homemade spreadsheets.

Currently working with early-access accountants at $150/portfolio/year. Would a 20-minute demo be worth your time?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 5,
        "firm": "Adept Super Pty Ltd",
        "principal": "Alice",
        "to": "alice@adeptsuper.com.au",
        "subject": "CGT schedule tool that reduces SMSF audit prep time",
        "body": """Hi Alice,

I came across Adept Super through the Auditors Institute directory. As an independent SMSF auditor, you're well placed to see which CGT schedules are clean and which ones need to be sent back.

I've built PortfolioForge to help the accounting side produce better input for auditors. It ingests CommSec, SelfWealth, Stake, and IBKR CSVs, runs the correct SMSF CGT rules (33.33% discount, mandatory 45-day franking rule, FIFO with partial lot handling), and produces a structured Word document with a full disposal log.

Currently at $150/portfolio/year for early-access users. Would a 20-minute conversation be worth your time?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 6,
        "firm": "Gardiner SMSF Audits",
        "principal": "Andrew",
        "to": "andrewg1502@gmail.com",
        "subject": "SMSF CGT tool — built for auditors to review, not just trustees",
        "body": """Hi Andrew,

I found your listing in the Auditors Institute directory. Running a specialist SMSF audit practice as a sole practitioner in regional NSW means every hour matters.

I've built a CGT calculation tool specifically for the SMSF space called PortfolioForge. It takes broker CSVs, applies correct SMSF rules (33.33% discount, 45-day franking enforcement, FIFO cost basis), and produces a Word document with a full line-by-line disposal log.

Currently $150/portfolio/year for early-access accountants and auditors. Would a quick 20-minute look be useful?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 7,
        "firm": "Kilara Group",
        "principal": "Andrew",
        "to": "aholmes@kilara.com.au",
        "subject": "Automated SMSF CGT reports for regional practices",
        "body": """Hi Andrew,

I came across Kilara Group through the Auditors Institute directory. An integrated accounting, planning, and SMSF practice serving regional NSW and Victoria is exactly the kind of firm I built PortfolioForge for.

PortfolioForge ingests trade history CSVs from major Australian brokers, runs the full SMSF CGT calculation (33.33% discount under ATO s.115-100, mandatory 45-day rule, FIFO with partial lots, cross-year loss carry-forward), and produces a clean Word document. Year-by-year tax summary, full CGT event log, and franking credit totals.

Validated against the ATO's published worked examples. Currently working with early-access accountants at $150/portfolio/year.

Worth a 20-minute demo?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 8,
        "firm": "Wright Evans Partners",
        "principal": "Annette",
        "to": "annette@wepartners.com.au",
        "subject": "SMSF CGT compliance tool — Word doc output, ATO-validated",
        "body": """Hi Annette,

I found Wright Evans Partners through the Auditors Institute directory. An SA practice covering tax, accounting, and specialist SMSF compliance is exactly the audience I built PortfolioForge for.

It takes broker trade CSVs, applies the correct SMSF CGT rules (33.33% discount, mandatory 45-day franking rule, FIFO cost basis with partial lot splitting), and exports a professional Word document ready to attach to the client file.

The engine handles the loss-ordering rule correctly (losses netted against non-discountable gains before the discount is applied), which is the rule most spreadsheets get wrong.

Currently at $150/portfolio/year for early-access practices. Would a 20-minute demo be worth exploring?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 9,
        "firm": "Newcastle Super Audits",
        "principal": "Balaji",
        "to": "Balaji.s@newcastlesuperaudits.com.au",
        "subject": "SMSF CGT schedules designed to make audits faster",
        "body": """Hi Balaji,

I found Newcastle Super Audits through the Auditors Institute directory. A specialist SMSF audit practice in the Hunter region means you've developed a strong sense of what makes a CGT schedule easy or painful to audit.

I've built PortfolioForge to produce schedules that sit on the clean end of that spectrum. It ingests broker CSVs directly, applies SMSF-specific CGT rules (33.33% discount, mandatory 45-day franking rule, FIFO with partial lots), and exports a Word document with a complete, line-by-line disposal log. Every disposal traces to a specific acquisition lot and date.

Currently $150/portfolio/year for early-access users. Worth a 20-minute walkthrough?

Best,
Edan
PortfolioForge
""",
    },
    {
        "id": 10,
        "firm": "Ezzura Tax Advisory",
        "principal": "Audrey",
        "to": "audrey@ezzuratax.com.au",
        "subject": "SMSF CGT automation — ATO-validated, Word doc output",
        "body": """Hi Audrey,

I came across Ezzura Tax Advisory through the Auditors Institute directory. A Fremantle practice specialising in SMSF auditing and taxation advisory is precisely the audience PortfolioForge was built for.

It ingests broker trade history CSVs, runs the correct SMSF CGT calculation (33.33% discount under ATO s.115-100, mandatory 45-day franking rule, FIFO cost basis with partial lot handling), and produces a Word document ready for the client file. Year-by-year tax summary, full CGT event log, and franking credit totals.

I validated the engine against the ATO's own published CGT fixtures, including the multi-parcel FIFO example and the cross-year loss carry-forward scenario.

Currently at $150/portfolio/year for early-access accountants and auditors. Would a 20-minute demo be worth your time?

Best,
Edan
PortfolioForge
""",
    },
]


# ---------------------------------------------------------------------------
# Follow-up emails (to send Monday 2026-03-16, 5 days after first touch)
# IDs match the original EMAILS list. ID 1 (Susan) and ID 6 (Andrew Gardiner)
# are excluded — Susan replied, Andrew declined.
# ---------------------------------------------------------------------------

FOLLOWUPS = [
    {
        "id": 2,
        "firm": "The SMSF Accountant",
        "principal": "Diana",
        "to": "diana@thesmsfaccountant.com.au",
        "subject": "Re: CGT calculation tool for SMSF practices",
        "body": """Hi Diana,

Following up on my note from last week. I've since put a live demo online if you want to see the output before committing any time to a conversation:

{demo_url}

It runs a complete CGT calculation for a sample SMSF portfolio and produces the Word document in under 60 seconds. No install, no login.

If it is not useful for your practice, no problem at all. Happy to hear that too.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 3,
        "firm": "Grow SMSF",
        "principal": "Kris",
        "to": "contact@growsmsf.com.au",
        "subject": "Re: PortfolioForge — CGT automation for SMSF specialists",
        "body": """Hi Kris,

I sent a note last week about PortfolioForge, a CGT tool built for SMSF-only practices.

Since then I've put a live demo online:

{demo_url}

It processes a sample portfolio through the full CGT calculation and downloads a Word report. Takes about 60 seconds to run. Worth a look before deciding if a conversation makes sense.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 4,
        "firm": "A.H. Law Accounting & SMSF Auditing",
        "principal": "Adrian",
        "to": "adrian@law-smsf.com.au",
        "subject": "Re: Automated CGT schedules for SMSF auditors",
        "body": """Hi Adrian,

Following up on my note from last week. I know it is a busy time of year.

I've put a live demo online that shows exactly what the output looks like from the auditor's perspective:

{demo_url}

The CGT event log in the Word document is what I'd value your opinion on most. Each disposal is traced to a specific acquisition lot with the ATO rule stated explicitly. Curious whether that format is actually useful when you're working through a fund's return.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 5,
        "firm": "Adept Super Pty Ltd",
        "principal": "Alice",
        "to": "alice@adeptsuper.com.au",
        "subject": "Re: CGT schedule tool that reduces SMSF audit prep time",
        "body": """Hi Alice,

Quick follow-up from last week. I've put a live demo of PortfolioForge online:

{demo_url}

You can run a full CGT calculation and download the Word report in about 60 seconds. It shows the disposal log format I mentioned. Would be genuinely interested in your view on whether that structure is useful from an audit standpoint.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 7,
        "firm": "Kilara Group",
        "principal": "Andrew",
        "to": "aholmes@kilara.com.au",
        "subject": "Re: Automated SMSF CGT reports for regional practices",
        "body": """Hi Andrew,

Following up from last week. I've put a live demo online so you can see the output without scheduling a call first:

{demo_url}

Select a preset portfolio, click Generate, and the Word document downloads in under a minute. The year-by-year tax summary and CGT event log are both in there.

Happy to walk through it live if the demo raises questions.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 8,
        "firm": "Wright Evans Partners",
        "principal": "Annette",
        "to": "annette@wepartners.com.au",
        "subject": "Re: SMSF CGT compliance tool — Word doc output, ATO-validated",
        "body": """Hi Annette,

Following up from last week. I've now got a live demo online:

{demo_url}

Takes about 60 seconds to run a full CGT calculation and produce the Word document. No install required.

The loss-ordering section of the report is what I'd point an SA compliance specialist to first. It shows exactly how losses are netted before the discount is applied, with the ATO rule cited.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 9,
        "firm": "Newcastle Super Audits",
        "principal": "Balaji",
        "to": "Balaji.s@newcastlesuperaudits.com.au",
        "subject": "Re: SMSF CGT schedules designed to make audits faster",
        "body": """Hi Balaji,

Following up from last week. I've put the live demo online if you want to see what the output looks like before deciding whether a conversation is worth it:

{demo_url}

The disposal log in the Word document traces every CGT event back to a specific acquisition lot and date, with the ATO rule applied stated plainly. Curious whether that format is actually useful from where you sit.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
    {
        "id": 10,
        "firm": "Ezzura Tax Advisory",
        "principal": "Audrey",
        "to": "audrey@ezzuratax.com.au",
        "subject": "Re: SMSF CGT automation — ATO-validated, Word doc output",
        "body": """Hi Audrey,

Following up from last week. I've put a live demo online so you can see the output before committing any time:

{demo_url}

Run a sample SMSF portfolio through the CGT calculation and download the Word document in about 60 seconds. The SMSF-specific rules (33.33% discount, 45-day franking) are all visible in the report alongside the ATO citations.

Best,
Edan
PortfolioForge
""".format(demo_url=DEMO_URL),
    },
]


# ---------------------------------------------------------------------------
# Reply to Susan O'Connor (responded that her software already does CGT)
# ---------------------------------------------------------------------------

SUSAN_REPLY = {
    "to": "susan@susanoconnoraccounting.com.au",
    "subject": "Re: Australian CGT software built specifically for SMSF accountants",
    "body": """Hi Susan,

Thanks for getting back to me. Good to know you are already covered on that front.

Out of genuine curiosity, what are you using? I ask partly because the tools in this space vary a lot in how they handle SMSF-specific rules, and partly because understanding what is already working well for practices like yours helps me figure out where PortfolioForge actually adds value versus where it does not.

If there is ever a situation where you need a second opinion on a calculation or want a quick cross-check on a tricky parcel, feel free to reach out.

Best,
Edan
PortfolioForge
""",
}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def preview_all(emails: list[dict]) -> None:
    print(f"\n{'='*70}")
    print(f"  {len(emails)} EMAILS — PREVIEW")
    print(f"{'='*70}\n")
    for e in emails:
        print(f"[{e['id']}] TO: {e['to']}")
        print(f"    FIRM: {e['firm']}")
        print(f"    SUBJECT: {e['subject']}")
        print("-" * 70)
        print(e["body"])
        print("=" * 70)


def send_emails(emails: list[dict], ids: list[int]) -> None:
    from_addr, password = get_credentials()
    for e in emails:
        if e["id"] not in ids:
            continue
        raw = send_via_smtp(from_addr, password, e["to"], e["subject"], e["body"])
        save_to_sent(from_addr, password, raw)
        print(f"  Sent [{e['id']}] -> {e['to']} ({e['firm']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="PortfolioForge Gmail outreach sender")
    parser.add_argument("--preview", action="store_true", help="Preview all initial emails")
    parser.add_argument("--preview-followup", action="store_true", help="Preview all follow-up emails")
    parser.add_argument("--preview-susan", action="store_true", help="Preview Susan reply")
    parser.add_argument("--send", help="Send initial emails by ID (comma-separated or 'all')")
    parser.add_argument("--followup", help="Send follow-up emails by ID (comma-separated or 'all')")
    parser.add_argument("--send-susan", action="store_true", help="Send Susan reply")
    args = parser.parse_args()

    if args.preview:
        preview_all(EMAILS)
        return

    if args.preview_followup:
        preview_all(FOLLOWUPS)
        return

    if args.preview_susan:
        print(f"\nTO: {SUSAN_REPLY['to']}")
        print(f"SUBJECT: {SUSAN_REPLY['subject']}")
        print("-" * 70)
        print(SUSAN_REPLY["body"])
        return

    if args.send:
        ids = [e["id"] for e in EMAILS] if args.send == "all" else [int(x.strip()) for x in args.send.split(",")]
        print(f"\nSending {len(ids)} initial email(s)...")
        send_emails(EMAILS, ids)
        print("\nDone.")
        return

    if args.followup:
        ids = [e["id"] for e in FOLLOWUPS] if args.followup == "all" else [int(x.strip()) for x in args.followup.split(",")]
        print(f"\nSending {len(ids)} follow-up email(s)...")
        send_emails(FOLLOWUPS, ids)
        print("\nDone.")
        return

    if args.send_susan:
        from_addr, password = get_credentials()
        raw = send_via_smtp(from_addr, password, SUSAN_REPLY["to"], SUSAN_REPLY["subject"], SUSAN_REPLY["body"])
        save_to_sent(from_addr, password, raw)
        print(f"  Sent Susan reply -> {SUSAN_REPLY['to']}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
