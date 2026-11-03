from __future__ import annotations

from typing import Any

from app.models.horse import Horse
from app.models.product import Product

EXCHANGE_RATES = {
    "CNY": 1.0,
    "USD": 0.14,
    "EUR": 0.13,
    "JPY": 21.5,
    "GBP": 0.11,
    "KRW": 186.0,
    "THB": 4.9,
    "MYR": 0.64,
}

ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW"}

LOCALE_PRESETS: dict[str, dict[str, Any]] = {
    "zh-CN": {
        "locale_name": "简体中文",
        "market": "中国大陆",
        "currency": "CNY",
        "brand": "百骑谱",
        "generic_tags": ["国风收藏", "历史名马", "文化礼赠"],
    },
    "en": {
        "locale_name": "English",
        "market": "Global English",
        "currency": "USD",
        "brand": "Baiqipu",
        "generic_tags": ["Chinese culture", "collectible horse", "giftable decor"],
    },
    "ja": {
        "locale_name": "日本語",
        "market": "日本",
        "currency": "JPY",
        "brand": "百騎譜",
        "generic_tags": ["中国文化", "コレクション", "ギフト向け"],
    },
    "ko": {
        "locale_name": "한국어",
        "market": "대한민국",
        "currency": "KRW",
        "brand": "백기보",
        "generic_tags": ["중국 문화", "컬렉터블", "선물 추천"],
    },
    "es": {
        "locale_name": "Español",
        "market": "Mercado hispanohablante",
        "currency": "USD",
        "brand": "Baiqipu",
        "generic_tags": ["cultura china", "coleccionable", "decoracion de regalo"],
    },
    "th": {
        "locale_name": "ไทย",
        "market": "ประเทศไทย",
        "currency": "THB",
        "brand": "Baiqipu",
        "generic_tags": ["วัฒนธรรมจีน", "ของสะสม", "เหมาะเป็นของขวัญ"],
    },
    "ms": {
        "locale_name": "Bahasa Melayu",
        "market": "Malaysia",
        "currency": "MYR",
        "brand": "Baiqipu",
        "generic_tags": ["budaya Cina", "barangan koleksi", "sesuai untuk hadiah"],
    },
}

LOCALE_ALIASES = {
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "en-us": "en",
    "en-gb": "en",
    "jp": "ja",
    "ja-jp": "ja",
    "ko-kr": "ko",
    "es-es": "es",
    "es-mx": "es",
    "th-th": "th",
    "ms-my": "ms",
}

TERM_TRANSLATIONS: dict[str, dict[str, str]] = {
    "忠诚": {"en": "loyalty", "ja": "忠義", "ko": "충성", "es": "lealtad", "th": "ความภักดี", "ms": "kesetiaan"},
    "忠义": {"en": "loyalty", "ja": "忠義", "ko": "충의", "es": "lealtad", "th": "ความภักดี", "ms": "kesetiaan"},
    "速度": {"en": "speed", "ja": "疾走感", "ko": "속도감", "es": "velocidad", "th": "ความเร็ว", "ms": "kelajuan"},
    "锋芒": {"en": "edge", "ja": "鋭さ", "ko": "예리함", "es": "caracter", "th": "ความคมชัด", "ms": "ketajaman"},
    "孤勇": {"en": "solitary bravery", "ja": "孤高の勇", "ko": "고독한 용기", "es": "valor solitario", "th": "ความกล้าเดียวดาย", "ms": "keberanian sendirian"},
    "逆境": {"en": "resilience", "ja": "逆境突破", "ko": "역경 돌파", "es": "resiliencia", "th": "การฝ่าฟันอุปสรรค", "ms": "ketabahan"},
    "悲壮": {"en": "epic tragedy", "ja": "悲壮", "ko": "비장미", "es": "epica tragica", "th": "โศกนาฏกรรมอันยิ่งใหญ่", "ms": "tragis epik"},
    "转机": {"en": "turning point", "ja": "好転", "ko": "반전", "es": "giro de fortuna", "th": "จุดเปลี่ยน", "ms": "titik perubahan"},
    "避险": {"en": "escape", "ja": "危機回避", "ko": "위기 회피", "es": "escape", "th": "การหลีกเลี่ยงอันตราย", "ms": "mengelak bahaya"},
    "天命": {"en": "destiny", "ja": "天命", "ko": "천명", "es": "destino", "th": "ชะตาฟ้า", "ms": "takdir"},
    "威猛": {"en": "power", "ja": "剛猛", "ko": "강인함", "es": "fuerza", "th": "พลัง", "ms": "kekuatan"},
    "力量": {"en": "strength", "ja": "力強さ", "ko": "힘", "es": "fuerza", "th": "พลัง", "ms": "kuasa"},
    "守护": {"en": "guardianship", "ja": "守護", "ko": "수호", "es": "proteccion", "th": "การปกป้อง", "ms": "perlindungan"},
    "冷静": {"en": "composure", "ja": "冷静", "ko": "침착함", "es": "templanza", "th": "ความนิ่ง", "ms": "ketenangan"},
    "执行": {"en": "discipline", "ja": "遂行力", "ko": "실행력", "es": "disciplina", "th": "วินัย", "ms": "disiplin"},
    "护主": {"en": "protective spirit", "ja": "主を守る力", "ko": "주군 수호", "es": "espiritu protector", "th": "จิตวิญญาณแห่งการปกป้อง", "ms": "semangat melindungi"},
}


