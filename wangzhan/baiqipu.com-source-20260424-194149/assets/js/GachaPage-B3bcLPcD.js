import { j as e, m as motion, A as AnimatePresence } from "./motion-CDZyDkei.js";
import { r as React } from "./router-BGfvzgzq.js";
import {
  c as useAuthStore,
  e as BACKEND_ENABLED,
  i as getCheckinStatus,
  p as performCheckin,
  j as getLeaderboard,
  u as useGachaStore,
  k as getCollection,
  A as ACHIEVEMENTS,
  G as GACHA_POOL,
  H as HORSES,
  t as api,
  a as analytics,
} from "./index-CpqDpQs9.js";
import { G as GiftIcon, L as LoaderIcon, k as TrophyIcon, S as SparklesIcon, n as HistoryIcon, T as BadgeIcon, X as XIcon } from "./icons-DW3jfwfF.js";
import "./charts-TQ27S2Uq.js";

const PITY_LIMIT = 50;
const SOFT_PITY_START = 40;
const LOCAL_RATES = { SSR: 5, SR: 15, R: 80 };
const FRAGMENT_REWARDS = { SSR: 60, SR: 20, R: 5 };
const REDEEM_COSTS = { SSR: 180, SR: 80, R: 30 };
const FRAGMENT_STORAGE_KEY = "baiqipu-gacha-fragments-v2";
const SOUND_STORAGE_KEY = "baiqipu-gacha-sound";
const CHECKIN_REWARDS = [
  { day: 1, reward: "单抽券", reward_type: "draw" },
  { day: 2, reward: "50 积分", reward_type: "points" },
  { day: 3, reward: "单抽券", reward_type: "draw" },
  { day: 4, reward: "100 积分", reward_type: "points" },
  { day: 5, reward: "SR 展示徽章", reward_type: "badge" },
  { day: 6, reward: "200 积分", reward_type: "points" },
  { day: 7, reward: "十连券", reward_type: "draw_ten" },
];

const HORSE_ID_BY_NAME = {
  赤兔: "chitu",
  乌骓: "wuzhui",
  的卢: "dilu",
  绝影: "jueying",
  汗血: "hanxue",
  追风: "zhuifeng",
  踏雪: "taxue",
  飞电: "feidian",
};

const FEATURED_POOLS = [
  {
    id: "classic",
    label: "经典池",
    name: "百骑群英",
    upHorseId: null,
    accent: "#38bdf8",
    description: "标准 SSR / SR / R 概率，适合补齐图鉴。",
  },
  {
    id: "chitu-up",
    label: "赤兔 UP",
    name: "赤焰突阵",
    upHorseId: "chitu",
    accent: "#f97316",
    description: "命中 SSR 时，50% 转为赤兔。",
  },
  {
    id: "wuzhui-up",
    label: "乌骓 UP",
    name: "孤勇夜驰",
    upHorseId: "wuzhui",
    accent: "#a78bfa",
    description: "命中 SSR 时，50% 转为乌骓。",
  },
];

const RARITY_THEME = {
  SSR: {
    label: "传说",
    text: "#fde68a",
    border: "#fbbf24",
    glow: "rgba(251,191,36,0.42)",
    surface: "rgba(251,191,36,0.12)",
    description: "全屏揭示动画，命中后重置 SSR 保底。",
  },
  SR: {
    label: "稀有",
    text: "#e9d5ff",
    border: "#c084fc",
    glow: "rgba(192,132,252,0.34)",
    surface: "rgba(192,132,252,0.12)",
    description: "十连至少出现 1 张 SR 或以上。",
  },
  R: {
    label: "普通",
    text: "#bae6fd",
    border: "#38bdf8",
    glow: "rgba(56,189,248,0.24)",
    surface: "rgba(56,189,248,0.1)",
    description: "重复名马会转为碎片，可用于兑换未拥有卡。",
  },
};

const FALLBACK_IMAGE_BY_NAME = {
  赤兔: "/images/chitu.png",
  乌骓: "/images/wuzhui.png",
  的卢: "/images/dilu.png",
  绝影: "/images/jueying.png",
  汗血: "/images/hanxue.png",
  追风: "/images/hanxue.png",
  踏雪: "/images/dilu.png",
  飞电: "/images/chitu.png",
};

function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function getHorseId(value) {
  const horse = HORSES.find((item) => item.id === value || item.name === value);
  if (horse?.id) return horse.id;
  return HORSE_ID_BY_NAME[value] || value;
}

function getHorseInfo(name) {
  const horse = HORSES.find((item) => item.name === name || item.id === name);
  const poolItem = GACHA_POOL.find((item) => item.name === name || getHorseId(item.name) === name);
  return {
    id: horse?.id || poolItem?.horse_id || getHorseId(poolItem?.name || name),
    name: horse?.name || poolItem?.name || name,
    title: horse?.title || (poolItem?.rarity === "SSR" ? "传说名马" : poolItem?.rarity === "SR" ? "稀有名马" : "骏马"),
    rarity: horse?.rarity || poolItem?.rarity || "R",
    image: horse?.image || FALLBACK_IMAGE_BY_NAME[name] || "/images/chitu.png",
    trait: horse?.trait || "奔行意志",
    story: horse?.story || "一张等待补全故事的名马卡。",
    dropRate: poolItem?.dropRate || 0,
  };
}

function getHorseInfoById(horseId) {
  const horse = HORSES.find((item) => item.id === horseId);
  if (horse) return getHorseInfo(horse.name);
  const poolItem = GACHA_POOL.find((item) => getHorseId(item.name) === horseId);
  return getHorseInfo(poolItem?.name || horseId);
}

function calculateRates(pityCount) {
  if (pityCount >= PITY_LIMIT - 1) return { SSR: 100, SR: 0, R: 0 };
  if (pityCount >= SOFT_PITY_START) {
    const bonus = (pityCount - SOFT_PITY_START) * 5;
    const ssr = Math.min(LOCAL_RATES.SSR + bonus, 100);
    const sr = Math.max(LOCAL_RATES.SR - bonus * 0.3, 0);
    return { SSR: ssr, SR: sr, R: Math.max(100 - ssr - sr, 0) };
  }
  return { ...LOCAL_RATES };
}

