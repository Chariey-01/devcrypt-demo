"""Hardcoded Knowledge Check question bank for the 6 sponsor booths.

Per an explicit product decision for this event's MVP: authoring these through the Agent
Dashboard (which already has a working Knowledge Check CRUD UI, reused for any *future*
event) added an admin-interface risk/effort tradeoff that wasn't worth it 2 days out. This
module is the single source of truth instead -- edit questions here, then re-run
`scripts/sync_knowledge_bank.py` to idempotently upsert them into the same KnowledgeQuestion/
KnowledgeOption tables the rest of the app already reads from. Nothing about how a booth is
served, answered, or cipher-revealed cares whether a question's content originated here or
from the Agent Dashboard -- this file only changes *how the content got into the database*,
not the runtime path.

Each booth's pool is intentionally larger (15-18) than what any one team is actually asked (5,
picked randomly per team, one per distinct category where possible -- see
MissionService.assign_knowledge_subset) -- this adds variety between teams and reduces the
value of one team calling out answers to a team at another booth.

Every question is tagged with one of the 10 discipline categories in CATEGORIES below.
assign_knowledge_subset() uses this tag to draw a category-diverse 5-question hand per booth
(one per category, cycling if a booth has fewer than 5 distinct categories in its pool)
instead of a flat random sample that could hand a team five near-identical questions.

`explanation` is for maintainers only -- never sent to the player-facing API.

To swap this for a fully database-authored bank later (no player-facing changes required):
stop calling sync_knowledge_bank.py and just let Agents edit KnowledgeQuestion rows directly
through the existing Agent Dashboard UI -- the serving/answering/reveal code already reads
from the database either way.
"""

from dataclasses import dataclass

CATEGORIES = (
    "Cybersecurity",
    "Software Engineering",
    "Data Science",
    "AI/ML",
    "DevOps",
    "Git",
    "Networking",
    "APIs",
    "Databases",
    "Testing",
)


@dataclass(frozen=True)
class BankQuestion:
    key: str  # stable id for idempotent sync -- never change once an event has used it
    text: str
    options: tuple  # exactly 4 option strings
    correct_index: int  # 0-3
    category: str  # one of CATEGORIES above, used for balanced sampling
    explanation: str  # internal only, not shown to players

    def __post_init__(self):
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.key!r} has unknown category {self.category!r}")


