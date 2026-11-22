"""Generate the first golden dataset: 200 synthetic support tickets.

Fictional product: CareSlot, a clinic appointment-booking app.
We plant 8 known problems at different frequencies, then mix in one-off
noise tickets. Because we know the answer, we can score the synthesis stage:
how many of the 8 does it find, and does it rank the frequent ones higher?

Run:  python generate.py   (writes tickets.csv and planted_problems.json)
The output is committed, so evals are reproducible. Seed is fixed.
"""

import csv
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)
HERE = Path(__file__).parent

CLINICS = ["Lakeview Family Clinic", "Northside Pediatrics", "Greenfield Dental",
           "City Heart Centre", "Riverside Skin Clinic", "Hillcrest Ortho"]
DOCTORS = ["Dr. Mehta", "Dr. Alvarez", "Dr. Chen", "Dr. Okafor", "Dr. Rao", "Dr. Lindqvist"]
TIMES = ["9:30 AM", "10:15 AM", "11:00 AM", "2:45 PM", "4:30 PM", "6:00 PM"]
CHANNELS = ["email", "in-app chat", "app store review", "phone (transcribed)"]


def fill(template: str) -> str:
    return template.format(
        clinic=random.choice(CLINICS),
        doctor=random.choice(DOCTORS),
        time=random.choice(TIMES),
        n=random.randint(2, 5),
    )


# id, title, expected frequency, severity, phrasings
PLANTED = [
    ("P1", "Appointment reminders arrive late or at the wrong time", 30, "high", [
        ("Reminder came after my appointment",
         "Got the SMS reminder for my {time} slot with {doctor} about an hour AFTER the appointment. Missed it and got charged a no-show fee."),
        ("Wrong time in reminder",
         "The reminder text says my visit at {clinic} is at a different time than what the app shows. Which one is right??"),
        ("Reminder timing is off",
         "Reminders keep showing up late. I travel between cities and I think it's using the wrong time zone."),
        ("No-show fee unfair",
         "You charged me a no-show fee but your reminder arrived when I was supposed to already be at {clinic}. Please refund."),
        ("Notification delay",
         "Push notification for my appointment with {doctor} came the next morning. Useless."),
    ]),
    ("P2", "No way to reschedule; cancelling to rebook loses the slot", 22, "high", [
        ("How do I reschedule?",
         "I need to move my appointment with {doctor} by a day. Only option is cancel. If I cancel will I lose my spot?"),
        ("Lost my slot",
         "Cancelled my {time} booking to pick a new time and by then all slots at {clinic} were gone for {n} weeks. Please add a reschedule button."),
        ("Reschedule option missing",
         "Every other booking app lets you change the time. Why do I have to cancel and start over?"),
        ("Rebooking is painful",
         "Had to cancel and rebook {n} times this month because my shifts change. Each time I fill the whole form again."),
    ]),
    ("P3", "Payment charged twice when the app times out at checkout", 18, "critical", [
        ("Charged twice",
         "The payment screen froze, I tapped pay again and now I see two charges for the same consult at {clinic}."),
        ("Double payment",
         "App said 'something went wrong' at checkout but my card was charged. Tried again, charged again. Need a refund for one."),
        ("Duplicate charge on my card",
         "My bank statement shows the consultation fee twice on the same day. Only one appointment was booked."),
        ("Payment timeout",
         "Checkout spins forever on mobile data then fails, but money is gone. This happened {n} times."),
    ]),
    ("P4", "Doctor search ignores the language-spoken filter", 14, "medium", [
        ("Language filter not working",
         "I filtered for doctors who speak Tamil and it still shows everyone, including {doctor} who doesn't."),
        ("Need doctor who speaks my language",
         "Booked for my mother using the Hindi filter. The doctor at {clinic} only spoke English. She couldn't explain her symptoms."),
        ("Search filters broken",
         "Language filter seems to do nothing. Results are identical with or without it."),
    ]),
    ("P5", "Can't book for family members from one account", 10, "medium", [
        ("Booking for my child",
         "I want to book a visit for my son at {clinic} but the form only takes my own details. Do I need a separate account for a {n} year old?"),
        ("Family profiles",
         "I manage appointments for both my parents. Logging in and out of three accounts is exhausting. Please add family members."),
        ("Book for someone else",
         "There's no way to book on behalf of my wife. The confirmation goes to me and the clinic has my name, not hers."),
    ]),
    ("P6", "Video consult link fails on Android in-app browser", 8, "high", [
        ("Video call won't open",
         "Tapped 'Join video consult' for my {time} appointment and got a blank screen. Using a Samsung phone."),
        ("Can't join teleconsult",
         "Video link opens inside the app and asks for camera permission forever. Had to call the clinic instead. Android 14."),
        ("Video consult broken on Android",
         "My husband's iPhone joins fine but my Android just shows a spinner on the video consult page."),
    ]),
    ("P7", "Prescription PDF downloads blank or won't open", 6, "medium", [
        ("Prescription is blank",
         "{doctor} said the prescription is in the app. The PDF downloads but every page is blank."),
        ("Cannot download prescription",
         "Pharmacy needs the prescription from my visit at {clinic}. Download button does nothing."),
    ]),
    ("P8", "Clinic staff can't see notes patients add when booking", 4, "medium", [
        ("Notes ignored",
         "I wrote in the booking notes that I need wheelchair access. The receptionist at {clinic} said they never see those notes."),
        ("Does the clinic read my notes?",
         "I added my allergy details in the notes field. {doctor}'s assistant had no idea. What's the point of that field?"),
    ]),
]