function weightedPick(pool, totalRate) {
  const roll = Math.random() * totalRate;
  let cursor = 0;
  for (const item of pool) {
    cursor += item.effectiveRate;
    if (roll <= cursor) return item;
  }
  return pool[0];
}

function applyLocalUp(item, upHorseId) {
  if (!upHorseId || item.rarity !== "SSR") return item;
  const upItem = GACHA_POOL.map((poolItem) => ({ ...poolItem, horse_id: getHorseId(poolItem.name) })).find((poolItem) => poolItem.horse_id === upHorseId && poolItem.rarity === "SSR");
  if (!upItem) return item;
  return item.horse_id === upHorseId || Math.random() < 0.5 ? upItem : item;
}

function localDrawOnce(pityCount, upHorseId = null) {
  const rates = calculateRates(pityCount);
  const rarityTotals = GACHA_POOL.reduce((acc, item) => {
    acc[item.rarity] = (acc[item.rarity] || 0) + item.dropRate;
    return acc;
  }, {});
  const pool = GACHA_POOL.map((item) => ({
    ...item,
    horse_id: getHorseId(item.name),
    effectiveRate: rarityTotals[item.rarity] ? (item.dropRate / rarityTotals[item.rarity]) * rates[item.rarity] : 0,
  }));
  return applyLocalUp(weightedPick(pool, 100), upHorseId);
}

function localGuaranteedSr() {
  const pool = GACHA_POOL.filter((item) => item.rarity === "SR").map((item) => ({ ...item, horse_id: getHorseId(item.name), effectiveRate: item.dropRate }));
  const total = pool.reduce((sum, item) => sum + item.effectiveRate, 0);
  return weightedPick(pool, total || 1);
}

function normalizeResult(item, ownedSet, timestamp = Date.now()) {
  const horse = getHorseInfo(item.horse_name || item.name);
  const horseId = item.horse_id || horse.id;
  const isNew = typeof item.is_new === "boolean" ? item.is_new : !ownedSet.has(horse.name);
  return {
    horse_id: horseId,
    horse_name: horse.name,
    name: horse.name,
    title: horse.title,
    image: horse.image,
    trait: horse.trait,
    story: horse.story,
    rarity: item.rarity || horse.rarity,
    is_new: isNew,
    is_pity: Boolean(item.is_pity),
    is_up: Boolean(item.is_up),
    fragments_awarded: Number(item.fragments_awarded || 0),
    timestamp,
  };
}

function localDrawBatch(count, pityCount, ownedHorses, upHorseId = null) {
  const ownedSet = new Set(ownedHorses);
  const results = [];
  let currentPity = pityCount;

  for (let index = 0; index < count; index += 1) {
    const item = localDrawOnce(currentPity, upHorseId);
    const normalized = normalizeResult(
      {
        horse_id: item.horse_id,
        horse_name: item.name,
        rarity: item.rarity,
        is_pity: currentPity >= PITY_LIMIT - 1,
        is_up: Boolean(upHorseId && item.horse_id === upHorseId),
      },
      ownedSet,
    );
    if (!normalized.is_new) normalized.fragments_awarded = FRAGMENT_REWARDS[normalized.rarity] || 0;
    results.push(normalized);
    if (normalized.is_new) ownedSet.add(normalized.name);
    currentPity = normalized.rarity === "SSR" ? 0 : currentPity + 1;
  }

  if (count >= 10 && !results.some((item) => item.rarity === "SSR" || item.rarity === "SR")) {
    const item = localGuaranteedSr();
    const guaranteed = normalizeResult(
      {
        horse_id: item.horse_id,
        horse_name: item.name,
        rarity: item.rarity,
        is_pity: false,
        is_up: Boolean(upHorseId && item.horse_id === upHorseId),
      },
      ownedSet,
    );
    if (!guaranteed.is_new) guaranteed.fragments_awarded = FRAGMENT_REWARDS[guaranteed.rarity] || 0;
    results[results.length - 1] = guaranteed;
  }

  return { results, pity_count: currentPity };
}