# Keyed by Mission.booth_id (1-6), matching scripts/seed.py's booth numbering.
BOOTH_QUESTION_BANKS = {
    # ---------------------------------------------------------------- Booth 1 -- Elewa
    1: [
        BankQuestion(
            key="elewa-01",
            category="Software Engineering",
            text=(
                "A product team ships a new onboarding flow behind a feature flag, rolled out "
                "to 5% of users. Conversion drops sharply for that 5%, but the team can't tell "
                "if it's the flow itself or a tracking bug. What should they do first?"
            ),
            options=(
                "Roll the flag out to 100% to get a larger, more reliable sample",
                "Verify the analytics events fire correctly before drawing any conclusion from the drop",
                "Revert the flow immediately and abandon the idea",
                "Extend the test for another month without changing anything",
            ),
            correct_index=1,
            explanation="Classic instrumentation-before-inference trap -- a real product-analytics gotcha.",
        ),
        BankQuestion(
            key="elewa-02",
            category="Git",
            text=(
                "Two engineers each branch off main to build unrelated features and both edit "
                "the same config file in different places. When the second branch tries to "
                "merge, what happens?"
            ),
            options=(
                "Git silently keeps whichever branch merged first and discards the other's change",
                "A merge conflict is raised, requiring a human to reconcile both edits",
                "The repository becomes corrupted and must be re-cloned",
                "Git automatically writes both changes to separate files",
            ),
            correct_index=1,
            explanation="Tests whether the student understands what a merge conflict actually is, not just that the term exists.",
        ),
        BankQuestion(
            key="elewa-03",
            category="Software Engineering",
            text=(
                "A startup's MVP needs to validate demand before investing in a scalable "
                "architecture. Which approach best reflects the actual purpose of an MVP?"
            ),
            options=(
                "Build the full feature set but skip automated testing to save time",
                "Ship the smallest version that lets you learn something real from actual users",
                "Launch privately and never let real users touch it until it's feature-complete",
                "Focus entirely on infrastructure scalability before any user validation",
            ),
            correct_index=1,
            explanation="MVP is a validated-learning concept, not 'do it badly' or 'do it small forever'.",
        ),
        BankQuestion(
            key="elewa-04",
            category="DevOps",
            text=(
                "A deploy pipeline starts failing after a new dependency is added. Existing "
                "services keep running fine, but freshly deployed containers fail on startup "
                "due to an incompatible transitive package version. What best improves "
                "long-term deployment stability here?"
            ),
            options=(
                "Restart the failing containers until one deploy succeeds",
                "Pin dependency versions and use reproducible, lockfile-based builds",
                "Increase the container's memory limit",
                "Deploy straight to production to skip staging inconsistencies",
            ),
            correct_index=1,
            explanation="Deterministic dependency resolution is the actual fix; the others are workarounds or make it worse.",
        ),
        BankQuestion(
            key="elewa-05",
            category="Software Engineering",
            text=(
                "A team wants to reduce the time between writing code and getting user feedback "
                "on it. Which practice most directly supports that Agile goal?"
            ),
            options=(
                "Writing complete upfront specifications before any code is written",
                "Delivering working software in short, frequent increments",
                "Freezing all requirements at the start of the project",
                "Waiting until the final release to gather any user feedback",
            ),
            correct_index=1,
            explanation="Directly tests the Agile Manifesto's core value, phrased as a scenario rather than a definition-recall question.",
        ),
        BankQuestion(
            key="elewa-06",
            category="Software Engineering",
            text=(
                "An API returns HTTP 500 intermittently under load, but works fine in local "
                "testing. Which is the most likely class of bug to investigate first?"
            ),
            options=(
                "A syntax error in the code, since it would fail every time",
                "A race condition or shared-resource contention issue that only appears under concurrency",
                "The client's internet connection",
                "A typo in the API's URL",
            ),
            correct_index=1,
            explanation="'Works locally, fails under load' is the textbook signature of concurrency bugs, not syntax errors.",
        ),
        BankQuestion(
            key="elewa-07",
            category="Testing",
            text=(
                "A code review flags a pull request for having zero automated tests on a "
                "critical payment path. The author argues it works because they tested it "
                "manually once. What's the strongest counterargument?"
            ),
            options=(
                "Manual testing is always wrong and should never be used",
                "Automated tests catch regressions on every future change; a one-time manual check doesn't",
                "The reviewer should just trust the author and approve it",
                "Tests are only needed for UI code, not backend logic",
            ),
            correct_index=1,
            explanation="Tests the *why* of automated testing (regression protection over time), not just 'testing is good'.",
        ),
        BankQuestion(
            key="elewa-08",
            category="Data Science",
            text=(
                "A product manager wants a single number to know if last week's release "
                "improved user retention. Which is the most meaningful way to evaluate that?"
            ),
            options=(
                "Compare a cohort's retention before vs. after the release, controlling for other changes",
                "Count how many people opened the app on release day",
                "Ask five users in a hallway if they liked it",
                "Check how many lines of code were shipped",
            ),
            correct_index=0,
            explanation="Cohort comparison with confound control is the real product-analytics answer; the others are vanity metrics.",
        ),
        BankQuestion(
            key="elewa-09",
            category="APIs",
            text=(
                "In a REST API, which HTTP method is expected to be idempotent -- calling it "
                "multiple times with the same input produces the same end state as calling it once?"
            ),
            options=(
                "POST",
                "PUT",
                "Both are equally non-idempotent by design",
                "Neither method has any idempotency expectation",
            ),
            correct_index=1,
            explanation="PUT (full replace) is idempotent by REST convention; POST (create) generally is not.",
        ),
        BankQuestion(
            key="elewa-10",
            category="Software Engineering",
            text=(
                "A junior engineer wants to skip writing a README because 'the code is "
                "self-explanatory.' What's the strongest reason documentation still matters here?"
            ),
            options=(
                "Documentation is a legal requirement for all software",
                "Code explains *how*, but rarely explains *why* a decision was made -- future maintainers need both",
                "Nobody reads code without a README first",
                "It makes the repository look more professional to outsiders",
            ),
            correct_index=1,
            explanation="Distinguishes 'self-documenting code' myths from the real gap docs fill: intent and tradeoffs.",
        ),
        BankQuestion(
            key="elewa-11",
            category="Software Engineering",
            text=(
                "A team debates between a monolith and microservices for a brand-new product "
                "with three engineers and no confirmed users yet. What's the strongest argument "
                "for starting with a monolith?"
            ),
            options=(
                "Monoliths scale better than microservices at any size",
                "Microservices add operational and coordination overhead that isn't justified before the product's boundaries are even known",
                "Microservices are always slower at runtime",
                "A monolith requires no testing",
            ),
            correct_index=1,
            explanation="The real tradeoff is premature architectural complexity, not a performance claim (which is false either way).",
        ),
        BankQuestion(
            key="elewa-12",
            category="Testing",
            text=(
                "A function's unit tests all pass, but a bug still reaches production because "
                "the tests never exercised how two independently-correct functions behave "
                "together. What kind of testing gap does this describe?"
            ),
            options=(
                "A missing integration test",
                "A missing unit test",
                "A missing code comment",
                "A missing README",
            ),
            correct_index=0,
            explanation="Unit tests verify components in isolation; integration tests verify their interaction -- exactly the gap described.",
        ),
        BankQuestion(
            key="elewa-13",
            category="Software Engineering",
            text=(
                "A startup's engineering lead insists every pull request needs at least one "
                "review before merging, even for a one-line fix. What's the best justification "
                "for keeping that rule even for tiny changes?"
            ),
            options=(
                "Small changes are never risky, so the rule is really about optics",
                "A second set of eyes catches assumptions the author can't see in their own change, regardless of size",
                "It's required by most programming languages",
                "It slows down attackers trying to commit malicious code",
            ),
            correct_index=1,
            explanation="Tests understanding of *why* review exists (catching blind spots), not just 'because policy says so'.",
        ),
        BankQuestion(
            key="elewa-14",
            category="Databases",
            text=(
                "An engineering team is choosing a database for a new feature that needs strict "
                "referential integrity between orders and customers. Which factor matters most "
                "in that specific decision?"
            ),
            options=(
                "Whether the database supports foreign key constraints and transactions",
                "Whether the database has the most GitHub stars",
                "Whether the database is the newest one available",
                "Whether the database was used in the founder's last company",
            ),
            correct_index=0,
            explanation="Tests whether the student can map a stated requirement (referential integrity) to the actual relevant technical property.",
        ),
        BankQuestion(
            key="elewa-15",
            category="DevOps",
            text=(
                "A team's CI pipeline takes 45 minutes to run, so engineers start skipping it "
                "before merging 'small' changes. What's the healthiest long-term fix?"
            ),
            options=(
                "Formally allow skipping CI for changes under 10 lines",
                "Invest in making the pipeline faster (parallelization, caching) so skipping is never tempting",
                "Remove CI entirely since it's clearly too slow to be useful",
                "Only run CI once a week to reduce the burden",
            ),
            correct_index=1,
            explanation="The root cause is pipeline speed, not the review policy -- a classic 'fix the process, not the compliance' scenario.",
        ),
    ],
    # ---------------------------------------------------------------- Booth 2 -- Workforce Africa
    2: [
        BankQuestion(
            key="wfa-01",
            category="Cybersecurity",
            text=(
                "An HR platform grants a contractor temporary access to payroll data for one "
                "project. Six months after the project ends, the access is still active. What "
                "security principle was violated?"
            ),
            options=(
                "Least privilege",
                "Defense in depth",
                "Zero trust",
                "Two-factor authentication",
            ),
            correct_index=0,
            explanation="Least privilege includes time-bounding access to what's actually needed, not just role-scoping it.",
        ),
        BankQuestion(
            key="wfa-02",
            category="Cybersecurity",
            text=(
                "A workforce platform wants to grant permissions based on whether someone is a "
                "'Manager,' 'HR Admin,' or 'Employee,' rather than assigning permissions to each "
                "person individually. Which access control model does this describe?"
            ),
            options=(
                "Role-Based Access Control (RBAC)",
                "Discretionary Access Control granted per-user",
                "Mandatory Access Control based on data classification labels",
                "No access control -- this is just a UI convenience",
            ),
            correct_index=0,
            explanation="Directly tests the definition of RBAC applied to the exact HR/workforce context of this booth.",
        ),
        BankQuestion(
            key="wfa-03",
            category="Cybersecurity",
            text=(
                "A login system only requires a password, and a phishing campaign successfully "
                "steals several employees' passwords. Which control would have limited the "
                "damage even after the passwords were stolen?"
            ),
            options=(
                "Longer minimum password length",
                "Multi-factor authentication (MFA)",
                "A stronger password hashing algorithm",
                "A password expiry policy",
            ),
            correct_index=1,
            explanation="MFA is specifically effective against credential theft since a second factor is required beyond the leaked password.",
        ),
        BankQuestion(
            key="wfa-04",
            category="Cybersecurity",
            text=(
                "An HR system needs to store employee salary data. Which practice best protects "
                "that data if the database is ever exfiltrated?"
            ),
            options=(
                "Storing it in plaintext but restricting database access with a firewall",
                "Encrypting sensitive fields at rest, in addition to access controls",
                "Renaming the database table to something less obvious",
                "Relying only on the login page requiring a password",
            ),
            correct_index=1,
            explanation="Defense in depth: access control alone doesn't help once the DB itself is exfiltrated; encryption at rest does.",
        ),
        BankQuestion(
            key="wfa-05",
            category="DevOps",
            text=(
                "A company operating across 40 African markets needs its HR platform available "
                "even if one data center goes down. Which cloud concept most directly addresses "
                "that requirement?"
            ),
            options=(
                "Vertical scaling (bigger servers)",
                "Multi-region redundancy / high availability",
                "Using a newer programming language",
                "Reducing the number of API endpoints",
            ),
            correct_index=1,
            explanation="Availability across regions/zones is the actual answer to 'don't go down if one location fails.'",
        ),
        BankQuestion(
            key="wfa-06",
            category="DevOps",
            text=(
                'Which of these best describes what "SaaS" (Software as a Service) means for '
                "a company buying an HR platform instead of building one?"
            ),
            options=(
                "They install and maintain the software on their own servers",
                "They access hosted software over the internet, typically via subscription, without managing the underlying infrastructure",
                "They receive the full source code to modify freely",
                "They must purchase new hardware every year",
            ),
            correct_index=1,
            explanation="Core SaaS definition, framed against the buy-vs-build decision an HR platform customer actually faces.",
        ),
        BankQuestion(
            key="wfa-07",
            category="Data Science",
            text=(
                "A dataset of employee records has some rows with the same national ID appearing "
                "twice, due to a sync bug between two systems. Before running any analysis, what "
                "should happen first?"
            ),
            options=(
                "Run the analysis anyway -- a handful of duplicates won't matter",
                "Data cleaning: deduplicate and validate the records before analysis",
                "Delete the national ID field entirely from the dataset",
                "Assume the newer system's data is always correct without checking",
            ),
            correct_index=1,
            explanation="Classic data-cleaning-before-analysis principle, applied to the exact duplicate-ID scenario this booth's challenge involves.",
        ),
        BankQuestion(
            key="wfa-08",
            category="AI/ML",
            text=(
                "An HR platform wants to predict which employees are at risk of resigning, "
                "using historical data on tenure, promotions, and pay changes. What type of "
                "machine learning problem is this?"
            ),
            options=(
                "Unsupervised clustering with no labeled outcomes",
                "Supervised learning, since past resignation outcomes are known and used to train the model",
                "Reinforcement learning, since the model plays against itself",
                "This isn't a machine learning problem at all",
            ),
            correct_index=1,
            explanation="Past labeled outcomes (did they resign or not) make this a textbook supervised classification setup.",
        ),
        BankQuestion(
            key="wfa-09",
            category="Cybersecurity",
            text=(
                "A company audits its cloud storage and discovers a bucket containing employee "
                "personal data is publicly readable by anyone with the URL. What is the most "
                "accurate way to describe this finding?"
            ),
            options=(
                "A minor cosmetic issue since URLs are hard to guess",
                "A serious misconfiguration -- data exposure due to broken access control",
                "Expected behavior for cloud storage",
                "Not a concern as long as the bucket name isn't indexed by search engines",
            ),
            correct_index=1,
            explanation="Public buckets with PII are one of the most common real-world breach root causes -- tests whether 'security by obscurity' is recognized as false safety.",
        ),
        BankQuestion(
            key="wfa-10",
            category="AI/ML",
            text=(
                "A recruiter wants to automatically screen resumes using a language model. What "
                "is the most important risk to evaluate before deploying that system?"
            ),
            options=(
                "Whether the model runs fast enough",
                "Whether the model has learned biased patterns from historical hiring data that could unfairly disadvantage some candidates",
                "Whether the model's output is in English",
                "Whether the resumes are in PDF format",
            ),
            correct_index=1,
            explanation="Bias in AI-driven hiring is a well-documented, high-stakes real-world failure mode -- the correct 'most important' answer among plausible operational concerns.",
        ),
        BankQuestion(
            key="wfa-11",
            category="Cybersecurity",
            text=(
                "An HR system logs every login attempt, including failed ones. A security "
                "analyst notices 500 failed login attempts for one account within a minute. "
                "What does this most likely indicate?"
            ),
            options=(
                "The employee forgot their password once and tried again",
                "A brute-force credential-stuffing attack against that account",
                "A normal software update process",
                "The account was deleted",
            ),
            correct_index=1,
            explanation="Volume and speed are the tell -- one honest mistake looks nothing like 500 attempts in a minute.",
        ),
        BankQuestion(
            key="wfa-12",
            category="DevOps",
            text=(
                "A workforce platform wants to move a legacy on-premise payroll system into the "
                "cloud with minimal code changes. Which migration strategy best fits that goal?"
            ),
            options=(
                "Rearchitecting the entire application into microservices first",
                '"Lift and shift" -- moving the existing application largely as-is onto cloud infrastructure',
                "Rewriting the system in a different programming language",
                "Deleting the payroll system and starting over",
            ),
            correct_index=1,
            explanation="Lift-and-shift is specifically the low-code-change migration pattern; the other options contradict 'minimal code changes.'",
        ),
        BankQuestion(
            key="wfa-13",
            category="Cybersecurity",
            text=(
                "A company wants employee data encrypted both while stored in the database and "
                "while traveling between the app and the server. Which two concepts together "
                "cover that requirement?"
            ),
            options=(
                "Encryption at rest and encryption in transit",
                "Two-factor authentication and password hashing",
                "Load balancing and caching",
                "Version control and code review",
            ),
            correct_index=0,
            explanation="'Stored' = at rest, 'traveling between app and server' = in transit -- tests whether the two terms are correctly mapped, not just recognized.",
        ),
        BankQuestion(
            key="wfa-14",
            category="AI/ML",
            text=(
                "An analyst building a model to predict attrition includes an employee's "
                "resignation date as an input feature. What's wrong with this?"
            ),
            options=(
                "Nothing -- more data is always better",
                "Data leakage: the resignation date is only known *after* the outcome being predicted, so it can't be a legitimate input",
                "Dates can't be used in machine learning models at all",
                "It will make the model run too slowly",
            ),
            correct_index=1,
            explanation="Classic data leakage scenario -- using a feature only available after the fact inflates apparent accuracy but is useless in production.",
        ),
        BankQuestion(
            key="wfa-15",
            category="APIs",
            text=(
                "A workforce management API rate-limits requests per client to 100/minute. A "
                "partner integration keeps hitting HTTP 429. What does that status code mean?"
            ),
            options=(
                "Internal server error",
                "Too Many Requests -- the client has exceeded the rate limit",
                "The requested resource was not found",
                "The request succeeded",
            ),
            correct_index=1,
            explanation="429 is a specific, commonly-encountered API status code every SE/DevOps-track student should recognize.",
        ),
    ],
    # ---------------------------------------------------------------- Booth 3 -- Unispot
    3: [
        BankQuestion(
            key="unispot-01",
            category="Networking",
            text=(
                "A student applies to five universities through a routing platform. What is "
                "DNS's role the first time their browser loads that platform's website?"
            ),
            options=(
                "It encrypts the connection between browser and server",
                "It translates the platform's domain name into an IP address the browser can connect to",
                "It compresses the images on the page for faster loading",
                "It manages the database transactions for the application form",
            ),
            correct_index=1,
            explanation="Core DNS definition, tested via a concrete first-load scenario rather than pure recall.",
        ),
        BankQuestion(
            key="unispot-02",
            category="Cybersecurity",
            text=(
                'A student notices a university application form\'s URL starts with "http://" '
                'instead of "https://" and their advisor tells them to be cautious. Why?'
            ),
            options=(
                "http:// pages load faster and that's the only difference",
                "Without TLS/SSL encryption, data submitted over http:// can potentially be intercepted in transit",
                "http:// pages are always fake",
                "There is no real difference in modern browsers",
            ),
            correct_index=1,
            explanation="Tests the practical *consequence* of missing HTTPS, not just the acronym.",
        ),
        BankQuestion(
            key="unispot-03",
            category="APIs",
            text=(
                "A university's admissions system and a student-routing platform need to "
                "exchange application data automatically, without a human copying data between "
                "them. What allows two separate systems to do that?"
            ),
            options=(
                "A shared physical hard drive",
                "An API -- a defined set of rules for how the two systems communicate and exchange data",
                "Both systems must run on the same IP address",
                "A VPN alone is sufficient with no other integration work",
            ),
            correct_index=1,
            explanation="API definition applied to the exact system-to-system integration this booth's real-world scenario involves.",
        ),
        BankQuestion(
            key="unispot-04",
            category="Software Engineering",
            text=(
                "A routing platform wants to average the processing time of thousands of "
                "applications daily without recomputing from scratch every time a new one "
                "arrives. Which approach is most efficient?"
            ),
            options=(
                "Recompute the average over every single stored application on every request",
                "Maintain a running sum and count, updating the average incrementally as new applications arrive",
                "Only compute the average once per year",
                "Store every historical average and never update it",
            ),
            correct_index=1,
            explanation="Incremental/streaming aggregation vs. brute-force recomputation -- a real algorithmic-efficiency tradeoff, not trivia.",
        ),
        BankQuestion(
            key="unispot-05",
            category="Data Science",
            text=(
                "An advisor wants to know if application processing time differs meaningfully "
                "between two intake periods, not just by chance. What kind of analysis answers "
                "that question properly?"
            ),
            options=(
                "Just compare the two average numbers by eye",
                "A statistical significance test (e.g. comparing distributions, not just point averages)",
                "Ask the advising team to guess",
                "Whichever number is higher is automatically the meaningful one",
            ),
            correct_index=1,
            explanation="Tests whether the student distinguishes 'numbers look different' from 'statistically meaningfully different.'",
        ),
        BankQuestion(
            key="unispot-06",
            category="Cybersecurity",
            text=(
                "A phishing email impersonates a university's admissions office, asking a "
                'student to "verify" their application by entering their password on a '
                "look-alike site. What is the best way to verify the email is legitimate?"
            ),
            options=(
                "Click the link and see if the site looks official",
                "Independently navigate to the university's known official website rather than clicking the email's link",
                "Reply to the email asking if it's real",
                "Forward it to a friend for a second opinion",
            ),
            correct_index=1,
            explanation="The core anti-phishing behavior: never trust the link in a suspicious message, navigate independently instead.",
        ),
        BankQuestion(
            key="unispot-07",
            category="Cybersecurity",
            text=(
                "A routing platform's server-side code directly inserts a user-submitted "
                "university name into a SQL query string. What vulnerability class does this "
                "create?"
            ),
            options=(
                "Cross-site scripting (XSS)",
                "SQL injection",
                "Denial of service",
                "DNS spoofing",
            ),
            correct_index=1,
            explanation="String-concatenated SQL from user input is the textbook SQL injection setup.",
        ),
        BankQuestion(
            key="unispot-08",
            category="Databases",
            text=(
                "Which fix most directly closes the SQL injection risk described in the "
                "previous scenario?"
            ),
            options=(
                "Using parameterized queries / prepared statements instead of string concatenation",
                "Making the password field longer",
                "Adding more RAM to the database server",
                "Changing the university name field to uppercase",
            ),
            correct_index=0,
            explanation="Parameterization is the actual class-level fix for injection, not a workaround.",
        ),
        BankQuestion(
            key="unispot-09",
            category="APIs",
            text=(
                "A partner university wants real-time updates the instant a new application "
                "arrives, rather than checking every few minutes. Which approach is best suited "
                "to that requirement?"
            ),
            options=(
                "The partner's system repeatedly polls the API every few minutes forever",
                "A webhook or push-based notification triggered the moment a new application is created",
                "The partner manually refreshes a spreadsheet",
                "Batch export once per week",
            ),
            correct_index=1,
            explanation="Push/webhook vs. polling is a real architectural tradeoff for 'as close to real-time as possible' requirements.",
        ),
        BankQuestion(
            key="unispot-10",
            category="Data Science",
            text=(
                "A dataset of application processing times has one entry of 400 days, while "
                "every other entry is under 60 days -- almost certainly a data-entry error. "
                "What's the appropriate first step?"
            ),
            options=(
                "Include it as-is since removing data is always dishonest",
                "Investigate the outlier before deciding whether to correct, exclude, or keep it -- don't silently drop it without reason",
                "Automatically delete every value above the median",
                "Replace it with zero",
            ),
            correct_index=1,
            explanation="Tests responsible outlier handling: investigate first, don't blindly keep or blindly discard.",
        ),
        BankQuestion(
            key="unispot-11",
            category="Networking",
            text=(
                "A load balancer sits in front of three application servers handling student "
                "traffic. What is its primary purpose?"
            ),
            options=(
                "To encrypt traffic between the client and server",
                "To distribute incoming requests across multiple servers to avoid overloading any single one",
                "To store application data permanently",
                "To translate domain names into IP addresses",
            ),
            correct_index=1,
            explanation="Core load balancer purpose, distinguished from DNS and TLS which do different jobs (common confusion point).",
        ),
        BankQuestion(
            key="unispot-12",
            category="Software Engineering",
            text=(
                "A student's application status page shows stale data because it's cached "
                "aggressively. What's the tradeoff being made by using a cache here at all?"
            ),
            options=(
                "Caching has no tradeoffs -- it should always be used everywhere",
                "Faster/cheaper repeated reads, at the cost of potentially serving outdated data until the cache is invalidated or expires",
                "Caching makes the database permanently faster with no downside",
                "Caching is only relevant for image files",
            ),
            correct_index=1,
            explanation="Tests understanding of the actual caching tradeoff (speed vs. freshness), not just 'caching = good.'",
        ),
        BankQuestion(
            key="unispot-13",
            category="Data Science",
            text=(
                "A routing desk wants to know which countries send the most applications, using "
                "a bar chart grouped by country. Which data preparation step is essential before "
                "building that chart?"
            ),
            options=(
                "None -- charts don't need any data preparation",
                "Grouping/aggregating the raw application records by country first",
                "Deleting all applications except the most recent one",
                "Converting the chart to a pie chart instead",
            ),
            correct_index=1,
            explanation="Group-by/aggregation is the actual required step before a per-category chart makes sense.",
        ),
        BankQuestion(
            key="unispot-14",
            category="AI/ML",
            text=(
                "An application-review AI assistant is trained mostly on essays from one "
                "region's writing style and starts scoring other regions' equally strong essays "
                "lower. What is this an example of?"
            ),
            options=(
                "A hardware failure",
                "Bias in the model resulting from unrepresentative training data",
                "A DNS misconfiguration",
                "Expected and acceptable behavior for any AI system",
            ),
            correct_index=1,
            explanation="Training-data bias producing unfair real-world outcomes -- a core, examinable AI/ML ethics concept.",
        ),
        BankQuestion(
            key="unispot-15",
            category="Software Engineering",
            text=(
                "A platform wants to reduce how often students abandon a slow-loading "
                "application form. Which single change is likely to have the biggest measurable "
                "impact?"
            ),
            options=(
                "Changing the font color of the submit button",
                "Reducing page load time / latency, since slow load is a well-documented driver of abandonment",
                "Adding more required fields to the form",
                "Removing the progress indicator",
            ),
            correct_index=1,
            explanation="Latency-driven abandonment is a well-established, measurable UX/performance relationship -- distinguishes real impact from cosmetic changes.",
        ),
    ],
    # ---------------------------------------------------------------- Booth 4 -- Close the Gap
    4: [
        BankQuestion(
            key="ctg-01",
            category="Cybersecurity",
            text=(
                "A company donates old laptops for refurbishment. Simply deleting the files "
                "before donating isn't considered secure. Why not?"
            ),
            options=(
                "Deleting a file only removes its reference from the file system; the underlying data often remains recoverable until overwritten",
                "Deleted files are automatically encrypted",
                "Deletion physically destroys the storage medium",
                "Deleted files are instantly and permanently unrecoverable on all hardware",
            ),
            correct_index=0,
            explanation="Core distinction this booth's whole scenario hinges on: delete vs. secure wipe (overwrite).",
        ),
        BankQuestion(
            key="ctg-02",
            category="Cybersecurity",
            text=(
                'Which best describes what a proper "secure wipe" does that simple deletion '
                "does not?"
            ),
            options=(
                "It overwrites the storage so the original data can't be practically recovered",
                "It renames the files to random strings",
                "It moves files to a hidden folder",
                "It compresses the files into an archive",
            ),
            correct_index=0,
            explanation="Direct technical definition of secure wipe, distinguished from cosmetic-only actions.",
        ),
        BankQuestion(
            key="ctg-03",
            category="Software Engineering",
            text=(
                'What best describes "circular economy" as applied to electronics refurbishment?'
            ),
            options=(
                "Manufacturing new devices as fast as possible to meet demand",
                "Keeping products and materials in use longer through reuse and refurbishment, reducing waste",
                "Recycling only the packaging, not the device itself",
                "A financial model with no relationship to environmental impact",
            ),
            correct_index=1,
            explanation="Core circular-economy definition, directly relevant to what this sponsor actually does.",
        ),
        BankQuestion(
            key="ctg-04",
            category="Software Engineering",
            text=('Which of the following is generally classified as "e-waste"?'),
            options=(
                "A decommissioned company laptop no longer in use",
                "A cloud storage subscription",
                "An email account that's been deleted",
                "A software license key",
            ),
            correct_index=0,
            explanation="Tests whether the student can distinguish physical e-waste from digital/service-based non-examples.",
        ),
        BankQuestion(
            key="ctg-05",
            category="Cybersecurity",
            text=(
                'A refurbishment hub\'s inventory tracker shows a device as "wiped" but an '
                "audit later finds recoverable personal data on it. What does this most likely "
                "indicate?"
            ),
            options=(
                "The wipe process was interrupted or failed, and the tracker's status wasn't verified against the actual device state",
                "This is expected and not a problem",
                "The device was never plugged into a network",
                "The audit tool itself is broken by definition",
            ),
            correct_index=0,
            explanation="Points at a real operational risk: status flags in a system of record can drift from ground truth if not independently verified.",
        ),
        BankQuestion(
            key="ctg-06",
            category="Cybersecurity",
            text=(
                "A hard drive uses full-disk encryption. If the drive is later securely wiped "
                "by simply destroying the encryption key (crypto-erase) instead of overwriting "
                "every sector, why can this still be considered secure?"
            ),
            options=(
                "It isn't secure -- data is still fully readable",
                "Without the key, the encrypted data is computationally infeasible to recover, achieving effective erasure much faster than a full overwrite",
                "Destroying a key has no effect on encrypted data",
                "Crypto-erase only works on hard drives, never on SSDs",
            ),
            correct_index=1,
            explanation="Crypto-erase is a legitimate, well-documented and much faster alternative to full-disk overwrite -- tests whether the student understands *why* it works.",
        ),
        BankQuestion(
            key="ctg-07",
            category="Cybersecurity",
            text=(
                "A batch of devices arrives for refurbishment from many different companies. "
                "What is the biggest data-security risk specific to this stage of the process?"
            ),
            options=(
                "None -- risk only exists after refurbishment is complete",
                "Devices may still contain the previous owner's sensitive data, so chain-of-custody and wipe-before-handling matter from intake onward",
                "The devices are too old to contain any usable data",
                "Refurbishment itself erases all data automatically",
            ),
            correct_index=1,
            explanation="Tests whether the student thinks about data risk across the whole lifecycle, not just 'after wiping is done.'",
        ),
        BankQuestion(
            key="ctg-08",
            category="Testing",
            text=(
                'A tracking system logs "1" for a device that still needs a secure wipe. If '
                'the flag is accidentally flipped to "0" by a software bug, what is the '
                "real-world consequence?"
            ),
            options=(
                "None -- it's just a display issue",
                "A device with recoverable personal data could be redeployed as if it were already safe, a real data-breach risk",
                "The device would stop working entirely",
                "The refurbishment hub would automatically be notified and correct it",
            ),
            correct_index=1,
            explanation="Connects a software correctness bug directly to a physical-world security consequence -- exactly this booth's evidence-log scenario.",
        ),
        BankQuestion(
            key="ctg-09",
            category="Cybersecurity",
            text=(
                "Which industry-standard concept describes permanently and verifiably destroying "
                "data so it meets compliance requirements (e.g. for regulated data like health "
                "or financial records)?"
            ),
            options=(
                "Data sanitization / certified data destruction",
                "Data compression",
                "Data replication",
                "Data caching",
            ),
            correct_index=0,
            explanation="Correct industry terminology, distinguished from unrelated but plausible-sounding data-engineering terms.",
        ),
        BankQuestion(
            key="ctg-10",
            category="Cybersecurity",
            text=(
                "A refurbishment company wants to prove to auditors, after the fact, exactly "
                "which employee wiped which device and when. What should the system provide?"
            ),
            options=(
                "Nothing is needed -- trusting staff verbally is sufficient for audits",
                "An immutable audit log recording who performed the wipe action and when",
                "A single shared login for all technicians to simplify things",
                "Deleting old records regularly to save storage",
            ),
            correct_index=1,
            explanation="Audit-log/accountability is the real compliance answer; shared logins and no-record-keeping are anti-patterns.",
        ),
        BankQuestion(
            key="ctg-11",
            category="Software Engineering",
            text=(
                "Why might refurbishing and reselling used enterprise hardware be considered "
                "more sustainable than the buyer purchasing new hardware, from a lifecycle "
                "perspective?"
            ),
            options=(
                "New hardware is always defective",
                "It extends the usable life of materials and manufacturing already invested in the device, avoiding the environmental cost of producing a new one",
                "Refurbished hardware never fails",
                "There is no real environmental difference either way",
            ),
            correct_index=1,
            explanation="Tests the actual lifecycle/embodied-carbon argument for reuse, not just 'refurbished is cheaper.'",
        ),
        BankQuestion(
            key="ctg-12",
            category="Software Engineering",
            text=(
                "A batch of 200 devices needs a status check: how many are unwiped vs. wiped. "
                'Which is the correct way to compute "how many entries equal a specific value" '
                "in a list of flags?"
            ),
            options=(
                "Sort the list and read the last value",
                "Count the occurrences of that specific value across the list",
                "Multiply the list length by 2",
                "Take the average of the whole list",
            ),
            correct_index=1,
            explanation="Basic but correctly-scoped algorithmic check tied directly to this booth's actual coding challenge shape.",
        ),
        BankQuestion(
            key="ctg-13",
            category="Cybersecurity",
            text=(
                "A device's storage is physically destroyed (shredded) rather than wiped for "
                "reuse. When is this the more appropriate choice over a secure wipe?"
            ),
            options=(
                "Never -- wiping is always preferred regardless of drive condition",
                "When the drive is damaged/unreliable enough that a wipe can't be verified as complete, physical destruction guarantees no recoverable data remains",
                "Only for devices under warranty",
                "Physical destruction is always worse for the environment, so it should never be used",
            ),
            correct_index=1,
            explanation="Tests a real operational judgment call: wipe-and-reuse vs. destroy, based on verifiability, not a blanket rule.",
        ),
        BankQuestion(
            key="ctg-14",
            category="Cybersecurity",
            text=(
                'Which of these is the most accurate description of what "data breach" means '
                "in the context of improperly wiped refurbished devices?"
            ),
            options=(
                "A device running slowly",
                "Unauthorized exposure of data to someone who shouldn't have access to it",
                "A device being physically stolen only",
                "A software update failing to install",
            ),
            correct_index=1,
            explanation="Core term definition, distinguished from unrelated hardware/performance issues that could be superficially confused with it.",
        ),
        BankQuestion(
            key="ctg-15",
            category="Data Science",
            text=(
                "A refurbishment company wants a dashboard showing wipe-completion rate over "
                "time to catch process regressions early. What is the most useful visualization "
                "choice for that goal?"
            ),
            options=(
                "A single number updated once a year",
                "A time-series trend line so regressions or improvements are visible as they happen",
                "A random sample of five devices shown with no aggregation",
                "No visualization is useful for operational monitoring",
            ),
            correct_index=1,
            explanation="Time-series monitoring is the correct answer for 'catch regressions early' -- a real operational-analytics pattern.",
        ),
        BankQuestion(
            key="ctg-16",
            category="Networking",
            text=(
                "A refurbishment hub keeps intake devices (still holding a previous owner's data) "
                "on the same flat network as its already-wiped, ready-to-ship inventory. What's "
                "the strongest networking-level fix?"
            ),
            options=(
                "Segment the network (e.g. VLANs) so intake devices can't reach the ready-to-ship inventory systems",
                "Give every device the same static IP to make tracking simpler",
                "Disable DNS for the intake devices",
                "There's no networking angle here -- this is purely a software problem",
            ),
            correct_index=0,
            explanation="Network segmentation limiting blast radius between untrusted intake and trusted inventory is the actual infrastructure-level control here.",
        ),
        BankQuestion(
            key="ctg-17",
            category="Git",
            text=(
                "Two technicians both edit the same device-intake tracking script in their own "
                "branches. Before either can merge into main, what does Git require if they both "
                "touched the same lines?"
            ),
            options=(
                "Nothing -- Git always keeps both versions automatically",
                "The conflicting branch must be rebased or merged with main and any conflicting hunks resolved by hand before it can be merged",
                "The second branch is permanently blocked from ever merging",
                "Git deletes one technician's branch automatically to resolve it",
            ),
            correct_index=1,
            explanation="Tests the actual mechanics of resolving a real merge conflict, not just recognizing the term.",
        ),
    ],
    # ---------------------------------------------------------------- Booth 5 -- Zuberi
    5: [
        BankQuestion(
            key="zuberi-01",
            category="Cybersecurity",
            text=(
                "A mobile game submits match scores directly from the player's device to update "
                "the leaderboard, trusting whatever value the client sends. What is the main "
                "risk of this design?"
            ),
            options=(
                "The game will run slower on older phones",
                "A modified client can submit fabricated scores, since the server never independently verifies them",
                "The leaderboard will use more storage",
                "There is no real risk to this design",
            ),
            correct_index=1,
            explanation="Client-trust vulnerability -- exactly why server-side score validation matters, directly tied to this booth's scenario.",
        ),
        BankQuestion(
            key="zuberi-02",
            category="Cybersecurity",
            text=(
                "Why do most competitive mobile games validate scores server-side instead of "
                "trusting the value the client reports?"
            ),
            options=(
                "Server-side validation makes the game load faster",
                "It prevents players from tampering with scores locally to cheat the leaderboard",
                "It's required by every app store regardless of game type",
                "Client-side validation is impossible on mobile devices",
            ),
            correct_index=1,
            explanation="Direct application of the previous question's concept -- the actual defensive reason, not an unrelated benefit.",
        ),
        BankQuestion(
            key="zuberi-03",
            category="Cybersecurity",
            text=(
                "A game's input field for a player's username doesn't validate or sanitize what "
                "is submitted before storing it. What class of risk does this create?"
            ),
            options=(
                "None -- usernames are just cosmetic text",
                "Injection or crash vulnerabilities, if the unvalidated input is later used in a query, rendered unsafely, or processed unexpectedly",
                "The game will automatically run faster",
                "The UI will redesign itself based on the username",
            ),
            correct_index=1,
            explanation="Tests the general principle that unvalidated input is a security/stability risk regardless of how 'harmless' the field looks.",
        ),
        BankQuestion(
            key="zuberi-04",
            category="Software Engineering",
            text=('In game development, "FPS" most commonly refers to which of the following?'),
            options=(
                "Frames Per Second, a measure of rendering smoothness",
                "File Processing Server",
                "Final Product Stage",
                "Fast Packet Switching",
            ),
            correct_index=0,
            explanation="Standard game-dev terminology, included as a genuinely industry-specific but unambiguous term.",
        ),
        BankQuestion(
            key="zuberi-05",
            category="Testing",
            text=(
                "A mobile game experiences a spike in crashes after a new update, but only on "
                "one specific Android device model. What's the most effective first debugging "
                "step?"
            ),
            options=(
                "Assume it's an isolated hardware fault and ignore it",
                "Reproduce the crash on that device model (or an emulator matching its specs) and inspect the crash logs",
                "Roll back the entire update for all players immediately without investigation",
                "Tell affected players to buy a new phone",
            ),
            correct_index=1,
            explanation="Reproduce-then-diagnose is the correct debugging methodology, versus premature rollback or dismissal.",
        ),
        BankQuestion(
            key="zuberi-06",
            category="DevOps",
            text=(
                "A leaderboard service goes down under a sudden traffic spike during a "
                "tournament. Which architectural choice would most directly help it handle "
                "sudden load spikes gracefully?"
            ),
            options=(
                "A single server with no redundancy, kept as simple as possible",
                "Horizontal scaling (adding more server instances) behind a load balancer",
                "Storing all data in the client app instead of a server",
                "Reducing the game's graphics quality",
            ),
            correct_index=1,
            explanation="Direct architectural response to variable load -- horizontal scaling behind a load balancer, not client-side or graphics changes.",
        ),
        BankQuestion(
            key="zuberi-07",
            category="Data Science",
            text=(
                "A game studio wants to know if a new matchmaking algorithm actually reduces "
                "wait times compared to the old one. What is the most rigorous way to find out?"
            ),
            options=(
                'Ask the community on social media which one they "feel" is faster',
                "Run an A/B test comparing wait times between the old and new algorithm under similar conditions",
                "Assume the newer algorithm is always better since it's newer",
                "Only test it internally with the development team, who know the game well",
            ),
            correct_index=1,
            explanation="A/B testing under controlled conditions is the correct empirical approach versus anecdote or assumption.",
        ),
        BankQuestion(
            key="zuberi-08",
            category="AI/ML",
            text=(
                "A mobile game wants to recommend which game mode a player is most likely to "
                "enjoy next, based on their play history. Which type of system is this?"
            ),
            options=(
                "A recommendation system, typically built using supervised or collaborative-filtering techniques on historical behavior data",
                "A firewall",
                "A load balancer",
                "A DNS resolver",
            ),
            correct_index=0,
            explanation="Correctly identifies the ML system category, distinguished from unrelated infrastructure terms included as plausible-sounding distractors.",
        ),
        BankQuestion(
            key="zuberi-09",
            category="Cybersecurity",
            text=(
                "A game's backend API has no rate limiting. What is the most likely consequence "
                "if a malicious actor scripts thousands of rapid requests against it?"
            ),
            options=(
                "Nothing -- APIs handle unlimited traffic by default",
                "A denial-of-service-like impact, degrading performance or availability for legitimate players",
                "The API will automatically start rate-limiting itself",
                "The game's graphics will improve",
            ),
            correct_index=1,
            explanation="Tests understanding of why rate limiting exists as a defensive measure, not just as a feature checkbox.",
        ),
        BankQuestion(
            key="zuberi-10",
            category="Cybersecurity",
            text=(
                "A studio collects gameplay telemetry (session length, level failures, in-app "
                "purchases) from players. Which practice best respects player privacy while "
                "still enabling useful analysis?"
            ),
            options=(
                "Collect everything possible with no limits or disclosure",
                "Collect only what's needed, disclose it clearly, and anonymize/aggregate where individual identity isn't required",
                "Never collect any data, making analysis impossible",
                "Sell raw player data to any interested third party without consent",
            ),
            correct_index=1,
            explanation="Data minimization + transparency is the correct, realistic middle ground -- not 'collect nothing' or 'collect everything.'",
        ),
        BankQuestion(
            key="zuberi-11",
            category="DevOps",
            text=(
                "A game studio pushes an update directly to 100% of players with no staged "
                "rollout, and it introduces a game-breaking bug. What would a staged/canary "
                "rollout have done differently?"
            ),
            options=(
                "Nothing -- staged rollouts don't affect bug impact",
                "Limited the bug's exposure to a small percentage of players first, catching the issue before it affected everyone",
                "Made the update deploy faster",
                "Automatically fixed the bug before release",
            ),
            correct_index=1,
            explanation="Real deployment-risk-mitigation concept (canary release), tested via consequence rather than definition.",
        ),
        BankQuestion(
            key="zuberi-12",
            category="Networking",
            text=(
                'Which best describes the difference between a game\'s "client" and its '
                '"server" in an online multiplayer architecture?'
            ),
            options=(
                "There is no meaningful difference -- they run identical code",
                "The client renders and handles local input/display; the server maintains authoritative game state and mediates between players",
                "The server only exists for single-player games",
                "The client stores the entire player database",
            ),
            correct_index=1,
            explanation="Correct client/server responsibility split -- foundational for understanding why server-authoritative validation (an earlier question) matters at all.",
        ),
        BankQuestion(
            key="zuberi-13",
            category="AI/ML",
            text=(
                "A studio wants to reduce cheating in a competitive mode without server-side "
                "validation being technically feasible for every single action. Which "
                "additional approach is commonly used alongside validation?"
            ),
            options=(
                "Anomaly detection -- statistically flagging players whose results are implausible for manual or automated review",
                "Removing the leaderboard entirely",
                "Ignoring the issue since cheating cannot be detected",
                "Making the game single-player only",
            ),
            correct_index=0,
            explanation="Anomaly/statistical detection is a real complementary anti-cheat layer used industry-wide, beyond pure validation.",
        ),
        BankQuestion(
            key="zuberi-14",
            category="Software Engineering",
            text=(
                "A mobile game's crash reports show most failures happen on low-end devices "
                "with limited memory. What's the most directly relevant fix category?"
            ),
            options=(
                "Improve memory management / reduce memory footprint for constrained devices",
                "Increase the game's minimum required Android version to exclude those devices",
                "Add more visual effects to distract from crashes",
                "Reduce the price of the game",
            ),
            correct_index=0,
            explanation="Matches the fix to the actual root cause (memory pressure) rather than an unrelated or evasive action.",
        ),
        BankQuestion(
            key="zuberi-15",
            category="DevOps",
            text=(
                "Why might a game studio choose to store player progress in the cloud rather "
                "than only on-device?"
            ),
            options=(
                "Cloud storage guarantees the game runs faster",
                "It lets players continue progress across devices and recover it if a device is lost or reset",
                "On-device storage is illegal in most countries",
                "There is no benefit -- it only adds cost",
            ),
            correct_index=1,
            explanation="Real, practical product reason for cloud save systems, distinguished from a false performance claim.",
        ),
    ],
    # ---------------------------------------------------------------- Booth 6 -- TBM Limited
    6: [
        BankQuestion(
            key="tbm-01",
            category="Cybersecurity",
            text=(
                'A company adopts a "Zero Trust" security architecture. What does that '
                "fundamentally assume, compared to a traditional perimeter-based model?"
            ),
            options=(
                "That all traffic inside the corporate network is automatically safe",
                "That no user or device should be trusted by default, even if it's already inside the network perimeter",
                "That passwords are no longer necessary anywhere",
                "That only external users need to be verified",
            ),
            correct_index=1,
            explanation="Core Zero Trust principle, distinguished from the perimeter-trust model it replaces.",
        ),
        BankQuestion(
            key="tbm-02",
            category="Cybersecurity",
            text=("What is the primary purpose of a Security Operations Center (SOC)?"),
            options=(
                "Monitor systems and respond to security incidents in real time",
                "Design marketing campaigns for the company",
                "Manage payroll and HR systems",
                "Host the company's public marketing website",
            ),
            correct_index=0,
            explanation="Standard SOC definition, framed to rule out plausible-but-wrong 'business operations center' confusions.",
        ),
        BankQuestion(
            key="tbm-03",
            category="Cybersecurity",
            text=(
                "An enterprise client asks TBM Limited to review why an internal server was "
                "compromised despite having a firewall. The attacker had valid, stolen employee "
                "credentials. Why didn't the firewall stop this attack?"
            ),
            options=(
                "The firewall was misconfigured and should have blocked all traffic",
                "Firewalls primarily filter network traffic based on rules; they don't prevent misuse of already-valid, legitimate credentials",
                "Firewalls are obsolete technology with no real purpose",
                "This scenario is impossible if a firewall exists",
            ),
            correct_index=1,
            explanation="Tests understanding of what a firewall actually protects against, versus credential-based attacks that bypass it entirely.",
        ),
        BankQuestion(
            key="tbm-04",
            category="AI/ML",
            text=('In AI/ML, what is "training data" used for?'),
            options=(
                "Teaching a model to recognize patterns by learning from examples",
                "Storing user passwords securely",
                "Rendering 3D graphics in an application",
                "Compiling source code into an executable",
            ),
            correct_index=0,
            explanation="Foundational ML term, distinguished from unrelated systems concepts used as distractors.",
        ),
        BankQuestion(
            key="tbm-05",
            category="Cybersecurity",
            text=(
                "A cybersecurity team receives an alert that a server is sending large volumes "
                "of outbound traffic to an unfamiliar external IP at 3 AM, when no scheduled job "
                "should be running. What should happen first?"
            ),
            options=(
                "Ignore it since outbound traffic is generally normal",
                "Investigate the alert as a potential data exfiltration or compromise, following incident response procedure",
                "Immediately format the server without investigation",
                "Wait until business hours to look into it",
            ),
            correct_index=1,
            explanation="Textbook indicator of compromise (unusual off-hours outbound traffic); tests appropriate incident-response instinct over both extremes (ignore or overreact by wiping).",
        ),
        BankQuestion(
            key="tbm-06",
            category="Cybersecurity",
            text=("Which best describes the difference between a vulnerability and an exploit?"),
            options=(
                "They are exactly the same thing",
                "A vulnerability is a weakness in a system; an exploit is a method or code that takes advantage of that weakness",
                "An exploit is a type of firewall",
                "A vulnerability only applies to hardware, never software",
            ),
            correct_index=1,
            explanation="Precise distinction frequently conflated by newcomers -- weakness vs. the mechanism that leverages it.",
        ),
        BankQuestion(
            key="tbm-07",
            category="DevOps",
            text=(
                "TBM's cloud team migrates a client's infrastructure to use auto-scaling. What "
                "problem does auto-scaling primarily solve?"
            ),
            options=(
                "It automatically fixes bugs in the application code",
                "It adjusts the number of running server instances based on real-time demand, avoiding both over- and under-provisioning",
                "It encrypts all data at rest",
                "It replaces the need for any monitoring",
            ),
            correct_index=1,
            explanation="Correct cloud-infrastructure concept, distinguished from unrelated security/monitoring claims.",
        ),
        BankQuestion(
            key="tbm-08",
            category="Cybersecurity",
            text=(
                "A company stores customer passwords using a fast, unsalted MD5 hash. Why is "
                "this considered poor practice today?"
            ),
            options=(
                "MD5 is fast and unsalted, making precomputed rainbow-table and brute-force attacks practical against stolen hashes",
                "MD5 hashes take up too much disk space",
                "Hashing passwords is never a good idea under any circumstances",
                "This is actually still considered fully secure practice",
            ),
            correct_index=0,
            explanation="Tests understanding of *why* salted, slow hashing algorithms (bcrypt/argon2) replaced fast unsalted hashes for passwords specifically.",
        ),
        BankQuestion(
            key="tbm-09",
            category="AI/ML",
            text=(
                "An AI model performs very well on its training data but poorly on new, unseen "
                "data. What is this phenomenon called?"
            ),
            options=(
                "Underfitting",
                "Overfitting -- the model has memorized training data patterns rather than learning generalizable ones",
                "Data encryption",
                "Load balancing",
            ),
            correct_index=1,
            explanation="Core ML failure mode with a specific, correct name, distinguished from its opposite (underfitting) as a distractor.",
        ),
        BankQuestion(
            key="tbm-10",
            category="Cybersecurity",
            text=(
                "A client asks TBM to help them meet a compliance requirement that all sensitive "
                "data be unreadable if a laptop is lost or stolen. Which control most directly "
                "addresses that specific requirement?"
            ),
            options=(
                "Full-disk encryption",
                "A stronger Wi-Fi password",
                "More frequent software updates",
                "A company-wide password reset",
            ),
            correct_index=0,
            explanation="Full-disk encryption is the control that specifically protects data confidentiality on a physically lost/stolen device.",
        ),
        BankQuestion(
            key="tbm-11",
            category="Cybersecurity",
            text=('Which of these best describes the purpose of a "penetration test"?'),
            options=(
                "Authorized, simulated attacks against a system to find exploitable weaknesses before real attackers do",
                "A routine performance benchmark with no security relevance",
                "An automatic process that fixes vulnerabilities without human involvement",
                "A test that only checks whether a website loads correctly",
            ),
            correct_index=0,
            explanation="Correct, precise definition of pen testing as authorized offensive security testing -- not to be confused with general QA testing.",
        ),
        BankQuestion(
            key="tbm-12",
            category="DevOps",
            text=(
                "A DevOps team wants every infrastructure change to be reviewed, versioned, and "
                "reproducible rather than made by hand on live servers. Which practice enables "
                "that?"
            ),
            options=(
                "Manually SSH-ing into servers to make changes as needed",
                "Infrastructure as Code (IaC) -- defining infrastructure in version-controlled configuration files",
                "Disabling all logging to speed up changes",
                "Sharing one root password among the whole team",
            ),
            correct_index=1,
            explanation="IaC is the specific practice that satisfies review/version/reproducibility requirements, versus ad hoc manual changes.",
        ),
        BankQuestion(
            key="tbm-13",
            category="Cybersecurity",
            text=(
                "Why do enterprise security teams generally prefer centralized logging (all "
                "systems shipping logs to one place) over each server keeping its own local "
                "logs only?"
            ),
            options=(
                "It's required by every operating system by default",
                "It enables correlation across systems during an investigation and protects logs if an individual system is compromised and its local logs tampered with",
                "It makes each individual server run faster",
                "There is no real security benefit to centralizing logs",
            ),
            correct_index=1,
            explanation="Correct dual justification (correlation + tamper-resistance) for centralized logging, a real SOC/incident-response practice.",
        ),
        BankQuestion(
            key="tbm-14",
            category="AI/ML",
            text=(
                "An AI chatbot deployed by a company starts giving confidently wrong answers to "
                "factual questions. What is this commonly called?"
            ),
            options=(
                "Hallucination -- the model generating plausible-sounding but factually incorrect output",
                "Encryption failure",
                "A firewall breach",
                "A denial-of-service attack",
            ),
            correct_index=0,
            explanation="Standard, specific terminology for this well-known LLM failure mode.",
        ),
        BankQuestion(
            key="tbm-15",
            category="Cybersecurity",
            text=(
                'A client\'s cybersecurity policy requires "defense in depth." What does that '
                "principle actually mean?"
            ),
            options=(
                "Relying on a single very strong control instead of multiple layers",
                "Using multiple, overlapping layers of security controls so that if one fails, others still provide protection",
                "Only securing the network perimeter and nothing internal",
                "A policy that applies exclusively to physical building security",
            ),
            correct_index=1,
            explanation="Correct, precise definition of defense in depth as layered/redundant controls, not single-point reliance.",
        ),
        BankQuestion(
            key="tbm-16",
            category="Git",
            text=(
                "TBM's security team wants every change to a client's incident-response runbook "
                "reviewed and reversible if it turns out wrong. Which practice most directly "
                "enables that?"
            ),
            options=(
                "Editing the shared runbook document in place with no history kept",
                "Version-controlling the runbook (e.g. in Git) so every change has a reviewable diff and can be reverted",
                "Emailing the updated runbook to the team once a quarter",
                "Keeping only one physical printed copy in the office",
            ),
            correct_index=1,
            explanation="Version control's reviewability/revertability is the actual mechanism that satisfies both requirements here.",
        ),
        BankQuestion(
            key="tbm-17",
            category="Testing",
            text=(
                "Before rolling a new detection rule out to a client's entire SOC, TBM runs it "
                "against a year of historical logs to see how many alerts it would have fired. "
                "What is this practice primarily meant to catch?"
            ),
            options=(
                "Whether the rule is written in the correct programming language",
                "A high false-positive rate that would overwhelm analysts before the rule ever reaches production",
                "Whether the client's Wi-Fi password is strong enough",
                "Nothing useful -- historical replay has no relationship to future rule performance",
            ),
            correct_index=1,
            explanation="Backtesting a detection rule against historical data is specifically a test for false-positive rate before it burdens real analysts.",
        ),
        BankQuestion(
            key="tbm-18",
            category="Networking",
            text=(
                "A client asks TBM why their internal file server, reachable from every "
                "department's subnet, was an easy pivot point once a single laptop was "
                "compromised. What networking concept explains the risk?"
            ),
            options=(
                "Lack of network segmentation -- flat networks let a single compromised host reach far more of the environment",
                "The server's hostname was too easy to guess",
                "The server was using too new a version of its operating system",
                "This has nothing to do with networking design",
            ),
            correct_index=0,
            explanation="Flat-network lateral movement is a core networking-security concept, distinct from the unrelated distractors.",
        ),
    ],
}

# question_text -> category, for correlating a database KnowledgeQuestion row back to its
# origin category without adding a DB column -- see MissionService.assign_knowledge_subset,
# which uses this for category-balanced sampling. Only ever populated from this file, since
# KnowledgeQuestion rows are never authored anywhere else (see app/blueprints/agent.py). A
# question whose text isn't found here (e.g. a test fixture) is simply left uncategorized by
# the caller, which degrades to a plain random sample -- never an error.
CATEGORY_BY_TEXT = {
    bank_q.text: bank_q.category
    for bank_questions in BOOTH_QUESTION_BANKS.values()
    for bank_q in bank_questions
}


def category_for_text(question_text):
    return CATEGORY_BY_TEXT.get(question_text)
