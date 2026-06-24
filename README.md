# DevCrypt

## Decode. Collaborate. Restore the Core.

DevCrypt is a six-vault cyber incident response simulation built with Flask and Python. It combines software engineering, cybersecurity, databases, networking, and incident response into a collaborative challenge where participants investigate a large-scale cyberattack and restore critical systems.

Unlike traditional coding competitions or Capture-The-Flag (CTF) events, DevCrypt focuses on teamwork, engineering decision-making, debugging, security analysis, and real-world problem solving.

---

# Vision

DevCrypt recreates how modern technology teams respond to incidents under pressure.

Participants do not simply answer questions or solve isolated coding puzzles. Instead, they investigate evidence, identify vulnerabilities, repair systems, recover compromised data, and work together to restore a fictional smart city known as Metaverse City.

The experience is designed to mirror real engineering and security workflows while remaining engaging and competitive.

---

# Product Overview

Teams act as an emergency response unit tasked with restoring city infrastructure after a devastating cyberattack.

Throughout the simulation participants:

* Investigate technical evidence
* Analyze compromised systems
* Fix security vulnerabilities
* Recover encrypted intelligence
* Collaborate under time pressure
* Restore critical services

Each completed vault reveals part of the final recovery sequence.

Successfully completing all six vaults reveals:

```text
FLAG{METAVERSE RESTORED}
```

---

# Learning Outcomes

Participants will learn to:

* Analyze technical evidence
* Investigate cybersecurity incidents
* Debug production-like systems
* Apply secure coding principles
* Work collaboratively under pressure
* Restore compromised services
* Communicate technical findings
* Demonstrate engineering reasoning

---

# Target Audience

* Software Engineering Students
* Cybersecurity Students
* Backend Developers
* Frontend Developers
* Networking Students
* Data Professionals
* Technology Enthusiasts

---

# Team Structure

Recommended Team Size:

4–6 Participants

Suggested Roles:

* Incident Lead
* Security Analyst
* Software Engineer
* Systems Analyst
* Researcher
* Documentation Lead

Roles may rotate throughout the experience.

---

# Narrative

Metaverse City has suffered a catastrophic cyberattack.

Critical services are failing.

Authentication systems have been compromised.

Internal communications have broken down.

Database records show signs of manipulation.

Participants must investigate the attack, identify root causes, repair systems, and restore the Metaverse Core.

Each completed vault reveals a cipher fragment.

All six fragments combine into the final recovery flag:

```text
FLAG{RESTORE}
```

---

# Core Gameplay Loop

```text
INVESTIGATE
    ↓
DISCUSS
    ↓
DECIDE
    ↓
IMPLEMENT
    ↓
RECOVER FRAGMENT
    ↓
PROCEED
```

---

# Vault Sequence

| Vault | Scenario                            | Time   |
| ----- | ----------------------------------- | ------ |
| 01    | Authentication Bypass               | 5 min  |
| 02    | Leaked API Tokens                   | 5 min  |
| 03    | Network Exfiltration                | 5 min  |
| 04    | Corrupted Database Schema           | 7 min  |
| 05    | SQL Injection Breach                | 7 min  |
| 06    | Attacker Blueprint & Final Recovery | 10 min |

---

# Challenge Design

Every vault contains realistic evidence and engineering tasks.

Participants may encounter:

* Source code
* Logs
* API documentation
* Configuration files
* SQL dumps
* Security reports
* Encrypted messages
* Forensic artifacts

Each vault follows the structure:

## 1. Incident Brief

Explains the current situation.

## 2. Evidence Collection

Participants receive files and clues.

## 3. Investigation

Teams identify what happened and why.

## 4. Engineering Challenge

Teams implement a fix or identify a vulnerability.

## 5. Fragment Reward

Successful completion unlocks a recovery fragment.

---

# Current Vault Content

The prototype currently contains six fully playable vaults featuring realistic engineering and security scenarios:

### Vault 1 — Authentication Incident

Participants analyze Python authentication code containing a hidden security flaw involving improper exception handling and token validation.

### Vault 2 — Infrastructure Misconfiguration

Teams investigate exposed secrets within environment configuration files and Docker deployment settings.

### Vault 3 — Network Exfiltration

Players examine realistic network traffic logs to determine how sensitive information left the organization.

### Vault 4 — Database Recovery

Participants repair a corrupted SQL schema and identify data integrity failures involving broken relationships and foreign key constraints.

### Vault 5 — Secure Coding

Teams investigate and patch a vulnerable Flask search endpoint susceptible to SQL injection attacks.

### Vault 6 — Attacker Blueprint

Players decode an encrypted attacker blueprint using ROT-13 and assemble all recovered fragments to complete the final recovery process.

---

# Scoring System

Example scoring model:

| Action                 | Points |
| ---------------------- | ------ |
| Investigation Question | +10    |
| Engineering Challenge  | +20    |
| No Hint Used           | +5     |
| Fast Completion        | +5     |
| Perfect Vault          | +10    |

---

# Hint System

Each team receives:

* 3 Hint Tokens

Hint Costs:

| Hint   | Cost |
| ------ | ---- |
| Hint 1 | -5   |
| Hint 2 | -10  |
| Hint 3 | -15  |

Maximum:

* 3 hints per vault

---

# Technical Architecture

```text
Participants
      ↓
DevCrypt Interface
      ↓
Vault Engine
      ↓
Scoring System
      ↓
Fragment System
      ↓
Final Recovery
      ↓
FLAG{RESTORE}
```

---

# Project Structure

```text
devcrypt/
├── app.py
├── requirements.txt
├── data/
│   └── vaults.py
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── register.html
│   ├── vault.html
│   └── leaderboard.html
├── static/
│   ├── css/
│   │   └── main.css
│   └── js/
│       ├── main.js
│       └── vault.js
└── database/
    └── sqlite.db
```

---

# Setup

```bash
git clone <repository>
cd devcrypt

python -m venv venv

source venv/bin/activate
# Windows:
# venv\Scripts\activate

pip install -r requirements.txt

python app.py
```

Open:

```text
http://localhost:5000
```

---

# Future Enhancements

Planned features include:

* Moderator Dashboard
* Live Team Scores
* SQLite Persistence
* Hint Purchase System
* Admin Analytics
* Dynamic Challenge Generation
* QR-Based Vault Access
* Multiplayer Cloud Deployment

---

# Why DevCrypt?

Most technical competitions evaluate isolated skills.

DevCrypt evaluates how participants think, communicate, investigate, debug, secure, and collaborate under pressure.

The goal is not simply to find a flag.

The goal is to simulate how real engineers restore systems, solve incidents, and work together during a crisis.
