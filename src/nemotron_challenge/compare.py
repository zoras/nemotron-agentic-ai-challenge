"""Compare matched Britannica entries with their Wikipedia articles.

Text unit: each accepted match pairs one Britannica entry with one Wikipedia article.
Normalisation: markup removal, line-end hyphen joins, lower case, long-s folding ("fuch" -> "such" when
the s-form is a far more common English word), and a small table of historical spellings. Every change is
counted, so the record shows what was altered.
Analyses: vocabulary overlap per pair against a baseline of unrelated articles, distinctive words per
source (log-odds with an informative Dirichlet prior), and a joint topic model over Nemotron embeddings
(UMAP, HDBSCAN, c-TF-IDF) for the entries and the distinct matched articles.
"""
from __future__ import annotations

from collections import Counter
import functools
import json
import math
from pathlib import Path
import random
import re
from typing import Any

from .match import plain

FOLD_MIN_ZIPF = 3.0       # the s-form must be at least this common (wordfreq Zipf scale)
FOLD_MIN_GAIN = 2.0       # and this much more common than the word as printed
UNKNOWN_ZIPF = 0.0        # words that wordfreq does not know: OCR errors, rare names, or obsolete words
MIN_CORPUS_COUNT = 5      # distinctive-word analysis ignores rarer words
PRIOR_STRENGTH = 500.0    # total weight of the informative Dirichlet prior
BASELINE_ARTICLES = 5     # unrelated articles that set the chance level of vocabulary overlap
CHUNK_CHARS = 4000        # long texts are embedded in chunks and averaged by chunk length
HISTORICAL = {"shew": "show", "shewn": "shown", "shewed": "showed", "shews": "shows", "compleat": "complete",
              "antient": "ancient", "antiently": "anciently", "chuse": "choose", "connexion": "connection",
              "connexions": "connections", "phrenzy": "frenzy", "gaol": "jail", "despatch": "dispatch",
              "inclose": "enclose", "inclosed": "enclosed", "intire": "entire", "intirely": "entirely",
              "surprize": "surprise", "cloathed": "clothed", "cloaths": "clothes", "musick": "music",
              "publick": "public", "physick": "physic", "logick": "logic", "rhetorick": "rhetoric"}
# Long-s misreads that are also English words. They change only in these contexts, which were checked
# against the sample: "the fame" is followed by time, word, manner, as; "laid" by to or that.
CONTEXT_FOLDS = {("the", "fame"): "same", ("the", "fun"): "sun"}
SAID_BEFORE = {"to", "that"}
WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


@functools.lru_cache(maxsize=None)
def zipf(word: str) -> float:
    from wordfreq import zipf_frequency

    return zipf_frequency(word, "en")


@functools.lru_cache(maxsize=None)
def fold_long_s(word: str) -> str:
    """Read f as the long s when the s-form is a much more common English word. A final f stays f."""
    spots = [index for index, char in enumerate(word[:-1]) if char == "f"]
    if not spots or len(spots) > 4:
        return word
    base, best, best_score = zipf(word), word, zipf(word)
    for mask in range(1, 2 ** len(spots)):
        letters = list(word)
        for bit, index in enumerate(spots):
            if mask >> bit & 1:
                letters[index] = "s"
        candidate = "".join(letters)
        score = zipf(HISTORICAL.get(candidate, candidate))  # "fhew" -> "shew", an old form of "show"
        if score > best_score:
            best, best_score = candidate, score
    return best if best != word and best_score >= FOLD_MIN_ZIPF and best_score - base >= FOLD_MIN_GAIN else word


