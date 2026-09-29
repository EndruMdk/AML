# AML — Anticipation Market Lab

AML (Anticipation Market Lab) is a web-based prediction market platform built around real-world events. Users predict event outcomes by staking the virtual currency **AuraCoins**—no real money is involved. The core of the application is a personalized feed of active Yes/No events with dynamic odds and voting deadlines.

The project was developed for the [Principles of Software Engineering (SI3PSI)](https://si3psi.etf.bg.ac.rs/) course at the University of Belgrade School of Electrical Engineering. This repository covers the complete project lifecycle: the initial idea, requirements specification, prototype, formal inspection, database design, implementation, UML models, and testing.

## Team

This project was created collaboratively by a four-member team:

- Andrija Trnavčević
- Luka Pantović
- Vuk Bojović
- Mihailo Mandić

The work was not divided into isolated, member-owned modules. **Every team member participated in every project phase and contributed to the analysis, documentation, design, implementation, and testing.** Decisions and responsibility for the final solution were shared by the entire team.

## Features

### Guest

- Browse active events and current odds.
- Receive a registration prompt when attempting to vote.

### Registered user

- Register, sign in, sign out, and reset a forgotten password.
- Select and update topics of interest.
- Browse a personalized event feed.
- Search and filter events by title and category.
- Vote Yes or No by staking AuraCoins.
- View odds that change dynamically based on total stakes.
- Check the wallet balance and transaction history.
- Review active and completed votes.
- View prediction accuracy and profit/loss statistics.

### Arbitrator

- Apply for an arbitrator account by submitting a CV.
- Review event suggestions retrieved from Polymarket.
- Create and publish events manually.
- Close events and determine their final outcome.
- Trigger automatic payouts to winning users.

### Administrator

- Approve or reject arbitrator applications.
- Ban and reactivate user accounts.
- Manually adjust AuraCoin balances.
- View aggregate platform statistics.
- Review an audit trail of important administrator and arbitrator actions.

## Project phases and documentation

| Phase | Repository contents |
| --- | --- |
| Initial idea and project proposal | `AML.docx` — problem statement, users, features, constraints, and priorities |
| Requirements and prototype | `SSU/` — use-case specifications; `Prototip/` — HTML screen prototypes |
| Formal inspection | `FR/` — inspector logs, meeting report, and defect report |
| Database design | `Baza/` — specification, MySQL Workbench model, SQL dump, and model image |
| Web application implementation | Django applications: `accounts`, `events`, `betting`, `wallet`, and `core` |
| UML modeling | `UML/` — use-case, class, and sequence diagrams in PNG and PlantUML formats |
| Testing | `tests/`, tests inside the Django applications, and `VAMP Katalon testiranje.krecorder` |

## Technology stack

- Python 3.14.6
- Django 6.0.7
- MySQL and `mysqlclient`
- HTML, CSS, and JavaScript
- Selenium 4.46.0
- Polymarket API for real-world event suggestions
- PlantUML for UML models
- MySQL Workbench for database modeling
- Git for version control and team collaboration

Exact Python package versions are listed in `requirements.txt`.

## Project structure

```text
.
├── accounts/       # users, roles, and arbitrator applications
├── events/         # events, feed, odds, creation, and resolution
├── betting/        # votes and voting history
├── wallet/         # AuraCoin wallets and transactions
├── core/           # administration, audit logs, and statistics
├── templates/      # shared Django templates
├── static/         # CSS, JavaScript, images, and fonts
├── tests/          # functional, integration, and Selenium tests
├── Baza/           # database model and documentation
├── FR/             # formal inspection artifacts
├── Prototip/       # interactive HTML prototype
├── SSU/            # use-case specifications
├── UML/            # UML source files and exported images
├── AML.docx        # initial project proposal
├── manage.py
└── requirements.txt
```

## Local setup

### Prerequisites

- Python 3.14 (the project was developed with Python 3.14.6)
- MySQL 8
- Google Chrome for Selenium tests

### 1. Create a virtual environment and install dependencies

```bash
python -m venv .venv
```

Activate it in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Activate it on Linux or macOS:

```bash
source .venv/bin/activate
```

Install the required packages:

```bash
python -m pip install -r requirements.txt
```

### 2. Configure the database and environment variables

Create an empty MySQL database:

```sql
CREATE DATABASE AMLDB CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy `.env.example` to `.env` and enter your local database credentials:

```env
SECRET_KEY=enter-a-local-secret-key
DEBUG=True

DB_NAME=AMLDB
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

The `.env` file contains local secrets and must not be committed to GitHub.

### 3. Apply migrations and run the application

```bash
python manage.py migrate
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`.

The migrations create a development administrator account with the username `admin` and password `admin`. Change these credentials before deploying the application publicly.

### 4. Fetch event suggestions

To retrieve current event suggestions from the Polymarket API:

```bash
python manage.py fetch_suggested_events --limit 100
```

This command requires an internet connection. An arbitrator can review the retrieved suggestions, complete the required information, and publish a selected event.

## Testing

Run the complete Django test suite with:

```bash
python manage.py test
```

The test suite covers models, controllers, access control, input validation, registration and authentication flows, the event feed, dynamic odds, voting, wallets, administration, and event creation and resolution. Selenium scenarios run Chrome in headless mode, so Chrome must be installed and available on the system.

An additional Katalon scenario is stored in `VAMP Katalon testiranje.krecorder`.

## Notes

- AuraCoins are a virtual currency with no monetary value.
- Dynamic odds are a simplified prediction-market simulation, not an actuarial model for real-money betting.
- `Baza/AMLDB_dump.sql` is an artifact from the database-design phase. To run the current Django application, create an empty database and apply the Django migrations.
- User uploads, the local database, `.env`, virtual environments, and IDE settings are intentionally excluded from the repository.

## Academic context

The project demonstrates the practical application of software engineering principles throughout a complete development process: requirements engineering, prototyping, formal inspection, database design, object-oriented and UML modeling, collaborative implementation with version control, and automated testing.