NOISE = [
    ("Forgot password", "I can't log in, reset email never arrives. Checked spam."),
    ("Change phone number", "I have a new number. How do I update it in my profile?"),
    ("Great app", "Booked a visit at {clinic} in 2 minutes. Love it."),
    ("Insurance question", "Does {clinic} accept my insurance? The app doesn't say."),
    ("Clinic hours", "What time does {clinic} close on Sundays?"),
    ("Dark mode please", "Would love a dark mode. The white screen is harsh at night."),
    ("Thanks to {doctor}", "{doctor} was wonderful. Please pass on my thanks."),
    ("Delete my account", "Please delete my account and data."),
    ("App slow today", "Everything is loading slowly today. Is there an outage?"),
    ("Receipt for claim", "Where can I find an itemised receipt for my employer claim?"),
    ("Parking info", "Is there parking at {clinic}? Would be nice to show in the app."),
    ("Wrong clinic address", "The map pin for {clinic} is on the wrong street."),
    ("Rating a doctor", "How do I leave a review for {doctor}?"),
    ("Referral letter", "My GP gave me a referral letter. Where do I upload it?"),
    ("Promo code not working", "The WELCOME10 code says invalid."),
]


def main() -> None:
    rows = []
    truth = []
    for pid, title, count, severity, phrasings in PLANTED:
        for _ in range(count):
            subject, body = random.choice(phrasings)
            rows.append({"pid": pid, "subject": fill(subject), "body": fill(body)})
        truth.append({"id": pid, "title": title, "expected_count": count,
                      "severity": severity})

    noise_count = 200 - len(rows)
    for _ in range(noise_count):
        subject, body = random.choice(NOISE)
        rows.append({"pid": None, "subject": fill(subject), "body": fill(body)})

    random.shuffle(rows)
    start = datetime(2026, 9, 1, 8, 0)
    out = []
    for i, r in enumerate(rows, start=1):
        tid = f"T-{i:04d}"
        if r["pid"]:
            next(t for t in truth if t["id"] == r["pid"]).setdefault("ticket_ids", []).append(tid)
        out.append({
            "ticket_id": tid,
            "created_at": (start + timedelta(hours=random.randint(0, 24 * 60))).isoformat(timespec="minutes"),
            "channel": random.choice(CHANNELS),
            "subject": r["subject"],
            "body": r["body"],
        })
    out.sort(key=lambda r: r["created_at"])

    with open(HERE / "tickets.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        writer.writeheader()
        writer.writerows(out)

    with open(HERE / "planted_problems.json", "w", encoding="utf-8") as f:
        json.dump({"dataset": "clinic_tickets_v1", "total_tickets": len(out),
                   "noise_tickets": noise_count, "problems": truth}, f, indent=2)

    print(f"Wrote {len(out)} tickets, {len(truth)} planted problems, {noise_count} noise")


if __name__ == "__main__":
    main()
