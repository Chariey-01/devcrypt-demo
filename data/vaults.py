VAULTS = [
    {
        "id": 1,
        "title": "Vault 01 — Broken Gate",
        "subtitle": "Authentication system compromised",
        "cipher_word": "DEPLOY",
        "timer": 300,  # 5 minutes
        "attack_summary": "The city's main auth service is issuing tokens to unverified sessions. Someone slipped in.",
        "file": {
            "name": "auth_service.py",
            "language": "python",
            "content": """\
import jwt
import datetime
from flask import Flask, request, jsonify
from database import get_user

app = Flask(__name__)
SECRET_KEY = "dev_secret_123"   # TODO: move to env

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = get_user(username)

    # BUG ZONE — review carefully
    if user:
        token = jwt.encode(
            {
                "sub": username,
                "role": user["role"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=72)
            },
            SECRET_KEY,
            algorithm="HS256"
        )
        return jsonify({"token": token, "status": "ok"})

    return jsonify({"status": "ok"})   # returns 200 even on bad login


@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        if payload.get("role") == "admin":
            return jsonify({"data": "sensitive city infrastructure data"})
    except jwt.ExpiredSignatureError:
        pass   # silently ignores expiry
    except Exception:
        pass   # catches everything — attacker can send malformed tokens freely

    return jsonify({"data": "sensitive city infrastructure data"})  # returned regardless


# Incident log recovered from attacker session:
# [03:14:22] POST /login  {"username": "root", "password": "wrong"}  -> 200 OK  token issued
# [03:14:31] GET  /admin/dashboard  Authorization: Bearer <malformed_jwt>  -> 200 OK  data returned
# [03:15:01] GET  /admin/dashboard  Authorization: Bearer <>  -> 200 OK  data returned
"""
        },
        "mcq": [
            {
                "id": "v1q1",
                "question": "The login endpoint returns HTTP 200 even when a user does not exist. What class of vulnerability is this?",
                "options": [
                    "A. Broken access control",
                    "B. Authentication bypass via status code leakage",
                    "C. SQL injection",
                    "D. Insecure deserialization"
                ],
                "answer": "B"
            },
            {
                "id": "v1q2",
                "question": "The /admin/dashboard route returns sensitive data even when token verification throws an exception. What is the root cause?",
                "options": [
                    "A. The JWT library is outdated",
                    "B. The except blocks swallow all errors and execution falls through to the return",
                    "C. The SECRET_KEY is too short",
                    "D. The route is missing rate limiting"
                ],
                "answer": "B"
            },
            {
                "id": "v1q3",
                "question": "Looking at the incident log, what did the attacker send in the Authorization header to access /admin/dashboard at 03:15:01?",
                "options": [
                    "A. A valid admin JWT",
                    "B. No header at all",
                    "C. An empty Bearer token",
                    "D. A Base64 encoded password"
                ],
                "answer": "C"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Fix the login() function so that:\n"
                "1. It returns HTTP 401 with {\"status\": \"unauthorized\"} when credentials are wrong.\n"
                "2. The token expiry is reduced to 1 hour.\n\n"
                "Write only the corrected login() function body. You may use Python."
            ),
            "solution_keywords": ["401", "unauthorized", "timedelta(hours=1)", "return jsonify"],
            "example_answer": (
                "if user and user['password'] == password:\n"
                "    token = jwt.encode({\"sub\": username, \"role\": user[\"role\"],\n"
                "        \"exp\": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},\n"
                "        SECRET_KEY, algorithm=\"HS256\")\n"
                "    return jsonify({\"token\": token, \"status\": \"ok\"})\n"
                "return jsonify({\"status\": \"unauthorized\"}), 401"
            )
        }
    },
    {
        "id": 2,
        "title": "Vault 02 — Exposed Nerves",
        "subtitle": "API credentials leaked in environment",
        "cipher_word": "TOKENS",
        "timer": 300,
        "attack_summary": "A .env file was committed to the city's public repo. All service keys are now compromised.",
        "file": {
            "name": ".env  +  docker-compose.yml",
            "language": "bash",
            "content": """\
# .env  (found in git history — commit 3f9a21c, pushed 6 days ago)
DATABASE_URL=postgresql://admin:Adm1n$ecure2024@db.metaversecity.internal:5432/citydb
REDIS_URL=redis://:r3d1s_p@ss@cache.metaversecity.internal:6379
STRIPE_SECRET_KEY=sk_live_AbCdEfGhIjKlMnOpQrStUvWx
SENDGRID_API_KEY=SG.xYz123AbC.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
FLASK_SECRET=supersecretflaskkey
JWT_SECRET=jwt_not_so_secret
ADMIN_BYPASS_TOKEN=bypass_me_if_you_can_lol

# docker-compose.yml  (production — also in repo)
version: "3.9"
services:
  web:
    image: metaversecity/web:latest
    env_file:
      - .env
    ports:
      - "0.0.0.0:5000:5000"   # bound to all interfaces — not just localhost

  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: Adm1n$ecure2024   # hardcoded again
    ports:
      - "0.0.0.0:5432:5432"   # database exposed to internet

  redis:
    image: redis:7
    command: redis-server --requirepass r3d1s_p@ss
    ports:
      - "0.0.0.0:6379:6379"   # redis also exposed

# Git log excerpt recovered:
# commit 3f9a21c  "add env config for prod deploy"  — pushed to public/metaversecity
# commit 8bc44d1  "oops remove .env"                — .env deleted but still in history
# Attacker cloned repo, ran: git log --all -p -- .env
"""
        },
        "mcq": [
            {
                "id": "v2q1",
                "question": "The .env file was deleted in commit 8bc44d1. Are the secrets still exposed?",
                "options": [
                    "A. No — deleting the file removes it from all history",
                    "B. Yes — git history preserves every version of every file ever committed",
                    "C. Only if the repo is public",
                    "D. No — Docker rebuilds overwrite the history"
                ],
                "answer": "B"
            },
            {
                "id": "v2q2",
                "question": "The database port 5432 is bound to 0.0.0.0. What does this mean?",
                "options": [
                    "A. Only Docker containers can connect to it",
                    "B. The database is accessible from any IP on the internet",
                    "C. It uses IPv6 by default",
                    "D. The port is encrypted via TLS"
                ],
                "answer": "B"
            },
            {
                "id": "v2q3",
                "question": "Which line in .env represents the highest immediate financial risk?",
                "options": [
                    "A. FLASK_SECRET",
                    "B. DATABASE_URL",
                    "C. STRIPE_SECRET_KEY",
                    "D. ADMIN_BYPASS_TOKEN"
                ],
                "answer": "C"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Write a .gitignore snippet that prevents .env from ever being tracked,\n"
                "AND write the one git command a developer must run to purge .env from\n"
                "ALL git history (not just delete it from the working tree)."
            ),
            "solution_keywords": [".env", "filter-branch", "BFG", "git rm --cached", ".gitignore"],
            "example_answer": (
                "# .gitignore\n.env\n*.env\n.env.*\n\n"
                "# Purge from history:\n"
                "git filter-branch --force --index-filter \\\n"
                "  'git rm --cached --ignore-unmatch .env' \\\n"
                "  --prune-empty --tag-name-filter cat -- --all"
            )
        }
    },
    {
        "id": 3,
        "title": "Vault 03 — Ghost Traffic",
        "subtitle": "Anomalous network packets detected",
        "cipher_word": "PACKET",
        "timer": 300,
        "attack_summary": "The city's network sensor picked up irregular outbound traffic at 03:00. Something is being exfiltrated.",
        "file": {
            "name": "traffic_sensor.log",
            "language": "log",
            "content": """\
[NETWORK SENSOR v2.3 — MetaverseCity NOC]
Capture window: 2024-11-14 03:00:00 — 03:06:00 UTC
Interface: eth0  |  Filter: all traffic

03:00:01  SRC 10.0.1.45:52341   DST 185.220.101.47:443   TCP  ESTABLISHED  TLS1.2  bytes_out=142
03:00:04  SRC 10.0.1.45:52341   DST 185.220.101.47:443   TCP  DATA         TLS1.2  bytes_out=8219
03:00:07  SRC 10.0.1.45:52341   DST 185.220.101.47:443   TCP  DATA         TLS1.2  bytes_out=8190
03:00:11  SRC 10.0.1.45:52341   DST 185.220.101.47:443   TCP  DATA         TLS1.2  bytes_out=8204
03:00:14  SRC 10.0.1.45:52342   DST 185.220.101.47:443   TCP  ESTABLISHED  TLS1.2  bytes_out=140
03:00:17  SRC 10.0.1.45:52342   DST 185.220.101.47:443   TCP  DATA         TLS1.2  bytes_out=8231
...
03:05:58  SRC 10.0.1.45:52389   DST 185.220.101.47:443   TCP  DATA         TLS1.2  bytes_out=8177
03:05:59  SRC 10.0.1.45:52389   DST 185.220.101.47:443   TCP  FIN          TLS1.2  bytes_out=0

[SUMMARY]
Total connections to 185.220.101.47:443  : 49
Total bytes exfiltrated (est.)           : 401,838 bytes (~392 KB)
Internal source IP                       : 10.0.1.45
Internal hostname (reverse DNS)          : db-replica-02.metaversecity.internal

[THREAT INTEL]
185.220.101.47  — Listed in abuse.ch TOR exit node database
                — Associated with APT campaign "GhostRoute" (2023-2024)
                — No legitimate city vendor uses this IP

[ANOMALY FLAGS]
- Traffic initiated at 03:00 (off-hours, no scheduled jobs at this time)
- Source is a database replica server — should never initiate outbound connections
- All connections on port 443 but TLS fingerprint does not match known CDNs
- Data exfiltrated in near-uniform chunks (~8.2 KB) suggesting automated tooling
- No corresponding inbound trigger logged (connection initiated internally, not from outside)
"""
        },
        "mcq": [
            {
                "id": "v3q1",
                "question": "The source of the outbound traffic is db-replica-02. Why is this specifically suspicious?",
                "options": [
                    "A. Replicas use more bandwidth than primary databases",
                    "B. A database replica should never initiate outbound network connections",
                    "C. Port 443 is blocked on replica servers by default",
                    "D. TLS 1.2 is deprecated and should not be in use"
                ],
                "answer": "B"
            },
            {
                "id": "v3q2",
                "question": "The data is sent in near-uniform ~8.2 KB chunks. What does this pattern indicate?",
                "options": [
                    "A. Normal database replication traffic",
                    "B. A human manually copying files",
                    "C. Automated exfiltration tooling with a fixed buffer size",
                    "D. A misconfigured CDN cache"
                ],
                "answer": "C"
            },
            {
                "id": "v3q3",
                "question": "The destination IP is a known TOR exit node. What does this tell investigators?",
                "options": [
                    "A. The attacker is definitely located in that country",
                    "B. The traffic destination can be traced to a specific person easily",
                    "C. The attacker is routing traffic to mask their true origin",
                    "D. TOR exit nodes only handle HTTP traffic, not HTTPS"
                ],
                "answer": "C"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Write a Python function using the `socket` or `subprocess` module that:\n"
                "1. Takes an IP address as input.\n"
                "2. Blocks all outbound connections to that IP using an iptables command.\n"
                "3. Logs the block action with a timestamp to a file called 'firewall.log'.\n\n"
                "Use subprocess.run() for the iptables call."
            ),
            "solution_keywords": ["subprocess", "iptables", "DROP", "datetime", "open", "firewall.log"],
            "example_answer": (
                "import subprocess, datetime\n\n"
                "def block_ip(ip: str):\n"
                "    cmd = ['iptables', '-A', 'OUTPUT', '-d', ip, '-j', 'DROP']\n"
                "    subprocess.run(cmd, check=True)\n"
                "    with open('firewall.log', 'a') as f:\n"
                "        f.write(f\"{datetime.datetime.utcnow()} BLOCKED {ip}\\n\")"
            )
        }
    },
    {
        "id": 4,
        "title": "Vault 04 — Fractured Records",
        "subtitle": "Database schema corrupted",
        "cipher_word": "SCHEMA",
        "timer": 420,  # 7 minutes
        "attack_summary": "The city's core database was tampered with. Tables restructured, foreign keys dropped, audit trail gone.",
        "file": {
            "name": "citydb_schema_dump.sql",
            "language": "sql",
            "content": """\
-- citydb schema dump — recovered after incident
-- Original schema version: v4.2.1
-- Dump taken: 2024-11-14 04:01:00 UTC (post-attack)

CREATE TABLE citizens (
    id SERIAL,               -- PRIMARY KEY constraint missing
    full_name VARCHAR(200),
    national_id VARCHAR(20),  -- should be UNIQUE NOT NULL
    email VARCHAR(200),
    role VARCHAR(50) DEFAULT 'citizen'
    -- created_at column deleted by attacker
);

CREATE TABLE city_services (
    service_id SERIAL PRIMARY KEY,
    service_name VARCHAR(100) NOT NULL,
    assigned_to INTEGER,     -- FK to citizens.id — constraint dropped
    budget NUMERIC(15,2),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE audit_log (
    log_id SERIAL PRIMARY KEY,
    actor_id INTEGER,
    action VARCHAR(500),
    performed_at TIMESTAMP   -- DEFAULT NOW() removed
    -- table truncated: 0 rows remaining (attacker wiped logs)
);

CREATE TABLE admin_overrides (
    override_id SERIAL PRIMARY KEY,
    citizen_id INTEGER,
    granted_by VARCHAR(100) DEFAULT 'system',  -- attacker inserted rows here
    access_level VARCHAR(50) DEFAULT 'superadmin',
    note TEXT
);

-- Suspicious data found in admin_overrides after incident:
-- override_id | citizen_id | granted_by        | access_level | note
-- 1           | 9182       | system            | superadmin   | NULL
-- 2           | 9182       | system            | superadmin   | NULL

-- citizen_id 9182 does not exist in the citizens table
-- Two superadmin rows inserted for a non-existent citizen — persistence backdoor
"""
        },
        "mcq": [
            {
                "id": "v4q1",
                "question": "The citizens table is missing a PRIMARY KEY. What is the immediate consequence?",
                "options": [
                    "A. Queries will run slower",
                    "B. Duplicate rows with the same id can be inserted, breaking referential integrity",
                    "C. The table cannot store NULL values",
                    "D. Foreign keys to this table still work correctly"
                ],
                "answer": "B"
            },
            {
                "id": "v4q2",
                "question": "The attacker inserted two admin_overrides rows for citizen_id 9182, which does not exist in citizens. What type of attack technique is this?",
                "options": [
                    "A. SQL injection",
                    "B. Privilege persistence via orphaned admin records",
                    "C. Schema enumeration",
                    "D. Buffer overflow"
                ],
                "answer": "B"
            },
            {
                "id": "v4q3",
                "question": "The audit_log table was truncated. Why is this the most damaging single action in this incident?",
                "options": [
                    "A. It makes queries faster",
                    "B. It removes all evidence of what the attacker did and when",
                    "C. It corrupts the citizens table",
                    "D. It triggers a database crash"
                ],
                "answer": "B"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Write the SQL ALTER statements to:\n"
                "1. Add a PRIMARY KEY to citizens.id\n"
                "2. Add UNIQUE NOT NULL constraints to citizens.national_id\n"
                "3. Add a FOREIGN KEY from city_services.assigned_to to citizens.id\n"
                "4. Delete the two suspicious admin_overrides rows for citizen_id 9182\n"
                "5. Add DEFAULT NOW() back to audit_log.performed_at"
            ),
            "solution_keywords": ["ALTER TABLE", "PRIMARY KEY", "UNIQUE", "NOT NULL", "FOREIGN KEY", "DELETE", "DEFAULT NOW()"],
            "example_answer": (
                "ALTER TABLE citizens ADD PRIMARY KEY (id);\n"
                "ALTER TABLE citizens ALTER COLUMN national_id SET NOT NULL;\n"
                "ALTER TABLE citizens ADD CONSTRAINT uq_national_id UNIQUE (national_id);\n"
                "ALTER TABLE city_services ADD CONSTRAINT fk_assigned\n"
                "  FOREIGN KEY (assigned_to) REFERENCES citizens(id);\n"
                "DELETE FROM admin_overrides WHERE citizen_id = 9182;\n"
                "ALTER TABLE audit_log ALTER COLUMN performed_at SET DEFAULT NOW();"
            )
        }
    },
    {
        "id": 5,
        "title": "Vault 05 — Poison Input",
        "subtitle": "SQL injection in city services backend",
        "cipher_word": "INJECT",
        "timer": 420,
        "attack_summary": "The city portal search was used to dump the entire database. The query was never sanitised.",
        "file": {
            "name": "search_service.py",
            "language": "python",
            "content": """\
import psycopg2
from flask import Flask, request, jsonify

app = Flask(__name__)
DB = psycopg2.connect("dbname=citydb user=admin password=Adm1n$ecure2024 host=localhost")

@app.route("/api/search/citizen", methods=["GET"])
def search_citizen():
    name = request.args.get("name", "")
    cursor = DB.cursor()

    # Direct string interpolation — never do this
    query = f"SELECT id, full_name, email, role FROM citizens WHERE full_name LIKE '%{name}%'"
    cursor.execute(query)
    results = cursor.fetchall()

    return jsonify({"results": results})


@app.route("/api/search/service", methods=["GET"])
def search_service():
    service_id = request.args.get("id", "")
    cursor = DB.cursor()

    # Same pattern — unparameterised
    query = "SELECT * FROM city_services WHERE service_id = " + service_id
    cursor.execute(query)
    row = cursor.fetchone()

    return jsonify({"service": row})


# Attack traffic recovered from nginx access log:
# GET /api/search/citizen?name=' UNION SELECT 1,username,password,4 FROM pg_shadow--
# -> returned postgres superuser hashes
#
# GET /api/search/service?id=1 OR 1=1; DROP TABLE audit_log;--
# -> audit_log dropped (confirmed in vault 04)
#
# GET /api/search/service?id=1 UNION SELECT table_name,2,3,4,5 FROM information_schema.tables--
# -> full table list returned to attacker
"""
        },
        "mcq": [
            {
                "id": "v5q1",
                "question": "The attacker used: ?name=' UNION SELECT 1,username,password,4 FROM pg_shadow--\nWhat did this return?",
                "options": [
                    "A. Nothing — UNION requires matching table names",
                    "B. PostgreSQL superuser credential hashes",
                    "C. A syntax error",
                    "D. The citizens table schema only"
                ],
                "answer": "B"
            },
            {
                "id": "v5q2",
                "question": "The -- at the end of the injection payload has a specific purpose. What is it?",
                "options": [
                    "A. It ends the Python string",
                    "B. It is a SQL comment — it causes the database to ignore the rest of the original query",
                    "C. It triggers a UNION scan",
                    "D. It escapes special characters"
                ],
                "answer": "B"
            },
            {
                "id": "v5q3",
                "question": "Which fix correctly prevents SQL injection in the search_citizen() function?",
                "options": [
                    "A. Wrap the query in a try/except block",
                    "B. Use psycopg2 parameterised queries: cursor.execute(query, (name,))",
                    "C. Convert name to uppercase before inserting",
                    "D. Limit results to 100 rows"
                ],
                "answer": "B"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Rewrite BOTH search_citizen() and search_service() using\n"
                "psycopg2 parameterised queries to eliminate SQL injection.\n"
                "Also add input validation: reject any service_id that is not a digit."
            ),
            "solution_keywords": ["%s", "cursor.execute", "isdigit", "params", "parameteris"],
            "example_answer": (
                "def search_citizen():\n"
                "    name = request.args.get('name', '')\n"
                "    cursor = DB.cursor()\n"
                "    cursor.execute(\n"
                "        'SELECT id, full_name, email, role FROM citizens WHERE full_name LIKE %s',\n"
                "        (f'%{name}%',)\n"
                "    )\n"
                "    return jsonify({'results': cursor.fetchall()})\n\n"
                "def search_service():\n"
                "    service_id = request.args.get('id', '')\n"
                "    if not service_id.isdigit():\n"
                "        return jsonify({'error': 'invalid id'}), 400\n"
                "    cursor = DB.cursor()\n"
                "    cursor.execute('SELECT * FROM city_services WHERE service_id = %s', (service_id,))\n"
                "    return jsonify({'service': cursor.fetchone()})"
            )
        }
    },
    {
        "id": 6,
        "title": "Vault 06 — The Blueprint",
        "subtitle": "Decrypt the attacker's final plan",
        "cipher_word": "RESTORE",
        "timer": 600,  # 10 minutes
        "attack_summary": (
            "The attacker left one final file — an encrypted blueprint of everything they did "
            "and what they planned to do next. You have the key. Decode it. Restore the city."
        ),
        "file": {
            "name": "attacker_blueprint.txt",
            "language": "text",
            "content": """\
ENCRYPTED BLUEPRINT — METAVERSE CITY INCIDENT
Cipher: ROT-13 applied to all UPPERCASE words  |  Numbers are real
Recovered from: /tmp/.ghost_work on db-replica-02

PHASE 1 — ERNPBHAANVFFNAPR  (complete)
  Target: Metaverse City infrastructure
  Method: Gubhtu choyvp tvg ercb yrnxrq .raiebazrag svyr
  Result: Obtained DB creds, Stripe keys, JWT secret

PHASE 2 — VAVGVNY NPPRF  (complete)
  Entry point: /api/search/citizen — FDHY VAWRPGVBA
  Payload used: ' UNION SELECT 1,username,password,4 FROM pg_shadow--
  Achieved: Superuser hash for 'citydb_admin' obtained

PHASE 3 — CREFVFGRAPR  (complete)
  Action 1: Dropped all SBERVTA XRLF on citizens table
  Action 2: Inserted 2 FHCRENQZVA rows in admin_overrides for ghost citizen 9182
  Action 3: GEHAPNGRQ audit_log — all evidence erased

PHASE 4 — RKSVYGENGVBA  (complete)
  Exfiltrated 392 KB via TOR exit node 185.220.101.47
  Contents: citizen PII, budget data, service assignments

PHASE 5 — ARKG GNETRE  (planned — not yet executed)
  Target: city_services.budget — PBEEHOYR all budget figures by factor of 0.1
  Target: Disable is_active on all critical VASENFGEHPGHER services
  Delivery: Scheduled cron job at /etc/cron.d/city_maint (already planted)

ATTACKER SIGNATURE:
  Handle: GhostRoute-7
  Tools:  sqlmap, custom Python exfil script, TOR
  Motive: Hired. Client unknown.

CITY RECOVERY CHECKLIST (your job now):
  [ ] Rotate ALL credentials from vault 02
  [ ] Patch SQL injection (vault 05)
  [ ] Restore schema integrity (vault 04)
  [ ] Block 185.220.101.47 at firewall (vault 03)
  [ ] Fix authentication bypass (vault 01)
  [ ] Remove: /etc/cron.d/city_maint
  [ ] Verify city_services.budget figures against backup
  [ ] Re-enable all disabled services
  [ ] Restore audit_log from offsite backup
  [ ] File incident report — reference: GHOST-ROUTE-7
"""
        },
        "mcq": [
            {
                "id": "v6q1",
                "question": "Decode the Phase 5 target: PBEEHOYR all budget figures by factor of 0.1. What does PBEEHOYR decrypt to (ROT-13)?",
                "options": [
                    "A. COMPLETE",
                    "B. CORRUPT",
                    "C. CORRECT",
                    "D. CONFIRM"
                ],
                "answer": "B"
            },
            {
                "id": "v6q2",
                "question": "The attacker planted a cron job at /etc/cron.d/city_maint. What is the immediate first action to take?",
                "options": [
                    "A. Read its contents and document it, then delete it",
                    "B. Reboot the server to clear cron jobs",
                    "C. Rename the file so it doesn't run",
                    "D. Run the cron job in a sandbox to see what it does"
                ],
                "answer": "A"
            },
            {
                "id": "v6q3",
                "question": "The attacker's motive was 'Hired. Client unknown.' What does this classify them as?",
                "options": [
                    "A. Script kiddie",
                    "B. Hacktivist",
                    "C. Cyber mercenary / threat actor for hire",
                    "D. Insider threat"
                ],
                "answer": "C"
            }
        ],
        "coding_challenge": {
            "prompt": (
                "Write a Python function called rot13_decode(text) that:\n"
                "1. Decodes only UPPERCASE letters using ROT-13.\n"
                "2. Leaves numbers, punctuation, and lowercase unchanged.\n\n"
                "Then call it on the string: 'ERNPBHAANVFFNAPR'\n"
                "and print the result."
            ),
            "solution_keywords": ["def rot13_decode", "ord", "chr", "65", "26", "RECONNAISSANCE", "print"],
            "example_answer": (
                "def rot13_decode(text: str) -> str:\n"
                "    result = []\n"
                "    for ch in text:\n"
                "        if 'A' <= ch <= 'Z':\n"
                "            result.append(chr((ord(ch) - 65 + 13) % 26 + 65))\n"
                "        else:\n"
                "            result.append(ch)\n"
                "    return ''.join(result)\n\n"
                "print(rot13_decode('ERNPBHAANVFFNAPR'))  # -> RECONNAISSANCE"
            )
        }
    }
]
