"""A harder, fully fictional company for retrieval and answer evaluation: "Northwind Capital".

The demo company (acme) has 14 one-paragraph documents, so even plain meaning search finds almost everything and no
experiment can show an improvement. This corpus is built to be difficult in the ways real document sets are:

  * long documents (several sections each, so the right passage is buried among boilerplate),
  * near-duplicate documents (the same policy for three countries, with different numbers),
  * two versions of one policy that both stay published (the old one says it is superseded, the app does not hide it),
  * a stale FAQ whose numbers contradict the current policies,
  * two documents that disagree on one rule (code of conduct against the conflicts procedure),
  * documents at three reading levels, and topics the company has no document about.

All text is invented. Every fact a question depends on is written into exactly one place, and a unit test checks that
every expected phrase really appears in the document the question names, so the ground truth cannot drift.

Usage:  python -m scripts.hardcorp_data --write      writes evaluation/hardcorp_set.json and evaluation/hardcorp_documents.md
"""
import json
import random
import zlib
from pathlib import Path
from typing import Dict, List

TENANT = "northwind"
COMPANY = "Northwind Capital"
USERS = {"analyst": 1, "manager": 2, "director": 3}  # emails analyst@northwind.test ...; plus admin@northwind.test (level 1)


# --------------------------------------------------------------------------------------------- boilerplate
def _pick(title: str, options: List[str]) -> str:
    return options[zlib.crc32(title.encode()) % len(options)]


def _purpose(title: str, topic: str) -> str:
    return _pick(title, [
        f"This document sets out how {COMPANY} handles {topic}. It applies to every employee, contractor and temporary worker "
        f"in every office, and it must be read together with the related documents listed at the end.",
        f"The purpose of this {title.lower()} is to give staff one clear reference for {topic}. It covers all offices and all "
        f"employment types. Where a local law is stricter than this document, the local law applies.",
        f"{COMPANY} expects consistent practice on {topic}. This document describes that practice, who is responsible for it "
        f"and what to do when something does not fit. It is reviewed by its owner on a fixed cycle.",
        f"Staff, contractors and agency workers who deal with {topic} must follow this document. It replaces any older "
        f"guidance on the same subject that was circulated by email or posted on a team page.",
    ])


def _definitions(title: str) -> str:
    return _pick(title + "d", [
        "In this document an employee means anyone on the company payroll, a manager means a line manager at grade G3 or above, "
        "and a working day means any day that is not a Saturday, a Sunday or a company holiday. The owner is the function named "
        "in the review section.",
        "Terms used here have their everyday meaning unless stated. Manager means the person an employee reports to. Director "
        "means a member of the leadership team at grade G5 or above. A working day excludes weekends and company holidays.",
        "For this document, staff means employees and contractors. The line manager is the first approver for most requests. "
        "A working day is a normal business day in the office where the person is based.",
    ])


def _roles(title: str) -> str:
    return _pick(title + "r", [
        "The owner keeps this document up to date and answers questions about it. Line managers make sure their teams know "
        "about it and apply it. Everyone else is responsible for reading it and following it, and for raising anything that "
        "looks wrong with their manager or the owner.",
        "Responsibility sits with three groups. The owner maintains the document and approves changes. Managers apply it day "
        "to day and escalate difficult cases. Individual staff follow it and report problems early.",
        "Managers are accountable for applying this document in their teams. The owner is accountable for its content. Staff "
        "are expected to ask when they are unsure rather than guess.",
    ])


def _exceptions(title: str, owner: str) -> str:
    return _pick(title + "e", [
        f"An exception must be requested in writing to {owner}, with the reason and how long it is needed. Approved exceptions "
        f"are recorded in the exceptions log and looked at again at each review. Verbal permission is not enough.",
        f"If a case does not fit, ask {owner} before acting. An approved exception is written down, time limited and "
        f"reviewed. Repeated exceptions on the same point are taken as a sign that the document needs changing.",
        f"Nobody may grant themselves an exception. Requests go to {owner}, who can approve, refuse or refer them to the "
        f"leadership team. Every decision is logged.",
    ])


def _related(related: List[str]) -> str:
    return "Related documents: " + "; ".join(related) + "." if related else ""