def normalize_locale(locale: str | None) -> str:
    normalized = str(locale or "zh-CN").strip()
    canonical = LOCALE_ALIASES.get(normalized.lower(), normalized)
    if canonical in LOCALE_PRESETS:
        return canonical
    lowered = canonical.lower()
    if lowered in LOCALE_PRESETS:
        return lowered
    return "en"


def get_locale_preset(locale: str | None) -> dict[str, Any]:
    return LOCALE_PRESETS[normalize_locale(locale)]


def convert_price_from_cny(amount: float, currency: str) -> float:
    rate = EXCHANGE_RATES.get(currency.upper())
    if rate is None:
        raise ValueError(f"Unsupported currency: {currency}")
    converted = float(amount) * rate
    if currency.upper() in ZERO_DECIMAL_CURRENCIES:
        return float(int(round(converted, 0)))
    return round(converted, 2)


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _translate_term(term: str, locale: str) -> str:
    normalized_locale = normalize_locale(locale)
    if normalized_locale == "zh-CN":
        return term
    term_map = TERM_TRANSLATIONS.get(term)
    if term_map:
        return term_map.get(normalized_locale, term_map.get("en", term))
    return term


def _translated_traits(horse: Horse, locale: str) -> list[str]:
    raw_traits = [str(item).strip() for item in (horse.traits or []) if str(item).strip()]
    if not raw_traits and horse.trait:
        raw_traits = [str(horse.trait).strip()]
    return _unique([_translate_term(item, locale) for item in raw_traits])[:4]


def _spec_value(product: Product, key: str, fallback: str) -> str:
    value = product.specs.get(key) if isinstance(product.specs, dict) else None
    normalized = str(value or "").strip()
    return normalized or fallback


def _build_titles(product: Product, horse: Horse, locale: str, preset: dict[str, Any], traits: list[str]) -> tuple[str, str]:
    primary_trait = traits[0] if traits else horse.title
    if locale == "ja":
        short_title = f"{horse.name}・{product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} コレクターズフィギュア | {primary_trait}"
    elif locale == "ko":
        short_title = f"{horse.name} {product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} 컬렉터블 피규어 | {primary_trait}"
    elif locale == "es":
        short_title = f"{horse.name} {product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} figura coleccionable | {primary_trait}"
    elif locale == "th":
        short_title = f"{horse.name} {product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} ของสะสมม้าในตำนาน | {primary_trait}"
    elif locale == "ms":
        short_title = f"{horse.name} {product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} koleksi edisi khas | {primary_trait}"
    elif locale == "zh-CN":
        short_title = product.name
        title = product.name
    else:
        short_title = f"{horse.name} {product.series or horse.title}"
        title = f"{preset['brand']} {horse.name} Collectible Figure | {primary_trait}"
    return short_title, title


def _build_highlights(product: Product, horse: Horse, locale: str, traits: list[str]) -> list[str]:
    material = _spec_value(product, "material", "树脂")
    size = _spec_value(product, "size", "15cm")
    extras = _spec_value(product, "extras", "典藏证书与故事卡")
    primary_trait = " / ".join(traits[:3]) if traits else horse.title

    if locale == "ja":
        return [
            f"{horse.owner or '歴史人物'}ゆかりの名馬をテーマにしたコレクターズモデル",
            f"{material}仕上げ、サイズは{size}",
            f"{extras}付き。キーワードは {primary_trait}",
        ]
    if locale == "ko":
        return [
            f"{horse.owner or '역사 인물'}와 연결된 명마 스토리텔링 굿즈",
            f"{material} 소재, 크기는 {size}",
            f"{extras} 포함. 핵심 키워드는 {primary_trait}",
        ]
    if locale == "es":
        return [
            f"Coleccion inspirado en el legendario caballo de {horse.owner or 'los heroes historicos'}",
            f"Acabado en {material} y formato de {size}",
            f"Incluye {extras}. Rasgos clave: {primary_trait}",
        ]
    if locale == "th":
        return [
            f"ของสะสมที่หยิบแรงบันดาลใจจากม้าในตำนานของ {horse.owner or 'วีรบุรุษประวัติศาสตร์'}",
            f"วัสดุ {material} ขนาด {size}",
            f"มาพร้อม {extras} และอารมณ์หลักคือ {primary_trait}",
        ]
    if locale == "ms":
        return [
            f"Barangan koleksi berasaskan kuda legenda milik {horse.owner or 'wira sejarah'}",
            f"Material {material} dengan saiz {size}",
            f"Disertakan {extras}. Tema utama: {primary_trait}",
        ]
    if locale == "zh-CN":
        return [
            f"围绕 {horse.owner or '历史名将'} 与 {horse.name} 的故事重新设计",
            f"{material} 材质，约 {size} 展示尺寸",
            f"附带 {extras}，核心气质为 {primary_trait}",
        ]
    return [
        f"A collectible tribute to the legendary horse of {horse.owner or 'Chinese heroes'}",
        f"Finished in {material} with a display size of {size}",
        f"Packed with {extras}; the core mood is {primary_trait}",
    ]


