"""Word lists used by the analysers.

Every subjective judgement llmtone makes lives in this one file. If you disagree
with a score, this is almost always the file to look at first: change a list here
and rerun ``llmtone profile`` to see the effect.

These lists are hand-curated, English-only, and deliberately small. They are not
derived from a corpus and they are not exhaustive. They encode "words that, when
present, are weak evidence of a style" -- not "the definitive set of formal words".
"""

from __future__ import annotations

# --- Contractions -----------------------------------------------------------
# Contractions are also detected by regex (see syntax.py). This set exists so
# that genuine contractions can be told apart from possessive apostrophes.
CONTRACTIONS = frozenset({
    "i'm", "i've", "i'll", "i'd", "you're", "you've", "you'll", "you'd",
    "he's", "he'll", "he'd", "she's", "she'll", "she'd", "it's", "it'll",
    "we're", "we've", "we'll", "we'd", "they're", "they've", "they'll",
    "they'd", "that's", "that'll", "there's", "there'll", "here's", "what's",
    "who's", "where's", "how's", "let's", "isn't", "aren't", "wasn't",
    "weren't", "hasn't", "haven't", "hadn't", "doesn't", "don't", "didn't",
    "won't", "wouldn't", "can't", "couldn't", "shouldn't", "mustn't",
    "mightn't", "shan't", "ain't", "y'all", "gonna", "gotta", "wanna",
    "kinda", "sorta",
})

# --- Pronouns ---------------------------------------------------------------
FIRST_PERSON = frozenset({
    "i", "me", "my", "mine", "myself",
    "we", "us", "our", "ours", "ourselves",
})

SECOND_PERSON = frozenset({
    "you", "your", "yours", "yourself", "yourselves",
})

# --- Hedging ----------------------------------------------------------------
# Words that soften a claim. High rates read as tentative; near-zero reads blunt.
HEDGE_WORDS = frozenset({
    "probably", "possibly", "perhaps", "maybe", "might", "seems", "seem",
    "seemed", "appears", "apparently", "arguably", "somewhat", "slightly",
    "fairly", "rather", "roughly", "approximately", "generally", "usually",
    "typically", "sometimes", "occasionally", "presumably", "supposedly",
    "allegedly", "likely", "unlikely", "tend", "tends", "tended", "suppose",
    "reckon", "unsure", "unclear", "ish", "possible", "potentially",
})

# Hedges that are only hedges as a phrase. Counted separately so that "kind
# regards" and "a kind of engine" are not scored as hedging.
HEDGE_PHRASES = (
    "sort of", "kind of", "a bit", "a little", "i think", "i would say",
    "more or less", "if anything", "to be fair", "i guess", "i suppose",
    "not sure", "as far as i", "in my experience", "it depends",
    "i tend to", "my sense is", "i could be wrong", "or something",
    "more of a", "at least", "in theory", "for the most part",
)

# --- Fillers and qualifiers -------------------------------------------------
FILLERS = frozenset({
    "basically", "essentially", "actually", "literally", "honestly", "frankly",
    "obviously", "clearly", "simply", "just", "really", "totally",
    "definitely", "certainly", "absolutely", "completely", "entirely",
    "particularly", "especially", "specifically", "effectively", "practically",
    "virtually", "anyway", "anyhow", "regardless", "somehow", "quite",
})

INTENSIFIERS = frozenset({
    "very", "really", "extremely", "incredibly", "hugely", "massively",
    "totally", "absolutely", "seriously", "genuinely", "super", "insanely",
    "ridiculously", "wildly", "deeply", "utterly", "immensely", "so",
})

# --- Corporate buzzwords ----------------------------------------------------
BUZZWORDS = frozenset({
    "leverage", "leveraging", "leveraged", "synergy", "synergies",
    "synergise", "synergize", "alignment", "stakeholder", "stakeholders",
    "deliverable", "deliverables", "actionable", "bandwidth", "ideate",
    "ideation", "operationalise", "operationalize", "streamline",
    "streamlined", "holistic", "paradigm", "ecosystem", "touchpoint",
    "upskill", "reskill", "learnings", "empower", "empowering", "disrupt",
    "disruptive", "scalable", "robust", "seamless", "frictionless",
    "granular", "cadence", "workstream", "socialise", "socialize",
    "greenfield", "impactful", "proactive", "proactively", "strategic",
    "strategically", "innovative", "cutting-edge", "world-class",
    "best-in-class", "mission-critical", "value-add", "north-star",
})