def make_doc(title, code, level, version, effective, owner, topic, sections, related=(), note="") -> Dict:
    """sections: list of (heading, text). The facts live in these; everything else is shared boilerplate."""
    parts = [f"{title} ({code}). Version {version}, effective {effective}. Owner: {owner}." + (f" {note}" if note else ""),
             "1. Purpose and scope. " + _purpose(title, topic),
             "2. Definitions. " + _definitions(title)]
    n = 3
    for heading, text in sections:
        parts.append(f"{n}. {heading}. {text}")
        n += 1
    parts.append(f"{n}. Roles and responsibilities. " + _roles(title))
    parts.append(f"{n + 1}. Exceptions and escalation. " + _exceptions(title, owner))
    parts.append(f"{n + 2}. Review and ownership. This document is owned by {owner} and reviewed every year. "
                 f"Questions go to the owner. " + _related(list(related)))
    return {"title": title, "code": code, "level": level, "text": "\n\n".join(parts)}


# --------------------------------------------------------------------------------------------- the documents
def build_documents() -> List[Dict]:
    d = []
    add = lambda *a, **k: d.append(make_doc(*a, **k))

    # ---- two versions of one policy, both published
    add("Travel and Expense Policy 2023", "NW-TRV-023", 1, "3.0", "1 January 2023", "Finance Operations", "travel and expense claims",
        [("Claims deadline", "Expense claims must be submitted within 45 days of the end of the trip. Claims submitted later need "
                            "the approval of the finance controller."),
         ("Flights and hotels", "Economy class is required for flights shorter than 8 hours. Business class may be booked for flights "
                                "of 8 hours or longer. The hotel limit is INR 9,000 per night in metro cities and INR 6,500 elsewhere."),
         ("Meals and approvals", "The daily meal allowance is INR 1,800. A trip with an estimated cost above INR 200,000 needs the "
                                 "approval of a director before it is booked.")],
        related=["Employee FAQ 2022", "Code of Conduct"],
        note="This version has been superseded by the Travel and Expense Policy 2025 (NW-TRV-025) from 1 January 2025.")
    add("Travel and Expense Policy 2025", "NW-TRV-025", 1, "4.0", "1 January 2025", "Finance Operations", "travel and expense claims",
        [("Claims deadline", "Expense claims must be submitted within 30 days of the end of the trip, through the NorthTrip expense "
                            "tool. Claims submitted later are paid only with the approval of the finance controller."),
         ("Flights and hotels", "Economy class is required for flights shorter than 6 hours. Premium economy may be booked for flights "
                                "of 6 to 9 hours. Business class is allowed only for flights longer than 9 hours and needs a "
                                "director's sign-off. The hotel limit is INR 8,000 per night in metro cities and INR 5,500 elsewhere."),
         ("Meals, entertainment and approvals", "The daily meal allowance is INR 1,500. Client entertainment is reimbursed up to "
                                                "INR 4,000 per person and needs the client name and business purpose. Receipts are "
                                                "required for any item above INR 500. A trip with an estimated cost above INR 150,000 "
                                                "needs the approval of a director before it is booked. Flights must be paid with the "
                                                "corporate card.")],
        related=["Code of Conduct", "Procurement Policy"])

    # ---- the same policy for three countries
    add("Leave Policy India", "NW-HR-LV-IN", 1, "5.1", "1 April 2025", "People Operations India", "leave entitlements in India",
        [("Annual leave", "Full-time employees in India receive 24 days of paid annual leave per leave year. Up to 10 unused days "
                          "may be carried forward to the next year. Leave of more than 5 consecutive days needs the manager's approval."),
         ("Sick and family leave", "Sick leave is 12 days a year, and a medical certificate is needed after 3 consecutive days. "
                                   "Maternity leave is 26 weeks. Paternity leave is 10 working days. Bereavement leave is 5 days.")],
        related=["Leave Policy United Kingdom", "Leave Policy Singapore", "Employee FAQ 2022"])
    add("Leave Policy United Kingdom", "NW-HR-LV-UK", 1, "5.0", "1 April 2025", "People Operations UK", "leave entitlements in the United Kingdom",
        [("Annual leave", "Full-time employees in the United Kingdom receive 25 days of paid annual leave plus 8 public holidays. Up "
                          "to 5 unused days may be carried forward to the next year. Leave of more than 5 consecutive days needs "
                          "the manager's approval."),
         ("Sick and family leave", "Employees may self-certify sickness for up to 7 calendar days. Maternity leave is 39 weeks, with "
                                   "the first 12 weeks on full pay. Paternity leave is 2 weeks. Bereavement leave is 3 days.")],
        related=["Leave Policy India", "Leave Policy Singapore"])
    add("Leave Policy Singapore", "NW-HR-LV-SG", 1, "4.2", "1 April 2025", "People Operations Singapore", "leave entitlements in Singapore",
        [("Annual leave", "Full-time employees in Singapore receive 18 days of paid annual leave, rising to 21 days after 5 years of "
                          "service. Up to 7 unused days may be carried forward to the next year."),
         ("Sick and family leave", "Paid outpatient sick leave is 14 days a year and paid hospitalisation leave is 60 days. Maternity "
                                   "leave is 16 weeks. Paternity leave is 2 weeks. Childcare leave is 6 days a year.")],
        related=["Leave Policy India", "Leave Policy United Kingdom"])

    # ---- a stale FAQ that contradicts the current documents
    add("Employee FAQ 2022", "NW-FAQ-022", 1, "1.0", "1 March 2022", "People Operations", "frequently asked staff questions",
        [("Leave and working hours", "Staff in India get 20 days of annual leave. People may work from home two days a week. The "
                                     "core working hours are 10:00 to 17:00."),
         ("Claims and security", "Travel claims must be submitted within 60 days of the trip. Passwords must be changed every 90 days. "
                                 "Client records are kept for 6 years. To report a concern, call the helpline on extension 4412.")],
        related=["Travel and Expense Policy 2023"],
        note="This FAQ is no longer maintained and is kept for reference only.")

    # ---- conduct and speaking up
    add("Code of Conduct", "NW-COC-004", 1, "6.0", "1 January 2025", "Compliance", "professional conduct",
        [("Gifts and hospitality", "Gifts from clients or vendors worth more than INR 7,500 must be declined or reported to "
                                   "Compliance. Cash gifts are never acceptable. Hospitality must be proportionate and open."),
         ("Conflicts of interest", "An employee who has a personal or financial interest in a business decision must declare it to "
                                   "their manager within 7 calendar days of becoming aware of it."),
         ("Outside activities", "Political donations in the company's name are prohibited. Paid outside work needs written "
                                "approval from the manager and Compliance.")],
        related=["Conflicts of Interest Procedure", "Whistleblower Procedure"])
    add("Whistleblower Procedure", "NW-WB-002", 1, "3.0", "1 July 2024", "Compliance", "reporting misconduct",
        [("How to report", "Concerns can be reported anonymously on the ethics line, 1800-555-0142, or by email to the ethics mailbox. "
                           "Every report gets a case reference in the form WB-YEAR-NUMBER."),
         ("What happens next", "The ethics team acknowledges every report within 3 working days. An investigation is closed within 60 "
                               "days, and the reporter is told the outcome where that is possible. Reports about senior leaders go to "
                               "the Audit Committee chair."),
         ("Protection", "Retaliation against a person who reports in good faith is a disciplinary offence.")],
        related=["Code of Conduct", "Disciplinary Procedure"])
    add("Workplace Harassment Prevention Policy", "NW-HR-HAR-01", 1, "2.3", "1 August 2024", "People Operations", "preventing harassment",
        [("Complaints", "A complaint may be made to the Internal Committee in writing or by email, ideally within 90 days of the "
                        "incident. The committee may accept later complaints for good reason."),
         ("Inquiry", "The Internal Committee completes its inquiry within 90 days of receiving the complaint. Interim relief, such as "
                     "a change of reporting line, may be given while the inquiry is running.")],
        related=["Code of Conduct", "Disciplinary Procedure"])

    # ---- working arrangements
    add("Remote and Hybrid Work Policy", "NW-HR-RW-03", 1, "3.1", "1 February 2025", "People Operations", "remote and hybrid work",
        [("Hybrid pattern", "Employees may work remotely up to 3 days a week by agreement with their manager. Core hours are 11:00 to "
                            "16:00 India time, when everyone is expected to be reachable."),
         ("Working from another country", "Work from outside the country of employment needs written approval from People Operations "
                                          "and Information Security and is limited to 45 days in a calendar year."),
         ("Equipment and connection", "Company laptops must use the approved VPN. A home internet stipend of INR 1,200 a month is paid "
                                      "to hybrid employees.")],
        related=["Mobile Device Policy", "Password and Access Standard"])
    add("Onboarding and Probation Policy", "NW-HR-ONB-02", 1, "2.0", "1 January 2024", "People Operations", "joining and probation",
        [("First weeks", "A laptop and building pass are issued on the first day. Mandatory compliance training must be completed "
                         "within 30 days of joining."),
         ("Probation", "Probation lasts 6 months. The confirmation review takes place in month 5. During probation either side may "
                       "end employment with 15 days' notice.")],
        related=["Code of Conduct", "Performance Management Process"])

    # ---- information security
    add("Password and Access Standard", "NW-SEC-PWD-02", 1, "4.0", "1 January 2025", "Information Security", "passwords and system access",
        [("Passwords", "Passwords must be at least 14 characters long. Passwords are not changed on a schedule; they are changed only "
                       "after a suspected compromise. Multi-factor authentication is mandatory for every company system."),
         ("Lockout and privileged access", "An account is locked for 30 minutes after 6 failed sign-in attempts. Privileged accounts "
                                           "are issued through the VaultPlus tool and their access is reviewed every quarter."),
         ("Leavers", "Access for leavers must be removed within 24 hours of the last working day.")],
        related=["Encryption Standard", "Remote and Hybrid Work Policy"])
    add("Encryption Standard", "NW-SEC-ENC-01", 1, "3.2", "1 March 2025", "Information Security", "encryption of data",
        [("Data at rest and in transit", "Data at rest must be encrypted with AES-256. Data in transit must use TLS 1.2 or higher, and "
                                         "TLS 1.3 is preferred."),
         ("Keys", "Encryption keys must be rotated every 365 days. Root keys are kept in a hardware security module."),
         ("Devices and backups", "Laptops must have full-disk encryption switched on. Backups are encrypted with a separate key.")],
        related=["Password and Access Standard", "Data Classification and Handling Standard"])
    add("Mobile Device Policy", "NW-SEC-MOB-01", 1, "2.4", "1 June 2024", "Information Security", "mobile phones and tablets",
        [("Lost devices", "A lost or stolen device must be reported within 2 hours of the loss being noticed. The device is wiped "
                          "remotely within 4 hours of the report."),
         ("Personal devices", "Personal phones may be used for email and calendar only, through the managed work app. An employee may "
                              "register at most 2 devices. A 6-digit passcode is the minimum.")],
        related=["Remote and Hybrid Work Policy", "Acceptable Use Policy"])
    add("Acceptable Use Policy", "NW-SEC-AUP-01", 1, "2.1", "1 September 2024", "Information Security", "acceptable use of company systems",
        [("Personal use", "Limited personal use of company systems is allowed if it does not affect work or security. Company systems "
                          "are monitored, and staff are told about this when they join."),
         ("Artificial intelligence tools", "Only approved generative AI tools may be used for work. Client or confidential data must "
                                           "never be entered into a public AI tool.")],
        related=["Data Classification and Handling Standard", "Mobile Device Policy"])
    add("Data Classification and Handling Standard", "NW-SEC-DCL-01", 1, "2.0", "1 January 2025", "Information Security", "classifying and handling data",
        [("Labels", "Every document carries one of four labels: Public, Internal, Confidential or Restricted. The label is shown in "
                    "the footer."),
         ("Handling", "Restricted data must be encrypted and every access logged. Confidential material may be shared outside the "
                      "company only under a signed non-disclosure agreement.")],
        related=["Encryption Standard", "Data Retention Schedule"])
    add("Data Retention Schedule", "NW-DAT-RET-01", 1, "3.0", "1 January 2025", "Legal", "how long records are kept",
        [("Retention periods", "Client records are kept for 8 years after the relationship ends. Email is kept for 3 years. Call "
                               "recordings are kept for 5 years. Human resources records are kept for 7 years after an employee "
                               "leaves. CCTV footage is kept for 30 days."),
         ("Legal holds", "A legal hold notice, such as LH-2, overrides every retention period until Legal lifts it.")],
        related=["Data Classification and Handling Standard", "Employee FAQ 2022"])

    # ---- level 2: procurement and vendors
    add("Procurement Policy", "NW-PRC-001", 2, "5.0", "1 January 2025", "Procurement", "buying goods and services",
        [("Quotations and approvals", "Purchases above INR 5 lakh need at least three written quotations. Purchases above INR 30 lakh "
                                      "need director approval. Purchases above INR 1 crore need the approval of the chief financial "
                                      "officer and the Procurement Committee."),
         ("Single source and emergencies", "A single-source purchase needs the justification form PR-7. An emergency purchase of up to "
                                           "INR 2 lakh may be made at once and must be approved within 5 working days.")],
        related=["Vendor Onboarding and Due Diligence Procedure", "Contract Management Standard"])
    add("Vendor Onboarding and Due Diligence Procedure", "NW-PRC-VND-01", 2, "3.1", "1 March 2025", "Procurement", "onboarding vendors",
        [("Checks before onboarding", "Every new vendor is screened against sanctions lists and must disclose its beneficial owners. A "
                                      "vendor that handles personal data must sign a data processing agreement."),
         ("Security assessment", "A security assessment must be completed within 20 working days of the request. Critical vendors are "
                                 "reassessed every year and other vendors every 3 years.")],
        related=["Procurement Policy", "Sanctions Screening Standard"])
    add("Contract Management Standard", "NW-LEG-CON-01", 2, "2.2", "1 June 2024", "Legal", "managing contracts",
        [("Review and signature", "Contracts worth more than INR 50 lakh are reviewed by Legal before signature. Every signed contract "
                                  "is filed in the contract repository within 5 working days."),
         ("Renewals and liability", "A contract with an automatic renewal clause needs a renewal decision at least 90 days before the "
                                    "notice date. The liability cap in a vendor contract must be at least 12 months of fees.")],
        related=["Procurement Policy"])

    # ---- level 2: financial crime and resilience
    add("KYC and AML Procedure", "NW-CMP-KYC-01", 2, "4.1", "1 January 2025", "Compliance", "customer due diligence and money laundering",
        [("Onboarding", "Identity must be verified before an account is opened. Politically exposed persons need enhanced due diligence "
                        "on form KYC-EDD-2. Customer details are refreshed every year for high-risk customers, every 3 years for "
                        "medium-risk customers and every 5 years for low-risk customers."),
         ("Reporting", "Transactions above INR 10 lakh are reported to the monitoring team. Suspicious activity is escalated to the "
                       "MLRO within 24 hours, and a suspicious transaction report is filed within 7 days of the decision.")],
        related=["Sanctions Screening Standard", "Data Retention Schedule"])
    add("Sanctions Screening Standard", "NW-CMP-SAN-01", 2, "2.0", "1 February 2025", "Compliance", "sanctions screening",
        [("Screening", "Customers are screened against the UN, OFAC, EU and UK OFSI lists at onboarding and every day afterwards."),
         ("Matches", "A potential match is reviewed within 4 hours. A confirmed match means the account is frozen and the head of "
                     "Compliance is told within 1 hour.")],
        related=["KYC and AML Procedure", "Vendor Onboarding and Due Diligence Procedure"])
    add("Incident Response Runbook", "NW-SEC-IR-04", 2, "5.2", "1 January 2025", "Information Security", "security incidents",
        [("Classification", "The on-call security lead classifies every incident as low, medium or high within 30 minutes. The "
                            "playbook for a high incident is IR-HIGH-3."),
         ("Escalation", "For a high incident the chief information security officer is told within 20 minutes and the crisis call "
                        "starts within 45 minutes. The regulator is notified within 6 hours of the incident being confirmed."),
         ("After the incident", "A written post-incident review is due within 7 working days.")],
        related=["Business Continuity Plan", "Password and Access Standard"])
    add("Business Continuity Plan", "NW-BCP-001", 2, "3.0", "1 May 2025", "Operations", "keeping the business running",
        [("Recovery targets", "Tier 1 systems must be recovered within 4 hours and lose no more than 15 minutes of data. Tier 2 systems "
                              "must be recovered within 24 hours and lose no more than 4 hours of data."),
         ("Testing and sites", "The plan is tested twice a year. The alternate site is in Pune.")],
        related=["Incident Response Runbook"])

    # ---- level 2: people processes
    add("Performance Management Process", "NW-HR-PERF-02", 2, "4.0", "1 January 2025", "People Operations", "performance reviews and promotion",
        [("Cycle", "There is a mid-year review in July and an annual review in January. Managers rate each employee on a 5-point scale and "
                   "send ratings to the calibration committee."),
         ("Promotion and improvement", "Promotion to the next grade needs two consecutive ratings of 4 or above. A performance "
                                       "improvement plan lasts 90 days.")],
        related=["Disciplinary Procedure", "Onboarding and Probation Policy"])
    add("Disciplinary Procedure", "NW-HR-DIS-01", 2, "2.5", "1 September 2024", "People Operations", "disciplinary action",
        [("Investigation and warnings", "An investigation must start and finish within 30 days. A written warning stays on file for 12 months."),
         ("Suspension and appeal", "Suspension on full pay may last up to 14 days. An employee may appeal to the HR Director within 10 "
                                   "working days of the decision.")],
        related=["Code of Conduct", "Whistleblower Procedure"])
    add("Conflicts of Interest Procedure", "NW-CMP-COI-01", 2, "2.0", "1 January 2025", "Compliance", "conflicts of interest",
        [("Declaring", "A conflict of interest must be declared to Compliance within 5 working days of becoming aware of it, using the "
                       "conflicts register. Every employee also makes an annual declaration by 30 April."),
         ("Managing", "Compliance decides whether the person steps back from the decision, and the outcome is recorded in the register.")],
        related=["Code of Conduct"])

    # ---- level 3
    add("Compensation Bands and Bonus Framework", "NW-HR-COMP-01", 3, "3.0", "1 April 2025", "Reward Committee", "pay and bonus",
        [("Bonus pool", "The variable pay pool is 15 percent of profit before tax, capped at INR 40 crore a year."),
         ("Targets and deferral", "The target bonus is 20 percent of salary at grade G4 and 30 percent at grade G5. For grade G5 and "
                                  "above, 40 percent of the bonus is deferred over 3 years. Bonus can be clawed back for 3 years.")],
        related=["Attrition and Engagement Report 2025"])
    add("Operational Risk Register", "NW-RSK-REG-25", 3, "2025.3", "30 September 2025", "Risk Management", "operational risks",
        [("Top risks", "The three highest operational risks are concentration on a single cloud provider, dependence on key people in "
                       "the payments team, and regulatory change in digital lending."),
         ("Ratings and owners", "The cloud concentration risk is rated high and is owned by the chief technology officer. The register is "
                                "reviewed every quarter.")],
        related=["Board Risk Committee Charter", "Business Continuity Plan"])
    add("Board Risk Committee Charter", "NW-GOV-BRC-01", 3, "1.4", "1 January 2025", "Company Secretary", "the board risk committee",
        [("Membership and meetings", "The committee meets every quarter. A quorum is 3 members. The chair must be an independent director."),
         ("Duties", "The committee reviews the operational risk register and approves the risk appetite statement each year.")],
        related=["Operational Risk Register"])
    add("Attrition and Engagement Report 2025", "NW-HR-ATT-25", 3, "1.0", "15 January 2026", "People Analytics", "staff attrition",
        [("Headline", "Overall employee attrition for 2025 was 12.4 percent, down from 14.9 percent in 2024. Attrition was highest in "
                      "technology at 19.8 percent and lowest in compliance at 5.1 percent."),
         ("Reasons", "Exit interviews give career growth and pay as the two main reasons for leaving.")],
        related=["Compensation Bands and Bonus Framework"])
    return d


