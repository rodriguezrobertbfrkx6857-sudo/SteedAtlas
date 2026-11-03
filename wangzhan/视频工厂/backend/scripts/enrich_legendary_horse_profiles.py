"""Enrich legendary horse JSON profiles for the in-site RAG library.

The script keeps existing ids/images/prompts intact and expands the three
reader-facing fields:
  - story: about 50+ Chinese characters
  - horse_life_story: 100+ Chinese characters
  - owner_life_story: around 300-400 Chinese characters
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_FILES = (
    "legendary_horses_top5.json",
    "legendary_horses_batch1.json",
    "legendary_horses_batch2.json",
)


OWNER_LONG_NOTES = {
    "吕布 → 曹操 → 关羽": "赤兔的主人线横跨吕布、曹操与关羽三段。吕布以勇武著称，早年依附丁原、董卓，后据徐州，在群雄夹击中败于下邳；曹操则以政治和军事整合能力掌控北方，把名马纳入权力秩序；关羽随刘备起兵，经历流离、守义、镇荆州与麦城败亡，最终被后世塑造成忠义象征。",
    "吕布（前期）/ 关羽（后期）": "赤兔的主人线横跨吕布、曹操与关羽三段。吕布以勇武著称，早年依附丁原、董卓，后据徐州，在群雄夹击中败于下邳；曹操则以政治和军事整合能力掌控北方，把名马纳入权力秩序；关羽随刘备起兵，经历流离、守义、镇荆州与麦城败亡，最终被后世塑造成忠义象征。",
    "刘备": "刘备出身汉室宗亲旁支，早年以织席贩履的困顿形象进入叙事，随后在黄巾、徐州、荆州、益州等局势中辗转求存。他的人生不是一路强势推进，而是多次失地、多次依附、多次重起，最终在蜀地建立政权。刘备的魅力常来自逆境中的韧性、识人用人的能力，以及对名分与人心的经营。",
    "汉武帝（国家层面征集）": "汉武帝刘彻在位时间长，推动中央集权、对匈奴大规模用兵，并把西域纳入汉朝视野。张骞通西域后，大宛、乌孙等地的良马成为国家战略资源，天马叙事也由此进入帝国想象。汉武帝的人生线更像国家意志的展开：宫廷决策、远征成本、边疆经营和盛世野心彼此交织。",
    "曹操": "曹操是东汉末年的政治家、军事家与文学家，早年参与镇压黄巾，后迎奉汉献帝，以许都为政治中心，逐步统一北方。官渡之战击败袁绍，是其人生最关键的战略转折之一。曹操的形象兼具雄才、疑心、权谋与诗性，常被放在乱世判断力和高压执行力的叙事中理解。",
    "项羽": "项羽出身楚地贵族之后，少年时便显出强烈的英雄气和反秦意志。巨鹿之战中破釜沉舟，奠定其霸王声威；分封天下后与刘邦进入长期楚汉对抗。垓下之围、四面楚歌与乌江自刎构成他人生的终局：巅峰极高，坠落也极陡，最后留下的是失败中的尊严和悲壮。",
    "赵云（文学演绎）": "赵云在演义与评书系统中常被塑造成冷静、忠勇、身法极快的白马英雄。长坂坡救主、随刘备转战、后期仍能出阵，使他区别于纯粹猛将：他的核心是可靠、清亮、克制和临危不乱。围绕赵云的名马叙事，常把人物的干净气质、快速机动和守护精神放大。",
    "秦琼": "秦琼在隋唐演义中是义气型名将，常与双锏、黄骠马、瓦岗群雄和门神形象相连。他早年多在乱世奔走，经历投军、结义、转投与建功，人物底色不是张扬的神异，而是厚重、可靠、讲情义。黄骠马进入秦琼故事时，最适合承接这种风尘旧友般的陪伴感。",
    "尉迟恭": "尉迟恭是隋唐系统中的猛将代表，形象粗犷、力量感强，常与黑色、重甲、铁鞭和门神叙事相连。他在乱世中以武力进入权力核心，后成为唐初功臣。与他相关的名马不宜写得轻盈秀气，而应强调正面冲阵、沉重压迫、骤然爆发和把敌阵撕开的力量。",
    "罗成": "罗成是隋唐演义里的少年名将形象，常被写成白袍银枪、俊美冷峻、枪法高绝。他的人生线带有强烈的戏剧色彩：少年登场、锋芒耀眼、战功迅疾，却也常伴随短促而悲剧的命运收束。玉兰白龙驹进入这条线时，重点是清贵、速度和少年英雄的冷光感。",
    "关羽（民间演义）": "关羽在三国叙事中以忠义、勇武和悲剧收束著称。早年随刘备起事，辗转徐州、许都、荆州等地；“过五关斩六将”等民间情节强化了他的义气与威严；后期镇守荆州，败走麦城，最终成为后世武圣形象。与关羽相关的名马，往往承担忠义、行路与赴难的象征。",
    "黄忠（民间演义）": "黄忠是老将成名的典型人物，早年长期在荆州体系中活动，归刘备后以定军山一战确立名将地位。其形象的力量来自“年岁已高而锋芒不减”：沉稳、迟到的爆发、老练的判断共同构成他的人生主题。相关战马适合承接稳、准、厚的叙事节奏。",
    "张飞（民间演义）": "张飞在刘备集团中代表爆发力与强烈情绪：从桃园结义到长坂据桥，再到入蜀作战，其人生线充满压迫感、怒气和突进动作。演义里的张飞粗中有细，不只是莽撞猛将，也能以气势震慑敌阵。绑定张飞的战马，适合表现重踏、冲阵和骤然爆发。",
    "赵云（民间演义）": "赵云在演义体系中常被塑造成冷静、忠勇、身法极快的白马英雄。长坂坡救主、随刘备转战、后期仍能出阵，使他区别于纯粹猛将：他的核心是可靠、清亮、克制和临危不乱。围绕赵云的名马叙事，常把人物的干净气质、快速机动和守护精神放大。",
    "唐僧（《西游记》）": "唐僧是取经叙事的核心人物，身上承载的是信念、戒律、慈悲和漫长行路。他并非武将，却不断穿过妖怪、国度、诱惑与误解。白龙马由西海龙王三太子受罚化身而来，长期陪伴取经队伍西行；这组关系的重点不是战功，而是赎罪、陪伴、远行和修行。",
    "唐太宗李世民": "李世民早年参与唐朝建立，经历虎牢、洛阳等关键战争，玄武门之变后即位，开创贞观政治。他的人生有鲜明的创业帝王色彩：战场判断、权力决断、制度建设和历史自我塑造彼此交织。昭陵六骏把他的战马固定成历史记忆，每匹马都像一场战役的纪念碑。",
    "唐玄宗御马体系": "唐玄宗前期开元之治使唐代国力达到高峰，宫廷马政、绘画与贵族审美也高度繁荣；后期天宝乱局又把盛世推向转折。照夜白等御马意象应放在盛世光华和转折阴影之间理解：它们既代表繁华秩序，也让观众感到盛极而衰的历史余味。",
    "汉武帝时期天马体系": "汉武帝刘彻在位期间大规模经营边疆和西域，对匈奴用兵，也推动了通西域后的国家想象。天马叙事表现的是帝国为了速度、军力与远方而付出的远征成本。这里的人物不是单一骑手，而是皇帝、使者、将军和边地共同构成的国家行动。",
    "汉武帝时期西域贡马体系": "汉武帝时代的西域马不只属于个人，而属于国家战略：从张骞通西域到大宛、乌孙等地名进入汉廷视野，良马成为交通、军事和外交网络的一部分。对应人物应按帝国行动群像处理，重点是远方、开拓、代价与天马入汉的想象力。",
    "唐代边塞将领群像": "唐代边塞诗与边军叙事常把马写成将士命运的延伸：长途行军、风沙边塞、旌旗与归乡愿望交织。此类马的主人不是单一人物，而是远戍军士、边将、斥候和驿使共同构成的群像。他们的人生由军令、寒夜、功名和归途组成。",
    "周穆王": "周穆王是先秦传说中的远游君王，常与八骏、西巡、昆仑、会西王母等母题相连。他的故事并非普通战争传记，而是王权、远方、神话地理和古代想象力的结合。八骏进入这条线时，应像一组承载远游愿望的神骏，而不是单纯的速度排行。",
    "黄帝（神话体系）": "黄帝是上古神话与文明始祖叙事中的核心人物，常被放在迁徙、征伐、制度开端和族群记忆之中。相关神马象征天命与通达远方的能力。此类故事不宜写成具体朝代写实，而应保留神话史诗感，让马匹承接文明开端和英雄远行的意象。",
    "古代贤主群像": "骐骥一类名号更多是典籍中的良马象征，常被用来比喻贤才、明主识才和道路远大。它的主人应按贤主群像处理：有人能识马，也有人因不识而埋没良材。人物线的重点不是某一场战斗，而是识别、任用、等待和千里之志。",
    "古代礼制与车马体系": "先秦礼制里车马与身份、战争、祭祀和秩序密切相关。此类马的主人不是单一英雄，而是礼制社会中的贵族、将领、御者和车战系统。讲述时应把人物放在仪式、军阵、道路和等级秩序中，突出古代社会如何借车马表达权力与荣誉。",
    "古代骑军群像": "这类马更接近颜色与品类称谓，常服务于骑军、驿道和边地行动。它们的主人是古代骑手、将校、驿使和行旅者共同构成的群像。人物一生可以理解为在道路上完成使命：传令、探路、奔袭、护送或归乡，马匹承担耐力和方向感。",
    "古代神骏叙事群像": "神骏叙事常以速度、灵性和异相塑造超越普通马匹的存在，主人往往是帝王、方士、将帅或传说英雄的合成影像。这类人物线不宜落得太实，应突出“被时代需要的人”如何借神骏穿越险阻、完成使命，并把马留下为传奇符号。",
    "民间评书将帅群像": "评书与民间演义常把名马配给猛将、侠将或少主，用响亮名号先立人物气质，再通过冲阵、护主和夜奔强化记忆点。对应人物通常带有夸张而鲜明的性格：义气、少年锐气、猛勇或悲情。马匹则帮助观众在第一眼记住这个人物。",
    "三国演义将帅群像": "三国题材中的马经常绑定乱世选择：投奔、转战、守城、突围和败亡。若无固定主人，应按三国将帅群像处理，重点写忠义、谋略与战场转折。人物一生不必落在单个姓名上，而要呈现乱世中将领如何被局势推着前行。",
    "隋唐演义将帅群像": "隋唐演义的名马多服务于猛将擂台、瓦岗聚义、沙场冲阵和兄弟义气，人物线重在从草莽豪气走向王朝开端。对应主人可以是一类将帅：他们在乱世中凭武艺与义气立身，又在权力更替里承受命运转弯。",
    "边塞骑军群像": "边塞骑军的主人是远戍将士、驿使和斥候群像：他们的人生由风沙、军令、归途和战功组成。与他们相关的名马不靠神异取胜，而靠耐力、方向感和在恶劣环境中坚持。人物情绪应是克制的，带一点远行者的孤独。",
    "传奇侠客群像": "传奇侠客型主人常游走于江湖与战场之间，人生线强调快意、危局救援和身份转折。他们可能不是正史主角，却能用一次夜奔、一次护送、一次突围留下故事。马匹适合表现突然出现、快速离场和把人物带向下一段命运的作用。",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_text(item) for item in value if _text(item)]
    text = _text(value)
    return [text] if text else []


def _owner_note(profile: dict[str, Any]) -> str:
    owner = _text(profile.get("owner"))
    figure = _text(profile.get("figure"))
    name = _text(profile.get("name"))
    for key in (owner, figure):
        if key in OWNER_LONG_NOTES:
            return OWNER_LONG_NOTES[key]
    for key, note in OWNER_LONG_NOTES.items():
        if key and (key in owner or key in figure or owner in key or figure in key):
            return note
    if "关羽" in owner or "关羽" in figure:
        return OWNER_LONG_NOTES["关羽（民间演义）"]
    if "赵云" in owner or "赵云" in figure:
        return OWNER_LONG_NOTES["赵云（民间演义）"]
    if "唐太宗" in owner or "李世民" in owner:
        return OWNER_LONG_NOTES["唐太宗李世民"]
    if "周穆王" in owner:
        return OWNER_LONG_NOTES["周穆王"]
    if "三国" in owner:
        return OWNER_LONG_NOTES["三国演义将帅群像"]
    if "隋唐" in owner:
        return OWNER_LONG_NOTES["隋唐演义将帅群像"]
    if "边塞" in owner:
        return OWNER_LONG_NOTES["边塞骑军群像"]
    return (
        f"{name}对应的人物在现阶段资料中更接近群像或待考人物。可以把主人理解为处在"
        "乱世、远行、军阵或传说中的行动者：他未必拥有完整正史传记，却通过一次出场、"
        "一次突围、一次护主或一次远行留下记忆。这样的主人线适合保留弹性，让后续史料"
        "补强时继续细化。"
    )


def enrich_profile(profile: dict[str, Any]) -> dict[str, Any]:
    item = dict(profile)
    name = _text(item.get("name"))
    owner = _text(item.get("owner") or item.get("figure") or "相关人物")
    dynasty = _text(item.get("dynasty") or item.get("historical_source") or "传统叙事")
    source_type = _text(item.get("source_type") or "历史与传说资料")
    trait = _text(item.get("trait")) or (_list(item.get("traits")) or ["名马气质"])[0]
    traits = _list(item.get("traits") or item.get("labels")) or [trait, "速度", "守护", "命运感"]
    visual_keywords = _list(item.get("visual_keywords")) or ["古道", "烟尘", "旗影", "马蹄"]
    hook = _text(item.get("hook"))

    scene_a = visual_keywords[0]
    scene_b = visual_keywords[1] if len(visual_keywords) > 1 else "险路"
    scene_c = visual_keywords[2] if len(visual_keywords) > 2 else "旗影"
    trait_b = traits[1] if len(traits) > 1 else trait
    trait_c = traits[2] if len(traits) > 2 else "守护"
    conflict = _text(item.get("conflict")) or f"{owner}面对局势压迫时，需要速度、判断和一匹可靠的马。"
    hook_line = hook or f"{name}最适合讲一段人物命运与名马并肩的故事。"

    item["story"] = (
        f"{name}与{owner}相连，是{dynasty}叙事中辨识度很高的名马。"
        f"它的核心气质是{trait}与{trait_b}，既能服务战场行动，也能承接人物命运。"
        f"{hook_line}读它时，应同时看见马的速度、主人的处境，以及后世为什么记住这个名字。"
    )

    item["horse_life_story"] = (
        f"{name}的一生可以按“初见、试炼、留名”三段来读。初见时，它先用毛色、名号、姿态或传说感进入{source_type}，"
        f"让观众立刻知道这不是普通坐骑。试炼阶段，它常出现在{scene_a}、{scene_b}、{scene_c}之间，承担奔袭、突围、护主、远行或压阵的关键动作，"
        f"把{trait}、{trait_b}和{trait_c}变成可见的画面。留名阶段，它不再只是交通工具，而是{owner}人生转折的见证者："
        f"人们记住它，是因为它把一个人的选择、一个时代的压力和一段故事的余味都驮在了身上。"
    )

    base_owner_note = _owner_note(item)
    item["owner_life_story"] = (
        f"{base_owner_note}"
        f"{name}进入这条人物线后，作用不只是“载人前进”。它把{owner}的人生压缩成更容易观看的几个瞬间："
        f"初登场时立住身份，中段在危局中显出{trait}与{trait_b}，高潮处把人物的抉择推到眼前，"
        "结尾则留下荣光、败局或远行后的回声。"
        f"如果把{owner}的一生写成视频资料，应先说明他所处的时代压力，再写他为什么必须上路、出阵或做出选择；"
        f"接着让{name}出现在转折点，让观众看到马与人如何互相成全。"
        f"这段关系的重点不是炫耀马有多快，而是通过{scene_a}、{scene_b}等具体场景，把人物的胆识、犹疑、责任或悲剧变成可感的动作。"
        f"最后再回到后世记忆：{owner}之所以被讲述，是因为他的人生留下了可以反复观看的矛盾；"
        f"{name}之所以被记住，是因为它让这些矛盾有了形状。{conflict}"
    )

    item["rag_summary"] = (
        f"{name}｜{owner}｜{dynasty}｜核心气质：{trait}。"
        f"适合围绕{hook or '人物命运与名马关系'}展开。"
    )
    item.setdefault(
        "horse_timeline",
        [
            f"登场：{name}以{trait}气质进入{dynasty}叙事。",
            f"试炼：在{visual_keywords[0]}等场景中承担关键行动。",
            f"留名：成为{owner}人生线里的视觉符号。",
        ],
    )
    item.setdefault(
        "owner_timeline",
        [
            "人物进入时代局势",
            f"与{name}建立行动关系",
            "危局中作出关键选择",
            "故事以荣光、败局或远行余味收束",
        ],
    )
    item.setdefault("voiceover_seed", f"{name}记住的，是{owner}在命运转弯处的那一次选择。")
    return item


def enrich_file(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a list")
    enriched = [enrich_profile(item) for item in data if isinstance(item, dict)]
    path.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(enriched)


def main() -> None:
    server_dir = Path(__file__).resolve().parents[1]
    data_dir = server_dir / "data"
    total = 0
    for filename in DATA_FILES:
        path = data_dir / filename
        count = enrich_file(path)
        total += count
        print(f"[OK] enriched {count} -> {path}")
    print(f"[DONE] enriched total={total}")


if __name__ == "__main__":
    main()
