"""Build all Sprint 5 NLP outputs: analysis_parsed, cross_validation, tag report, pros/cons (+ sentiment)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from src.nlp import parser, pros_cons, sentiment, tagger

ROOT = Path(__file__).resolve().parents[2]


def build_nlp(db_path: Path = ROOT / "data" / "nifty100.db", out_dir: Path = ROOT / "output") -> dict:
    """Write CSV outputs and the pros_cons_generated table; return summary stats."""
    out_dir.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        parsed, bad = parser.parse_analysis(pd.read_sql("SELECT * FROM analysis", conn))
        ratios = pd.read_sql("SELECT * FROM financial_ratios", conn)
        cv = parser.cross_validate(parsed, ratios)
        tags = tagger.validation_report(pd.read_sql("SELECT id, about_company FROM companies", conn), pd.read_sql("SELECT * FROM sectors", conn))
        feats = pros_cons.build_features(conn)
        sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn).set_index("company_id")["broad_sector"]
        pc = pros_cons.generate(feats, sectors)
        src = pd.read_sql("SELECT company_id FROM prosandcons", conn)["company_id"].unique()
        pc["has_source_entry"] = pc["company_id"].isin(src).astype(int)
        pc["sentiment"] = pc["text"].map(sentiment.score)
        pc.to_sql("pros_cons_generated", conn, if_exists="replace", index=False)
        raw = pd.read_sql("SELECT company_id, pros, cons FROM prosandcons", conn)
    # sentiment of the supplied pros/cons (does a general-purpose lexicon agree with the labels?)
    long = pd.concat([raw[["company_id", "pros"]].rename(columns={"pros": "text"}).assign(type="pro"),
                      raw[["company_id", "cons"]].rename(columns={"cons": "text"}).assign(type="con")]).dropna(subset=["text"])
    long["sentiment"] = long["text"].map(sentiment.score)
    long["agrees_with_label"] = ((long["type"] == "pro") == (long["sentiment"] > 0)).astype(int)
    parsed.to_csv(out_dir / "analysis_parsed.csv", index=False)
    bad.to_csv(out_dir / "parse_failures.csv", index=False)
    cv.to_csv(out_dir / "cross_validation.csv", index=False)
    tags.to_csv(out_dir / "tag_validation_report.csv", index=False)
    pc.to_csv(out_dir / "pros_cons_generated.csv", index=False)
    long.to_csv(out_dir / "sentiment_scores.csv", index=False)
    return {"parsed": len(parsed), "parse_failures": len(bad), "cv_diverge": int((cv["flag"] == "DIVERGES").sum()), "cv_rows": len(cv),
            "tag_accuracy": round(tags["match"].mean(), 3), "pros_cons_rows": len(pc), "sentiment_engine": sentiment.engine_name(),
            "sentiment_agreement": round(long["agrees_with_label"].mean(), 3)}


if __name__ == "__main__":
    print(build_nlp())