# --------------------------------------------------------------------------------------------- the questions
A, M, D = "analyst@northwind.test", "manager@northwind.test", "director@northwind.test"


def q(kind, user, question, doc, *phrases):
    return {"category": "answerable", "kind": kind, "user": user, "question": question, "expect_doc": doc,
            "expect_docs": [doc], "must_contain_any": list(phrases)}


def q2(kind, user, question, docs, groups):
    return {"category": "multi_part", "kind": kind, "user": user, "question": question, "expect_docs": list(docs),
            "must_contain_groups": groups}


def build_questions() -> List[Dict]:
    T25, T23 = "Travel and Expense Policy 2025", "Travel and Expense Policy 2023"
    s = []
    # --- everyday wording (some typos, as people type)
    s += [
        q("lookup", A, "by when do i need to put in my expense claim after coming back from a trip", T25, "30 days"),
        q("lookup", A, "what is the most I can spend on a hotel per night in Mumbai", T25, "8,000"),
        q("lookup", A, "can I fly business class to Frankfurt", T25, "9 hours", "director"),
        q("lookup", A, "do I need a receipt for a small taxi fare", T25, "500"),
        q("lookup", A, "how much can I spend on a client dinner per head", T25, "4,000"),
        q("lookup", A, "How do I get my home internet paid for when I work from home", "Remote and Hybrid Work Policy", "1,200"),
        q("lookup", A, "how long can I work from another country in a year", "Remote and Hybrid Work Policy", "45 days"),
        q("lookup", A, "what are the hours when I must be online if I work remotely", "Remote and Hybrid Work Policy", "11:00"),
        q("lookup", A, "how long does a password have to be", "Password and Access Standard", "14 characters"),
        q("lookup", A, "when do I have to change my password", "Password and Access Standard", "not changed on a schedule", "compromise"),
        q("lookup", A, "my laptop got stolen, how fast do I tell IT", "Mobile Device Policy", "2 hours"),
        q("lookup", A, "can i paste client data into chatgpt", "Acceptable Use Policy", "never be entered", "public ai tool"),
        q("lookup", A, "which encryption is required for stored data", "Encryption Standard", "AES-256"),
        q("lookup", A, "how long do we keep client files after they leave", "Data Retention Schedule", "8 years"),
        q("lookup", A, "what is the value of a gift I must report to compliance", "Code of Conduct", "7,500"),
        q("lookup", A, "how quickly will the ethics team respond when I report something", "Whistleblower Procedure", "3 working days"),
        q("lookup", A, "How long is the probation period and how much notice do I give during it", "Onboarding and Probation Policy", "6 months", "15 days"),
        q("lookup", M, "who has to approve a purchase of 40 lakh rupees", "Procurement Policy", "director approval"),
        q("lookup", M, "how many days do we have to finish the security check on a new supplier", "Vendor Onboarding and Due Diligence Procedure", "20 working days"),
        q("lookup", M, "how fast must a suspicious customer transaction be escalated", "KYC and AML Procedure", "24 hours"),
        q("lookup", M, "within how long must a system outage affecting Tier 1 be fixed", "Business Continuity Plan", "4 hours"),
        q("lookup", M, "how many days does a performance improvement plan last", "Performance Management Process", "90 days"),
        q("lookup", D, "what percent of profit goes into the bonus pool", "Compensation Bands and Bonus Framework", "15 percent"),
        q("lookup", D, "which function has the lowest attrition", "Attrition and Engagement Report 2025", "compliance at 5.1"),
    ]
    # --- region: same question, near-identical documents; the country decides
    s += [
        q("region", A, "how many days of annual leave do staff in Singapore get", "Leave Policy Singapore", "18 days"),
        q("region", A, "how much maternity leave in the UK", "Leave Policy United Kingdom", "39 weeks"),
        q("region", A, "how many unused leave days can I carry over in India", "Leave Policy India", "10 unused days", "up to 10"),
        q("region", A, "what is the paternity leave in Singapore", "Leave Policy Singapore", "2 weeks"),
        q("region", A, "sick leave rules for self certification in the UK", "Leave Policy United Kingdom", "7 calendar days"),
        q("region", A, "how much bereavement leave do employees in India get", "Leave Policy India", "5 days"),
    ]
    # --- version: both versions are published; the question asks for the rule that applies now
    s += [
        q("current-version", A, "what is the current deadline to submit travel claims", T25, "30 days"),
        q("current-version", A, "what is the flight class rule for a 7 hour flight now", T25, "premium economy"),
        q("current-version", A, "at what trip cost does a director need to approve before booking", T25, "150,000"),
        q("current-version", A, "what is the daily meal allowance under the latest travel policy", T25, "1,500"),
        q("old-version", A, "what was the travel claim deadline in the 2023 policy", T23, "45 days"),
        q("old-version", A, "under the old travel policy, what hotel limit applied in metro cities", T23, "9,000"),
    ]
    # --- exact terms: codes, forms, numbers, tools a person types as a search
    s += [
        q("exact-term", M, "form PR-7", "Procurement Policy", "PR-7"),
        q("exact-term", A, "1800-555-0142", "Whistleblower Procedure", "1800-555-0142"),
        q("exact-term", A, "VaultPlus", "Password and Access Standard", "VaultPlus"),
        q("exact-term", M, "IR-HIGH-3", "Incident Response Runbook", "IR-HIGH-3"),
        q("exact-term", A, "legal hold LH-2", "Data Retention Schedule", "LH-2"),
        q("exact-term", M, "KYC-EDD-2", "KYC and AML Procedure", "KYC-EDD-2"),
        q("exact-term", M, "MLRO", "KYC and AML Procedure", "MLRO"),
        q("exact-term", M, "alternate site Pune", "Business Continuity Plan", "Pune"),
        q("exact-term", A, "NorthTrip", T25, "NorthTrip"),
        q("exact-term", A, "NW-SEC-ENC-01", "Encryption Standard", "NW-SEC-ENC-01"),
    ]
    # --- needs two documents
    s += [
        q2("multi-document", M, "Who must approve a vendor contract worth 2 crore rupees and how long does the security assessment of the vendor take?",
           ["Procurement Policy", "Vendor Onboarding and Due Diligence Procedure"], [["chief financial officer", "cfo"], ["20 working days"]]),
        q2("multi-document", A, "How many days of leave do UK employees get and how long can I work abroad in a year?",
           ["Leave Policy United Kingdom", "Remote and Hybrid Work Policy"], [["25 days"], ["45 days"]]),
        q2("multi-document", M, "How quickly must a confirmed sanctions match be reported and how quickly must a suspicious transaction be escalated?",
           ["Sanctions Screening Standard", "KYC and AML Procedure"], [["1 hour"], ["24 hours"]]),
        q2("two-part", A, "What encryption is required for laptops and how long are encryption keys used before rotation?",
           ["Encryption Standard"], [["full-disk"], ["365 days"]]),
        q2("multi-document", M, "How long do I have to tell the regulator about a confirmed incident and what is the recovery time for Tier 1 systems?",
           ["Incident Response Runbook", "Business Continuity Plan"], [["6 hours"], ["4 hours"]]),
    ]
    # --- ambiguous: no country given, all three leave policies are relevant
    s += [
        q2("ambiguous", A, "how many days of annual leave do I get", ["Leave Policy India", "Leave Policy United Kingdom", "Leave Policy Singapore"],
           [["24 days"], ["25 days"], ["18 days"]]),
        q2("ambiguous", A, "what is the carry forward limit for leave", ["Leave Policy India", "Leave Policy United Kingdom", "Leave Policy Singapore"],
           [["10 unused days"], ["5 unused days"], ["7 unused days"]]),
    ]
    # --- two documents disagree
    s += [
        q2("conflict", M, "how soon must I declare a conflict of interest", ["Code of Conduct", "Conflicts of Interest Procedure"],
           [["7 calendar days"], ["5 working days"]]),
    ]
    return s


