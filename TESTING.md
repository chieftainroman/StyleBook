# Testing Showpiece

339 tests. 312 pass today. The other 27 describe 17 known bugs and fail on purpose until each fix is applied.

## Run the tests

You need a **local** Postgres (not SQLite: `MasterProfile.languages` is an `ArrayField`).

```bash
source venv/bin/activate
export TEST_DATABASE_URL=postgres://localhost:5432/stylebook   # LOCAL Postgres only, never Render

python manage.py test --settings=core.settings_test --exclude-tag=known_bug   # should end with OK
python manage.py test --settings=core.settings_test --tag=known_bug           # the open bugs (fail until fixed)
python manage.py test --settings=core.settings_test                           # everything
python manage.py test --settings=core.settings_test portfolio.tests.test_services   # one file
```

**Always add `--settings=core.settings_test`.** `core/settings_test.py` ignores `DATABASE_URL` on purpose, so a test run can never touch production even if `.env` points there. Django creates a throwaway `test_stylebook` database and deletes it afterwards.

## See what the tests don't reach (coverage)

```bash
coverage run manage.py test --settings=core.settings_test --exclude-tag=known_bug
coverage report       # % of lines run, per file
coverage html         # then open htmlcov/index.html: untested lines are red
```

`.coveragerc` already limits the report to the app code.

## Where the tests are

| Folder | Covers |
| --- | --- |
| `bookings/tests/` | Available times, the client booking journey, codes, cancel/reschedule links, master actions, models, signed links |
| `accounts/tests/` | Login, sign-up, password reset, email verification, onboarding, middleware |
| `portfolio/tests/` | Profile, edit profile, services, experience/certificates/honors, uploads, ownership, Instagram generator, template filters |
| `core/tests/` | Every page opens without a server error; branding |
| `*/tests/test_bugs.py` | The 17 known bugs below, tagged `known_bug` |
| `core/factories.py` | Helpers that build test data: `make_master`, `make_service`, `make_booking`, `make_otp`, `day_at`, `future_day` |

## Known bugs

Each fix patch removes the `known_bug` tag from its own tests, so a fixed bug is guarded from then on.

| # | Bug |
| --- | --- |
| 1 | An abandoned booking (code never entered) blocks the time slot forever |
| 2 | Server runs on Chicago time, an hour behind New York |
| 3 | Deleting a service that was ever booked crashes |
| 4 | Cancel/reschedule links die after 30 days, but clients can book 90 days ahead |
| 5 | A master can revive a cancelled booking into a double booking |
| 6 | Login `?next=` can redirect to another site (phishing) |
| 7 | Two accounts can share one email with different capitals |
| 8 | A client can't move their booking by 15 minutes |
| 9 | Two clients booking the same slot at the same moment both succeed |
| 10 | A mangled cancel link crashes instead of showing "link unavailable" |
| 11 | Production starts quietly with missing or unsafe settings |
| 12 | Usernames like `john/doe`, `edit` or a 200-character name break pages |
| 13 | Bad input or a failing email/Cloudinary call shows a server error page |
| 14 | Public profile's client count ignores real bookings |
| 15 | If the code email fails, the client is told it was sent |
| 16 | "StyleBook" still shows in emails, page titles, QR downloads, Instagram images |
| 17 | The "link unavailable" page never says why |

## Writing a new test

1. Pick the file for that area, or make `test_<something>.py` in the app's `tests/` folder.
2. Build the data with `core/factories.py`, do one action with `self.client`, check what a user would notice.
3. Run that one file. A new test should fail first if you're writing it for a bug, then pass after the fix.
4. Found a bug you can't fix now? Write the test, put `@tag('known_bug')` on it, and add it to the table above.
