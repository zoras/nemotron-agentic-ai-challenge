"""Append labels for subtopic targets. Same method as write_labels_round1.py."""
import json
m = json.load(open("artifacts/match/matches.json"))
results = {r["target_id"]: r for r in m["results"]}
full = {}
for tid in results:
    eid = tid.split("#")[0]
    full[eid.replace("page-", "")[:4] + ":" + eid.split(":")[1]] = eid
Y, P, N = "yes", "partial", "no"
J = [
 ("0013:e1", "Longitudinal framing", P, "the page describes diagonal framing, a different system"),
 ("0217:e1", "Scenic America", N, ""), ("0220:e1", "Queen Charlotte Sound (Canada)", Y, ""), ("0247:e1", "Mount Etna", Y, ""),
 ("0251:e1", "Hypothetical partition of Switzerland", N, ""), ("0251:e1", "Switzerland", Y, ""), ("0258:e1", "William of Wykeham", Y, ""),
 ("0266:e1", "Prohibited degree of kinship", Y, ""), ("0268:e1", "Benzoin resin", N, "the resin comes from Styrax, not this Laurus"),
 ("0318:e1", "Nile", P, "the page is about the source of the White Nile"), ("0383:e1", "Wealth", N, "the page is about prices"),
 ("0403:e1", "Daniel and Verda", N, ""), ("0473:e1", "Patella skelettensis", N, ""),
 ("0499:e1", "Indian campaign of Alexander the Great", Y, ""), ("0611:e1", "Potential flow", Y, ""),
 ("0681:e1", "Image formation", P, ""), ("0681:e1", "Plane mirror", Y, ""), ("0756:e1", "Remanence", Y, ""),
 ("0851:e1", "Reflection (physics)", Y, ""), ("0944:e1", "Ell", P, ""), ("1032:e1", "Blood pressure", P, ""),
 ("1102:e1", "Étienne de Poncher", N, ""), ("1250:e1", "Quincunx (Roman coin)", N, ""),
 ("1284:e1", "Mary Stuart Proclaiming Her Innocence", N, "the article is a painting"), ("1284:e1", "Mary, Queen of Scots", Y, ""),
 ("1324:e1", "Hedge", P, "the page describes stone fences and ditches"), ("1327:e1", "Geysir", P, "inferred from the description"),
 ("1344:e1", "Hydrocephalus", Y, ""), ("1415:e1", "Inga Hedberg", N, ""), ("1430:e1", "History of ancient Egypt", P, ""),
 ("1430:e1", "Hyksos", Y, "Salatis was a Hyksos king"), ("1614:e1", "Topcliffe, North Yorkshire", N, "the page is Richmond"),
 ("1670:e1", "Cappadocia (Roman province)", Y, ""), ("1678:e1", "Bilfinger", N, ""),
 ("1678:e1", "Georg Bernhard Bilfinger", Y, "inferred: an engineer in correspondence during the war in Serbia"),
 ("1680:e1", "Tie (engineering)", Y, ""), ("1722:e1", "Arsenic", Y, ""), ("1805:e1", "Right of asylum", Y, ""), ("1904:e1", "Lyre", Y, ""),
 ("1910:e1", "Lightning", P, "the page is about the return stroke"), ("1933:e1", "Repetition (rhetorical device)", Y, ""),
 ("1939:e1", "Cannabis flower essential oil", N, ""), ("1939:e1", "Essential oil", Y, ""), ("1942:e1", "Hugh Linstead", N, ""),
 ("1945:e1", "Optical instrument", Y, ""), ("2051:e1", "Helmichis", Y, ""), ("2093:e1", "Chess", N, "the page uses a chess player as an example"),
 ("2108:e1", "Battle of Fort Niagara", P, ""), ("2108:e1", "Great Britain in the Seven Years' War", Y, ""),
 ("2131:e1", "Climate of Kolkata", N, ""), ("2155:e1", "Louis Braille", N, ""), ("2250:e1", "Hudson Bay", P, "Button's Bay is part of Hudson Bay"),
 ("2277:e1", "Cervical plexus", Y, ""), ("2296:e1", "Vasili Pronchishchev", N, ""), ("2307:e1", "Algiers expedition (1541)", Y, ""),
 ("2402:e1", "Sacrum", Y, ""), ("2424:e1", "Cattle feeding", Y, ""), ("2446:e1", "Phosphorus", Y, ""),
 ("2448:e1", "Iconoclast: A Neuroscientist Reveals How to Think Differently", N, ""), ("2464:e1", "Notarikon", P, "one of the three kinds"),
 ("2493:e1", "Magnesium sulfite", Y, ""), ("2524:e1", "Architecture of India", N, "the page is about crimes and punishments"),
 ("2569:e1", "Kingdom of Aksum", Y, ""),
]
data = json.load(open("evaluation/match_labels.json"))
have = {(l["target_id"], l["page_id"]) for l in data["labels"]}
added, missing = 0, []
for short, title, value, note in J:
    tid = full[short] + "#subtopic"
    row = next((x for x in results[tid]["ranked"] if x["title"] == title), None)
    if row is None:
        missing.append((short, title)); continue
    if (tid, row["page_id"]) not in have:
        data["labels"].append({"target_id": tid, "page_id": row["page_id"], "title": title, "label": value,
                               "correct": value != "no", "note": note})
        added += 1
json.dump(data, open("evaluation/match_labels.json", "w"), ensure_ascii=False, indent=1)
print("added", added, "missing", missing, "total", len(data["labels"]))