BUZZ_PHRASES = (
    "circle back", "touch base", "reach out", "move the needle",
    "low hanging fruit", "low-hanging fruit", "at the end of the day",
    "going forward", "boil the ocean", "take this offline", "drill down",
    "deep dive", "double click", "north star", "value add", "best in class",
    "mission critical", "think outside the box", "table stakes",
    "quick win", "on my radar", "close the loop", "align on",
    "it is important to note", "it should be noted",
)

# --- Overly formal vocabulary ----------------------------------------------
# Words with a shorter, plainer everyday alternative.
FORMAL_VOCAB = frozenset({
    "utilise", "utilize", "utilised", "utilized", "utilisation", "utilization",
    "commence", "commenced", "commencement", "terminate", "terminated",
    "endeavour", "endeavor", "endeavours", "endeavors", "ascertain",
    "facilitate", "facilitated", "facilitates", "demonstrate", "demonstrates",
    "demonstrated", "additionally", "furthermore", "moreover", "nevertheless",
    "nonetheless", "notwithstanding", "henceforth", "heretofore",
    "aforementioned", "subsequent", "subsequently", "regarding", "concerning",
    "pertaining", "accordingly", "consequently", "therefore", "thus", "hence",
    "whilst", "amongst", "upon", "shall", "sufficient", "insufficient",
    "numerous", "obtain", "obtained", "assistance", "attempt", "purchase",
    "residence", "inquire", "enquire", "kindly", "sincerely", "respectfully",
    "cordially", "expedite", "optimal", "initiate", "initiated", "cease",
    "ceased", "hereby", "therein", "thereof", "whereby", "wherein",
    "furthermore", "aforesaid", "endeavouring", "requisite", "aforestated",
})

# Straight swaps the renderer can suggest. Keys are formal, values plain.
FORMAL_TO_PLAIN = {
    "utilise": "use", "utilize": "use", "commence": "start",
    "terminate": "end", "endeavour": "try", "endeavor": "try",
    "ascertain": "find out", "facilitate": "help", "demonstrate": "show",
    "additionally": "also", "furthermore": "also", "moreover": "also",
    "nevertheless": "even so", "subsequently": "later", "prior to": "before",
    "regarding": "about", "concerning": "about", "accordingly": "so",
    "consequently": "so", "whilst": "while", "amongst": "among",
    "upon": "on", "obtain": "get", "purchase": "buy", "residence": "home",
    "inquire": "ask", "enquire": "ask", "sufficient": "enough",
    "numerous": "many", "assistance": "help", "attempt": "try",
    "expedite": "speed up", "initiate": "start", "cease": "stop",
    "optimal": "best", "in order to": "to", "at this time": "now",
    "due to the fact that": "because", "in the event that": "if",
}

# Formal connectives specifically -- a strong, low-noise formality signal.
FORMAL_TRANSITIONS = frozenset({
    "furthermore", "moreover", "additionally", "nevertheless", "nonetheless",
    "consequently", "accordingly", "therefore", "thus", "hence", "henceforth",
    "notwithstanding", "conversely", "likewise", "similarly", "indeed",
    "subsequently", "heretofore", "whereas", "whereby",
})

# --- Colloquial language ----------------------------------------------------
COLLOQUIALISMS = frozenset({
    "stuff", "loads", "tons", "heaps", "bunch", "yeah", "yep", "nope", "nah",
    "okay", "cool", "weird", "messy", "tricky", "handy", "dodgy", "rubbish",
    "grim", "faff", "hassle", "mess", "chaos", "nightmare", "annoying",
    "boring", "silly", "daft", "massive", "tiny", "fiddly", "clunky",
    "janky", "gnarly", "sketchy", "wonky", "bloke", "folks", "guys",
    "chuck", "grab", "broke", "stuck", "gist", "vibe", "knackered",
    "bloody", "bin", "binned", "punt", "gubbins", "fine", "pretty",
})

