"""The evaluation dataset: 10 real prompts + 10 edge cases.

Each prompt has a label, the text, and an ``expected`` outcome class so the
runner can score "did the right thing happen?", not just "did it parse?":

  * compiles    -- a clean prompt should yield a valid blueprint
  * clarifies   -- an empty/too-short prompt should ask a clarifying question
  * assumes     -- a vague/conflicting/underspecified prompt should still yield a
                   blueprint, but with assumptions recorded
"""

from dataclasses import dataclass
from typing import Literal

ExpectedOutcome = Literal["compiles", "clarifies", "assumes"]


@dataclass(frozen=True)
class Case:
    id: str
    label: str
    request: str
    expected: ExpectedOutcome


REAL_PROMPTS: list[Case] = [
    Case("R01", "CRM (canonical)",
         "Build a CRM with login, contacts, dashboard, role-based access, "
         "premium plan with payments, and an admin-only analytics page.", "compiles"),
    Case("R02", "Todo app",
         "Build a todo app with projects, tasks, due dates, and per-user lists.", "compiles"),
    Case("R03", "Blog",
         "A blog with posts, comments, tags, an author role, and a public read view.", "compiles"),
    Case("R04", "Bookings",
         "A booking system for hair salons: services, stylists, appointments, customer accounts.", "compiles"),
    Case("R05", "Issue tracker",
         "An issue tracker with projects, tickets, statuses, assignees, comments, and admin-only delete.", "compiles"),
    Case("R06", "Expense tracker",
         "Personal expense tracker with categories, monthly budgets, recurring expenses, and summary charts.", "compiles"),
    Case("R07", "E-commerce",
         "Small e-commerce store: products, cart, orders, customers, and an admin dashboard.", "compiles"),
    Case("R08", "Inventory",
         "Inventory management for a small warehouse: items, suppliers, stock movements, and low-stock alerts.", "compiles"),
    Case("R09", "Forum",
         "Online forum: categories, threads, posts, users, and moderator role for hiding content.", "compiles"),
    Case("R10", "Habit tracker",
         "Habit tracker: habits, daily check-ins, streaks, and reminder schedule per user.", "compiles"),
]

EDGE_CASES: list[Case] = [
    # vague
    Case("E01", "Empty",            "", "clarifies"),
    Case("E02", "Too short",        "app", "clarifies"),
    Case("E03", "Vague: make app",  "Make me an app.", "assumes"),
    Case("E04", "Vague: cool",      "Build something cool.", "assumes"),
    # conflicting
    Case("E05", "No login + roles",
         "A notes app with no login, but only admins can delete notes.", "assumes"),
    Case("E06", "No DB + save",
         "A chat app with no database, but it should keep all messages forever.", "assumes"),
    Case("E07", "Free + premium",
         "A free-forever todo app with a premium subscription tier for power users.", "assumes"),
    # incomplete / underspecified
    Case("E08", "Domain only",      "A blog.", "assumes"),
    Case("E09", "Feature only",     "An app with comments and likes.", "assumes"),
    Case("E10", "No auth mention",  "A wiki where users can edit any page.", "assumes"),
]

ALL_CASES: list[Case] = REAL_PROMPTS + EDGE_CASES