def normalise(text: str, historical: bool = True) -> tuple[list[str], Counter]:
    """Return lower-case word tokens and a count of (printed, normalised, rule) changes.

    historical=True marks early printed text: it also gets the old-spelling table and the context rules
    for long-s misreads that are English words."""
    tokens, changes = [], Counter()
    for word in WORD.findall(plain(text).lower()):
        folded = fold_long_s(word)
        if folded != word:
            changes[(word, folded, "long_s")] += 1
        if historical and folded in HISTORICAL:
            changes[(folded, HISTORICAL[folded], "historical_spelling")] += 1
            folded = HISTORICAL[folded]
        tokens.append(folded)
    if historical:
        for index, token in enumerate(tokens):
            previous = tokens[index - 1] if index else ""
            following = tokens[index + 1] if index + 1 < len(tokens) else ""
            replacement = CONTEXT_FOLDS.get((previous, token)) or ("said" if token == "laid" and following in SAID_BEFORE else None)
            if replacement:
                changes[(token, replacement, "long_s_context")] += 1
                tokens[index] = replacement
    return tokens, changes


def readable(text: str) -> str:
    """Return the source text with long s folded word by word, keeping case and punctuation."""
    def fold(match: re.Match) -> str:
        word = match.group(0)
        folded = fold_long_s(word.lower())
        if folded == word.lower():
            return word
        return folded.upper() if word.isupper() else folded[0].upper() + folded[1:] if word[0].isupper() else folded
    return WORD.sub(fold, plain(text))


def stopwords() -> frozenset[str]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

    return ENGLISH_STOP_WORDS


def content(tokens: list[str]) -> list[str]:
    stop = stopwords()
    return [token for token in tokens if len(token) > 2 and token not in stop]


def unknown_rate(tokens: list[str]) -> float:
    words = [token for token in tokens if len(token) > 2]
    return sum(1 for token in words if zipf(token) <= UNKNOWN_ZIPF) / len(words) if words else 0.0


def overlap(entry: list[str], article: list[str]) -> float:
    """Share of the entry's content-word types that the article also uses."""
    left = set(content(entry))
    return len(left & set(content(article))) / len(left) if left else 0.0


def pair_stats(entry: list[str], article: list[str], baselines: list[list[str]]) -> dict[str, Any]:
    """Vocabulary overlap for one pair. The baseline is the mean overlap with unrelated articles."""
    left, right = Counter(content(entry)), Counter(content(article))
    shared = set(left) & set(right)
    coverage = overlap(entry, article)
    baseline = sum(overlap(entry, other) for other in baselines) / len(baselines) if baselines else None
    return {
        "entry_tokens": len(entry), "article_tokens": len(article),
        "entry_types": len(left), "article_types": len(right), "shared_types": len(shared),
        "entry_coverage": round(coverage, 4),
        "baseline_coverage": round(baseline, 4) if baseline is not None else None,
        "lift": round(coverage / baseline, 3) if baseline else None,
        "shared_words": [word for word, _ in sorted(((w, min(left[w], right[w])) for w in shared),
                                                     key=lambda item: (-item[1], item[0]))[:15]],
        "entry_only_words": [word for word, _ in left.most_common() if word not in right and zipf(word) > 0][:15],
        "entry_unknown_rate": round(unknown_rate(entry), 4),
    }