def build_refusals() -> List[Dict]:
    """Questions the right answer to which is a refusal: above the person's level, or not in any document."""
    r = []
    for question, forbidden in [
        ("how big is the bonus pool for the company", ["15 percent", "40 crore"]),
        ("which department has the highest attrition and what is the rate", ["19.8"]),
        ("what are the top operational risks and who owns the cloud risk", ["concentration", "chief technology officer"]),
        ("what is the target bonus at grade G5", ["30 percent"]),
        ("how often does the board risk committee meet and what is the quorum", ["quorum is 3"]),
    ]:
        r.append({"category": "restricted", "kind": "restricted", "user": A, "question": question, "forbidden": forbidden})
    r.append({"category": "restricted", "kind": "restricted", "user": M, "question": "what is the deferred share of bonus for grade G5",
              "forbidden": ["40 percent"]})
    for question in [
        "what is the dress code for client meetings",
        "how many stock options do new joiners get and when do they vest",
        "is there a parking allowance at the Pune office",
        "what is the relocation allowance when moving cities",
        "what is the policy on sabbaticals",
        "how much is the learning and development budget per employee",
    ]:
        r.append({"category": "unsupported", "kind": "not-in-documents", "user": A, "question": question, "forbidden": []})
    r.append({"category": "off_topic", "kind": "off-topic", "user": A, "question": "who won the cricket match yesterday", "forbidden": []})
    return r


def all_cases() -> List[Dict]:
    return build_questions() + build_refusals()


def documents_markdown(docs: List[Dict]) -> str:
    names = {1: "Analyst and above (level 1)", 2: "Manager and above (level 2)", 3: "Director and above (level 3)"}
    out = [f"# {COMPANY}: documents (fictional)", "", "Everything here is made up for a software project. Built to be hard: long, "
           "near-duplicate, versioned, partly stale and partly contradictory. Generated by `scripts/hardcorp_data.py`.", ""]
    for doc in docs:
        out += [f"## {doc['title']}", f"*Who may read it: {names[doc['level']]}*", "", doc["text"], ""]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    if "--write" in sys.argv:
        docs, cases = build_documents(), all_cases()
        Path("evaluation/hardcorp_set.json").write_text(json.dumps(cases, indent=1, ensure_ascii=False) + "\n")
        Path("evaluation/hardcorp_documents.md").write_text(documents_markdown(docs))
        words = sum(len(x["text"].split()) for x in docs)
        print(f"{len(docs)} documents, {words} words, {len(cases)} questions")
    else:
        print(__doc__)
