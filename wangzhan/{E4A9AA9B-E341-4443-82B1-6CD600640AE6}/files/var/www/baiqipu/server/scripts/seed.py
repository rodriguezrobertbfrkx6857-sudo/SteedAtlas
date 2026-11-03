"""Seed the database with initial horse and product data."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, Base, engine
from app.models.horse import Horse
from app.models.product import Product

Base.metadata.create_all(bind=engine)

HORSES_DATA = [
    {
        "id": "chitu",
        "name": "赤兔",
        "title": "烈焰先锋",
        "rarity": "SSR",
        "image": "/images/chitu.png",
        "story": "赤兔象征极致忠义与冲锋意志，适合在关键时刻扛旗前行的人。",
        "full_story": "赤兔马，本名'赤菟'，最早记载于《三国志·吕布传》。先随吕布征战，后归关羽。关羽败走麦城后，赤兔绝食而亡，以死殉主。赤兔代表了中国文化中最高级别的忠诚与义气。",
        "historical_source": "《三国志·魏书·吕布传》",
        "dynasty": "汉末三国",
        "owner": "吕布 → 曹操 → 关羽",
        "trait": "忠诚守护",
        "traits": ["忠诚", "坚持", "义薄云天"],
        "drop_rate": 2,
        "price": 399,
    },
    {
        "id": "wuzhui",
        "name": "乌骓",
        "title": "孤勇之影",
        "rarity": "SSR",
        "image": "/images/wuzhui.png",
        "story": "乌骓在逆境中依然稳健，是面对压力仍选择前进的精神化身。",
        "full_story": "乌骓是西楚霸王项羽的坐骑。垓下之战，四面楚歌，项羽突围至乌江，亭长备船劝渡。项羽将乌骓赠予亭长，自刎而死。乌骓不肯渡江，投水而亡。此马代表了绝境中不屈的精神。",
        "historical_source": "《史记·项羽本纪》",
        "dynasty": "秦末楚汉",
        "owner": "项羽",
        "trait": "孤勇爆发",
        "traits": ["力量", "不屈", "悲壮"],
        "drop_rate": 2,
        "price": 399,
    },
    {
        "id": "dilu",
        "name": "的卢",
        "title": "绝境转机",
        "rarity": "SSR",
        "image": "/images/dilu.png",
        "story": "的卢寓意逢凶化吉，适合善于等待并把握时机的行动者。",
        "full_story": "的卢马，额上有白斑，民间传说'妨主'。刘备骑的卢马过檀溪，马跃三丈，化险为夷。此后的卢成为'绝境逢生'的象征。正所谓：马作的卢飞快，弓如霹雳弦惊。",
        "historical_source": "《三国志·蜀书·先主传》",
        "dynasty": "汉末三国",
        "owner": "刘备",
        "trait": "机遇突围",
        "traits": ["幸运", "转机", "韧性"],
        "drop_rate": 1,
        "price": 369,
    },
    {
        "id": "jueying",
        "name": "绝影",
        "title": "夜行迅锋",
        "rarity": "SR",
        "image": "/images/jueying.png",
        "story": "绝影象征速度与判断，代表高压环境下稳定推进的能力。",
        "full_story": "绝影是曹操的坐骑。宛城之战中，张绣叛乱，绝影身中数箭仍载曹操突围，最终力竭而亡。其名取'绝影'之意——奔跑时连影子都跟不上。",
        "historical_source": "《三国志·魏书·武帝纪》裴注",
        "dynasty": "汉末三国",
        "owner": "曹操",
        "trait": "冷静执行",
        "traits": ["速度", "判断", "冷静"],
        "drop_rate": 7,
        "price": 299,
    },
    {
        "id": "hanxue",
        "name": "汗血",
        "title": "远征之魂",
        "rarity": "SR",
        "image": "/images/hanxue.png",
        "story": "汗血宝马代表耐力和远志，适合长期主义者的坚定旅程。",
        "full_story": "汗血宝马原产大宛国（今中亚），汉武帝为得此马两次远征大宛。此马日行千里，奔跑时肩部渗出血色汗液。汗血马代表了丝绸之路的开拓精神和坚韧意志。",
        "historical_source": "《史记·大宛列传》",
        "dynasty": "西汉",
        "owner": "汉武帝",
        "trait": "坚韧长跑",
        "traits": ["耐力", "远志", "坚定"],
        "drop_rate": 8,
        "price": 329,
    },
    {
        "id": "zhuifeng",
        "name": "追风",
        "title": "疾行破阵",
        "rarity": "R",
        "image": "/images/chitu.png",
        "story": "追风马以速度闻名，象征行动力与果断。",
        "trait": "果断行动",
        "traits": ["速度", "果断"],
        "drop_rate": 20,
        "price": 199,
    },
    {
        "id": "taxue",
        "name": "踏雪",
        "title": "雪原孤旅",
        "rarity": "R",
        "image": "/images/hanxue.png",
        "story": "踏雪马四蹄如雪，象征纯洁与坚守本心。",
        "trait": "纯洁坚守",
        "traits": ["纯洁", "坚守"],
        "drop_rate": 30,
        "price": 179,
    },
    {
        "id": "feidian",
        "name": "飞电",
        "title": "雷霆一击",
        "rarity": "R",
        "image": "/images/jueying.png",
        "story": "飞电马名取闪电，象征瞬间爆发的勇气。",
        "trait": "瞬间爆发",
        "traits": ["爆发", "勇气"],
        "drop_rate": 30,
        "price": 179,
    },
]

PRODUCTS_DATA = [
    {
        "id": "p_chitu_001",
        "name": "百骑谱·赤兔 忠义限量礼盒",
        "horse_id": "chitu",
        "series": "忠义系列",
        "price": 499,
        "original_price": 599,
        "stock": 500,
        "limited_edition": True,
        "limited_count": 500,
        "images": ["/images/chitu.png"],
        "description": "赤兔忠义限量礼盒，含手办+典藏证书+故事卡+定制包装。",
        "specs": {"material": "树脂", "size": "15cm", "extras": "典藏证书 + 故事卡 + 限量编号"},
        "emotional_points": ["赤兔代表忠诚守护的精神力量", "历史传说中最具代表性的名马", "送给最重要的人"],
    },
    {
        "id": "p_wuzhui_001",
        "name": "百骑谱·乌骓 孤勇系列",
        "horse_id": "wuzhui",
        "series": "孤勇系列",
        "price": 399,
        "original_price": 499,
        "stock": 500,
        "limited_edition": True,
        "limited_count": 500,
        "images": ["/images/wuzhui.png"],
        "description": "乌骓孤勇系列手办，致敬不屈精神。",
        "specs": {"material": "树脂", "size": "15cm", "extras": "典藏证书 + 故事卡"},
        "emotional_points": ["乌骓代表力量与忠诚", "项羽四面楚歌时的陪伴者", "送给正在低谷期的自己/朋友"],
    },
    {
        "id": "p_dilu_001",
        "name": "百骑谱·的卢 转机系列",
        "horse_id": "dilu",
        "series": "转机系列",
        "price": 369,
        "original_price": 469,
        "stock": 500,
        "limited_edition": False,
        "images": ["/images/dilu.png"],
        "description": "的卢转机系列手办，寓意逢凶化吉。",
        "specs": {"material": "树脂", "size": "15cm", "extras": "典藏证书 + 故事卡"},
        "emotional_points": ["的卢寓意逢凶化吉", "刘备跃檀溪的传奇", "送给即将突破困局的人"],
    },
    {
        "id": "p_jueying_001",
        "name": "百骑谱·绝影 迅锋系列",
        "horse_id": "jueying",
        "series": "迅锋系列",
        "price": 299,
        "stock": 800,
        "limited_edition": False,
        "images": ["/images/jueying.png"],
        "description": "绝影迅锋系列手办，致敬速度与判断。",
        "specs": {"material": "树脂", "size": "12cm", "extras": "故事卡"},
        "emotional_points": ["绝影象征冷静与高效执行", "高压下稳定前进的力量"],
    },
    {
        "id": "p_hanxue_001",
        "name": "百骑谱·汗血 远征系列",
        "horse_id": "hanxue",
        "series": "远征系列",
        "price": 329,
        "stock": 800,
        "limited_edition": False,
        "images": ["/images/hanxue.png"],
        "description": "汗血远征系列手办，致敬坚韧与远志。",
        "specs": {"material": "树脂", "size": "12cm", "extras": "故事卡"},
        "emotional_points": ["汗血宝马代表长期主义", "丝绸之路开拓精神"],
    },
]


def seed():
    db = SessionLocal()
    try:
        # Seed horses
        for data in HORSES_DATA:
            existing = db.query(Horse).filter(Horse.id == data["id"]).first()
            if not existing:
                horse = Horse(**data)
                db.add(horse)
                print(f"  + Horse: {data['name']}")
            else:
                print(f"  = Horse exists: {data['name']}")

        # Seed products
        for data in PRODUCTS_DATA:
            existing = db.query(Product).filter(Product.id == data["id"]).first()
            if not existing:
                product = Product(**data)
                db.add(product)
                print(f"  + Product: {data['name']}")
            else:
                print(f"  = Product exists: {data['name']}")

        db.commit()
        print("\nSeed complete!")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding database...")
    seed()