def _build_description(product: Product, horse: Horse, locale: str, traits: list[str], preset: dict[str, Any]) -> str:
    highlight_text = " / ".join(traits[:3]) if traits else horse.title
    material = _spec_value(product, "material", "树脂")
    size = _spec_value(product, "size", "15cm")
    extras = _spec_value(product, "extras", "典藏证书与故事卡")
    source = horse.historical_source or "中国古代史料"
    dynasty = horse.dynasty or "中国古代"
    story = horse.story.strip().rstrip("。")

    if locale == "ja":
        return (
            f"{horse.name} は {dynasty}・{source} に登場する名馬で、{story}。"
            f"本商品はその物語性をもとに、{material} 素材と {size} の飾りやすいサイズで再構成しました。"
            f"{extras} を同梱し、{highlight_text} を感じられる中国文化コレクターズアイテムとして展開します。"
        )
    if locale == "ko":
        return (
            f"{horse.name}는 {dynasty} {source}에 등장하는 명마로, {story}."
            f" 이 상품은 그 서사를 바탕으로 {material} 소재와 {size} 크기의 전시형 굿즈로 구성했습니다."
            f" {extras}를 함께 제공하며, {highlight_text}의 분위기를 담은 중국 문화 컬렉터블입니다."
        )
    if locale == "es":
        return (
            f"{horse.name} aparece en {source} de la epoca {dynasty}. {story}. "
            f"Esta pieza convierte ese relato en un coleccionable de {material}, tamano {size}, con {extras}. "
            f"Pensado para compradores que conectan con {highlight_text} y con la cultura ecuestre china."
        )
    if locale == "th":
        return (
            f"{horse.name} ปรากฏใน {source} ยุค {dynasty} และเป็นที่จดจำว่า {story}. "
            f"ชิ้นงานนี้ถ่ายทอดเรื่องเล่านั้นเป็นของสะสมวัสดุ {material} ขนาด {size} พร้อม {extras}. "
            f"เหมาะกับผู้ซื้อที่ชอบบรรยากาศแบบ {highlight_text} และเรื่องเล่าวัฒนธรรมจีน."
        )
    if locale == "ms":
        return (
            f"{horse.name} direkodkan dalam {source} pada zaman {dynasty}. {story}. "
            f"Produk ini menukarkan kisah tersebut kepada barangan koleksi berasaskan {material}, saiz {size}, lengkap dengan {extras}. "
            f"Sesuai untuk pembeli yang tertarik dengan aura {highlight_text} dan budaya kuda legenda China."
        )
    if locale == "zh-CN":
        return (
            f"{horse.name} 出自 {dynasty} 的 {source}，{story}。"
            f" 我们将这段名马叙事转化为 {material} 材质、{size} 规格的收藏摆件，并附带 {extras}。"
            f" 整体卖点围绕 {highlight_text} 展开，适合礼赠、收藏和国风内容陈列。"
        )
    return (
        f"{horse.name} is recorded in {source} from the {dynasty} period, remembered because {story}. "
        f"This product turns that story into a {material} collectible sized at {size}, bundled with {extras}. "
        f"It is positioned for shoppers who respond to {highlight_text} and Chinese heritage storytelling."
    )


def localize_product(product: Product, horse: Horse, locale: str) -> dict[str, Any]:
    normalized_locale = normalize_locale(locale)
    preset = get_locale_preset(normalized_locale)
    traits = _translated_traits(horse, normalized_locale)
    short_title, title = _build_titles(product, horse, normalized_locale, preset, traits)
    highlights = _build_highlights(product, horse, normalized_locale, traits)
    description = _build_description(product, horse, normalized_locale, traits, preset)
    tags = _unique([*traits, *preset["generic_tags"], horse.name, horse.owner or "", product.series or ""])[:8]
    keywords = _unique(
        [
            horse.name,
            horse.owner or "",
            horse.title,
            *(horse.traits or []),
            product.series or "",
            *preset["generic_tags"],
        ]
    )[:10]
    return {
        "locale": normalized_locale,
        "locale_name": preset["locale_name"],
        "market": preset["market"],
        "currency": preset["currency"],
        "short_title": short_title,
        "title": title,
        "description": description,
        "tags": tags,
        "highlights": highlights,
        "search_keywords": keywords,
        "price": convert_price_from_cny(float(product.price), preset["currency"]),
    }


def build_localized_bundle(product: Product, horse: Horse, target_languages: list[str]) -> dict[str, dict[str, Any]]:
    bundle: dict[str, dict[str, Any]] = {}
    for language in target_languages:
        normalized = normalize_locale(language)
        if normalized in bundle:
            continue
        bundle[normalized] = localize_product(product, horse, normalized)
    return bundle
