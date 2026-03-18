"""Generate a sales brief PDF for the PortfolioForge sales associate."""

import sys
from pathlib import Path

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Inter', Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #1a1a2e;
    background: white;
  }
  @page {
    size: A4;
    margin: 18mm 18mm 18mm 18mm;
    @bottom-right { content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #888; }
  }

  /* Cover */
  .cover {
    min-height: 220mm;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 40pt 0;
    page-break-after: always;
  }
  .cover-eyebrow {
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #4a9eff;
    margin-bottom: 14pt;
  }
  .cover-title {
    font-size: 32pt;
    font-weight: 700;
    color: #0d1b2a;
    line-height: 1.15;
    margin-bottom: 10pt;
  }
  .cover-sub {
    font-size: 12pt;
    color: #555;
    margin-bottom: 30pt;
    max-width: 480pt;
  }
  .cover-deadline {
    display: inline-block;
    background: #fff0e0;
    border-left: 4px solid #f59e0b;
    padding: 10pt 16pt;
    font-size: 10.5pt;
    font-weight: 600;
    color: #92400e;
    margin-bottom: 30pt;
    border-radius: 0 4pt 4pt 0;
  }
  .cover-links {
    font-size: 9pt;
    color: #888;
    line-height: 2;
  }
  .cover-links a { color: #4a9eff; text-decoration: none; }

  /* Section headings */
  h1 {
    font-size: 16pt;
    font-weight: 700;
    color: #0d1b2a;
    margin: 28pt 0 10pt 0;
    padding-bottom: 5pt;
    border-bottom: 2pt solid #4a9eff;
  }
  h2 {
    font-size: 12pt;
    font-weight: 600;
    color: #0d1b2a;
    margin: 18pt 0 6pt 0;
  }
  h3 {
    font-size: 10.5pt;
    font-weight: 600;
    color: #4a9eff;
    margin: 12pt 0 4pt 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  p { margin-bottom: 8pt; }

  /* Key points */
  .kp { background: #f0f7ff; border-left: 3pt solid #4a9eff; padding: 10pt 14pt; margin: 10pt 0; border-radius: 0 4pt 4pt 0; }
  .kp b { color: #0d1b2a; }

  /* Tables */
  table { width: 100%; border-collapse: collapse; margin: 10pt 0; font-size: 9.5pt; }
  th { background: #0d1b2a; color: white; padding: 7pt 10pt; text-align: left; font-weight: 600; font-size: 9pt; }
  td { padding: 6pt 10pt; border-bottom: 1pt solid #e5e7eb; }
  tr:nth-child(even) td { background: #f9fafb; }

  /* Checklist */
  .checklist { list-style: none; margin: 8pt 0 12pt 0; }
  .checklist li { display: flex; align-items: flex-start; margin-bottom: 7pt; font-size: 10.5pt; }
  .checklist li .box {
    display: inline-block;
    width: 14pt; height: 14pt;
    border: 1.5pt solid #4a9eff;
    border-radius: 3pt;
    margin-right: 9pt;
    flex-shrink: 0;
    margin-top: 2pt;
  }
  .checklist li.done .box { background: #4a9eff; }
  .check-label { flex: 1; }
  .check-sub { font-size: 9pt; color: #666; display: block; margin-top: 2pt; }

  /* Priority badges */
  .badge {
    display: inline-block;
    padding: 2pt 7pt;
    border-radius: 3pt;
    font-size: 8pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-left: 6pt;
    vertical-align: middle;
  }
  .badge-red { background: #fee2e2; color: #b91c1c; }
  .badge-amber { background: #fef3c7; color: #92400e; }
  .badge-green { background: #d1fae5; color: #065f46; }

  /* Message blocks */
  .msg-block {
    background: #f9fafb;
    border: 1pt solid #e5e7eb;
    border-radius: 5pt;
    padding: 12pt 14pt;
    margin: 8pt 0;
    font-size: 9.5pt;
    font-family: 'Courier New', monospace;
    line-height: 1.7;
    white-space: pre-wrap;
  }
  .msg-name { font-family: Arial, sans-serif; font-size: 9pt; font-weight: 700; color: #4a9eff; margin-bottom: 5pt; }

  /* Objection blocks */
  .obj-q { font-weight: 600; color: #b91c1c; margin: 12pt 0 4pt 0; }
  .obj-a { background: #f0fdf4; border-left: 3pt solid #22c55e; padding: 8pt 12pt; border-radius: 0 4pt 4pt 0; font-size: 10pt; }

  /* Page break helpers */
  .pb { page-break-before: always; }
  .no-break { page-break-inside: avoid; }

  /* Footer strip */
  .section-divider { height: 2pt; background: linear-gradient(90deg, #4a9eff, #0d1b2a); margin: 20pt 0 16pt 0; border-radius: 1pt; }

  /* Call out box */
  .callout { background: #0d1b2a; color: white; padding: 14pt 18pt; border-radius: 5pt; margin: 12pt 0; }
  .callout h3 { color: #4a9eff; margin-top: 0; }
  .callout p { color: #d1d5db; margin-bottom: 5pt; }

  /* Money highlight */
  .money { color: #065f46; font-weight: 700; }

  /* Script blocks */
  .script { background: #fffbeb; border: 1pt solid #fcd34d; border-radius: 5pt; padding: 10pt 14pt; margin: 8pt 0; font-style: italic; }
</style>
</head>
<body>

<!-- COVER -->
<div class="cover">
  <div class="cover-eyebrow">PortfolioForge &mdash; Confidential Sales Brief</div>
  <div class="cover-title">Your mission is to book<br>the first paying client.</div>
  <div class="cover-sub">
    Everything you need to know about the product, who to contact,
    what to say, and how to handle objections. Read this once.
    Keep it open during calls.
  </div>
  <div class="cover-deadline">
    Deadline: All 20 LinkedIn messages sent by Monday 23 March 2026
  </div>
  <div class="cover-links">
    <b>Landing page:</b> <a href="https://portfolioforge-au.netlify.app/">portfolioforge-au.netlify.app</a><br>
    <b>Live demo:</b> <a href="https://portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app/">portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app</a><br>
    <b>Your email:</b> portfolioforge.au@gmail.com<br>
    <b>Developer:</b> portfolioforge.au@gmail.com
  </div>
</div>

<!-- SECTION 1: WHAT IS IT -->
<h1>1. What Is PortfolioForge?</h1>

<p>
  PortfolioForge is a <b>compliance software tool</b> for Australian accountants who look
  after self-managed superannuation funds (SMSFs). It automates the most time-consuming
  part of their annual compliance work: the CGT calculation.
</p>

<div class="kp">
  <b>In plain English:</b> Every SMSF that owns shares has to calculate capital gains
  tax every financial year. Accountants currently do this in spreadsheets. It takes
  2&ndash;4 hours per client. PortfolioForge does it in under 10 seconds, and produces
  a Word document the accountant can hand straight to their client and auditor.
</div>

<h2>Three things to remember about the product</h2>
<ol style="margin: 8pt 0 0 18pt; line-height: 2;">
  <li><b>Input:</b> A CSV file the accountant exports from their client's broker (CommSec, SelfWealth, Stake, or Interactive Brokers)</li>
  <li><b>Output:</b> A Word document workpaper with every calculation traced to the specific tax law that produced it</li>
  <li><b>Speed:</b> Under 10 seconds. The accountant does not need to do any maths.</li>
</ol>

<h2>Why accountants will pay for it</h2>
<table>
  <tr><th>Problem without PortfolioForge</th><th>With PortfolioForge</th></tr>
  <tr><td>2&ndash;4 hours per client in spreadsheets</td><td>Under 10 seconds</td></tr>
  <tr><td>Common error: using 50% CGT discount instead of 33.33% (SMSF rate)</td><td>Hardwired correctly &mdash; can't get it wrong</td></tr>
  <tr><td>Loss ordering rules are hard to implement &mdash; most get it wrong</td><td>ATO rules enforced automatically</td></tr>
  <tr><td>Auditors push back on informal workpapers</td><td>Every number traces to the specific ITAA provision</td></tr>
</table>

<h2>What it is NOT</h2>
<p>
  It is <b>not financial advice</b>. It is a compliance tool for professional accountants.
  The accountant is the expert &mdash; PortfolioForge just does the maths faster and
  documents it properly. This matters if a prospect asks.
</p>

<!-- SECTION 2: WHO BUYS -->
<div class="pb"></div>
<h1>2. Who Buys It</h1>

<div class="kp">
  <b>Target buyer:</b> SMSF accountants at boutique or specialist practices with
  10&ndash;100 SMSF clients. They are CAs or CPAs. They are busy. They are technically
  competent but not interested in software for its own sake &mdash; only in time saved
  and audit-ready outputs.
</div>

<p><b>NOT</b> financial advisers. Not the SMSF members themselves. The accountant is the buyer.</p>

<h2>What they care about (in this order)</h2>
<ol style="margin: 8pt 0 0 18pt; line-height: 2.2;">
  <li>Time saved &mdash; they bill by the hour, compliance work is not where they want to spend it</li>
  <li>Audit defensibility &mdash; their workpapers need to stand up to scrutiny</li>
  <li>Accuracy &mdash; one wrong CGT discount rate is a real professional liability</li>
  <li>Workflow fit &mdash; Word output drops straight into existing client files, no new system to learn</li>
</ol>

<h2>Pricing</h2>
<table>
  <tr><th>Plan</th><th>Price</th><th>What's included</th></tr>
  <tr><td><b>Standard engagement</b></td><td>$150/yr</td><td>One SMSF fund, full workpaper, delivered within 24hrs</td></tr>
  <tr><td><b>Practice subscription</b></td><td>$300/month</td><td>Unlimited SMSF clients, direct app access, priority turnaround</td></tr>
</table>

<div class="kp">
  <b>The pitch on price:</b> At $300/month, it pays for itself if it saves two hours
  on one client at $150/hr. That is one client. Everything after that is pure margin.
  A practice with 20 SMSF clients saves 40&ndash;80 hours a year.
</div>

<h2>Your commission</h2>
<table>
  <tr><th>Deal type</th><th>Annual value</th><th>Your cut (20%)</th></tr>
  <tr><td>Practice subscription</td><td>$300 &times; 12 = $3,600</td><td class="money">$720</td></tr>
  <tr><td>Standard engagement</td><td>$150</td><td class="money">$30</td></tr>
</table>
<p>
  <b>Focus on practice subscriptions.</b> One practice with 20 SMSF clients is worth
  $720 to you in year one. Payment is monthly, from the month the client starts paying,
  for 12 months.
</p>

<!-- SECTION 3: YOUR ACTION PLAN -->
<div class="pb"></div>
<h1>3. Your Action Plan &mdash; By Monday 23 March</h1>

<div class="callout">
  <h3>What needs to happen this week</h3>
  <p>The 20 personalised LinkedIn messages in this document are written and ready to send.
  Your job is to get them out and keep the pipeline moving. These are warm, researched
  messages to real SMSF specialists &mdash; not spam.</p>
</div>

<h2>Step 1 &mdash; Set up your Calendly booking link <span class="badge badge-red">Do first</span></h2>
<ul class="checklist">
  <li><span class="box"></span><span class="check-label">Go to <b>calendly.com</b> (free tier is enough)<span class="check-sub">Create a 15-minute event called "PortfolioForge &mdash; Quick Demo"</span></span></li>
  <li><span class="box"></span><span class="check-label">Set your available times &mdash; be flexible, accountants are time-poor</span></li>
  <li><span class="box"></span><span class="check-label">Copy the link and send it to the developer at portfolioforge.au@gmail.com<span class="check-sub">They will add it to the landing page and email signature</span></span></li>
</ul>

<h2>Step 2 &mdash; Send the LinkedIn messages <span class="badge badge-red">Must be done by Monday 23 March</span></h2>
<ul class="checklist">
  <li><span class="box"></span><span class="check-label">Read Section 5 of this document &mdash; the 20 messages are printed there, ready to copy-paste</span></li>
  <li><span class="box"></span><span class="check-label">Replace <b>[YOUR NAME]</b> with your name in every message before you send anything</span></li>
  <li><span class="box"></span><span class="check-label">Send 5&ndash;10 per day, not all at once<span class="check-sub">LinkedIn flags bulk activity. Spread it across Thursday, Friday, Monday.</span></span></li>
  <li><span class="box"></span><span class="check-label">For each person: find them on LinkedIn first. If not connected, send a connection request with the note: <em>"Hi [Name] &mdash; I built something that might be useful for SMSF accountants. Worth a look?"</em> Once connected, send the main message.</span></li>
  <li><span class="box"></span><span class="check-label">Mark each person's status in the lead tracker (Section 7) as you go<span class="check-sub">Change NEW to SENT-1. Log the date.</span></span></li>
  <li><span class="box"></span><span class="check-label"><b>Do NOT contact Andrew Gardiner</b> (Gardiner SMSF Audits) &mdash; he has already declined</span></li>
</ul>

<h2>Step 3 &mdash; Monitor for replies <span class="badge badge-amber">Ongoing from this week</span></h2>
<ul class="checklist">
  <li><span class="box"></span><span class="check-label">Check <b>portfolioforge.au@gmail.com</b> daily for replies from the cold email round</span></li>
  <li><span class="box"></span><span class="check-label">Check LinkedIn messages daily once you start sending</span></li>
  <li><span class="box"></span><span class="check-label">When someone replies: send the Calendly link <em>immediately</em><span class="check-sub">Don't let the window close. Interested people go cold fast.</span></span></li>
</ul>

<h2>Step 4 &mdash; Follow-up sequence <span class="badge badge-amber">5&ndash;7 days after first message</span></h2>
<p>If someone doesn't reply to the first message, send the follow-ups below. These are in Section 5.</p>
<table>
  <tr><th>Day</th><th>Action</th><th>Status to log</th></tr>
  <tr><td>Day 1</td><td>Send first message</td><td>SENT-1</td></tr>
  <tr><td>Day 5&ndash;7</td><td>Send Follow-up 1 (if no reply)</td><td>SENT-FU1</td></tr>
  <tr><td>Day 12&ndash;14</td><td>Send Follow-up 2 (if still no reply)</td><td>SENT-FU2</td></tr>
  <tr><td>After FU2</td><td>No more contact. Mark as DEAD and move on.</td><td>DEAD</td></tr>
</table>

<h2>Step 5 &mdash; When someone books a call <span class="badge badge-green">The goal</span></h2>
<ul class="checklist">
  <li><span class="box"></span><span class="check-label">Read Section 4 (the call script) the night before</span></li>
  <li><span class="box"></span><span class="check-label">Download the example report from the landing page before the call: portfolioforge-au.netlify.app</span></li>
  <li><span class="box"></span><span class="check-label">Open the live demo in a browser tab: the Streamlit link at the top of this document</span></li>
  <li><span class="box"></span><span class="check-label">Follow Section 4 exactly during the call</span></li>
  <li><span class="box"></span><span class="check-label">If they say yes to a trial: email portfolioforge.au@gmail.com with their name, firm, and email. The developer handles everything from there.</span></li>
</ul>

<!-- SECTION 4: THE CALL -->
<div class="pb"></div>
<h1>4. The 15-Minute Call Script</h1>

<p><em>Use this on every discovery call. Follow the order. Do not skip steps.</em></p>

<h2>Before the call</h2>
<ul style="margin: 6pt 0 12pt 20pt; line-height: 2;">
  <li>Download the example Word report from the landing page (portfolioforge-au.netlify.app)</li>
  <li>Open the live demo: portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app</li>
  <li>Review the prospect's name and firm from the lead tracker</li>
</ul>

<h3>Opening &mdash; say this verbatim (30 seconds)</h3>
<div class="script">
  "Thanks for your time. PortfolioForge is a tool I built for SMSF accountants.
  It runs ATO-correct CGT calculations and exports a Word document you can attach
  to a client file. Important: PortfolioForge is a tool for you to use with clients
  &mdash; we don't provide financial advice to end investors. Three things in five minutes."
</div>

<h3>Step 1 &mdash; Show the output first (2 minutes)</h3>
<p>Open the example Word report. Show in this order:</p>
<ol style="margin: 6pt 0 0 18pt; line-height: 2.2;">
  <li><b>CGT event log</b> &mdash; acquired date, disposed date, cost base, proceeds, net gain, 33.33% SMSF discount applied, ATO rule annotation.<br>
    <em>Say: "Every disposal traced to the specific ATO rule. Your auditor can follow every number independently."</em></li>
  <li><b>Year-by-year tax table</b> &mdash; FY, CGT events, CGT payable, franking credits, carry-forward loss balance.<br>
    <em>Say: "The carry-forward loss column is the one most manual calculations get wrong. PortfolioForge implements the ATO rules correctly."</em></li>
  <li><b>Key numbers</b> &mdash; total return, after-tax CAGR, CGT payable.<br>
    <em>Say: "This is what the client actually took home after tax."</em></li>
</ol>

<h3>Step 2 &mdash; Show the live demo (2 minutes)</h3>
<p>Open the Streamlit demo URL. Walk through the input fields: tickers, weights, date range, entity type (SMSF), broker CSV upload.</p>
<div class="script">
  "The accountant uploads the broker CSV, sets the date range and entity type,
  and clicks run. The Word document comes out the other side. Under 10 seconds."
</div>

<h3>Step 3 &mdash; The close (1 minute)</h3>
<div class="script">
  "Pricing is $300/month for a practice subscription &mdash; unlimited clients.
  At two hours saved per SMSF client at $150/hr, it pays for itself with one client.
  What I'd suggest: try it on one real client portfolio. If the workpaper isn't
  better than what you're producing now, don't pay. Does that work?"
</div>

<h3>If they ask a technical question you can't answer</h3>
<div class="script">
  "Let me check with the developer and come back to you &mdash; I want to give you
  the right answer rather than guess."
</div>
<p>Then email portfolioforge.au@gmail.com with the question.</p>

<h3>After the call</h3>
<p><b>If they say yes to a trial:</b> Email portfolioforge.au@gmail.com with their name, firm, and email. The developer handles setup.</p>
<p><b>If they want to think about it:</b> Follow up in 3 days: <em>"Happy to answer any questions before you decide &mdash; what would be most useful to see?"</em></p>

<!-- SECTION 5: OBJECTIONS -->
<div class="pb"></div>
<h1>5. Handling Objections</h1>
<p><em>These will come up on almost every call. Know the answers before you dial.</em></p>

<div class="obj-q">"We already use Excel / another tool"</div>
<div class="obj-a no-break">
  "PortfolioForge doesn't replace your workflow &mdash; it replaces the spreadsheet part.
  The output is a Word document you drop into your existing client file. And unlike a
  spreadsheet, it implements ATO loss-ordering correctly: losses net against
  non-discountable gains first, before discountable gains, before the 33.33% discount.
  That's the rule most manual calculations get wrong."
</div>

<div class="obj-q">"Our clients don't need this"</div>
<div class="obj-a no-break">
  "If your SMSF clients hold shares and have made disposals in the last few years,
  they need a CGT calculation every year. The question is how long it takes you and
  whether the workpaper is audit-ready. PortfolioForge addresses both."
</div>

<div class="obj-q">"How do I know the CGT calculation is correct?"</div>
<div class="obj-a no-break">
  "Every calculation is validated against ATO published worked examples &mdash; the ATO's
  own Sonya, Mei-Ling, and multi-parcel FIFO examples are in the test suite and all pass.
  The Word export traces every dollar to the specific ATO rule that produced it.
  Any number can be verified by hand in under a minute."
</div>

<div class="obj-q">"Is this ATO-approved software?"</div>
<div class="obj-a no-break">
  "It's not ATO-certified &mdash; that designation doesn't exist for workpaper tools.
  What it is: validated against every published ATO worked example for CGT, with the
  methodology table citing specific ITAA provisions for every rule. Your auditor can
  verify every number independently. That's more defensible than a spreadsheet."
</div>

<div class="obj-q">"Too expensive / We'll think about it"</div>
<div class="obj-a no-break">
  "At $300/month it pays for itself if it saves two hours per client at $150/hr &mdash;
  that's one client. Run it on one real client portfolio in a two-week trial.
  If it doesn't save you time, don't pay."
</div>

<div class="obj-q">"Does it integrate with BGL or Class?"</div>
<div class="obj-a no-break">
  "Not yet natively &mdash; BGL integration is on the roadmap. Currently the output is
  a Word workpaper, which most auditors accept directly. CommSec, SelfWealth, Stake,
  and IBKR broker CSVs are supported as input today."
</div>

<div class="obj-q">"We're busy until end of FY"</div>
<div class="obj-a no-break">
  "Understood &mdash; that's actually the best time to try it, because you have real
  client files to test it against. If it saves time on a client you're currently
  processing, you'll know it works before you commit to anything."
</div>

<div class="obj-q">"What about our existing client data?"</div>
<div class="obj-a no-break">
  "PortfolioForge imports broker CSV exports from CommSec, SelfWealth, Stake, and IBKR
  directly. For existing portfolios, you declare opening cost basis via a simple CSV.
  The tool validates for duplicates and mismatches before writing anything."
</div>

<!-- SECTION 6: MESSAGES -->
<div class="pb"></div>
<h1>6. LinkedIn Messages &mdash; Copy-Paste Ready</h1>

<div class="callout">
  <h3>Before you send anything</h3>
  <p>Replace <b>[YOUR NAME]</b> with your actual name in every message. Do NOT send with the placeholder.</p>
  <p>Send 5&ndash;10 per day maximum. Start with messages 1&ndash;5 on Thursday, 6&ndash;10 on Friday, 11&ndash;20 across the weekend or Monday morning.</p>
</div>

<h2>Connection request note (use this before the main message if not connected)</h2>
<div class="msg-block">"Hi [Name] &mdash; I built something that might be useful for SMSF accountants. Worth a look?"</div>

<div class="msg-name">1 &mdash; Diana Morris | The SMSF Accountant</div>
<div class="msg-block">Hi Diana,

You've run The SMSF Accountant as a sole SMSF-only practice since 2010 &mdash; that
level of specialisation means clients expect technical depth, which needs to
show in the CGT workpaper.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">2 &mdash; Kris Kitto | Grow SMSF</div>
<div class="msg-block">Hi Kris,

Grow SMSF handles ASX, US stocks, and crypto SMSFs &mdash; which means you're dealing
with CGT scenarios most tools can't model correctly, let alone document to
ATO standard.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">3 &mdash; Solomon Forman | Forman Accounting Services</div>
<div class="msg-block">Hi Solomon,

With 30+ years as an SMSF Specialist Advisor, Accountant, Tax Agent, and
author &mdash; you've seen, and likely written about, exactly where CGT calculations
go wrong in practice.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">4 &mdash; Fiona O'Neill | Select SMSF &amp; Tax Solutions</div>
<div class="msg-block">Hi Fiona,

You opened Select SMSF &amp; Tax Solutions in 2020 after selling O'Neills
Accountants &mdash; building a lean, specialist practice from scratch is exactly
where automation pays the most per hour of compliance work.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">5 &mdash; Sara Baynes | SB Accounting &amp; SMSF Services</div>
<div class="msg-block">Hi Sara,

You run both SMSF accounting and SMSF audit at SB Accounting &mdash; meaning you see
CGT workpapers from both sides of the compliance process, as preparer and
as verifier.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">6 &mdash; Mari Ashted | Boutique CA practice (Brisbane)</div>
<div class="msg-block">Hi Mari,

Your CA SMSF Specialist accreditation in Brisbane means clients are coming to
you specifically for technical depth on superannuation tax &mdash; the CGT workpaper
is where that depth is most visible to them.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">7 &mdash; Dawood Hassan | DH Accountants</div>
<div class="msg-block">Hi Dawood,

You're both Tax Director at DH Accountants and an SMSF Auditor &mdash; which means
you've seen, from both sides, exactly where manual CGT calculations fall apart
under scrutiny.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">8 &mdash; Christopher Watson | Griffin Super</div>
<div class="msg-block">Hi Christopher,

Griffin Super's focus on SMSF and family trusts is exactly the client profile
where CGT complexity compounds &mdash; multiple parcels, mixed holding periods,
FIFO ordering across years.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">9 &mdash; Jodie Corbett | Boutique CA practice</div>
<div class="msg-block">Hi Jodie,

Your profile lists SMSF specialisation as the key differentiator of your
boutique CA practice &mdash; which means the quality and defensibility of your
CGT workpapers is a direct part of that brand.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">10 &mdash; Sally Byrne | SMSF Grapevine / Norcrest Business Services</div>
<div class="msg-block">Hi Sally,

You operate as CA SMSF Specialist across both SMSF Grapevine and Norcrest
Business Services &mdash; that's a client base that comes to you specifically for
technical accuracy on super tax.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="pb"></div>
<div class="msg-name">11 &mdash; Mark Foxley-Conolly | Boutique CA practice</div>
<div class="msg-block">Hi Mark,

Your CA practice focuses on family-owned SMEs and SMSF &mdash; that's the cohort
with the most complex portfolios and the least patience for slow, manual
CGT calculations.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">12 &mdash; Mark A Sage | Independent practice</div>
<div class="msg-block">Hi Mark,

You operate as both SMSF Advisor/Manager and Registered Tax Agent &mdash; the full
loop from strategy to compliance to CGT is exactly who PortfolioForge is
built for.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">13 &mdash; Taryn Holman | Seamless SMSF</div>
<div class="msg-block">Hi Taryn,

Seamless SMSF's brand promise is seamless compliance &mdash; which is hard to deliver
when the CGT workpaper is still the manual step in the workflow.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">14 &mdash; Natalie Muirhead | Boutique CA practice (Perth)</div>
<div class="msg-block">Hi Natalie,

Your Perth CA practice combines SMEs and SMSF &mdash; business owners who are also
SMSF trustees often have the most complex CGT scenarios, especially when
business assets and super investments intersect.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">15 &mdash; Sandy Hill | Tyrrell Partners</div>
<div class="msg-block">Hi Sandy,

Your SMSF work at Tyrrell Partners means you're regularly producing CGT
calculations that need to stand up to ATO scrutiny &mdash; and the workpaper quality
reflects directly on the practice.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">16 &mdash; Michael Holmes | Michael Holmes Chartered Accountant</div>
<div class="msg-block">Hi Michael,

As a sole-practitioner CA focused on SMSF advice, the documentation overhead
of building CGT workpapers manually is exactly the kind of cost that doesn't
scale as your client base grows.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">17 &mdash; Eddie Chau | Chau &amp; Hennessy</div>
<div class="msg-block">Hi Eddie,

Chau &amp; Hennessy's CA FCPA SMSF specialisation means clients are holding the
practice to a high technical standard &mdash; the CGT workpaper is where that
standard is most directly tested.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">18 &mdash; Brian Cosgrove | BIS Cosgrove</div>
<p style="font-size:9pt;color:#888;margin-bottom:4pt;"><em>LinkedIn search: "Brian Cosgrove BIS Cosgrove"</em></p>
<div class="msg-block">Hi Brian,

BIS Cosgrove's SMSF Specialist accreditation through the SMSF Association
signals a high standard of compliance work &mdash; the CGT workpaper is where
that standard is most visible to clients and auditors.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">19 &mdash; Craig Tschirpig | International Professional Services</div>
<p style="font-size:9pt;color:#888;margin-bottom:4pt;"><em>LinkedIn search: "Craig Tschirpig IPS Southport"</em></p>
<div class="msg-block">Hi Craig,

International Professional Services' Southport location puts you in one of the
highest concentrations of SMSF trustees in Australia &mdash; retirees and
pre-retirees where CGT ordering and carry-forward balances matter most.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<div class="msg-name">20 &mdash; Lisa Papachristoforos | Hughes O'Dea Corredig</div>
<p style="font-size:9pt;color:#888;margin-bottom:4pt;"><em>LinkedIn search: "Lisa Papachristoforos Hughes O'Dea"</em></p>
<div class="msg-block">Hi Lisa,

Hughes O'Dea Corredig's SMSF Specialist accreditation at Essendon means
clients are coming to you specifically for technical depth &mdash; and that depth
needs to be traceable in the workpaper you hand them.

I built a tool called PortfolioForge that produces ATO-validated CGT workpapers
for SMSF portfolios &mdash; FIFO, 33.33% SMSF discount, 45-day rule enforced,
franking credits, cross-year carry-forward &mdash; and exports a Word document you
can attach directly to a client file.

Most SMSF accountants are still doing this in spreadsheets. PortfolioForge
runs the full calculation in under 10 seconds and traces every dollar to the
specific ATO rule that produced it.

Worth a 15-min call to see if it's a fit for your SMSF clients?

[YOUR NAME]</div>

<h2>Follow-up messages</h2>

<div class="msg-name">Follow-up 1 &mdash; send 5&ndash;7 days after first message (no reply)</div>
<div class="msg-block">Hi [NAME],

Following up on my note last week. In case it helps to see before a call &mdash;
the Word document PortfolioForge exports includes the full CGT event log,
year-by-year tax table, and carry-forward loss balance: everything you'd
put in a client file today, generated in under 10 seconds.

Happy to send a sample document if that's easier than a call.

[YOUR NAME]</div>

<div class="msg-name">Follow-up 2 &mdash; send 5&ndash;7 days after Follow-up 1 (still no reply)</div>
<div class="msg-block">Hi [NAME],

Last follow-up from me. If the timing isn't right, no problem.

If it is &mdash; reply with a time that works and I'll send a calendar link.

[YOUR NAME]</div>

<!-- SECTION 7: LEAD TRACKER -->
<div class="pb"></div>
<h1>7. Lead Tracker</h1>
<p><em>Print this page. Check off each send. Update status as you go.</em></p>

<h2>Status codes</h2>
<table style="width:auto;">
  <tr><th>Code</th><th>Meaning</th></tr>
  <tr><td>NEW</td><td>Not yet contacted</td></tr>
  <tr><td>SENT-1</td><td>First message sent</td></tr>
  <tr><td>SENT-FU1</td><td>Follow-up 1 sent</td></tr>
  <tr><td>SENT-FU2</td><td>Follow-up 2 sent (final)</td></tr>
  <tr><td>REPLIED</td><td>Replied, conversation active</td></tr>
  <tr><td>CALL-BOOKED</td><td>Call scheduled</td></tr>
  <tr><td>TRIAL</td><td>Running a trial</td></tr>
  <tr><td>CLOSED</td><td>Paying client</td></tr>
  <tr><td>DEAD</td><td>Declined or no response after FU2</td></tr>
</table>

<table style="margin-top: 12pt;">
  <tr><th>#</th><th>Name</th><th>Firm</th><th>Status</th><th>Last contact</th><th>Notes</th></tr>
  <tr><td>1</td><td>Diana Morris</td><td>The SMSF Accountant</td><td>NEW</td><td></td><td>SMSF-only since 2010</td></tr>
  <tr><td>2</td><td>Kris Kitto</td><td>Grow SMSF</td><td>NEW</td><td></td><td>ASX, US stocks, crypto</td></tr>
  <tr><td>3</td><td>Solomon Forman</td><td>Forman Accounting</td><td>NEW</td><td></td><td>30+ yrs, SMSF author</td></tr>
  <tr><td>4</td><td>Fiona O'Neill</td><td>Select SMSF &amp; Tax</td><td>NEW</td><td></td><td>Lean specialist practice</td></tr>
  <tr><td>5</td><td>Sara Baynes</td><td>SB Accounting &amp; SMSF</td><td>NEW</td><td></td><td>Preparer + auditor</td></tr>
  <tr><td>6</td><td>Mari Ashted</td><td>Boutique CA (Brisbane)</td><td>NEW</td><td></td><td>CA SMSF Specialist</td></tr>
  <tr><td>7</td><td>Dawood Hassan</td><td>DH Accountants</td><td>NEW</td><td></td><td>Tax Director + Auditor</td></tr>
  <tr><td>8</td><td>Christopher Watson</td><td>Griffin Super</td><td>NEW</td><td></td><td>SMSF + family trusts</td></tr>
  <tr><td>9</td><td>Jodie Corbett</td><td>Boutique CA</td><td>NEW</td><td></td><td>SMSF differentiator</td></tr>
  <tr><td>10</td><td>Sally Byrne</td><td>SMSF Grapevine</td><td>NEW</td><td></td><td>Registered SMSF Auditor</td></tr>
  <tr><td>11</td><td>Mark Foxley-Conolly</td><td>Boutique CA</td><td>NEW</td><td></td><td>SMEs + SMSF</td></tr>
  <tr><td>12</td><td>Mark A Sage</td><td>Independent</td><td>NEW</td><td></td><td>FCPA, full-loop SMSF</td></tr>
  <tr><td>13</td><td>Taryn Holman</td><td>Seamless SMSF</td><td>NEW</td><td></td><td>Compliance efficiency brand</td></tr>
  <tr><td>14</td><td>Natalie Muirhead</td><td>Boutique CA (Perth)</td><td>NEW</td><td></td><td>SMEs + SMSF</td></tr>
  <tr><td>15</td><td>Sandy Hill</td><td>Tyrrell Partners</td><td>NEW</td><td></td><td>CPA, SMSF</td></tr>
  <tr><td>16</td><td>Michael Holmes</td><td>Michael Holmes CA</td><td>NEW</td><td></td><td>Sole practitioner, SMSF</td></tr>
  <tr><td>17</td><td>Eddie Chau</td><td>Chau &amp; Hennessy</td><td>NEW</td><td></td><td>CA FCPA, SMSF</td></tr>
  <tr><td>18</td><td>Brian Cosgrove</td><td>BIS Cosgrove</td><td>NEW</td><td></td><td>SMSF Association Specialist</td></tr>
  <tr><td>19</td><td>Craig Tschirpig</td><td>Intl Professional Services</td><td>NEW</td><td></td><td>Southport QLD</td></tr>
  <tr><td>20</td><td>Lisa Papachristoforos</td><td>Hughes O'Dea Corredig</td><td>NEW</td><td></td><td>SMSF Specialist, Essendon</td></tr>
</table>

<div style="margin-top:14pt;padding:10pt 14pt;background:#fee2e2;border-radius:4pt;font-size:9.5pt;">
  <b>Do NOT contact:</b> Andrew Gardiner (Gardiner SMSF Audits) &mdash; he has already declined.
</div>

<!-- SECTION 8: QUICK REFERENCE -->
<div class="pb"></div>
<h1>8. Quick Reference</h1>

<h2>Key links</h2>
<table>
  <tr><th>Resource</th><th>URL / Contact</th></tr>
  <tr><td>Landing page</td><td>portfolioforge-au.netlify.app</td></tr>
  <tr><td>Live demo (Streamlit)</td><td>portfolioforge-vupb82qsizvlzjte4jilg4.streamlit.app</td></tr>
  <tr><td>Email (check for replies)</td><td>portfolioforge.au@gmail.com</td></tr>
  <tr><td>Developer contact</td><td>portfolioforge.au@gmail.com</td></tr>
</table>

<h2>Glossary &mdash; terms you will hear</h2>
<table>
  <tr><th>Term</th><th>What it means (plain English)</th></tr>
  <tr><td>SMSF</td><td>Self-managed superannuation fund &mdash; a private super fund run by its members</td></tr>
  <tr><td>CGT</td><td>Capital gains tax &mdash; tax on profit from selling shares or assets</td></tr>
  <tr><td>Workpaper</td><td>A supporting document that shows an accountant's calculations, used in audits</td></tr>
  <tr><td>FIFO</td><td>"First in, first out" &mdash; the ATO rule for matching which shares you bought against which ones you sold</td></tr>
  <tr><td>ITAA</td><td>Income Tax Assessment Act &mdash; the law that defines CGT rules in Australia</td></tr>
  <tr><td>ATO</td><td>Australian Taxation Office</td></tr>
  <tr><td>CA / CPA</td><td>Chartered Accountant / Certified Practising Accountant &mdash; professional accounting qualifications</td></tr>
  <tr><td>BGL / Class</td><td>Popular SMSF administration software platforms. PortfolioForge integration is on the roadmap.</td></tr>
  <tr><td>Franking credits</td><td>Tax credits attached to dividends from Australian companies, passed to SMSF members</td></tr>
  <tr><td>45-day rule</td><td>ATO rule: you must hold shares for at least 45 days to claim franking credits</td></tr>
</table>

<h2>What to do if something goes wrong</h2>
<table>
  <tr><th>Situation</th><th>Action</th></tr>
  <tr><td>Technical question you can't answer</td><td>Say "Let me check with the developer." Email portfolioforge.au@gmail.com.</td></tr>
  <tr><td>Prospect wants a trial</td><td>Email portfolioforge.au@gmail.com: their name, firm, email. Developer handles setup.</td></tr>
  <tr><td>Prospect is rude or aggressive</td><td>Thank them for their time and move on. Don't argue.</td></tr>
  <tr><td>You can't find someone on LinkedIn</td><td>Skip them. Don't waste time. There are 20 on the list &mdash; move to the next one.</td></tr>
  <tr><td>Someone asks for the price in writing</td><td>$150/yr per engagement, $300/month practice subscription. Send the landing page link.</td></tr>
</table>

<div style="margin-top: 28pt; text-align: center; font-size: 9pt; color: #aaa; border-top: 1pt solid #e5e7eb; padding-top: 14pt;">
  PortfolioForge &mdash; Confidential. For authorised sales use only. &copy; 2026.
</div>

</body>
</html>
"""


def main() -> None:
    out_path = Path(__file__).parent / "PortfolioForge-Sales-Brief.pdf"

    try:
        from weasyprint import HTML as WP_HTML

        WP_HTML(string=HTML).write_pdf(str(out_path))
        print(f"PDF written to: {out_path}")
    except Exception as exc:  # noqa: BLE001
        print(f"WeasyPrint error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