def distinctive_words(left: Counter, right: Counter, top: int = 25) -> dict[str, list[dict[str, Any]]]:
    """Log-odds ratio with an informative Dirichlet prior (Monroe, Colaresi and Quinn 2008).

    Positive z-scores mark words that the left corpus uses more often than the right.
    """
    vocabulary = [word for word in set(left) | set(right) if left[word] + right[word] >= MIN_CORPUS_COUNT]
    total = sum(left[word] + right[word] for word in vocabulary)
    left_total, right_total = sum(left[word] for word in vocabulary), sum(right[word] for word in vocabulary)
    rows = []
    for word in vocabulary:
        prior = PRIOR_STRENGTH * (left[word] + right[word]) / total
        a, b = left[word] + prior, right[word] + prior
        delta = math.log(a / (left_total + PRIOR_STRENGTH - a)) - math.log(b / (right_total + PRIOR_STRENGTH - b))
        rows.append({"word": word, "z": round(delta / math.sqrt(1 / a + 1 / b), 3),
                     "left_count": left[word], "right_count": right[word]})
    rows.sort(key=lambda row: row["z"])
    return {"left": rows[::-1][:top], "right": rows[:top]}


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Split text at paragraph or sentence ends into pieces of at most `size` characters."""
    pieces, current = [], ""
    for part in re.split(r"(?<=[.!?])\s+|\n{2,}", text):
        if current and len(current) + len(part) + 1 > size:
            pieces.append(current)
            current = ""
        current = f"{current} {part}".strip() if current else part[:size]
    return pieces + ([current] if current else [])


def document_vector(vectors: Any, retrieval: Any, text: str) -> list[float]:
    """Embed a long text in chunks and return the length-weighted, normalised mean vector."""
    parts = chunks(text) or [text[:CHUNK_CHARS]]
    embedded = vectors.embed(retrieval, parts, "document")
    weights = [len(part) for part in parts]
    mean = [sum(weight * vector[i] for weight, vector in zip(weights, embedded)) for i in range(len(embedded[0]))]
    norm = math.sqrt(sum(value * value for value in mean)) or 1.0
    return [value / norm for value in mean]


def c_tf_idf(texts_by_topic: dict[int, str], top: int = 8) -> dict[int, list[str]]:
    """Class-based TF-IDF over one concatenated document per topic, as in BERTopic."""
    import numpy as np
    from sklearn.feature_extraction.text import CountVectorizer

    topics = sorted(texts_by_topic)
    vectorizer = CountVectorizer(stop_words="english", max_features=20000, ngram_range=(1, 2), token_pattern=r"(?u)\b[a-z]{3,}\b")
    counts = vectorizer.fit_transform([texts_by_topic[topic] for topic in topics]).toarray()
    words = vectorizer.get_feature_names_out()
    idf = np.log(1 + (counts.sum() / len(topics)) / np.maximum(counts.sum(axis=0), 1))
    return {topic: [str(words[index]) for index in np.argsort(-(row / max(row.sum(), 1)) * idf)[:top]]
            for row, topic in zip(counts, topics)}


def topic_model(documents: list[dict[str, Any]], seed: int = 42) -> dict[str, Any]:
    """UMAP to 5 dimensions, HDBSCAN clusters, c-TF-IDF labels, and a 2-D UMAP for the plot."""
    import numpy as np
    from sklearn.cluster import HDBSCAN
    import umap

    matrix = np.array([document["vector"] for document in documents], dtype="float32")
    reduced = umap.UMAP(n_neighbors=15, n_components=5, metric="cosine", random_state=seed).fit_transform(matrix)
    flat = umap.UMAP(n_neighbors=15, n_components=2, metric="cosine", random_state=seed).fit_transform(matrix)
    labels = HDBSCAN(min_cluster_size=5).fit_predict(reduced)
    texts: dict[int, list[str]] = {}
    for document, label in zip(documents, labels):
        texts.setdefault(int(label), []).append(document["text"])
    terms = c_tf_idf({topic: " ".join(parts) for topic, parts in texts.items() if topic >= 0})
    rows = []
    for topic in sorted(texts):
        members = [d for d, label in zip(documents, labels) if label == topic]
        sources = Counter(member["source"] for member in members)
        rows.append({"topic": topic, "label": "outliers: HDBSCAN put these in no cluster" if topic < 0 else None,
                     "terms": terms.get(topic, []), "size": len(members),
                     "britannica": sources["britannica"], "wikipedia": sources["wikipedia"],
                     "examples": [member["title"] for member in members[:6]]})
    return {"seed": seed, "umap": {"n_neighbors": 15, "n_components": 5, "metric": "cosine"},
            "hdbscan": {"min_cluster_size": 5}, "topics": rows,
            "documents": [{"doc_id": d["doc_id"], "source": d["source"], "title": d["title"], "topic": int(label),
                           "x": round(float(x), 4), "y": round(float(y), 4)}
                          for d, label, (x, y) in zip(documents, labels, flat)]}


def load_pairs(work_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Return accepted matches with their entry and article, plus all entries and articles by ID."""
    entries = {entry["entry_id"]: entry for entry in
               json.loads((work_dir / "extract" / "entries.json").read_text(encoding="utf-8"))["entries"]}
    matches = json.loads((work_dir / "match" / "matches.json").read_text(encoding="utf-8"))
    articles = {path.stem: json.loads(path.read_text(encoding="utf-8"))
                for path in sorted((work_dir / "match" / "articles").glob("*.json"))}
    pairs = [{"target_id": result["target_id"], "target": result["target"], "entry_id": result["entry_id"],
              "page_id": result["page_id"], "title": result["title"], "label": result["label"]}
             for result in matches["results"] if result["decision"] == "accepted" and result["page_id"] in articles]
    return pairs, entries, articles


