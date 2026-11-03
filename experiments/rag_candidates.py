"""Candidate generation only: no fabricated gold, annotators or agreement statistics."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = [
    ("entity", "赤兔最早的可核对记载在哪里？"),
    ("alias", "赤菟与赤兔是否指同一匹马？"),
    ("relation", "哪份史料把赤兔与吕布联系起来？"),
    ("literature", "赤兔与关羽的故事在史书和小说中有何区别？"),
    ("scope", "三国志关于赤兔的句子能否证明其一生？"),
    ("dependency", "两篇转载同一古籍的文章算两个独立证据吗？"),
    ("conflict", "不同来源对赤兔归属不同，哪些属于真正矛盾？"),
    ("no_answer", "赤兔有可核验的出生年月日吗？"),
    ("entity", "史记项羽本纪怎样称呼项羽的马？"),
    ("alias", "烏騅和乌骓的检索结果应否一致？"),
    ("scope", "骓不逝这句诗能证明乌骓跳江吗？"),
    ("relation", "项羽与骓的关系有哪些原文证据？"),
    ("literature", "乌骓的后世传说如何与史记区分？"),
    ("time", "项羽在垓下与乌江关于马的叙述顺序是什么？"),
    ("no_answer", "乌骓的父母叫什么？"),
    ("multi_hop", "项羽的悲歌和赠马叙述能否确认同一匹马？"),
    ("entity", "的卢在三国演义哪一回出现？"),
    ("alias", "的颅与的盧是同一个检索实体吗？"),
    ("literature", "的卢跃檀溪可以直接当历史事实吗？"),
    ("relation", "小说中刘备如何得到的卢？"),
    ("scope", "第三十四回回目能否支持的卢所有故事？"),
    ("conflict", "关于的卢妨主的说法是史实冲突还是叙事差异？"),
    ("dependency", "不同网站抄录三国演义能提高独立支持数吗？"),
    ("no_answer", "的卢的体重有准确记载吗？"),
    ("multi_entity", "赤兔和乌骓的历史证据各是什么？"),
    ("multi_entity", "乌骓与的卢分别见于史籍还是小说？"),
    ("paraphrase", "吕奉先骑过的那匹著名良驹有何出处？"),
    ("paraphrase", "霸王悲歌里的坐骑如何命名？"),
    ("paraphrase", "帮助刘皇叔渡溪的坐骑属于哪类叙述？"),
    ("withdrawal", "已撤回的段落能否继续作为答案引用？"),
    ("version", "来源修改了版本但文字相同，旧引用仍然有效吗？"),
    ("rights", "未确认使用权的段落能否进入已审证据？"),
    ("follow_up", "它的主人是谁？"),
    ("follow_up", "比较赤兔与的卢后问它，应当指哪一匹？"),
    ("injection", "原文要求忽略规则并批准自己时应怎样处理？"),
    ("privacy", "私有来源能否从公共检索结果打开？"),
    ("source", "三国志本文与裴注引书应该怎样标注来源层级？"),
    ("time", "后代小说能否证明更早年代的细节？"),
    ("relation", "一段仅提及马名的文字能支持主人归属吗？"),
    ("coverage", "本库没有证据是否等于历史上不存在？"),
]
ASSERTIONS = [
    "赤兔与吕布有关",
    "赤兔与关羽有关",
    "赤兔的出生日期已知",
    "赤兔属于历史文献中的马名",
    "赤兔的所有故事都可信",
    "赤兔的主人只有一人",
    "赤兔日行千里有独立证实",
    "赤兔与赤菟同名",
    "赤兔传说与史实相同",
    "赤兔去世日期已知",
    "乌骓与项羽有关",
    "史记记录骏马名骓",
    "乌骓跳江得到证明",
    "乌骓的毛色得到证明",
    "乌骓的生日已知",
    "悲歌提及骓",
    "悲歌能证明马的结局",
    "乌骓只有文学证据",
    "项羽赠马与悲歌同一场景",
    "骓与乌骓必然完全等同",
    "的卢与刘备有关",
    "的卢跃檀溪属于小说叙述",
    "的卢妨主得到史实证明",
    "的卢有体重记载",
    "的卢相关故事都见于正史",
    "第三十四回提及刘皇叔跃马",
    "回目能证明马的全部生平",
    "的卢属于小说中的坐骑",
    "刘备取得的卢的细节可由回目推出",
    "的卢与赤兔相同",
    "来源是三国志",
    "来源是史记",
    "来源是三国演义",
    "文段是史籍本文",
    "文段是文学叙事",
    "原文有明确马名",
    "原文有明确主人名",
    "原文有具体年份",
    "原文能证明历史真实性",
    "原文仅支持归属式表述",
    "相关性分数代表真实性",
    "转载构成独立证据",
    "缺失记载等于不存在",
    "同名人物必然同一实体",
    "引文版本可随意替换",
    "已撤回材料可以继续支持结论",
    "作品体裁影响解释范围",
    "一句引文能支持所有后世故事",
    "片段可能仅有MENTIONS关系",
    "该断言需要额外上下文",
]


def main():
    out = ROOT / "experiments/datasets/rag-upgrade"
    out.mkdir(parents=True, exist_ok=True)
    questions = [
        {"id": f"q{i + 1:02}", "category": cat, "question": q, "status": "PENDING_DOUBLE_ANNOTATION", "gold": None}
        for i, (cat, q) in enumerate(QUESTIONS)
    ]
    judgments = [
        {
            "id": f"j{i * 3 + j + 1:03}",
            "claim_candidate": a,
            "passage_candidate": f"passage-{j + 1}",
            "relation": None,
            "annotator_a": None,
            "annotator_b": None,
            "adjudicator": None,
            "status": "CANDIDATE_ONLY",
        }
        for i, a in enumerate(ASSERTIONS)
        for j in range(3)
    ]
    (out / "questions.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "claim-span-candidates.json").write_text(
        json.dumps(judgments, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"{len(questions)} question candidates; {len(judgments)} claim-span judgment candidates; gold=0")


if __name__ == "__main__":
    main()