function loadLocalFragments() {
  try {
    const raw = window.localStorage.getItem(FRAGMENT_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (error) {
    return {};
  }
}

function saveLocalFragments(inventory) {
  try {
    window.localStorage.setItem(FRAGMENT_STORAGE_KEY, JSON.stringify(inventory));
  } catch (error) {}
}

function fragmentsToInventory(items = []) {
  return items.reduce((acc, item) => {
    acc[item.horse_id] = Number(item.quantity || 0);
    return acc;
  }, {});
}

function playGachaSound(enabled, rarity = "R", phase = "reveal") {
  if (!enabled || typeof window === "undefined") return;
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return;
  try {
    const context = new AudioContext();
    const gain = context.createGain();
    const oscillator = context.createOscillator();
    const now = context.currentTime;
    const base = rarity === "SSR" ? 660 : rarity === "SR" ? 520 : 360;
    oscillator.type = rarity === "SSR" ? "triangle" : "sine";
    oscillator.frequency.setValueAtTime(phase === "charging" ? 180 : base, now);
    oscillator.frequency.exponentialRampToValueAtTime(phase === "charging" ? 260 : base * 1.35, now + 0.18);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(rarity === "SSR" ? 0.18 : 0.1, now + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + (rarity === "SSR" ? 0.46 : 0.28));
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(now);
    oscillator.stop(now + (rarity === "SSR" ? 0.5 : 0.32));
    window.setTimeout(() => context.close?.(), 700);
  } catch (error) {}
}

function RarityBadge({ rarity, compact = false }) {
  const theme = RARITY_THEME[rarity] || RARITY_THEME.R;
  return e.jsx("span", {
    className: "inline-flex items-center border px-2 py-1 text-xs font-semibold",
    style: {
      borderColor: theme.border,
      color: theme.text,
      background: theme.surface,
      padding: compact ? "2px 5px" : undefined,
      fontSize: compact ? 10 : undefined,
      lineHeight: compact ? 1.1 : undefined,
    },
    children: `${rarity} · ${theme.label}`,
  });
}

function ResultCard({ item, index, compact = false }) {
  const theme = RARITY_THEME[item.rarity] || RARITY_THEME.R;
  const chipStyle = compact ? { padding: "2px 5px", fontSize: 10, lineHeight: 1.1 } : undefined;
  const cardInitial = compact ? { opacity: 0, y: 8, scale: 0.96 } : { rotateY: 180, opacity: 0, y: 18 };
  const cardAnimate = compact ? { opacity: 1, y: 0, scale: 1 } : { rotateY: 0, opacity: 1, y: 0 };
  return e.jsxs(motion.div, {
    initial: cardInitial,
    animate: cardAnimate,
    transition: { delay: index * (compact ? 0.045 : 0.08), duration: compact ? 0.38 : 0.55, type: "spring", stiffness: 130, damping: 17 },
    className: "relative overflow-hidden border bg-black/45",
    style: {
      minHeight: compact ? 152 : 310,
      borderColor: theme.border,
      boxShadow: `0 0 ${compact ? 12 : 34}px ${theme.glow}`,
      transformStyle: "preserve-3d",
    },
    children: [
      e.jsx("div", {
        className: compact ? "absolute inset-x-0 top-0 h-12" : "absolute inset-x-0 top-0 h-20",
        style: { background: `linear-gradient(180deg, ${theme.glow}, transparent)` },
      }),
      e.jsx("img", {
        src: item.image,
        alt: item.name,
        className: "w-full object-cover",
        style: { height: compact ? 72 : 144, filter: item.rarity === "SSR" ? "saturate(1.15) contrast(1.04)" : "none" },
      }),
      e.jsxs("div", {
        className: compact ? "p-2" : "p-5",
        children: [
          e.jsxs("div", {
            className: compact ? "flex items-start justify-between gap-1" : "flex items-center justify-between gap-3",
            children: [
              e.jsx(RarityBadge, { rarity: item.rarity, compact }),
              e.jsxs("div", {
                className: "flex flex-wrap justify-end gap-1",
                children: [
                  item.is_up ? e.jsx("span", { className: "border border-amber-300/40 bg-amber-300/10 px-2 py-1 text-xs text-amber-100", style: chipStyle, children: "UP" }) : null,
                  item.is_new
                    ? e.jsx("span", { className: "border border-emerald-200/20 bg-emerald-300/10 px-2 py-1 text-xs text-emerald-100", style: chipStyle, children: "NEW" })
                    : e.jsx("span", { className: "border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-stone-400", style: chipStyle, children: "重复" }),
                  !item.is_new && item.fragments_awarded
                    ? e.jsxs("span", { className: "border border-cyan-200/30 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100", style: chipStyle, children: ["+", item.fragments_awarded] })
                    : null,
                ],
              }),
            ],
          }),
          e.jsx("h3", { className: compact ? "mt-2 truncate text-base font-semibold" : "mt-4 text-3xl font-semibold", children: item.name }),
          e.jsx("p", { className: compact ? "mt-0.5 truncate text-xs text-stone-300" : "mt-1 text-sm text-stone-300", children: item.title }),
          !compact
            ? e.jsx("p", { className: "mt-3 text-sm leading-6 text-stone-400", children: item.story })
            : null,
        ],
      }),
    ],
  });
}

function DrawOverlay({ phase, results, onClose }) {
  const top = results?.find((item) => item.rarity === "SSR") || results?.find((item) => item.rarity === "SR") || results?.[0];
  const theme = top ? RARITY_THEME[top.rarity] : RARITY_THEME.SSR;
  const isRevealing = phase === "reveal";

  React.useEffect(() => {
    if (!phase || !isRevealing) return undefined;
    function handleKeyDown(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [phase, isRevealing, onClose]);

  return e.jsx(AnimatePresence, {
    children: phase
      ? e.jsxs(motion.div, {
          className: "fixed inset-0 z-50 overflow-y-auto bg-black/90 px-4 py-4",
          initial: { opacity: 0 },
          animate: { opacity: 1 },
          exit: { opacity: 0 },
          onClick: (event) => {
            if (isRevealing && event.target === event.currentTarget) onClose();
          },
          children: [
            isRevealing
              ? e.jsx("button", {
                  type: "button",
                  onClick: onClose,
                  className: "fixed z-50 flex h-10 w-10 items-center justify-center border border-white/20 bg-black/50 text-stone-100 transition hover:border-amber-200 hover:text-amber-100",
                  style: { top: 24, right: 24 },
                  "aria-label": "关闭抽卡结果",
                  children: e.jsx(XIcon, { size: 20 }),
                })
              : null,
            e.jsx(motion.div, {
              className: "pointer-events-none absolute rounded-full",
              style: {
                width: 360,
                height: 360,
                left: "50%",
                top: "50%",
                marginLeft: -180,
                marginTop: -180,
                background: `radial-gradient(circle, ${theme.glow} 0%, transparent 70%)`,
              },
              animate: { scale: [1, 1.28, 1], opacity: [0.45, 0.95, 0.5] },
              transition: { duration: 1.2, repeat: Infinity },
            }),
            !isRevealing
              ? e.jsxs("div", {
                  className: "relative z-10 flex min-h-screen items-center justify-center text-center",
                  children: [
                    e.jsxs("div", {
                      children: [
                        e.jsx(motion.div, {
                          className: "mx-auto flex h-44 w-32 items-center justify-center border bg-stone-950 text-amber-200",
                          style: { borderColor: "#fbbf24", boxShadow: "0 0 48px rgba(251,191,36,0.32)" },
                          animate: { rotateY: [0, 180, 360], y: [0, -8, 0] },
                          transition: { duration: 1.1, repeat: Infinity, ease: "easeInOut" },
                          children: e.jsx(SparklesIcon, { size: 34 }),
                        }),
                        e.jsx("p", { className: "mt-6 text-lg font-semibold text-amber-100", children: "马蹄声渐近，卡面正在显现" }),
                        e.jsx("p", { className: "mt-2 text-sm text-stone-500", children: "十连会逐张翻开，SR 以上会触发更强光效" }),
                      ],
                    }),
                  ],
                })
              : e.jsxs("div", {
                  className: "relative z-10 mx-auto w-full",
                  style: {
                    maxWidth: results.length > 1 ? 1000 : 420,
                    minHeight: "calc(100vh - 32px)",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    paddingTop: results.length > 1 ? 24 : 0,
                    paddingBottom: results.length > 1 ? 12 : 0,
                  },
                  onClick: (event) => event.stopPropagation(),
                  children: [
                    e.jsxs("div", {
                      className: results.length > 1 ? "mb-5 flex flex-wrap items-end justify-between gap-3" : "mb-4 flex flex-wrap items-end justify-between gap-3",
                      style: { position: "relative", zIndex: 2, paddingRight: results.length > 1 ? 52 : 0 },
                      children: [
                        e.jsxs("div", {
                          children: [
                            e.jsx("p", { className: results.length > 1 ? "text-xs tracking-widest text-amber-200" : "text-sm tracking-widest text-amber-200", children: "召唤结果" }),
                            e.jsx("h2", { className: results.length > 1 ? "mt-1 text-xl font-semibold" : "mt-1 text-3xl font-semibold", children: top?.rarity === "SSR" ? "传说名马现身" : "卡面已揭示" }),
                          ],
                        }),
                        e.jsx("button", {
                          type: "button",
                          onClick: onClose,
                          className: "border border-white/20 px-5 py-2 text-sm text-stone-200 transition hover:border-amber-200 hover:text-amber-100",
                          children: "收起结果",
                        }),
                      ],
                    }),
                    e.jsx("div", {
                      className: results.length === 1 ? "mx-auto max-w-sm" : "grid gap-2 grid-cols-2 md:grid-cols-5",
                      style: { position: "relative", zIndex: 1 },
                      children: results.map((item, index) => e.jsx(ResultCard, { item, index, compact: results.length > 1 }, `${item.name}-${index}-${item.timestamp}`)),
                    }),
                    e.jsx("div", {
                      className: results.length > 1 ? "mt-3 flex justify-center" : "mt-5 flex justify-center",
                      children: e.jsx("button", {
                        type: "button",
                        onClick: onClose,
                        className: "bg-amber-300 px-5 py-2 text-sm font-semibold text-stone-900 transition hover:bg-amber-200",
                        children: "继续抽卡",
                      }),
                    }),
                  ],
                }),
          ],
        })
      : null,
  });
}

function PityMeter({ pityCount }) {
  const percent = Math.min(100, (pityCount / PITY_LIMIT) * 100);
  const next = Math.max(PITY_LIMIT - pityCount, 0);
  return e.jsxs("div", {
    className: "border border-white/10 bg-black/25 p-4",
    children: [
      e.jsxs("div", {
        className: "flex items-center justify-between gap-3",
        children: [
          e.jsx("span", { className: "text-sm text-stone-400", children: "SSR 保底进度" }),
          e.jsxs("strong", { className: "text-amber-200", children: [pityCount, "/", PITY_LIMIT] }),
        ],
      }),
      e.jsx("div", {
        className: "mt-3 h-2 overflow-hidden bg-white/10",
        children: e.jsx("span", {
          className: "block h-full",
          style: { width: `${percent}%`, background: "linear-gradient(90deg,#38bdf8,#fbbf24)" },
        }),
      }),
      e.jsxs("p", {
        className: "mt-3 text-sm leading-6 text-stone-400",
        children: ["再抽 ", next, " 次内必出 SSR；第 ", SOFT_PITY_START, " 抽后 SSR 概率逐步提升。"],
      }),
    ],
  });
}

function RulePanel({ pityCount }) {
  return e.jsxs("div", {
    className: "grid gap-3 md:grid-cols-3",
    children: Object.entries(RARITY_THEME).map(([rarity, theme]) =>
      e.jsxs("div", {
        className: "border bg-black/25 p-4",
        style: { borderColor: theme.border, boxShadow: `0 0 22px ${theme.glow}` },
        children: [
          e.jsx(RarityBadge, { rarity }),
          e.jsx("p", { className: "mt-3 text-2xl font-semibold", style: { color: theme.text }, children: `${LOCAL_RATES[rarity]}%` }),
          e.jsx("p", { className: "mt-2 text-sm leading-6 text-stone-400", children: theme.description }),
        ],
      }, rarity),
    ).concat([
      e.jsx("div", { className: "md:col-span-3", children: e.jsx(PityMeter, { pityCount }) }, "pity"),
    ]),
  });
}

function PoolSelector({ selectedPoolId, onSelect }) {
  return e.jsx("div", {
    className: "mt-6 grid gap-3 md:grid-cols-3",
    children: FEATURED_POOLS.map((pool) => {
      const selected = pool.id === selectedPoolId;
      const upHorse = pool.upHorseId ? getHorseInfoById(pool.upHorseId) : null;
      return e.jsxs("button", {
        type: "button",
        onClick: () => onSelect(pool.id),
        className: cx("border bg-black/25 p-4 text-left transition", selected ? "border-amber-300 text-stone-100" : "border-white/10 text-stone-300 hover:border-white/25"),
        style: selected ? { boxShadow: `0 0 24px ${pool.accent}55` } : {},
        children: [
          e.jsxs("div", {
            className: "flex items-center justify-between gap-3",
            children: [
              e.jsx("span", { className: "text-sm font-semibold", children: pool.label }),
              selected ? e.jsx(SparklesIcon, { size: 16, style: { color: pool.accent } }) : null,
            ],
          }),
          e.jsx("p", { className: "mt-2 text-lg font-semibold", children: pool.name }),
          e.jsx("p", { className: "mt-2 min-h-10 text-sm leading-5 text-stone-400", children: pool.description }),
          upHorse
            ? e.jsxs("div", {
                className: "mt-3 flex items-center gap-2 text-xs text-amber-100",
                children: [
                  e.jsx("img", { src: upHorse.image, alt: upHorse.name, className: "h-8 w-8 object-cover" }),
                  e.jsxs("span", { children: ["UP · ", upHorse.name] }),
                ],
              })
            : e.jsx("p", { className: "mt-3 text-xs text-stone-500", children: "无 UP，按基础权重抽取" }),
        ],
      }, pool.id);
    }),
  });
}

function CollectionGrid({ ownedHorses }) {
  const owned = new Set(ownedHorses);
  return e.jsx("div", {
    className: "grid grid-cols-2 gap-3 md:grid-cols-4",
    children: GACHA_POOL.map((poolItem) => {
      const info = getHorseInfo(poolItem.name);
      const has = owned.has(info.name);
      const theme = RARITY_THEME[info.rarity] || RARITY_THEME.R;
      return e.jsxs("div", {
        className: "overflow-hidden border bg-black/30",
        style: { borderColor: has ? theme.border : "rgba(255,255,255,0.12)" },
        children: [
          e.jsx("div", {
            className: "h-28 bg-stone-900",
            children: has
              ? e.jsx("img", { src: info.image, alt: info.name, className: "h-full w-full object-cover" })
              : e.jsx("div", { className: "flex h-full items-center justify-center text-3xl text-stone-700", children: "?" }),
          }),
          e.jsxs("div", {
            className: "p-3 text-sm",
            children: [
              e.jsx("p", { className: has ? "font-semibold text-stone-100" : "font-semibold text-stone-500", children: has ? info.name : "未解锁" }),
              e.jsxs("div", {
                className: "mt-2 flex items-center justify-between gap-2",
                children: [
                  e.jsx("span", { style: { color: theme.text }, children: info.rarity }),
                  e.jsxs("span", { className: "text-xs text-stone-500", children: [poolItem.dropRate, "% 权重"] }),
                ],
              }),
            ],
          }),
        ],
      }, poolItem.name);
    }),
  });
}

function FragmentPanel({ fragments, ownedHorses, onExchange, exchangeLoading, message }) {
  const owned = new Set(ownedHorses);
  const items = GACHA_POOL.map((poolItem) => {
    const info = getHorseInfo(poolItem.name);
    return {
      ...info,
      quantity: Number(fragments[info.id] || 0),
      redeemCost: REDEEM_COSTS[info.rarity] || 999,
      owned: owned.has(info.name),
    };
  });

  return e.jsxs("section", {
    className: "border border-white/15 bg-black/35 p-5",
    children: [
      e.jsxs("div", {
        className: "flex flex-wrap items-center justify-between gap-3",
        children: [
          e.jsx("h3", { className: "text-xl font-semibold", children: "碎片兑换" }),
          e.jsx("span", { className: "text-sm text-stone-500", children: "R 30 / SR 80 / SSR 180" }),
        ],
      }),
      message ? e.jsx("p", { className: "mt-3 border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-sm text-amber-100", children: message }) : null,
      e.jsx("div", {
        className: "mt-4 grid gap-3 md:grid-cols-2",
        children: items.map((item) => {
          const theme = RARITY_THEME[item.rarity] || RARITY_THEME.R;
          const percent = Math.min(100, (item.quantity / item.redeemCost) * 100);
          const disabled = item.owned || item.quantity < item.redeemCost || exchangeLoading;
          return e.jsxs("div", {
            className: "border bg-black/25 p-3",
            style: { borderColor: item.owned ? theme.border : "rgba(255,255,255,0.12)" },
            children: [
              e.jsxs("div", {
                className: "flex items-center gap-3",
                children: [
                  e.jsx("img", { src: item.image, alt: item.name, className: "h-12 w-12 object-cover" }),
                  e.jsxs("div", {
                    className: "min-w-0 flex-1",
                    children: [
                      e.jsxs("p", { className: "truncate font-semibold", children: [item.name, " · ", item.rarity] }),
                      e.jsxs("p", { className: "mt-1 text-xs text-stone-500", children: [item.quantity, "/", item.redeemCost, " 碎片"] }),
                    ],
                  }),
                ],
              }),
              e.jsx("div", {
                className: "mt-3 h-1.5 overflow-hidden bg-white/10",
                children: e.jsx("span", { className: "block h-full", style: { width: `${percent}%`, background: theme.border } }),
              }),
              e.jsx("button", {
                type: "button",
                onClick: () => onExchange(item.id),
                disabled,
                className: "mt-3 w-full border border-white/15 px-3 py-2 text-sm text-stone-200 transition hover:border-amber-300 hover:text-amber-100 disabled:border-white/5 disabled:text-stone-600",
                children: item.owned ? "已拥有" : item.quantity >= item.redeemCost ? "兑换" : `还差 ${item.redeemCost - item.quantity}`,
              }),
            ],
          }, item.id);
        }),
      }),
    ],
  });
}

function RecentHistory({ history }) {
  if (!history.length) {
    return e.jsx("div", { className: "border border-white/10 bg-black/20 p-4 text-sm text-stone-500", children: "还没有抽卡记录。完成一次召唤后，这里会显示最近 20 次结果。" });
  }
  return e.jsx("div", {
    className: "max-h-72 overflow-y-auto border border-white/10 bg-black/20 p-3",
    children: history.slice(0, 20).map((item, index) => {
      const theme = RARITY_THEME[item.rarity] || RARITY_THEME.R;
      return e.jsxs("div", {
        className: "flex items-center justify-between border-b border-white/5 py-2 text-sm last:border-b-0",
        children: [
          e.jsxs("span", { style: { color: theme.text }, children: [item.name, " · ", item.rarity] }),
          e.jsx("span", { className: "text-stone-500", children: new Date(item.timestamp).toLocaleString("zh-CN") }),
        ],
      }, `${item.name}-${item.timestamp}-${index}`);
    }),
  });
}

function CheckinPanel() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [status, setStatus] = React.useState(null);
  const [loading, setLoading] = React.useState(false);
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    if (!BACKEND_ENABLED || !isAuthenticated) return;
    let cancelled = false;
    setLoading(true);
    getCheckinStatus()
      .then((payload) => {
        if (!cancelled) setStatus(payload);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  async function onCheckin() {
    if (!BACKEND_ENABLED || !isAuthenticated) {
      setMessage("登录后可同步签到奖励。");
      return;
    }
    setLoading(true);
    try {
      const payload = await performCheckin();
      setStatus(payload.status);
      setMessage(payload.reward ? `已领取：${payload.reward.reward}` : payload.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "签到失败。");
    } finally {
      setLoading(false);
    }
  }

  const rewards = status?.rewards?.length ? status.rewards : CHECKIN_REWARDS;
  const completed = status?.completed_cycle_days || 0;
  const checkedToday = Boolean(status?.checked_today);

  return e.jsxs("section", {
    className: "border border-white/15 bg-black/35 p-5",
    children: [
      e.jsxs("div", {
        className: "flex items-center justify-between gap-3",
        children: [
          e.jsxs("h3", { className: "flex items-center gap-2 font-semibold", children: [e.jsx(GiftIcon, { size: 18, className: "text-amber-300" }), "每日签到"] }),
          e.jsx("span", { className: "text-sm text-stone-400", children: `连续 ${status?.streak || 0} 天` }),
        ],
      }),
      e.jsx("div", {
        className: "mt-4 grid grid-cols-7 gap-2",
        children: rewards.map((reward) =>
          e.jsxs("div", {
            className: cx("border p-2 text-center text-xs", reward.day <= completed ? "border-amber-300/40 bg-amber-300/10 text-amber-100" : "border-white/10 text-stone-500"),
            children: [e.jsxs("p", { children: ["第", reward.day, "天"] }), e.jsx("p", { className: "mt-1", children: reward.reward })],
          }, reward.day),
        ),
      }),
      e.jsx("button", {
        onClick: onCheckin,
        disabled: checkedToday || loading,
        className: "mt-4 flex w-full items-center justify-center gap-2 bg-amber-300 py-2.5 text-sm font-semibold text-stone-900 transition hover:bg-amber-200 disabled:bg-stone-700 disabled:text-stone-400",
        children: loading ? e.jsxs(React.Fragment, { children: [e.jsx(LoaderIcon, { size: 15, className: "animate-spin" }), "处理中"] }) : checkedToday ? "今天已签到" : "领取今日奖励",
      }),
      message ? e.jsx("p", { className: "mt-2 text-center text-sm text-amber-200", children: message }) : null,
    ],
  });
}

const FALLBACK_LEADERBOARD = [
  { rank: 1, user_id: "mock-1", nickname: "赤焰马厩", ssr_count: 3, total_owned: 8, total_draws: 42, is_current_user: false },
  { rank: 2, user_id: "mock-2", nickname: "青铜骑手", ssr_count: 2, total_owned: 7, total_draws: 35, is_current_user: false },
  { rank: 3, user_id: "mock-3", nickname: "月夜铁蹄", ssr_count: 2, total_owned: 6, total_draws: 28, is_current_user: false },
];

function LeaderboardPanel() {
  const [leaderboard, setLeaderboard] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (!BACKEND_ENABLED) return;
    let cancelled = false;
    setLoading(true);
    getLeaderboard(8)
      .then((payload) => {
        if (!cancelled) setLeaderboard(payload);
      })
      .catch(() => {
        if (!cancelled) setLeaderboard(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = leaderboard?.items?.length ? leaderboard.items : FALLBACK_LEADERBOARD;

  return e.jsxs("section", {
    className: "border border-white/15 bg-black/35 p-5",
    children: [
      e.jsxs("h3", { className: "flex items-center gap-2 font-semibold", children: [e.jsx(TrophyIcon, { size: 18, className: "text-amber-300" }), "收藏排行榜"] }),
      loading ? e.jsx("p", { className: "mt-3 text-sm text-stone-500", children: "正在加载排行榜..." }) : null,
      e.jsx("div", {
        className: "mt-4 space-y-1",
        children: items.map((item, index) =>
          e.jsxs("div", {
            className: cx("flex items-center gap-3 px-3 py-2 text-sm", index < 3 ? "bg-white/5" : "", item.is_current_user ? "border border-cyan-200/20 bg-cyan-300/10" : ""),
            children: [
              e.jsx("span", { className: "w-7 text-center text-amber-200", children: item.rank || index + 1 }),
              e.jsx("span", { className: "flex-1 truncate text-stone-200", children: item.nickname }),
              e.jsxs("span", { className: "text-amber-200/80", children: [item.ssr_count, " SSR"] }),
              e.jsxs("span", { className: "text-stone-500", children: [item.total_owned, " 匹"] }),
            ],
          }, item.user_id || index),
        ),
      }),
    ],
  });
}

function GachaPage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { ownedHorses, gachaHistory, pityCount } = useGachaStore();
  const [drawing, setDrawing] = React.useState(false);
  const [phase, setPhase] = React.useState(null);
  const [results, setResults] = React.useState([]);
  const [lastDrawType, setLastDrawType] = React.useState("single");
  const [error, setError] = React.useState("");
  const [selectedPoolId, setSelectedPoolId] = React.useState("classic");
  const [fragments, setFragments] = React.useState(() => loadLocalFragments());
  const [exchangeLoading, setExchangeLoading] = React.useState(false);
  const [exchangeMessage, setExchangeMessage] = React.useState("");
  const [soundEnabled, setSoundEnabled] = React.useState(() => {
    try {
      return window.localStorage.getItem(SOUND_STORAGE_KEY) !== "off";
    } catch (error) {
      return true;
    }
  });
  const selectedPool = FEATURED_POOLS.find((pool) => pool.id === selectedPoolId) || FEATURED_POOLS[0];

  React.useEffect(() => {
    if (!BACKEND_ENABLED || !isAuthenticated) return;
    let cancelled = false;
    getCollection()
      .then((payload) => {
        if (cancelled) return;
        useGachaStore.getState().setServerState({
          ownedHorses: payload.owned_horses.map((item) => item.horse_name),
          pityCount: payload.pity_count,
        });
        if (payload.fragments) setFragments(fragmentsToInventory(payload.fragments));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  React.useEffect(() => {
    if (!BACKEND_ENABLED || !isAuthenticated) saveLocalFragments(fragments);
  }, [fragments, isAuthenticated]);

  React.useEffect(() => {
    try {
      window.localStorage.setItem(SOUND_STORAGE_KEY, soundEnabled ? "on" : "off");
    } catch (error) {}
  }, [soundEnabled]);

  function applyFragmentAwards(drawResults) {
    const delta = drawResults.reduce((acc, item) => {
      if (!item.is_new && item.fragments_awarded) acc[item.horse_id] = (acc[item.horse_id] || 0) + item.fragments_awarded;
      return acc;
    }, {});
    if (!Object.keys(delta).length) return;
    setFragments((current) => {
      const next = { ...current };
      Object.entries(delta).forEach(([horseId, value]) => {
        next[horseId] = Number(next[horseId] || 0) + Number(value || 0);
      });
      return next;
    });
  }

  async function performDraw(drawType) {
    const count = drawType === "ten" ? 10 : 1;
    const ownedSet = new Set(useGachaStore.getState().ownedHorses);

    if (BACKEND_ENABLED && isAuthenticated) {
      const payload = await api.post("/gacha/draw", {
        draw_type: drawType,
        pool_id: selectedPool.id,
        up_horse_id: selectedPool.upHorseId,
      });
      const normalized = (payload.results || []).map((item) => normalizeResult(item, ownedSet));
      if (payload.fragments) setFragments(fragmentsToInventory(payload.fragments));
      useGachaStore.getState().addGachaResults(
        normalized.map((item) => ({ name: item.name, rarity: item.rarity, timestamp: item.timestamp })),
        payload.pity_count,
      );
      return { results: normalized, pity_count: payload.pity_count };
    }

    const fallback = localDrawBatch(count, useGachaStore.getState().pityCount, useGachaStore.getState().ownedHorses, selectedPool.upHorseId);
    applyFragmentAwards(fallback.results);
    useGachaStore.getState().addGachaResults(
      fallback.results.map((item) => ({ name: item.name, rarity: item.rarity, timestamp: item.timestamp })),
      fallback.pity_count,
    );
    return fallback;
  }

  async function startDraw(drawType) {
    if (drawing) return;
    setDrawing(true);
    setError("");
    setResults([]);
    setLastDrawType(drawType);
    setPhase("charging");
    setExchangeMessage("");
    playGachaSound(soundEnabled, "R", "charging");

    try {
      const [payload] = await Promise.all([performDraw(drawType), sleep(drawType === "ten" ? 1100 : 850)]);
      const sorted = payload.results;
      setResults(sorted);
      setPhase("reveal");
      const best = sorted.find((item) => item.rarity === "SSR") || sorted.find((item) => item.rarity === "SR") || sorted[0];
      if (best) playGachaSound(soundEnabled, best.rarity, "reveal");
      if (best) analytics.gachaDraw(drawType, best.name, best.rarity);
    } catch (err) {
      const fallback = localDrawBatch(drawType === "ten" ? 10 : 1, useGachaStore.getState().pityCount, useGachaStore.getState().ownedHorses, selectedPool.upHorseId);
      applyFragmentAwards(fallback.results);
      useGachaStore.getState().addGachaResults(
        fallback.results.map((item) => ({ name: item.name, rarity: item.rarity, timestamp: item.timestamp })),
        fallback.pity_count,
      );
      setResults(fallback.results);
      setPhase("reveal");
      const best = fallback.results.find((item) => item.rarity === "SSR") || fallback.results.find((item) => item.rarity === "SR") || fallback.results[0];
      if (best) playGachaSound(soundEnabled, best.rarity, "reveal");
      setError(err instanceof Error ? `${err.message}，已改用本地演示抽卡。` : "接口暂不可用，已改用本地演示抽卡。");
    } finally {
      setDrawing(false);
    }
  }

  async function exchangeHorse(horseId) {
    if (exchangeLoading) return;
    setExchangeLoading(true);
    setExchangeMessage("");
    try {
      const info = getHorseInfoById(horseId);
      const currentOwned = useGachaStore.getState().ownedHorses;
      if (currentOwned.includes(info.name)) {
        setExchangeMessage(`${info.name} 已经在你的图鉴里。`);
        return;
      }

      if (BACKEND_ENABLED && isAuthenticated) {
        const payload = await api.post("/gacha/exchange", { horse_id: horseId });
        useGachaStore.getState().setServerState({
          ownedHorses: payload.owned_horses.map((item) => item.horse_name),
          pityCount: payload.pity_count,
        });
        setFragments(fragmentsToInventory(payload.fragments || []));
        setExchangeMessage(payload.message || `已兑换 ${info.name}。`);
        return;
      }

      const cost = REDEEM_COSTS[info.rarity] || 999;
      if (Number(fragments[horseId] || 0) < cost) {
        setExchangeMessage(`${info.name} 碎片不足。`);
        return;
      }
      const next = { ...fragments, [horseId]: Number(fragments[horseId] || 0) - cost };
      setFragments(next);
      useGachaStore.getState().setServerState({ ownedHorses: [...currentOwned, info.name] });
      setExchangeMessage(`已用 ${cost} 个碎片兑换 ${info.name}。`);
    } catch (err) {
      setExchangeMessage(err instanceof Error ? err.message : "兑换失败，请稍后再试。");
    } finally {
      setExchangeLoading(false);
    }
  }

  const bestResult = results.find((item) => item.rarity === "SSR") || results.find((item) => item.rarity === "SR") || results[0] || null;
  const nextAchievement = ACHIEVEMENTS.find((item) => ownedHorses.length < item.required);

  return e.jsxs("div", {
    className: "min-h-screen pt-24 pb-20",
    children: [
      e.jsxs("div", {
        className: "w-full px-6 md:px-12 xl:px-20 2xl:px-28",
        children: [
          e.jsxs("section", {
            className: "grid gap-8 xl:grid-cols-2",
            children: [
              e.jsxs("div", {
                className: "border border-white/15 bg-black/35 p-6 xl:p-8",
                children: [
                  e.jsx("p", { className: "text-sm tracking-widest text-amber-200", children: "百骑谱召唤台" }),
                  e.jsx("h1", { className: "mt-3 text-4xl font-semibold md:text-5xl xl:text-6xl", children: "名马抽卡" }),
                  e.jsx("p", { className: "mt-4 max-w-3xl text-lg leading-8 text-stone-300 xl:text-xl", children: "选择限定池后召唤，命中 SSR 时 UP 名马有 50% 机会出现。重复卡会转为碎片，攒够后可直接兑换未拥有名马。" }),
                  e.jsx(PoolSelector, { selectedPoolId, onSelect: setSelectedPoolId }),
                  e.jsxs("div", {
                    className: "mt-7 flex flex-wrap items-center gap-3",
                    children: [
                      e.jsxs("button", {
                        onClick: () => startDraw("single"),
                        disabled: drawing,
                        className: "inline-flex items-center gap-2 bg-amber-300 px-6 py-3 text-base font-semibold text-stone-900 transition hover:bg-amber-200 disabled:opacity-50 xl:text-lg",
                        children: [drawing && lastDrawType === "single" ? e.jsx(LoaderIcon, { size: 16, className: "animate-spin" }) : e.jsx(SparklesIcon, { size: 16 }), " 单次召唤"],
                      }),
                      e.jsxs("button", {
                        onClick: () => startDraw("ten"),
                        disabled: drawing,
                        className: "inline-flex items-center gap-2 border border-amber-300 px-6 py-3 text-base font-semibold text-amber-200 transition hover:bg-amber-300/10 disabled:opacity-50 xl:text-lg",
                        children: [drawing && lastDrawType === "ten" ? e.jsx(LoaderIcon, { size: 16, className: "animate-spin" }) : e.jsx(GiftIcon, { size: 16 }), " 十连召唤"],
                      }),
                      e.jsxs("button", {
                        type: "button",
                        onClick: () => setSoundEnabled((value) => !value),
                        className: cx("inline-flex items-center gap-2 border px-4 py-3 text-sm transition", soundEnabled ? "border-cyan-200/30 text-cyan-100" : "border-white/15 text-stone-500"),
                        children: [e.jsx(SparklesIcon, { size: 15 }), soundEnabled ? "音效开" : "音效关"],
                      }),
                    ],
                  }),
                  error ? e.jsx("p", { className: "mt-4 text-sm text-rose-200", children: error }) : null,
                ],
              }),
              e.jsxs("div", {
                className: "border border-white/15 bg-black/35 p-6 xl:p-8",
                children: [
                  e.jsxs("div", {
                    className: "flex items-center justify-between gap-4",
                    children: [
                      e.jsxs("div", {
                        children: [
                          e.jsx("p", { className: "text-sm text-stone-500", children: "本轮最高结果" }),
                          e.jsx("h2", { className: "mt-1 text-2xl font-semibold", children: bestResult ? bestResult.name : "等待召唤" }),
                          e.jsxs("p", { className: "mt-1 text-sm text-amber-200/80", children: ["当前卡池 · ", selectedPool.label] }),
                        ],
                      }),
                      bestResult ? e.jsx(RarityBadge, { rarity: bestResult.rarity }) : e.jsx("span", { className: "border border-white/10 px-3 py-1 text-sm text-stone-500", children: "未开始" }),
                    ],
                  }),
                  bestResult
                    ? e.jsx("div", { className: "mt-5", children: e.jsx(ResultCard, { item: bestResult, index: 0 }) })
                    : e.jsxs("div", {
                        className: "mt-5 flex items-center justify-center border border-white/10 bg-black/20 text-center",
                        style: { minHeight: 310 },
                        children: [
                          e.jsxs("div", {
                            children: [
                              e.jsx(BadgeIcon, { size: 42, className: "mx-auto text-stone-600" }),
                              e.jsx("p", { className: "mt-3 text-stone-400", children: "完成一次召唤后，这里会停留展示最高稀有度卡面。" }),
                            ],
                          }),
                        ],
                      }),
                ],
              }),
            ],
          }),
          e.jsxs("section", {
            className: "mt-8 grid gap-8 xl:grid-cols-2",
            children: [
              e.jsxs("div", {
                className: "space-y-5",
                children: [
                  e.jsxs("div", {
                    className: "border border-white/15 bg-black/35 p-5",
                    children: [
                      e.jsxs("div", {
                        className: "flex items-center justify-between gap-4",
                        children: [
                          e.jsx("h2", { className: "text-xl font-semibold", children: "抽卡机制" }),
                          e.jsx("span", { className: "text-sm text-stone-500", children: isAuthenticated ? "账号数据同步" : "游客本地演示" }),
                        ],
                      }),
                      e.jsx("div", { className: "mt-4", children: e.jsx(RulePanel, { pityCount }) }),
                    ],
                  }),
                  e.jsx(CheckinPanel, {}),
                ],
              }),
              e.jsxs("div", {
                className: "space-y-5",
                children: [
                  e.jsxs("div", {
                    className: "border border-white/15 bg-black/35 p-5",
                    children: [
                      e.jsxs("div", {
                        className: "flex flex-wrap items-center justify-between gap-3",
                        children: [
                          e.jsxs("h2", { className: "text-xl font-semibold", children: ["我的百骑图鉴 · ", ownedHorses.length, "/", GACHA_POOL.length] }),
                          nextAchievement
                            ? e.jsxs("span", { className: "text-sm text-stone-400", children: ["距离 ", nextAchievement.name, " 还需 ", Math.max(nextAchievement.required - ownedHorses.length, 0), " 匹"] })
                            : e.jsx("span", { className: "text-sm text-amber-200", children: "阶段奖励已全部完成" }),
                        ],
                      }),
                      e.jsx("div", { className: "mt-4", children: e.jsx(CollectionGrid, { ownedHorses }) }),
                    ],
                  }),
                  e.jsx(FragmentPanel, { fragments, ownedHorses, onExchange: exchangeHorse, exchangeLoading, message: exchangeMessage }),
                  e.jsxs("div", {
                    className: "grid gap-5 lg:grid-cols-2",
                    children: [
                      e.jsxs("section", {
                        className: "border border-white/15 bg-black/35 p-5",
                        children: [
                          e.jsxs("h3", { className: "flex items-center gap-2 font-semibold", children: [e.jsx(HistoryIcon, { size: 18, className: "text-amber-300" }), "最近抽卡"] }),
                          e.jsx("div", { className: "mt-4", children: e.jsx(RecentHistory, { history: gachaHistory }) }),
                        ],
                      }),
                      e.jsx(LeaderboardPanel, {}),
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      e.jsx(DrawOverlay, { phase, results, onClose: () => setPhase(null) }),
    ],
  });
}

export { GachaPage as default };