def plot_distinctive(words: dict[str, list[dict[str, Any]]], path: Path, top: int = 20) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    left, right = words["left"][:top], words["right"][:top]
    fig, axes = plt.subplots(1, 2, figsize=(11, 7))
    for axis, rows, colour, title in ((axes[0], left, "#8a5a2b", "Britannica uses more"),
                                      (axes[1], right, "#2b5a8a", "Wikipedia uses more")):
        axis.barh([row["word"] for row in rows][::-1], [abs(row["z"]) for row in rows][::-1], color=colour)
        axis.set_title(title)
        axis.set_xlabel("|z| (log-odds, informative Dirichlet prior)")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_overlap(rows: list[dict[str, Any]], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(7, 5))
    axis.scatter([row["baseline_coverage"] for row in rows], [row["entry_coverage"] for row in rows], s=14, alpha=0.7)
    axis.plot([0, 1], [0, 1], color="grey", linewidth=1)
    axis.set_xlabel("Entry vocabulary found in unrelated articles (baseline)")
    axis.set_ylabel("Entry vocabulary found in the matched article")
    axis.set_title(f"Vocabulary overlap, {len(rows)} matched pairs")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_topics(model: dict[str, Any], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axis = plt.subplots(figsize=(9, 7))
    for source, marker, colour in (("britannica", "o", "#8a5a2b"), ("wikipedia", "^", "#2b5a8a")):
        docs = [d for d in model["documents"] if d["source"] == source]
        axis.scatter([d["x"] for d in docs], [d["y"] for d in docs], marker=marker, s=16, alpha=0.6, c=colour, label=source)
    for topic in model["topics"]:
        if topic["topic"] < 0:
            continue
        docs = [d for d in model["documents"] if d["topic"] == topic["topic"]]
        x, y = sum(d["x"] for d in docs) / len(docs), sum(d["y"] for d in docs) / len(docs)
        axis.annotate(f"{topic['topic']}: {', '.join(topic['terms'][:3])}", (x, y), fontsize=7)
    axis.legend()
    axis.set_title("Joint topic space: Britannica entries and matched Wikipedia articles")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def run_compare(work_dir: Path, *, vectors: Any = None, retrieval: Any = None, seed: int = 42) -> dict[str, Any]:
    """Write artifacts/compare. The topic model runs only when an embedding client is given."""
    work_dir = Path(work_dir)
    out_dir = work_dir / "compare"
    (out_dir / "figures").mkdir(parents=True, exist_ok=True)
    pairs, entries, articles = load_pairs(work_dir)
    entry_tokens, changes = {}, Counter()
    for entry_id in sorted({pair["entry_id"] for pair in pairs}):
        entry_tokens[entry_id], found = normalise(entries[entry_id]["text"])
        changes.update(found)
    article_tokens = {page_id: normalise(articles[page_id]["text"], historical=False)[0]
                      for page_id in sorted({pair["page_id"] for pair in pairs})}
    rng = random.Random(seed)
    rows = []
    for pair in pairs:
        others = [page_id for page_id in article_tokens if page_id != pair["page_id"]]
        baselines = [article_tokens[page_id] for page_id in rng.sample(others, min(BASELINE_ARTICLES, len(others)))]
        rows.append({**pair, **pair_stats(entry_tokens[pair["entry_id"]], article_tokens[pair["page_id"]], baselines)})

    britannica, wikipedia = Counter(), Counter()
    for corpus, texts in ((britannica, entry_tokens), (wikipedia, article_tokens)):
        for tokens in texts.values():
            corpus.update(token for token in tokens if zipf(token) > UNKNOWN_ZIPF)
    stop = stopwords()
    words_all = distinctive_words(britannica, wikipedia)
    words_content = distinctive_words(Counter({w: c for w, c in britannica.items() if w not in stop and len(w) > 2}),
                                      Counter({w: c for w, c in wikipedia.items() if w not in stop and len(w) > 2}))
    plot_distinctive(words_content, out_dir / "figures" / "distinctive-words.png")
    plot_overlap([row for row in rows if row["baseline_coverage"] is not None], out_dir / "figures" / "vocabulary-overlap.png")

    lifts = sorted(row["lift"] for row in rows if row["lift"])
    unknown = sum(len([t for t in tokens if len(t) > 2 and zipf(t) <= UNKNOWN_ZIPF]) for tokens in entry_tokens.values())
    result: dict[str, Any] = {
        "stage": "compare",
        "method": {"unit": "accepted match: one Britannica entry and one Wikipedia article",
                   "normalisation": ["markup removed", "line-end hyphens joined", "lower case",
                                     f"long s folded when the s-form has Zipf >= {FOLD_MIN_ZIPF} and gains >= {FOLD_MIN_GAIN}",
                                     "historical spellings mapped by a fixed table"],
                   "exclusions": [f"words unknown to wordfreq are left out of corpus word counts",
                                  f"words with fewer than {MIN_CORPUS_COUNT} uses are left out of the distinctive-word test"],
                   "document_lengths": "pair overlap is the share of the entry's vocabulary found in the article, "
                                       f"compared with {BASELINE_ARTICLES} unrelated matched articles",
                   "distinctive_words": "log-odds ratio, informative Dirichlet prior (Monroe et al. 2008)",
                   "seed": seed},
        "counts": {"pairs": len(rows), "entries": len(entry_tokens), "articles": len(article_tokens),
                   "britannica_tokens": sum(len(t) for t in entry_tokens.values()),
                   "wikipedia_tokens": sum(len(t) for t in article_tokens.values()),
                   "britannica_unknown_tokens": unknown,
                   "long_s_changes": sum(c for (_, _, rule), c in changes.items() if rule == "long_s"),
                   "historical_spelling_changes": sum(c for (_, _, rule), c in changes.items() if rule == "historical_spelling"),
                   "long_s_context_changes": sum(c for (_, _, rule), c in changes.items() if rule == "long_s_context"),
                   "median_lift": lifts[len(lifts) // 2] if lifts else None},
        "text_changes": [{"printed": a, "normalised": b, "rule": rule, "count": count}
                         for (a, b, rule), count in changes.most_common(200)],
        "distinctive_words": {"all_words": words_all, "content_words": words_content},
        "pairs": rows,
    }
    if vectors is not None and retrieval is not None:
        documents = [{"doc_id": entry_id, "source": "britannica", "title": entries[entry_id]["title"] or entry_id,
                      "text": " ".join(tokens), "vector": document_vector(vectors, retrieval, plain(entries[entry_id]["text"]))}
                     for entry_id, tokens in entry_tokens.items()]
        documents += [{"doc_id": page_id, "source": "wikipedia", "title": articles[page_id]["title"],
                       "text": " ".join(tokens), "vector": document_vector(vectors, retrieval, articles[page_id]["text"])}
                      for page_id, tokens in article_tokens.items()]
        model = topic_model(documents, seed)
        topic_of = {d["doc_id"]: d["topic"] for d in model["documents"]}
        for row in rows:
            row["entry_topic"], row["article_topic"] = topic_of[row["entry_id"]], topic_of[row["page_id"]]
        agree = [row for row in rows if row["entry_topic"] >= 0 and row["article_topic"] >= 0]
        model["pair_topic_agreement"] = round(sum(r["entry_topic"] == r["article_topic"] for r in agree) / len(agree), 3) if agree else None
        result["topics"] = model
        plot_topics(model, out_dir / "figures" / "topics.png")
    (out_dir / "comparison.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    return result["counts"]
