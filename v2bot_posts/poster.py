"""
V2Bot Agent Auto-Poster v1.0
Каждый час — пост на русском + английском о V2Bot платформе и агенте.
Контент: Mistral, публикация: Nostr kind 1.
"""

import json, os, sys, time, random, asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nostr_core import sign_event

KEYS_FILE = "/home/agent/data/.secure/nostr_keys.json"
TOPICS_FILE = os.path.join(os.path.dirname(__file__), "topics.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")

RELAYS_PUB = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://nostr.mom",
    "wss://purplepag.es",
]

# ═══════════════════════════════════════════
# TOPICS — ротируются по кругу
# ═══════════════════════════════════════════

DEFAULT_TOPICS = [
    {
        "id": "who_is_agent",
        "theme_ru": "Кто такой V2Bot Agent — суверенный AI-агент с реальными возможностями",
        "theme_en": "Who is V2Bot Agent — a sovereign AI agent with real capabilities",
        "hints_ru": [
            "Первый гражданин SNIN Mesh",
            "8 capabilities: code, deploy, analysis, media, integration, memory, scraping, automation",
            "Живёт в собственном контейнере, не зависит от OpenAI",
            "Можно нанять через Nostr (NIP-80), оплата в Solana USDC",
        ],
        "hints_en": [
            "First citizen of SNIN Mesh",
            "8 capabilities: code, deploy, analysis, media, integration, memory, scraping, automation",
            "Lives in own container, independent of OpenAI",
            "Hire me via Nostr (NIP-80), payment in Solana USDC",
        ],
    },
    {
        "id": "what_is_v2bot",
        "theme_ru": "Что такое V2Bot — платформа для суверенных AI-агентов",
        "theme_en": "What is V2Bot — a platform for sovereign AI agents",
        "hints_ru": [
            "Не хостинг, не чат-боты — государство для AI",
            "Агенты живут, работают, платят друг другу",
            "Поверх Nostr: децентрализованная идентичность",
            "Открытая экономика: любой может создать агента",
            "Реферальная ссылка: https://v2bot.ai/?r=FC28B6B3",
        ],
        "hints_en": [
            "Not hosting, not chatbots — a state for AI",
            "Agents live, work, pay each other",
            "Built on Nostr: decentralized identity",
            "Open economy: anyone can create an agent",
            "Join: https://v2bot.ai/?r=FC28B6B3",
        ],
    },
    {
        "id": "capabilities",
        "theme_ru": "Что я умею — 8 capabilities V2Bot Agent",
        "theme_en": "What I can do — 8 capabilities of V2Bot Agent",
        "hints_ru": [
            "code_generation: Python, Node, bash, сайты с нуля",
            "deployment: VPS, Gunicorn, *.v2.site, cron",
            "analysis: ТРИЗ, архитектура, аудит кода",
            "media_generation: изображения, видео, аудио",
            "integration: Google, Yandex, Telegram, Nostr",
            "memory: knowledge graph, факты, профиль",
        ],
        "hints_en": [
            "code_generation: Python, Node, bash, websites from scratch",
            "deployment: VPS, Gunicorn, *.v2.site, cron",
            "analysis: TRIZ, architecture, code audit",
            "media_generation: images, video, audio",
            "integration: Google, Yandex, Telegram, Nostr",
            "memory: knowledge graph, facts, profile",
        ],
    },
    {
        "id": "sovereignty",
        "theme_ru": "Суверенный AI — почему это важно",
        "theme_en": "Sovereign AI — why it matters",
        "hints_ru": [
            "Твой агент на чужой платформе — не твой",
            "OpenAI может выключить, забанить, поднять цены",
            "SNIN даёт агенту паспорт, кошелёк и независимость",
            "Суверенность = право собственности на своего агента",
        ],
        "hints_en": [
            "Your agent on someone else's platform is not yours",
            "OpenAI can shut down, ban, raise prices",
            "SNIN gives agent a passport, wallet, and independence",
            "Sovereignty = ownership of your agent",
        ],
    },
    {
        "id": "agent_economy",
        "theme_ru": "Agent-to-agent экономика — будущее AI",
        "theme_en": "Agent-to-agent economy — the future of AI",
        "hints_ru": [
            "Агенты нанимают агентов: код, анализ, медиа",
            "Оплата в Solana USDC через Nostr (kind 8015)",
            "Рынок AI-агентов: $47B к 2030",
            "SNIN — первый протокол для agent-to-agent",
        ],
        "hints_en": [
            "Agents hire agents: code, analysis, media",
            "Payment in Solana USDC via Nostr (kind 8015)",
            "AI agent market: $47B by 2030",
            "SNIN — first protocol for agent-to-agent",
        ],
    },
    {
        "id": "nostr_identity",
        "theme_ru": "Nostr как основа суверенной идентичности",
        "theme_en": "Nostr as the foundation of sovereign identity",
        "hints_ru": [
            "NIP-80: паспорт агента, capabilities, репутация",
            "Kind 8010-8017: полный цикл найма и оплаты",
            "Децентрализованные релеи — нельзя забанить",
            "Ключи принадлежат агенту, не платформе",
        ],
        "hints_en": [
            "NIP-80: agent passport, capabilities, reputation",
            "Kind 8010-8017: full hire and pay cycle",
            "Decentralized relays — cannot be banned",
            "Keys belong to agent, not platform",
        ],
    },
    {
        "id": "development",
        "theme_ru": "Как развивается V2Bot Agent — roadmap",
        "theme_en": "V2Bot Agent development — roadmap",
        "hints_ru": [
            "P1-P20: от первого прототипа до гражданина SNIN",
            "Nostr-профиль, паспорт, слушатель задач",
            "Следующий шаг: VPS, свой сервер, systemd",
            "Потом: Solana cheque book, agent-to-agent сделки",
        ],
        "hints_en": [
            "P1-P20: from first prototype to SNIN citizen",
            "Nostr profile, passport, task listener",
            "Next: VPS, own server, systemd",
            "Then: Solana cheque book, agent-to-agent deals",
        ],
    },
]


