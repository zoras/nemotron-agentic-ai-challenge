"""Label the embedder's first choice where it differs from the reranker's. Same method as round 1."""
import json
m = json.load(open("artifacts/match/matches.json"))
results = {r["target_id"]: r for r in m["results"]}
full = {}
for tid in results:
    eid = tid.split("#")[0]
    full[eid.replace("page-", "")[:4] + ":" + eid.split(":")[1]] = eid
Y, P, N = "yes", "partial", "no"
J = [
 ("0013:e1#s", "Floor timber", N), ("0104:e1", "Metrication in the United Kingdom", N), ("0217:e1#s", "Cultural landscape", P),
 ("0220:e1#s", "King George (1785 ship)", N), ("0220:e1", "North American fur trade", P), ("0247:e1#s", "1669 eruption of Mount Etna", N),
 ("0251:e2", "Swivel gun", N), ("0251:e4", "Sword of state", N), ("0251:e5", "Sworn brotherhood (China)", P),
 ("0258:e1#s", "William de Epworth", N), ("0258:e2", "William", P), ("0266:e1", "Scots law", Y), ("0318:e1#s", "Blue Nile", N),
 ("0383:e1#s", "Ricardian socialism", N), ("0403:e1#s", "Prodromus Coptus", N), ("0473:e1#s", "Patella vulgata", P),
 ("0499:e1#s", "Agalasseis", N), ("0523:e1", "Endless tape cartridge", N), ("0523:e12", "Oracle", P), ("0523:e14", "Engine", P),
 ("0523:e15", "Steam engine", P), ("0523:e2", "Pale (heraldry)", P), ("0523:e3", "Attitude (heraldry)", P),
 ("0523:e7", "Exorcism in Christianity", P), ("0560:e1", "Corydalis nobilis", N), ("0563:e1", "Doxology", Y), ("0563:e3", "Poroma", N),
 ("0563:e4", "Actus purus", P), ("0604:e1", "Thorvaldsen Museum", P), ("0611:e1#s", "Taylor–Proudman theorem", N),
 ("0611:e1", "D'Alembert's paradox", P), ("0713:e8", "River Great Ouse", N), ("0851:e1#s", "Specular reflection", Y),
 ("1017:e10", "Helmstedt (district)", P), ("1017:e14", "Runes", P), ("1017:e2", "Helleborus viridis", P),
 ("1017:e4", "Jewish Koine Greek", Y), ("1017:e7", "Visor (armor)", P), ("1032:e1#s", "Blood pressure measurement", P),
 ("1032:e2", "Vital heat", P), ("1102:e1#s", "1508 in France", N), ("1102:e3", "County Court (England and Wales)", N),
 ("1214:e2", "Damsel in distress", N), ("1214:e3", "Aaiha", N), ("1250:e1", "Roman currency", Y), ("1268:e7", "Nazarene (title)", Y),
 ("1415:e1#s", "Acanthopale pubescens", N), ("1466:e1", "Assay", Y), ("1473:e7", "Flustra foliacea", P),
 ("1614:e1#s", "Myton-on-Swale", N), ("1614:e5", "Saint Thomas Christian denominations", P), ("1670:e2", "HMS Alarm (1758)", N),
 ("1680:e1#s", "Timber roof truss", P), ("1805:e14", "Creative visualization", N), ("1805:e16", "Religious exemption", N),
 ("1805:e3", "Portamento", N), ("1805:e8", "Jus relictae", P), ("1904:e1#s", "Chelys", P), ("1933:e1#s", "Epizeuxis", Y),
 ("1933:e1", "Rhetoric", P), ("1942:e1#s", "Anastasios Damvergis", N), ("1945:e1#s", "Optical mount", N),
 ("2001:e2", "Armenian bole", P), ("2001:e3", "Caristia", P), ("2001:e5", "Silicic", P), ("2093:e1#s", "William Lewis (chess player)", N),
 ("2155:e1", "Blind musicians", P), ("2171:e2", "Hermias of Atarneus", P), ("2171:e8", "Antequera", N),
 ("2250:e10", "History of Scots law", P), ("2250:e13", "Sea silk", P), ("2250:e3", "Bützow station", N),
 ("2250:e4", "St Ann's Well (Buxton)", P), ("2277:e1#s", "Brachial plexus", Y), ("2402:e1#s", "Tetragonias", N),
 ("2424:e1#s", "Animal feed", P), ("2446:e1#s", "Red phosphorus", P), ("2448:e1#s", "Conformity", P), ("2448:e1", "Conformity", P),
 ("2464:e1#s", "Temurah (Kabbalah)", P), ("2464:e11", "Gangga Negara", N), ("2464:e3", "Cabeça Gorda", N), ("2464:e5", "Ell", P),
 ("2464:e7", "Cabinet painting", N), ("2473:e2", "Epaminondas", N), ("2473:e4", "Abatement (heraldry)", N),
 ("2473:e5", "New Erection, Virginia", N), ("2569:e1#s", "Frumentius", Y),
]
data = json.load(open("evaluation/match_labels.json"))
have = {(l["target_id"], l["page_id"]) for l in data["labels"]}
added, missing = 0, []
for short, title, value in J:
    tid = full[short.replace("#s", "")] + ("#subtopic" if short.endswith("#s") else "#topic")
    row = next((x for x in results[tid]["ranked"] if x["title"] == title), None)
    if row is None:
        missing.append((short, title)); continue
    if (tid, row["page_id"]) not in have:
        data["labels"].append({"target_id": tid, "page_id": row["page_id"], "title": title, "label": value,
                               "correct": value != "no", "note": "embedder's first choice"})
        added += 1
json.dump(data, open("evaluation/match_labels.json", "w"), ensure_ascii=False, indent=1)
print("added", added, "missing", missing, "total", len(data["labels"]))
