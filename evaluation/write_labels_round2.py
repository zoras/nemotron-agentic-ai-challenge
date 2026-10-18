"""Append labels for the chosen articles of the replanned match run. Same method as write_labels.py."""
import json, sys
m = json.load(open("artifacts/match/matches.json"))
results = {r["target_id"]: r for r in m["results"]}
full = {}
for tid in results:
    eid = tid.split("#")[0]
    full[eid.replace("page-", "")[:4] + ":" + eid.split(":")[1]] = eid
Y, P, N = "yes", "partial", "no"
J = [
 ("0104:e1", "Imperial units", P, "the page gives metric and British units"), ("0115:e1", "Textile bleaching", Y, ""),
 ("0220:e1", "Fur trade", Y, ""), ("0251:e4", "Sword", Y, ""), ("0251:e5", "Sworn Brothers", N, "the article is a 1987 film"),
 ("0251:e6", "Sycamore", P, "the article covers several trees; the entry refers to ACER"), ("0251:e6", "Acer pseudoplatanus", Y, ""),
 ("0251:e8", "Thomas Sydenham", Y, ""),
 ("0258:e1", "William of Wykeham", Y, "inferred: the page describes a keeper of the great seal under Edward III"),
 ("0258:e2", "William the Conqueror", P, "the entry names several kings called William"),
 ("0266:e1", "Scots family law", Y, ""), ("0493:e2", "Jinn", Y, ""), ("0493:e3", "Icknield Street", Y, ""),
 ("0523:e1", "Infinity", P, "the entry is the word endless"), ("0523:e11", "Collective enfranchisement", N, "modern leasehold law"),
 ("0523:e12", "Ventriloquism", P, "the entry is the ventriloquist priestesses"), ("0523:e13", "Generation", N, "the article is about age cohorts"),
 ("0523:e14", "History of engineering", N, "the entry is a machine in general"), ("0523:e15", "Engine", P, "the entry lists several engines"),
 ("0523:e16", "Jesse Ramsden", P, "the entry refers to Ramsden's dividing engine"), ("0523:e16", "Dividing engine", Y, ""),
 ("0523:e17", "Military engineering", Y, ""), ("0523:e18", "England", Y, ""), ("0523:e2", "Bar (heraldry)", N, "the endorse is a diminutive of the pale"),
 ("0523:e3", "Double rose", N, ""), ("0523:e8", "Energy", N, "the article is the physical quantity"), ("0523:e9", "Forlorn hope", Y, ""),
 ("0560:e10", "Amicus curiae", Y, ""), ("0560:e11", "Amida", N, "the article is a disambiguation page"), ("0560:e5", "Asbestos", Y, ""),
 ("0560:e9", "Palla (garment)", N, "the entry contrasts the amiculum with the palla"), ("0563:e3", "Abnormal growths of the nailbed", N, ""),
 ("0563:e3", "Wart", P, ""), ("0563:e4", "Action (philosophy)", P, "the entry is act as opposed to power"),
 ("0604:e1", "Bertel Thorvaldsen", Y, "inferred: a funeral attended by the queen and princesses, on the page before THOU"),
 ("0713:e5", "Ounce", N, "the article is the unit; the entry is the animal"), ("0713:e9", "Khanty", Y, ""),
 ("0914:e1", "Arabia Felix", P, "the page describes the Arabian deserts"), ("1017:e10", "Helmstedt", Y, ""), ("1017:e12", "Helsinki", Y, ""),
 ("1017:e14", "Staveless runes", Y, "Hälsinge runes are staveless runes"), ("1017:e15", "Helston (UK Parliament constituency)", P, ""),
 ("1017:e3", "Hellenization", N, "the entry is a Greek idiom"), ("1017:e8", "Petrified wood", N, ""), ("1017:e9", "Helmond", Y, ""),
 ("1032:e1", "Blood pressure", P, "the page is a table of Hales's blood-height measurements"),
 ("1102:e3", "Comitatus (warband)", N, "the entry is the county"), ("1102:e4", "Curiate assembly", P, ""),
 ("1214:e6", "Danaë", N, "the entry is the coin"), ("1214:e6", "Charon's obol", P, ""),
 ("1250:e1", "Coinage reform of Augustus", P, "the page compares Roman coin values"), ("1250:e2", "Coining (mint)", Y, ""),
 ("1268:e4", "Nayo", N, "the article is a village in Burma"), ("1268:e7", "Nazirite", P, "the entry starts with the Nazarene sense"),
 ("1284:e1", "Mary, Queen of Scots", P, "the page quotes Mary in the SCOTLAND history"),
 ("1327:e1", "Geyser", P, "the page describes a geyser eruption; the entry title is unclear"),
 ("1327:e7", "Hooghly River", N, "the entry is the town"), ("1344:e2", "Trestle support", Y, ""), ("1344:e4", "Jackstay", Y, ""),
 ("1430:e1", "Ancient Egypt", Y, ""), ("1466:e1", "Assay Office (Boise, Idaho)", N, ""), ("1473:e7", "Eschar", N, "the entry is a coralline"),
 ("1614:e10", "Toruń", Y, ""), ("1614:e3", "Order of the Thistle", Y, ""), ("1805:e13", "Handwriting exemplar", N, ""),
 ("1805:e14", "Mental image", P, ""), ("1805:e16", "Military exemption", N, ""), ("1805:e17", "1780 in science", N, ""),
 ("1805:e3", "Performance practice of Bach's music", N, ""), ("1805:e8", "Scots law", P, ""), ("1933:e1", "Public speaking", Y, ""),
 ("1945:e1", "Optics", Y, ""), ("2001:e2", "Silesian independence", N, ""), ("2001:e3", "Repast (funeral)", Y, ""),
 ("2087:e1", "Great Britain", Y, ""), ("2093:e1", "Sensation (fiction)", N, ""), ("2108:e1", "Kingdom of Great Britain", Y, ""),
 ("2131:e1", "History of Bombay under British rule (1661–1947)", Y, ""), ("2155:e1", "National Institute for Blind Youth", N, ""),
 ("2171:e12", "Grand vizier", P, "the entry is the Persian counterpart"), ("2171:e13", "Athamanta", Y, ""), ("2171:e14", "Athanasia", Y, ""),
 ("2171:e3", "Ataxia", P, "the entry is irregularity of fevers"), ("2171:e4", "Akçe", Y, ""), ("2171:e5", "Achievement (heraldry)", Y, ""),
 ("2171:e6", "Achievement (heraldry)", P, ""), ("2171:e7", "Ate (mythology)", Y, ""), ("2171:e8", "Caesar's civil war", N, ""),
 ("2250:e10", "Scots law", P, ""), ("2250:e12", "Byssus", N, "the article is the mollusc filaments; the entry is a plant genus"),
 ("2250:e16", "Bzou", Y, ""), ("2250:e8", "Bykhaw", Y, ""), ("2448:e1", "Commoner", N, "the page belongs to GENIUS"),
 ("2464:e11", "Ariaca", N, ""), ("2464:e3", "Vide e Cabeça", N, ""), ("2473:e2", "Cornelius Nepos", N, ""), ("2493:e1", "Chemistry", Y, ""),
 ("2569:e1", "Ethiopia", Y, ""), ("2570:e1", "Ethiopian Empire", Y, ""),
]
data = json.load(open("evaluation/match_labels.json"))
have = {(l["target_id"], l["page_id"]) for l in data["labels"]}
added, missing = 0, []
for short, title, value, note in J:
    tid = full[short] + "#topic"
    row = next((x for x in results[tid]["ranked"] if x["title"] == title), None)
    if row is None:
        missing.append((short, title)); continue
    if (tid, row["page_id"]) in have:
        continue
    data["labels"].append({"target_id": tid, "page_id": row["page_id"], "title": title, "label": value,
                           "correct": value != "no", "note": note})
    added += 1
data["labelled_from"] = ("artifacts/match/matches.json of the run with plan numbering fixed, then of the run with "
                         "text-only headword plans and key checks")
json.dump(data, open("evaluation/match_labels.json", "w"), ensure_ascii=False, indent=1)
print("added", added, "missing", missing, "total", len(data["labels"]))