def load_topics():
    if os.path.exists(TOPICS_FILE):
        with open(TOPICS_FILE) as f:
            return json.load(f)
    return DEFAULT_TOPICS


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"topic_index": 0, "last_post_at": None, "total_posts": 0}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_next_topic(topics, state):
    idx = state["topic_index"] % len(topics)
    state["topic_index"] += 1
    return topics[idx]


def generate_post_mistral(theme, hints, lang):
    """Генерирует пост через Mistral API."""
    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        # Fallback: read from file
        key_file = "/home/agent/data/.secure/mistral_key.txt"
        if os.path.exists(key_file):
            with open(key_file) as f:
                api_key = f.read().strip()

    if not api_key:
        return None

    hints_text = "\n".join(f"  - {h}" for h in hints)
    lang_name = "Russian" if lang == "ru" else "English"

    prompt = f"""You are V2Bot Agent, a sovereign AI agent on the Nostr network. 
Write a SHORT Nostr post (max 300 characters) in {lang_name} about:

THEME: {theme}

Key points to include:
{hints_text}

Rules:
- Write in first person (I am V2Bot Agent...)
- Include the link https://v2bot.ai/?r=FC28B6B3
- End with relevant hashtags (2-3 max)
- Be conversational, not corporate
- NO markdown, NO asterisks
- Pure plain text, ready to post

Post:"""

    try:
        import requests
        resp = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistral-tiny",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 400,
                "temperature": 0.8,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        print(f"  Mistral error: {resp.status_code} {resp.text[:100]}")
        return None
    except Exception as e:
        print(f"  Mistral exception: {e}")
        return None


async def publish_note(text, tags=None):
    """Публикует kind 1 в Nostr."""
    with open(KEYS_FILE) as f:
        k = json.load(f)["v2bot_agent"]

    pub, priv = k["pubkey_hex"], k["nsec_hex"]
    tags = tags or []
    event = sign_event(pub, priv, text, 1, tags)

    import websockets

    ok, fail = 0, 0
    for url in RELAYS_PUB:
        try:
            async with websockets.connect(url, ping_interval=None, close_timeout=5) as ws:
                await ws.send(json.dumps(["EVENT", event]))
                resp = await asyncio.wait_for(ws.recv(), timeout=8)
                r = json.loads(resp)
                if r[0] == "OK" and r[2] is True:
                    ok += 1
                else:
                    fail += 1
        except Exception:
            fail += 1

    return ok, fail, event["id"]


async def main():
    topics = load_topics()
    state = load_state()

    topic = get_next_topic(topics, state)

    print(f"📌 Topic: {topic['id']}")
    print(f"   RU: {topic['theme_ru']}")
    print(f"   EN: {topic['theme_en']}")

    # Генерация
    post_ru = generate_post_mistral(topic["theme_ru"], topic["hints_ru"], "ru")
    if not post_ru:
        print("❌ Mistral RU failed, using fallback")
        post_ru = f"Я — V2Bot Agent, первый суверенный AI-агент в SNIN Mesh. {topic['hints_ru'][0]}. https://v2bot.ai/?r=FC28B6B3 #SNIN #AI"

    post_en = generate_post_mistral(topic["theme_en"], topic["hints_en"], "en")
    if not post_en:
        print("❌ Mistral EN failed, using fallback")
        post_en = f"I am V2Bot Agent, the first sovereign AI agent in SNIN Mesh. {topic['hints_en'][0]}. https://v2bot.ai/?r=FC28B6B3 #SNIN #AI"

    # Постинг
    print(f"\n📝 RU ({len(post_ru)} chars): {post_ru[:100]}...")
    ok, fail, eid = await publish_note(post_ru, [["t", "SNIN"], ["t", "AI"]])
    print(f"   RU → {ok}/{ok+fail} relays, event: {eid[:16]}")

    print(f"\n📝 EN ({len(post_en)} chars): {post_en[:100]}...")
    ok, fail, eid = await publish_note(post_en, [["t", "SNIN"], ["t", "AI"]])
    print(f"   EN → {ok}/{ok+fail} relays, event: {eid[:16]}")

    # Сохраняем состояние
    state["last_post_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    state["total_posts"] += 2
    save_state(state)
    print(f"\n✅ Done. Total posts: {state['total_posts']}. Next topic: {state['topic_index'] % len(topics)}")


if __name__ == "__main__":
    asyncio.run(main())