COLLOQUIAL_PHRASES = (
    "sort out", "sorting out", "figure out", "figuring out", "work out",
    "end up", "ends up", "ended up", "come up", "blow up", "catch fire",
    "catching fire", "on fire", "fall over", "falls over", "fell over",
    "falling over", "a mess", "a nightmare", "a pain", "no idea", "no clue",
    "kick off", "kicks off", "wrap up", "in the weeds", "under the hood",
    "from scratch", "spot on", "up to speed", "down the line",
    "the whole thing", "all over the place", "a load of", "a bunch of",
    "get on with", "crack on", "nailed it", "good to go",
)

# --- Humour markers ---------------------------------------------------------
# Weak signals. Humour is the least reliable dimension llmtone infers, which is
# why its confidence ceiling in scoring/dimensions.py is the lowest of the eight.
HUMOUR_MARKERS = frozenset({
    "lol", "haha", "hah", "heh", "hilarious", "funny", "joke", "joking",
    "kidding", "ironically", "somehow", "allegedly", "naturally",
    "delightful", "glorious", "gloriously", "magnificent", "spectacularly",
    "beautifully", "wonderfully", "absurd", "ridiculous", "ridiculously",
    "nonsense", "chaos", "disaster", "catastrophe", "spectacular",
    "heroically", "valiantly", "mercifully", "inevitably", "obviously",
})

HUMOUR_PUNCTUATION = (":)", ":-)", ";)", ":d", "/s")

# --- Technical terminology --------------------------------------------------
# Domain-agnostic technical vocabulary. Pattern-based detection in vocabulary.py
# catches the rest (camelCase, snake_case, file.ext, ALLCAPS acronyms).
TECHNICAL_TERMS = frozenset({
    "api", "apis", "cli", "sdk", "http", "https", "json", "yaml", "xml",
    "sql", "database", "databases", "query", "queries", "schema", "schemas",
    "server", "servers", "client", "clients", "endpoint", "endpoints",
    "deploy", "deployed", "deployment", "deployments", "container",
    "containers", "kubernetes", "docker", "cache", "caching", "cached",
    "latency", "throughput", "concurrency", "async", "thread", "threads",
    "memory", "cpu", "disk", "network", "config", "configuration", "runtime",
    "compile", "compiler", "binary", "repository", "repositories", "repo",
    "commit", "commits", "branch", "merge", "rebase", "pipeline", "pipelines",
    "regression", "refactor", "refactoring", "dependency", "dependencies",
    "package", "packages", "module", "modules", "function", "functions",
    "method", "methods", "interface", "interfaces", "protocol", "protocols",
    "token", "tokens", "auth", "authentication", "authorisation",
    "authorization", "encryption", "encrypted", "hash", "hashing", "index",
    "indexes", "shard", "sharding", "replica", "replication", "failover",
    "rollback", "rollout", "monitoring", "observability", "logging", "logs",
    "metrics", "tracing", "infrastructure", "provisioning", "terraform",
    "ansible", "linux", "kernel", "daemon", "socket", "sockets", "buffer",
    "queue", "queues", "heap", "pointer", "recursion", "algorithm",
    "algorithms", "throughput", "middleware", "webhook", "webhooks",
    "serialisation", "serialization", "idempotent", "deterministic",
    "concurrent", "asynchronous", "namespace", "syscall", "regex",
})

# --- Baseline common words --------------------------------------------------
# Used to tell "distinctive vocabulary" from ordinary English. Membership here
# means "unremarkable", not "bad". Kept short on purpose so it stays readable.
STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "did", "do", "does",
    "doing", "done", "down", "during", "each", "few", "for", "from",
    "further", "get", "got", "had", "has", "have", "having", "he", "her",
    "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "itself", "just", "like", "me", "more",
    "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on",
    "once", "one", "only", "or", "other", "our", "ours", "ourselves", "out",
    "over", "own", "put", "said", "same", "see", "she", "should", "so",
    "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "us", "very", "was",
    "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "yourselves", "make", "made", "go", "goes", "went", "take", "takes",
    "come", "comes", "way", "ways", "time", "times", "day", "days", "new",
    "old", "good", "bad", "big", "small", "long", "short", "back", "even",
    "still", "much", "many", "lot", "lots", "give", "gives", "want",
    "wants", "need", "needs", "know", "knows", "say", "says", "look",
    "looks", "use", "used", "uses", "work", "works", "working", "thing",
    "things", "people", "person", "first", "last", "next", "well", "never",
    "always", "often", "every", "another", "around", "away", "yet", "us",
    "m", "s", "t", "re", "ve", "ll", "d",
})

# --- Conjunctions and subordinators ----------------------------------------
COORDINATING_CONJUNCTIONS = frozenset({
    "and", "but", "or", "nor", "for", "yet", "so",
})

SUBORDINATORS = frozenset({
    "although", "though", "because", "since", "unless", "whereas", "while",
    "whilst", "if", "when", "whenever", "wherever", "after", "before",
    "until", "once", "provided", "assuming", "despite", "whether", "which",
    "whom", "whose",
})

# Conjunctions that commonly open a sentence in informal writing.
SENTENCE_INITIAL_CONJUNCTIONS = frozenset({
    "and", "but", "so", "or", "yet", "because", "plus", "also", "still",
    "though", "anyway", "right", "okay",
})

# --- Verb cues (for the fragment approximation) -----------------------------
# A sentence containing none of these and no verb-shaped suffix is *guessed* to
# be a fragment. See docs/metrics.md for why this undercounts.
FINITE_VERB_CUES = frozenset({
    "am", "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "can", "could", "will", "would", "shall",
    "should", "may", "might", "must", "get", "gets", "got", "go", "goes",
    "went", "make", "makes", "made", "take", "takes", "took", "come",
    "comes", "came", "see", "sees", "saw", "know", "knows", "knew", "think",
    "thinks", "thought", "want", "wants", "need", "needs", "use", "uses",
    "used", "say", "says", "said", "look", "looks", "keep", "keeps", "let",
    "put", "run", "runs", "ran", "give", "gives", "gave", "find", "finds",
    "found", "tell", "tells", "told", "work", "works", "worked", "seem",
    "seems", "feel", "feels", "felt", "mean", "means", "meant", "leave",
    "leaves", "left", "call", "calls", "called", "try", "tries", "tried",
    "ask", "asks", "asked", "turn", "turns", "start", "starts", "started",
    "help", "helps", "helped", "show", "shows", "showed", "move", "moves",
    "moved", "like", "likes", "liked", "live", "lives", "believe", "hold",
    "holds", "bring", "brings", "happen", "happens", "happened", "write",
    "writes", "wrote", "sit", "sits", "stand", "stands", "lose", "loses",
    "lost", "pay", "pays", "paid", "meet", "meets", "met", "set", "sets",
    "learn", "learns", "learned", "change", "changes", "changed", "lead",
    "leads", "led", "understand", "understands", "watch", "watches",
    "follow", "follows", "stop", "stops", "stopped", "create", "creates",
    "speak", "speaks", "read", "reads", "spend", "spends", "spent", "grow",
    "grows", "open", "opens", "opened", "walk", "walks", "win", "wins",
    "offer", "offers", "remember", "remembers", "consider", "considers",
    "appear", "appears", "buy", "buys", "wait", "waits", "serve", "serves",
    "send", "sends", "sent", "expect", "expects", "build", "builds",
    "built", "stay", "stays", "fall", "falls", "fell", "cut", "cuts",
    "reach", "reaches", "raise", "raises", "pass", "passes", "sell",
    "sells", "sold", "decide", "decides", "return", "returns", "explain",
    "explains", "hope", "hopes", "develop", "develops", "carry", "carries",
    "break", "breaks", "broke", "receive", "receives", "agree", "agrees",
    "support", "supports", "produce", "produces", "cover", "covers",
    "catch", "catches", "draw", "draws", "choose", "chooses", "chose",
    "fix", "fixes", "fixed", "add", "adds", "added", "check", "checks",
    "checked", "means", "matters", "depends", "involves", "requires",
})

# Imperative openers: a sentence starting with one of these reads as a direct
# instruction. Used by the directness dimension.
IMPERATIVE_OPENERS = frozenset({
    "use", "do", "don't", "try", "make", "take", "check", "look", "see",
    "read", "write", "run", "start", "stop", "keep", "let", "put", "get",
    "give", "send", "add", "remove", "fix", "avoid", "consider", "note",
    "remember", "ask", "tell", "call", "pick", "choose", "set", "open",
    "close", "go", "come", "leave", "skip", "ignore", "install", "build",
    "test", "ship", "merge", "review", "delete", "focus", "drop", "pull",
})

# --- Modal verbs ------------------------------------------------------------
STRONG_MODALS = frozenset({"must", "will", "shall", "need", "should"})
WEAK_MODALS = frozenset({"might", "may", "could", "would", "can"})
