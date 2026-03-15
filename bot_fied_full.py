
import logging
import sqlite3
import random
import asyncio
import time
import os
import hashlib

import requests
from PIL import Image
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = "8550175395:AAEgfAlvO6VrORJn-5SEn80MTgu2NcSLMu8"

logging.basicConfig(level=logging.INFO)

conn = sqlite3.connect("game.db", check_same_thread=False)
cursor = conn.cursor()

# ---------------- DB HELPERS ----------------

def ensure_table():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players(
        user_id INTEGER PRIMARY KEY,
        money INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dealership(
        car TEXT PRIMARY KEY,
        stock INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS garage(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner INTEGER,
        car TEXT,
        speed REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS car_market(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        car TEXT,
        seller INTEGER,
        price INTEGER,
        speed REAL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mine_rewards(
        user_id INTEGER PRIMARY KEY,
        sharpening_stones INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS player_items(
        user_id INTEGER,
        item_key TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, item_key)
    )
    """)
    conn.commit()

def get_columns(table_name: str):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def ensure_column(table_name: str, column_sql: str):
    col_name = column_sql.split()[0]
    if col_name not in get_columns(table_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")
        conn.commit()

ensure_table()
ensure_column("players", "city TEXT DEFAULT 'Новоград'")
ensure_column("players", "taxi_level INTEGER DEFAULT 1")
ensure_column("players", "taxi_rides INTEGER DEFAULT 0")
ensure_column("players", "char_created INTEGER DEFAULT 0")
ensure_column("players", "char_top TEXT DEFAULT ''")
ensure_column("players", "char_bottom TEXT DEFAULT ''")
ensure_column("players", "char_hair TEXT DEFAULT ''")
ensure_column("car_market", "seller_name TEXT DEFAULT ''")

# ---------------- DATA ----------------

CARS = {
    "Chevrolet Bel Air": {"class": "Низкий", "price": 80000, "speed": 0.75, "race": 32, "img": "https://files.catbox.moe/ubffmr.jpg"},
    "Ford Taurus": {"class": "Низкий", "price": 120000, "speed": 0.85, "race": 40, "img": "https://files.catbox.moe/z9uydr.jpg"},
    "Chevrolet Impala 1959": {"class": "Низкий", "price": 180000, "speed": 1.0, "race": 48, "img": "https://files.catbox.moe/lvmnem.jpg"},
    "Skoda Favorit": {"class": "Средний", "price": 350000, "speed": 1.05, "race": 55, "img": "https://files.catbox.moe/ujcilp.jpg"},
    "Chevrolet Monte Carlo": {"class": "Средний", "price": 520000, "speed": 1.15, "race": 65, "img": "https://files.catbox.moe/mn1bc3.jpg"},
    "Mercedes W123": {"class": "Средний", "price": 650000, "speed": 1.2, "race": 72, "img": "https://files.catbox.moe/ov605q.jpg"},
    "Mazda RX-7": {"class": "Средний", "price": 950000, "speed": 1.35, "race": 88, "img": "https://files.catbox.moe/q98osg.jpg"},
    "Dodge Viper RT": {"class": "Высший", "price": 2200000, "speed": 1.55, "race": 105, "img": "https://files.catbox.moe/7h8mne.jpg"},
    "Ferrari 512": {"class": "Высший", "price": 3800000, "speed": 1.75, "race": 130, "img": "https://files.catbox.moe/gp2vbs.jpg"},
    "Lamborghini Countach": {"class": "Премиум", "price": 6500000, "speed": 1.95, "race": 150, "img": "https://files.catbox.moe/o5e7nj.jpg"},
    "Ferrari F40": {"class": "Премиум", "price": 9500000, "speed": 2.2, "race": 180, "img": "https://files.catbox.moe/wx6tjp.jpg"},
}

TAXI_RENTALS = [
    {"name": "Checker Marathon (1953)", "speed": 0.65, "rent": 180, "level": 1, "img": "https://files.catbox.moe/n2qd4c.jpg"},
    {"name": "VAZ 2107", "speed": 0.78, "rent": 260, "level": 2, "img": "https://files.catbox.moe/k9zq9g.jpg"},
    {"name": "ГАЗ Волга", "speed": 0.92, "rent": 360, "level": 3, "img": "https://files.catbox.moe/w6u3a0.jpg"},
    {"name": "Ford Crown Victoria", "speed": 1.05, "rent": 480, "level": 4, "img": "https://files.catbox.moe/7tpi8l.jpg"},
    {"name": "Peugeot 301", "speed": 1.15, "rent": 620, "level": 5, "img": "https://files.catbox.moe/7t4y7m.jpg"},
]

CITY_INDEX = {"Новоград": 1, "Инд-Сити": 2, "Форс-Сити": 3, "Вегаспорт": 4, "Пятый город": 5}
ALL_CITIES = list(CITY_INDEX.keys())

LAYER_BASE_WITH_ARMS = "https://files.catbox.moe/5yyuex.jpg"
LAYER_BASE_NO_ARMS = "https://files.catbox.moe/ljyuyk.jpg"

CHAR_TOPS = [
    {
        "key": "beach_shirt",
        "name": "Пляжная рубашка",
        "desc": "Мы что на вайс сити?.",
        "img": "https://files.catbox.moe/urpfnw.png",
        "layer": "https://files.catbox.moe/urpfnw.png",
        "special_bottom": False,
        "hide_arms": False,
    },
    {
        "key": "two_color_shirt",
        "name": "Двуцветная рубашка",
        "desc": "Слишком стильная, чтобы её игнорировать.",
        "img": "https://files.catbox.moe/3fxn0n.png",
        "layer": "https://files.catbox.moe/3fxn0n.png",
        "special_bottom": False,
        "hide_arms": False,
    },
    {
        "key": "green_shirt",
        "name": "Зелёная рубашка",
        "desc": "Правило простое: клетки есть - можно играть в крестики нолики.",
        "img": "https://files.catbox.moe/wtk2vh.png",
        "layer": "https://files.catbox.moe/wtk2vh.png",
        "special_bottom": False,
        "hide_arms": True,
    },
    {
        "key": "red_black_top",
        "name": "Красно-черный топ",
        "desc": "Для настящих секси-пекси.",
        "img": "https://files.catbox.moe/dat5qb.png",
        "layer": "https://files.catbox.moe/dat5qb.png",
        "special_bottom": True,
        "hide_arms": False,
    },
]

CHAR_BOTTOMS = [
    {
        "key": "camo_pants",
        "name": "Камуфляжные штаны",
        "desc": "Выглядят так, будто готовы к любому замесу.",
        "img": "https://files.catbox.moe/w03bea.png",
        "layer": "https://files.catbox.moe/w03bea.png",
    },
    {
        "key": "jeans",
        "name": "Джинсы",
        "desc": "Простые, надёжные и всегда уместные.",
        "img": "https://files.catbox.moe/a3qlw4.png",
        "layer": "https://files.catbox.moe/a3qlw4.png",
    },
    {
        "key": "color_shorts",
        "name": "Разноцветные шорты",
        "desc": "Если скучный стиль — не про тебя.",
        "img": "https://files.catbox.moe/n8ujb4.png",
        "layer": "https://files.catbox.moe/n8ujb4.png",
    },
    {
        "key": "gray_shorts",
        "name": "Серые шорты",
        "desc": "Коротко, удобно, без лишних вопросов.",
        "img": "https://files.catbox.moe/hxj54k.png",
        "layer": "https://files.catbox.moe/hxj54k.png",
    },
]

CHAR_HAIRS = [
    {
        "key": "korean_perm",
        "name": "Корейский перм",
        "desc": "Аккуратная укладка с характером.",
        "img": "https://files.catbox.moe/e1jwcr.png",
        "layer": "https://files.catbox.moe/e1jwcr.png",
    },
    {
        "key": "wolfcut_red",
        "name": "Рыжий вулфкат",
        "desc": "Стрижка, которая сразу заявляет о себе.",
        "img": "https://files.catbox.moe/jvf9j3.png",
        "layer": "https://files.catbox.moe/jvf9j3.png",
    },
    {
        "key": "vuksiya",
        "name": "Вуксия",
        "desc": "Ты что блять, японский генерал?.",
        "img": "https://files.catbox.moe/fpapif.png",
        "layer": "https://files.catbox.moe/fpapif.png",
    },
]

STARTER_ITEMS = [
    "sharpening_stones",
    "zatocka",
    "super_zatocka",
    "garage_upgrade",
    "warehouse_upgrade",
    "gpu_cards",
]

cursor.execute("SELECT COUNT(*) FROM dealership")
if cursor.fetchone()[0] == 0:
    for car in CARS:
        cursor.execute("INSERT INTO dealership(car, stock) VALUES(?, ?)", (car, 500))
    conn.commit()

mine_sessions = {}
factory_sessions = {}
taxi_orders = {}
next_taxi_order_id = 1

# ---------------- IMAGE BUILDERS ----------------

CACHE_DIR = "image_cache"
GENERATED_DIR = "generated_chars"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)

def cached_мdownload(url: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1] or ".img"
    name = hashlib.md5(url.encode("utf-8")).hexdigest() + ext
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path):
        return path
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    with open(path, "wb") as f:
        f.write(response.content)
    return path

def open_rgba(url: str) -> Image.Image:
    path = cached_download(url)
    return Image.open(path).convert("RGBA")

def get_top_meta(key: str):
    for item in CHAR_TOPS:
        if item["key"] == key:
            return item
    return None

def get_bottom_meta(key: str):
    for item in CHAR_BOTTOMS:
        if item["key"] == key:
            return item
    return None

def get_hair_meta(key: str):
    for item in CHAR_HAIRS:
        if item["key"] == key:
            return item
    return None

def build_layered_character(top_key: str = "", bottom_key: str = "", hair_key: str = "") -> str:
    top = get_top_meta(top_key) if top_key else None
    bottom = get_bottom_meta(bottom_key) if bottom_key else None
    hair = get_hair_meta(hair_key) if hair_key else None

    base_url = LAYER_BASE_NO_ARMS if top and top["hide_arms"] else LAYER_BASE_WITH_ARMS
    base = open_rgba(base_url)

    layers = []
    if top and top["special_bottom"]:
        layers.append(top["layer"])
        if bottom:
            layers.append(bottom["layer"])
    else:
        if bottom:
            layers.append(bottom["layer"])
        if top:
            layers.append(top["layer"])
    if hair:
        layers.append(hair["layer"])

    for layer_url in layers:
        layer = open_rgba(layer_url)
        if layer.size != base.size:
            layer = layer.resize(base.size)
        base.alpha_composite(layer)

    key = f"{top_key}_{bottom_key}_{hair_key}_{'noarms' if top and top['hide_arms'] else 'arms'}"
    out_path = os.path.join(GENERATED_DIR, hashlib.md5(key.encode("utf-8")).hexdigest() + ".png")
    base.save(out_path)
    return out_path

# ---------------- PLAYER HELPERS ----------------

def ensure_player_items(uid: int):
    for item_key in STARTER_ITEMS:
        cursor.execute(
            "INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)",
            (uid, item_key),
        )
    conn.commit()

def get_player(uid: int):
    cursor.execute("""
        SELECT user_id, city, money, taxi_level, taxi_rides, char_created, char_top, char_bottom, char_hair
        FROM players WHERE user_id=?
    """, (uid,))
    row = cursor.fetchone()
    if not row:
        cursor.execute(
            "INSERT INTO players(user_id, city, money, taxi_level, taxi_rides, char_created, char_top, char_bottom, char_hair) VALUES(?,?,?,?,?,?,?,?,?)",
            (uid, "Новоград", 100000, 1, 0, 0, "", "", ""),
        )
        cursor.execute("INSERT OR IGNORE INTO mine_rewards(user_id, sharpening_stones) VALUES(?, ?)", (uid, 0))
        conn.commit()
        ensure_player_items(uid)
        return {
            "city": "Новоград",
            "money": 100000,
            "taxi_level": 1,
            "taxi_rides": 0,
            "char_created": 0,
            "char_top": "",
            "char_bottom": "",
            "char_hair": "",
        }
    cursor.execute("INSERT OR IGNORE INTO mine_rewards(user_id, sharpening_stones) VALUES(?, ?)", (uid, 0))
    conn.commit()
    ensure_player_items(uid)
    return {
        "city": row[1],
        "money": row[2],
        "taxi_level": row[3],
        "taxi_rides": row[4],
        "char_created": row[5],
        "char_top": row[6] or "",
        "char_bottom": row[7] or "",
        "char_hair": row[8] or "",
    }

def get_money(uid: int) -> int:
    return get_player(uid)["money"]

def add_money(uid: int, amount: int):
    cursor.execute("UPDATE players SET money = money + ? WHERE user_id=?", (amount, uid))
    conn.commit()

def set_city(uid: int, city: str):
    cursor.execute("UPDATE players SET city=? WHERE user_id=?", (city, uid))
    conn.commit()

def add_sharpening_stone(uid: int, amount: int = 1):
    cursor.execute("INSERT OR IGNORE INTO mine_rewards(user_id, sharpening_stones) VALUES(?, ?)", (uid, 0))
    cursor.execute("UPDATE mine_rewards SET sharpening_stones = sharpening_stones + ? WHERE user_id=?", (amount, uid))
    cursor.execute("UPDATE player_items SET amount = amount + ? WHERE user_id=? AND item_key='sharpening_stones'", (amount, uid))
    conn.commit()

def get_item_amount(uid: int, item_key: str) -> int:
    ensure_player_items(uid)
    cursor.execute("SELECT amount FROM player_items WHERE user_id=? AND item_key=?", (uid, item_key))
    row = cursor.fetchone()
    return row[0] if row else 0

def add_taxi_ride(uid: int):
    cursor.execute("UPDATE players SET taxi_rides = taxi_rides + 1 WHERE user_id=?", (uid,))
    conn.commit()
    cursor.execute("SELECT taxi_rides, taxi_level FROM players WHERE user_id=?", (uid,))
    rides, level = cursor.fetchone()
    new_level = level
    if rides >= 40:
        new_level = 5
    elif rides >= 20:
        new_level = 4
    elif rides >= 10:
        new_level = 3
    elif rides >= 5:
        new_level = 2
    if new_level != level:
        cursor.execute("UPDATE players SET taxi_level=? WHERE user_id=?", (new_level, uid))
        conn.commit()
        return new_level
    return None

def set_char_part(uid: int, field_name: str, value: str):
    cursor.execute(f"UPDATE players SET {field_name}=? WHERE user_id=?", (value, uid))
    conn.commit()

def set_char_created(uid: int, created: int):
    cursor.execute("UPDATE players SET char_created=? WHERE user_id=?", (created, uid))
    conn.commit()

def reset_character(uid: int):
    cursor.execute(
        "UPDATE players SET char_created=0, char_top='', char_bottom='', char_hair='' WHERE user_id=?",
        (uid,),
    )
    conn.commit()

def character_summary_text(player: dict):
    top = get_top_meta(player["char_top"])
    bottom = get_bottom_meta(player["char_bottom"])
    hair = get_hair_meta(player["char_hair"])
    return (
        f"Верхняя одежда: {top['name'] if top else 'Не выбрано'}\n"
        f"Нижняя одежда: {bottom['name'] if bottom else 'Не выбрано'}\n"
        f"Прическа: {hair['name'] if hair else 'Не выбрано'}"
    )

def has_any_car(uid: int) -> bool:
    cursor.execute("SELECT 1 FROM garage WHERE owner=? LIMIT 1", (uid,))
    return cursor.fetchone() is not None

# ---------------- RENDER HELPERS ----------------

async def render_text(target_message, text: str, reply_markup=None):
    try:
        await target_message.edit_text(text, reply_markup=reply_markup)
    except Exception:
        chat_id = target_message.chat_id
        try:
            await target_message.delete()
        except Exception:
            pass
        return await target_message.get_bot().send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
    return target_message

async def render_photo(target_message, photo_url_or_path: str, caption: str, reply_markup=None):
    media_source = photo_url_or_path
    if os.path.exists(photo_url_or_path):
        media_source = open(photo_url_or_path, "rb")
    try:
        await target_message.edit_media(
            media=InputMediaPhoto(media=media_source, caption=caption),
            reply_markup=reply_markup
        )
    except Exception:
        chat_id = target_message.chat_id
        try:
            await target_message.delete()
        except Exception:
            pass
        if os.path.exists(photo_url_or_path):
            with open(photo_url_or_path, "rb") as f:
                return await target_message.get_bot().send_photo(chat_id=chat_id, photo=f, caption=caption, reply_markup=reply_markup)
        return await target_message.get_bot().send_photo(chat_id=chat_id, photo=photo_url_or_path, caption=caption, reply_markup=reply_markup)
    finally:
        if hasattr(media_source, "close"):
            media_source.close()
    return target_message

# ---------------- INTRO / CHARACTER CREATION ----------------

def intro_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Создать персонажа", callback_data="char_begin")]])

async def render_intro_message(target_message):
    text = (
        "Приветствую тебя в MetroLife! В мире где все может измениться в любую секунду!\n"
        "Будь кем угодно! Зарабатывай деньги покупай имущество и захвати рынок игры!\n\n"
        "Только для начала определимся как ты будешь выглядеть."
    )
    return await render_text(target_message, text, reply_markup=intro_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    player = get_player(uid)
    if not player["char_created"]:
        await update.message.reply_text(
            "Приветствую тебя в MetroLife! В мире где все может измениться в любую секунду!\n"
            "Будь кем угодно! Зарабатывай деньги покупай имущество и захвати рынок игры!\n\n"
            "Только для начала определимся как ты будешь выглядеть.",
            reply_markup=intro_keyboard()
        )
        return
    await send_main_menu_message(update.message, update.effective_user, player)

async def character_hub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    image = build_layered_character(player["char_top"], player["char_bottom"], player["char_hair"])

    if player["char_top"] and player["char_bottom"] and player["char_hair"]:
        text = f"{character_summary_text(player)}\n\nНравится ли тебе?"
        kb = [[InlineKeyboardButton("Да", callback_data="char_confirm_yes"),
               InlineKeyboardButton("Нет", callback_data="char_confirm_no")]]
    else:
        text = (
            "И так. Это ты.\n"
            "Но чего-то не хватает...\n"
            "Точно! Выбери себе одежду и прическу.\n\n"
            f"{character_summary_text(player)}"
        )
        kb = [
            [InlineKeyboardButton("Верхняя одежда", callback_data="char_pick_top")],
            [InlineKeyboardButton("Нижняя одежда", callback_data="char_pick_bottom")],
            [InlineKeyboardButton("Прическа", callback_data="char_pick_hair")],
        ]
        kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="char_begin")])

    await render_photo(query.message, image, text, reply_markup=InlineKeyboardMarkup(kb))

async def char_begin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await character_hub(update, context)

async def char_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    if not (player["char_top"] and player["char_bottom"] and player["char_hair"]):
        await query.answer("Сначала выбери все элементы")
        return
    set_char_created(query.from_user.id, 1)
    await main_menu(update, context)

async def char_confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reset_character(query.from_user.id)
    await render_intro_message(query.message)

async def char_pick_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    idx = context.user_data.get("char_top_idx", 0) % len(CHAR_TOPS)
    item = CHAR_TOPS[idx]
    preview = build_layered_character(item["key"], player["char_bottom"], player["char_hair"])
    text = f"{item['name']}\n\n{item['desc']}\n\nНажми подтвердить что бы выбрать данную кофту"
    kb = [[InlineKeyboardButton("⬅️", callback_data="char_top_prev"),
           InlineKeyboardButton("Подтвердить", callback_data=f"char_set_top_{item['key']}"),
           InlineKeyboardButton("➡️", callback_data="char_top_next")]]
    await render_photo(query.message, preview, text, reply_markup=InlineKeyboardMarkup(kb))

async def char_top_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_top_idx"] = (context.user_data.get("char_top_idx", 0) - 1) % len(CHAR_TOPS)
    await char_pick_top(update, context)

async def char_top_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_top_idx"] = (context.user_data.get("char_top_idx", 0) + 1) % len(CHAR_TOPS)
    await char_pick_top(update, context)

async def char_set_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("char_set_top_", "")
    set_char_part(query.from_user.id, "char_top", key)
    await character_hub(update, context)

async def char_pick_bottom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    idx = context.user_data.get("char_bottom_idx", 0) % len(CHAR_BOTTOMS)
    item = CHAR_BOTTOMS[idx]
    preview = build_layered_character(player["char_top"], item["key"], player["char_hair"])
    text = f"{item['name']}\n\n{item['desc']}\n\nНажми подтвердить что бы выбрать данный элемент"
    kb = [[InlineKeyboardButton("⬅️", callback_data="char_bottom_prev"),
           InlineKeyboardButton("Подтвердить", callback_data=f"char_set_bottom_{item['key']}"),
           InlineKeyboardButton("➡️", callback_data="char_bottom_next")]]
    await render_photo(query.message, preview, text, reply_markup=InlineKeyboardMarkup(kb))

async def char_bottom_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_bottom_idx"] = (context.user_data.get("char_bottom_idx", 0) - 1) % len(CHAR_BOTTOMS)
    await char_pick_bottom(update, context)

async def char_bottom_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_bottom_idx"] = (context.user_data.get("char_bottom_idx", 0) + 1) % len(CHAR_BOTTOMS)
    await char_pick_bottom(update, context)

async def char_set_bottom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("char_set_bottom_", "")
    set_char_part(query.from_user.id, "char_bottom", key)
    await character_hub(update, context)

async def char_pick_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    idx = context.user_data.get("char_hair_idx", 0) % len(CHAR_HAIRS)
    item = CHAR_HAIRS[idx]
    preview = build_layered_character(player["char_top"], player["char_bottom"], item["key"])
    text = f"{item['name']}\n\n{item['desc']}\n\nНажми подтвердить что бы выбрать данную прическу"
    kb = [[InlineKeyboardButton("⬅️", callback_data="char_hair_prev"),
           InlineKeyboardButton("Подтвердить", callback_data=f"char_set_hair_{item['key']}"),
           InlineKeyboardButton("➡️", callback_data="char_hair_next")]]
    await render_photo(query.message, preview, text, reply_markup=InlineKeyboardMarkup(kb))

async def char_hair_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_hair_idx"] = (context.user_data.get("char_hair_idx", 0) - 1) % len(CHAR_HAIRS)
    await char_pick_hair(update, context)

async def char_hair_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["char_hair_idx"] = (context.user_data.get("char_hair_idx", 0) + 1) % len(CHAR_HAIRS)
    await char_pick_hair(update, context)

async def char_set_hair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.replace("char_set_hair_", "")
    set_char_part(query.from_user.id, "char_hair", key)
    await character_hub(update, context)

# ---------------- MAIN MENU / PROFILE / INVENTORY ----------------

def main_menu_keyboard(uid: int):
    rows = [
        [InlineKeyboardButton("🏙 Город", callback_data="city_menu")],
        [InlineKeyboardButton("💼 Работа", callback_data="work_menu")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile_menu"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory_menu")],
    ]
    if has_any_car(uid):
        rows.append([InlineKeyboardButton("🚘 Гараж", callback_data="garage")])
    return InlineKeyboardMarkup(rows)

async def send_main_menu_message(message, user, player: dict):
    image = build_layered_character(player["char_top"], player["char_bottom"], player["char_hair"])
    text = (
        f"Привет {user.first_name}! Ты сейчас находишся в городе {player['city']}\n"
        f"На счету у тебя: {player['money']}$\n\n"
        f"Для более полной информации нажми кнопку профиль"
    )
    with open(image, "rb") as f:
        await message.reply_photo(photo=f, caption=text, reply_markup=main_menu_keyboard(user.id))

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    player = get_player(uid)

    if not player["char_created"]:
        await render_intro_message(query.message)
        return

    image = build_layered_character(player["char_top"], player["char_bottom"], player["char_hair"])
    text = (
        f"Привет {query.from_user.first_name}! Ты сейчас находишся в городе {player['city']}\n"
        f"На счету у тебя: {player['money']}$\n\n"
        f"Для более полной информации нажми кнопку профиль"
    )
    await render_photo(query.message, image, text, reply_markup=main_menu_keyboard(uid))

async def profile_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    player = get_player(uid)
    text = (
        f"👤 Профиль\n\n"
        f"Имя: {query.from_user.first_name}\n"
        f"Город: {player['city']}\n"
        f"Баланс: {player['money']}$\n"
        f"Уровень таксиста: {player['taxi_level']}\n"
        f"Поездок таксиста: {player['taxi_rides']}\n\n"
        f"{character_summary_text(player)}"
    )
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

async def inventory_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    text = (
        "🎒 Инвентарь :\n\n"
        f"Точильные камни: {get_item_amount(uid, 'sharpening_stones')}\n"
        f"Заточка: {get_item_amount(uid, 'zatocka')}\n"
        f"Супер заточка: {get_item_amount(uid, 'super_zatocka')}\n"
        f"Дополнение гаража: {get_item_amount(uid, 'garage_upgrade')}\n"
        f"Дополнение склада: {get_item_amount(uid, 'warehouse_upgrade')}\n"
        f"Видеокарты: {get_item_amount(uid, 'gpu_cards')}\n"
    )
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

# ---------------- CITY / WORK ----------------

async def work_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    buttons = [[InlineKeyboardButton("🚕 Таксист", callback_data="taxi_driver_menu")]]
    if city == "Новоград":
        buttons.insert(0, [InlineKeyboardButton("💼 Начальные работы", callback_data="starter_jobs")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="main")])
    await render_text(query.message, "💼 Работа", reply_markup=InlineKeyboardMarkup(buttons))

async def city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]

    if city == "Новоград":
        keyboard = [
            [InlineKeyboardButton("🏦 Банк Новограда", callback_data="placeholder_bank")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="placeholder_agency")],
            [InlineKeyboardButton("💼 Начальные работы", callback_data="starter_jobs")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Инд-Сити":
        keyboard = [
            [InlineKeyboardButton("🛒 Рынок", callback_data="placeholder_market")],
            [InlineKeyboardButton("💼 Работа", callback_data="work_menu")],
            [InlineKeyboardButton("🏦 Банк Инд-Сити", callback_data="placeholder_bank")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="placeholder_agency")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Форс-Сити":
        keyboard = [
            [InlineKeyboardButton("🚗 Автосалон", callback_data="dealership")],
            [InlineKeyboardButton("🏪 Авторынок", callback_data="market")],
            [InlineKeyboardButton("🏁 Гонки", callback_data="placeholder_race")],
            [InlineKeyboardButton("🔧 СТО", callback_data="placeholder_sto")],
            [InlineKeyboardButton("🏦 Банк Форс-Сити", callback_data="placeholder_bank")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="placeholder_agency")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Вегаспорт":
        keyboard = [
            [InlineKeyboardButton("🎰 Казино", callback_data="placeholder_casino")],
            [InlineKeyboardButton("🏛 Аукцион", callback_data="placeholder_auction")],
            [InlineKeyboardButton("⚙️ Крафт", callback_data="placeholder_craft")],
            [InlineKeyboardButton("🏦 Банк Вегаспорта", callback_data="placeholder_bank")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="placeholder_agency")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🏦 Банк", callback_data="placeholder_bank")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="placeholder_agency")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]

    await render_text(query.message, f"🏙 {city}", reply_markup=InlineKeyboardMarkup(keyboard))

async def placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Эта кнопка пока каркасом. Логику добавим дальше.")

async def travel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current_city = get_player(query.from_user.id)["city"]
    buttons = []
    for city in ALL_CITIES:
        if city != current_city:
            buttons.append([InlineKeyboardButton(city, callback_data=f"travel_{city}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")])
    await render_text(query.message, "Куда отправиться? (мгновенное перемещение-каркас)", reply_markup=InlineKeyboardMarkup(buttons))

async def travel_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("travel_", "")
    set_city(query.from_user.id, city)
    await render_text(query.message, f"Вы прибыли в {city}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏙 Меню города", callback_data="city_menu")]]))

# ---------------- TAXI ----------------

def get_distance(city_a: str, city_b: str) -> int:
    return abs(CITY_INDEX[city_a] - CITY_INDEX[city_b])

def get_taxi_payment(distance: int) -> int:
    if distance <= 1:
        return random.randint(300, 600)
    if distance == 2:
        return random.randint(600, 1200)
    return random.randint(1200, 2000)

def get_taxi_base_time(distance: int) -> int:
    if distance <= 1:
        return 60
    if distance == 2:
        return 120
    return 180

def get_selected_taxi_vehicle(context: ContextTypes.DEFAULT_TYPE, uid: int):
    return context.user_data.get(f"taxi_vehicle_{uid}")

def set_selected_taxi_vehicle(context: ContextTypes.DEFAULT_TYPE, uid: int, vehicle: dict):
    context.user_data[f"taxi_vehicle_{uid}"] = vehicle

def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins}м {secs}с"

async def finish_taxi_order_later(order_id: int, app):
    order = taxi_orders.get(order_id)
    if not order:
        return
    seconds = max(1, int(order["end_time"] - time.time()))
    await asyncio.sleep(seconds)

    order = taxi_orders.get(order_id)
    if not order or order["status"] != "in_progress":
        return

    order["status"] = "finished"

    if order["driver_type"] == "player":
        driver_uid = order["driver_id"]
        payout = max(0, order["payment"] - order["rental_cost"])
        add_money(driver_uid, payout)
        new_level = add_taxi_ride(driver_uid)
        try:
            await app.bot.send_message(
                chat_id=driver_uid,
                text=(
                    f"🚕 Поездка завершена\n\n"
                    f"Маршрут: {order['origin']} → {order['destination']}\n"
                    f"Машина: {order['vehicle_name']}\n"
                    f"Оплата: {order['payment']}$\n"
                    f"Аренда: {order['rental_cost']}$\n"
                    f"Вы получили: {payout}$"
                )
            )
            if new_level:
                await app.bot.send_message(chat_id=driver_uid, text=f"🎉 Уровень таксиста повышен! Теперь ваш уровень: {new_level}")
        except Exception:
            pass

    set_city(order["passenger_id"], order["destination"])
    try:
        await app.bot.send_message(chat_id=order["passenger_id"], text=f"🚕 Вы прибыли в {order['destination']}")
    except Exception:
        pass

async def taxi_npc_fallback(order_id: int, app):
    await asyncio.sleep(60)
    order = taxi_orders.get(order_id)
    if not order or order["status"] != "waiting":
        return

    order["status"] = "in_progress"
    order["driver_type"] = "npc"
    order["driver_id"] = 0
    order["driver_name"] = "Бот-таксист"
    order["vehicle_name"] = "Checker Marathon (1953)"
    order["vehicle_speed"] = 0.65
    order["rental_cost"] = 0
    ride_seconds = int(get_taxi_base_time(order["distance"]) / order["vehicle_speed"])
    order["end_time"] = time.time() + ride_seconds

    try:
        await app.bot.send_message(
            chat_id=order["passenger_id"],
            text=(
                f"🤖 Водитель не найден. Вас везёт бот.\n\n"
                f"Маршрут: {order['origin']} → {order['destination']}\n"
                f"Машина: Checker Marathon (1953)\n"
                f"Осталось времени: {format_seconds(ride_seconds)}"
            )
        )
    except Exception:
        pass

    app.create_task(finish_taxi_order_later(order_id, app))

async def taxi_call_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    current_city = get_player(query.from_user.id)["city"]
    buttons = []
    for city in ALL_CITIES:
        if city != current_city and CITY_INDEX[current_city] <= 4 and CITY_INDEX[city] <= 4:
            buttons.append([InlineKeyboardButton(city, callback_data=f"taxicall_{city}")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")])
    await render_text(query.message, "🚕 Куда вызвать такси?", reply_markup=InlineKeyboardMarkup(buttons))

async def taxi_call_to_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_taxi_order_id
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    player = get_player(uid)
    origin, money = player["city"], player["money"]
    destination = query.data.replace("taxicall_", "")
    distance = get_distance(origin, destination)
    payment = get_taxi_payment(distance)

    if money < payment:
        await render_text(query.message, f"Недостаточно денег для поездки.\nНужно: {payment}$\nУ вас: {money}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]]))
        return

    cursor.execute("UPDATE players SET money=money-? WHERE user_id=?", (payment, uid))
    conn.commit()

    order_id = next_taxi_order_id
    next_taxi_order_id += 1

    taxi_orders[order_id] = {
        "id": order_id,
        "passenger_id": uid,
        "passenger_name": query.from_user.full_name or str(uid),
        "origin": origin,
        "destination": destination,
        "distance": distance,
        "payment": payment,
        "status": "waiting",
        "driver_type": None,
        "driver_id": None,
        "driver_name": None,
        "vehicle_name": None,
        "vehicle_speed": None,
        "rental_cost": 0,
        "created_at": time.time(),
        "end_time": None,
    }

    context.application.create_task(taxi_npc_fallback(order_id, context.application))

    await render_text(
        query.message,
        f"🚕 Поиск водителя...\n\nМаршрут: {origin} → {destination}\nОплата: {payment}$\nЕсли водитель не найдётся за 1 минуту, вас отвезёт бот.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Обновить ⏳", callback_data=f"taxi_passenger_refresh_{order_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]
        ])
    )

async def taxi_passenger_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.replace("taxi_passenger_refresh_", ""))
    order = taxi_orders.get(order_id)

    if not order:
        await render_text(query.message, "Заказ не найден", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]]))
        return

    if order["status"] == "waiting":
        text = (
            f"🚕 Поиск водителя...\n\n"
            f"Маршрут: {order['origin']} → {order['destination']}\n"
            f"Оплата: {order['payment']}$\n"
            f"Если водитель не найдётся за 1 минуту, вас отвезёт бот."
        )
    elif order["status"] == "in_progress":
        left = int(order["end_time"] - time.time())
        text = (
            f"🚕 Поездка\n\n"
            f"Маршрут: {order['origin']} → {order['destination']}\n"
            f"Водитель: {order['driver_name']}\n"
            f"Машина: {order['vehicle_name']}\n"
            f"Осталось времени: {format_seconds(left)}"
        )
    else:
        text = f"🚕 Заказ завершён\n\nВы прибыли в {order['destination']}"

    await render_text(
        query.message,
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Обновить ⏳", callback_data=f"taxi_passenger_refresh_{order_id}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]
        ])
    )

async def taxi_driver_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    player = get_player(uid)
    vehicle = get_selected_taxi_vehicle(context, uid)
    vehicle_text = f"{vehicle['name']} | speed {vehicle['speed']} | аренда {vehicle['rent']}$" if vehicle else "не выбрана"

    keyboard = [
        [InlineKeyboardButton("🚕 Арендовать авто", callback_data="taxi_rental_menu")],
        [InlineKeyboardButton("🚗 Использовать своё авто", callback_data="taxi_own_car_menu")],
        [InlineKeyboardButton("📋 Доступные заказы", callback_data="taxi_orders_menu")],
        [InlineKeyboardButton("🧾 Текущая поездка", callback_data="taxi_current_trip")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="work_menu")]
    ]
    await render_text(
        query.message,
        f"🚕 Работа таксистом\n\nУровень таксиста: {player['taxi_level']}\nПоездок: {player['taxi_rides']}\nТекущая машина: {vehicle_text}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def taxi_rental_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    taxi_level = get_player(uid)["taxi_level"]

    i = context.user_data.get("taxi_rent_i", 0) % len(TAXI_RENTALS)
    rent = TAXI_RENTALS[i]
    lock_text = f"Требуется уровень таксиста: {rent['level']}" if taxi_level < rent["level"] else ""
    caption = f"{rent['name']}\n\nСкорость: {rent['speed']}\nЦена аренды: {rent['rent']}$\n{lock_text}"

    kb = [
        [InlineKeyboardButton("⬅️", callback_data="taxi_rent_prev"),
         InlineKeyboardButton("➡️", callback_data="taxi_rent_next")],
        [InlineKeyboardButton("Арендовать", callback_data=f"rent_pick_{i}")],
        [InlineKeyboardButton("Назад", callback_data="taxi_driver_menu")]
    ]
    await render_photo(query.message, rent["img"], caption, reply_markup=InlineKeyboardMarkup(kb))

async def taxi_rent_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["taxi_rent_i"] = (context.user_data.get("taxi_rent_i", 0) + 1) % len(TAXI_RENTALS)
    await taxi_rental_menu(update, context)

async def taxi_rent_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["taxi_rent_i"] = (context.user_data.get("taxi_rent_i", 0) - 1) % len(TAXI_RENTALS)
    await taxi_rental_menu(update, context)

async def taxi_rent_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    taxi_level = get_player(uid)["taxi_level"]
    idx = int(query.data.replace("rent_pick_", ""))
    rent = TAXI_RENTALS[idx]

    if taxi_level < rent["level"]:
        await query.answer("Недостаточный уровень таксиста")
        return

    set_selected_taxi_vehicle(context, uid, {
        "type": "rental",
        "name": rent["name"],
        "speed": rent["speed"],
        "rent": rent["rent"],
        "img": rent["img"],
    })

    await render_text(
        query.message,
        f"Вы арендовали:\n{rent['name']}\nСкорость: {rent['speed']}\nЦена аренды: {rent['rent']}$\n\nСтоимость списывается после завершения поездки.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]])
    )

async def taxi_own_car_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    cursor.execute("SELECT id, car, speed FROM garage WHERE owner=?", (uid,))
    cars = cursor.fetchall()
    if not cars:
        await render_text(query.message, "У вас нет своих машин в гараже", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]]))
        return

    text = "🚗 Выберите свою машину для такси\n\n"
    kb = []
    for cid, car, speed in cars:
        text += f"{cid} | {car} | speed {speed}\n"
        kb.append([InlineKeyboardButton(f"Использовать {car}", callback_data=f"taxi_use_own_{cid}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")])
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def taxi_use_own_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    cid = int(query.data.replace("taxi_use_own_", ""))

    cursor.execute("SELECT car, speed FROM garage WHERE id=? AND owner=?", (cid, uid))
    row = cursor.fetchone()
    if not row:
        await query.answer("Машина не найдена")
        return

    car, speed = row
    img = CARS.get(car, {}).get("img", "")
    set_selected_taxi_vehicle(context, uid, {
        "type": "own",
        "name": car,
        "speed": speed,
        "rent": 0,
        "img": img,
        "garage_id": cid,
    })

    await render_text(query.message, f"Теперь вы таксуете на своей машине: {car}\nСкорость: {speed}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]]))

async def taxi_orders_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    current_city = get_player(uid)["city"]
    vehicle = get_selected_taxi_vehicle(context, uid)

    if not vehicle:
        await render_text(query.message, "Сначала выберите машину для такси", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]]))
        return

    kb = []
    text = f"📋 Доступные заказы\n\nТекущая машина: {vehicle['name']}\n\n"
    found = False

    for order_id, order in sorted(taxi_orders.items()):
        if order["status"] == "waiting" and order["origin"] == current_city:
            found = True
            text += f"Заказ #{order_id}: {order['origin']} → {order['destination']} | {order['payment']}$\n"
            kb.append([InlineKeyboardButton(f"Взять заказ #{order_id}", callback_data=f"taxi_take_{order_id}")])

    if not found:
        text += "Свободных заказов нет"

    kb.append([InlineKeyboardButton("Обновить ⏳", callback_data="taxi_orders_menu")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")])

    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def taxi_take_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    order_id = int(query.data.replace("taxi_take_", ""))
    order = taxi_orders.get(order_id)

    if not order or order["status"] != "waiting":
        await render_text(query.message, "Заказ уже недоступен", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_orders_menu")]]))
        return

    vehicle = get_selected_taxi_vehicle(context, uid)
    if not vehicle:
        await render_text(query.message, "Сначала выберите машину", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]]))
        return

    order["status"] = "in_progress"
    order["driver_type"] = "player"
    order["driver_id"] = uid
    order["driver_name"] = query.from_user.full_name or str(uid)
    order["vehicle_name"] = vehicle["name"]
    order["vehicle_speed"] = vehicle["speed"]
    order["rental_cost"] = vehicle["rent"]
    ride_seconds = int(get_taxi_base_time(order["distance"]) / max(0.1, vehicle["speed"]))
    order["end_time"] = time.time() + ride_seconds

    context.application.create_task(finish_taxi_order_later(order_id, context.application))

    try:
        await context.bot.send_message(
            chat_id=order["passenger_id"],
            text=(
                f"🚕 Водитель найден\n\n"
                f"Маршрут: {order['origin']} → {order['destination']}\n"
                f"Водитель: {order['driver_name']}\n"
                f"Машина: {order['vehicle_name']}\n"
                f"Осталось времени: {format_seconds(ride_seconds)}"
            )
        )
    except Exception:
        pass

    await render_text(
        query.message,
        (
            f"🚕 Поездка началась\n\n"
            f"Маршрут: {order['origin']} → {order['destination']}\n"
            f"Пассажир: {order['passenger_name']}\n"
            f"Машина: {order['vehicle_name']}\n"
            f"Осталось времени: {format_seconds(ride_seconds)}"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Обновить ⏳", callback_data="taxi_current_trip")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]
        ])
    )

async def taxi_current_trip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    current_order = None
    for order in taxi_orders.values():
        if order["status"] == "in_progress" and order["driver_type"] == "player" and order["driver_id"] == uid:
            current_order = order
            break

    if not current_order:
        await render_text(query.message, "Текущей поездки нет", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]]))
        return

    left = int(current_order["end_time"] - time.time())
    await render_text(
        query.message,
        (
            f"🚕 Текущая поездка\n\n"
            f"Маршрут: {current_order['origin']} → {current_order['destination']}\n"
            f"Пассажир: {current_order['passenger_name']}\n"
            f"Машина: {current_order['vehicle_name']}\n"
            f"Осталось времени: {format_seconds(left)}"
        ),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Обновить ⏳", callback_data="taxi_current_trip")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="taxi_driver_menu")]
        ])
    )

# ---------------- STARTER JOBS ----------------

async def starter_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("⛏ Шахта", callback_data="mine_start")],
        [InlineKeyboardButton("🏭 Завод", callback_data="factory_start")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]
    ]
    await render_text(query.message, "💼 Начальные работы", reply_markup=InlineKeyboardMarkup(keyboard))

def generate_mine_track():
    track = ["⬛️"] * 11
    start = random.randint(0, 8)
    track[start] = "🟥"
    track[start + 1] = "🟥"
    track[start + 2] = "🟥"
    return track

async def mine_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    track = generate_mine_track()
    mine_sessions[uid] = {"track": track, "pos": 0, "stopped": False, "message": query.message}
    await render_text(query.message, "⛏ Подготовка шахты...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("СТОП", callback_data="mine_stop")]]))
    context.application.create_task(run_mine_animation(uid))

async def run_mine_animation(uid: int):
    session = mine_sessions.get(uid)
    if not session:
        return
    message = session["message"]
    positions = list(range(11)) + list(range(9, 0, -1))
    for _ in range(6):
        for pos in positions:
            session = mine_sessions.get(uid)
            if not session or session["stopped"]:
                return
            session["pos"] = pos
            track = session["track"][:]
            track[pos] = "🟩"
            text = "-----------------------------\n" + "".join(track) + "\n-----------------------------"
            await render_text(message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("СТОП", callback_data="mine_stop")]]))
            await asyncio.sleep(0.35)

    if uid in mine_sessions and not mine_sessions[uid]["stopped"]:
        mine_sessions[uid]["stopped"] = True
        await render_text(message, "❌ Вы не успели остановить квадрат", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        del mine_sessions[uid]

async def mine_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    session = mine_sessions.get(uid)
    if not session:
        await render_text(query.message, "Сессия шахты не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        return
    if session["stopped"]:
        return

    session["stopped"] = True
    pos = session["pos"]
    track = session["track"]

    if track[pos] == "🟥":
        reward = random.randint(120, 200)
        add_money(uid, reward)
        stone_text = ""
        if random.randint(1, 100) <= 15:
            add_sharpening_stone(uid, 1)
            stone_text = "\nВы получили: Точильный камень x1"
        text = f"⛏ Вы попали в руду!\n\nВы получили: {reward}$" + stone_text
    else:
        text = "❌ Мимо руды"

    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
    del mine_sessions[uid]

# ---------------- FACTORY ----------------

async def factory_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    broken = random.randint(0, 3)
    factory_sessions[uid] = {"broken": broken, "progress": 0}
    cells = ["⬛️", "⬛️", "⬛️", "⬛️"]
    cells[broken] = "⬜️"
    keyboard = [
        [InlineKeyboardButton(cells[0], callback_data="factory_cell_0"),
         InlineKeyboardButton(cells[1], callback_data="factory_cell_1")],
        [InlineKeyboardButton(cells[2], callback_data="factory_cell_2"),
         InlineKeyboardButton(cells[3], callback_data="factory_cell_3")],
    ]
    await render_text(query.message, "🏭 Найдите поломку", reply_markup=InlineKeyboardMarkup(keyboard))

async def factory_cell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    session = factory_sessions.get(uid)
    if not session:
        await render_text(query.message, "Сессия завода не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        return

    idx = int(query.data.split("_")[-1])
    if idx != session["broken"]:
        await render_text(query.message, "❌ Это не поломка", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        del factory_sessions[uid]
        return

    session["progress"] = 0
    await render_text(query.message, "🔧 Чините", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Починка (0/5)", callback_data="factory_repair")]]))

async def factory_repair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    session = factory_sessions.get(uid)
    if not session:
        await render_text(query.message, "Сессия завода не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        return

    session["progress"] += 1
    if session["progress"] >= 5:
        reward = random.randint(120, 200)
        add_money(uid, reward)
        await render_text(query.message, f"🔧 Починка завершена!\n\nВы получили: {reward}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="starter_jobs")]]))
        del factory_sessions[uid]
        return

    await render_text(query.message, "🔧 Чините", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"Починка ({session['progress']}/5)", callback_data="factory_repair")]]))

# ---------------- DEALERSHIP / GARAGE / MARKET ----------------

async def dealership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cars = list(CARS.keys())
    i = context.user_data.get("dealer_i", 0) % len(cars)
    context.user_data["dealer_i"] = i
    car = cars[i]
    data = CARS[car]
    cursor.execute("SELECT stock FROM dealership WHERE car=?", (car,))
    stock = cursor.fetchone()[0]
    caption = f"{car}\n\nКласс: {data['class']}\nСкорость: {data['speed']}\nЦена: {data['price']}$\nВ наличии: {stock}"
    kb = [
        [InlineKeyboardButton("⬅️", callback_data="dealer_prev"),
         InlineKeyboardButton("Купить", callback_data=f"buy_{car}"),
         InlineKeyboardButton("➡️", callback_data="dealer_next")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]
    ]
    await render_photo(query.message, data["img"], caption, reply_markup=InlineKeyboardMarkup(kb))

async def dealer_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["dealer_i"] = (context.user_data.get("dealer_i", 0) + 1) % len(CARS)
    await dealership(update, context)

async def dealer_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["dealer_i"] = (context.user_data.get("dealer_i", 0) - 1) % len(CARS)
    await dealership(update, context)

async def buy_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    car = query.data.replace("buy_", "")
    money = get_money(uid)
    price = CARS[car]["price"]

    if money < price:
        await query.answer("Недостаточно денег")
        return

    cursor.execute("SELECT stock FROM dealership WHERE car=?", (car,))
    stock = cursor.fetchone()[0]
    if stock <= 0:
        await query.answer("Нет в наличии")
        return

    cursor.execute("UPDATE players SET money=money-? WHERE user_id=?", (price, uid))
    cursor.execute("UPDATE dealership SET stock=stock-1 WHERE car=?", (car,))
    cursor.execute("INSERT INTO garage(owner,car,speed) VALUES(?,?,?)", (uid, car, CARS[car]["speed"]))
    conn.commit()

    await render_text(query.message, f"Вы купили: {car}\nВы потратили: {price}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]]))

async def garage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT id, car, speed FROM garage WHERE owner=?", (query.from_user.id,))
    cars = cursor.fetchall()
    if not cars:
        await render_text(query.message, "🚘 Гараж пуст", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))
        return

    text = "🚘 Ваш гараж\n\n"
    kb = []
    for cid, car, speed in cars:
        text += f"{cid} | {car} | speed {speed}\n"
        kb.append([InlineKeyboardButton(f"Продать {car}", callback_data=f"sell_{cid}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="main")])
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.replace("sell_", ""))
    cursor.execute("SELECT car FROM garage WHERE id=? AND owner=?", (cid, query.from_user.id))
    if not cursor.fetchone():
        await query.answer("Машина не найдена")
        return
    context.user_data["sell_car"] = cid
    await render_text(query.message, "Введите цену продажи следующим сообщением", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="garage")]]))

async def price_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "sell_car" not in context.user_data:
        return
    try:
        price = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Введите число")
        return

    cid = context.user_data["sell_car"]
    cursor.execute("SELECT car FROM garage WHERE id=?", (cid,))
    row = cursor.fetchone()
    if not row:
        await update.message.reply_text("Машина не найдена")
        context.user_data.pop("sell_car", None)
        return

    car = row[0]
    context.user_data["sell_price"] = price
    kb = [[InlineKeyboardButton("Да", callback_data="confirm_sell"),
           InlineKeyboardButton("Нет", callback_data="garage")]]
    await update.message.reply_text(f"Вы уверены что хотите выставить на продажу {car} за {price}$?", reply_markup=InlineKeyboardMarkup(kb))

async def confirm_sell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = context.user_data.get("sell_car")
    price = context.user_data.get("sell_price")
    if cid is None or price is None:
        await render_text(query.message, "Нет данных для продажи", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="garage")]]))
        return

    cursor.execute("SELECT car,speed,owner FROM garage WHERE id=?", (cid,))
    row = cursor.fetchone()
    if not row:
        await render_text(query.message, "Машина не найдена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="garage")]]))
        return

    car, speed, owner = row
    seller_name = query.from_user.full_name or str(owner)
    cursor.execute("DELETE FROM garage WHERE id=?", (cid,))
    cursor.execute("INSERT INTO car_market(car,seller,price,speed,seller_name) VALUES(?,?,?,?,?)", (car, owner, price, speed, seller_name))
    conn.commit()

    context.user_data.pop("sell_car", None)
    context.user_data.pop("sell_price", None)
    await render_text(query.message, "Машина выставлена на рынок", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏪 Открыть рынок", callback_data="market")]]))

async def market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT id,car,price,seller_name,speed FROM car_market ORDER BY id")
    cars = cursor.fetchall()
    if not cars:
        await render_text(query.message, "🏪 Авторынок пуст", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]]))
        return

    i = context.user_data.get("market_i", 0) % len(cars)
    context.user_data["market_i"] = i
    cid, car, price, seller_name, speed = cars[i]
    data = CARS[car]
    caption = f"{car}\n\nПродавец: {seller_name}\nЦена: {price}$\nЭлементы тюннинга:\n—\nСкорость: {speed}"
    kb = [
        [InlineKeyboardButton("⬅️", callback_data="market_prev"),
         InlineKeyboardButton("Купить", callback_data=f"market_buy_{cid}"),
         InlineKeyboardButton("➡️", callback_data="market_next")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")]
    ]
    await render_photo(query.message, data["img"], caption, reply_markup=InlineKeyboardMarkup(kb))

async def market_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT COUNT(*) FROM car_market")
    total = cursor.fetchone()[0]
    if total == 0:
        await render_text(query.message, "🏪 Авторынок пуст")
        return
    context.user_data["market_i"] = (context.user_data.get("market_i", 0) + 1) % total
    await market(update, context)

async def market_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("SELECT COUNT(*) FROM car_market")
    total = cursor.fetchone()[0]
    if total == 0:
        await render_text(query.message, "🏪 Авторынок пуст")
        return
    context.user_data["market_i"] = (context.user_data.get("market_i", 0) - 1) % total
    await market(update, context)

async def market_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cid = int(query.data.replace("market_buy_", ""))
    cursor.execute("SELECT car,price,seller,speed FROM car_market WHERE id=?", (cid,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Лот уже куплен")
        return

    car, price, seller, speed = row
    uid = query.from_user.id
    money = get_money(uid)
    if money < price:
        await query.answer("Недостаточно денег")
        return

    cursor.execute("UPDATE players SET money=money-? WHERE user_id=?", (price, uid))
    cursor.execute("UPDATE players SET money=money+? WHERE user_id=?", (price, seller))
    cursor.execute("DELETE FROM car_market WHERE id=?", (cid,))
    cursor.execute("INSERT INTO garage(owner,car,speed) VALUES(?,?,?)", (uid, car, speed))
    conn.commit()

    await render_text(query.message, f"Вы купили: {car}\nВы потратили: {price}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚘 В гараж", callback_data="garage")]]))

# ---------------- RUN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(CallbackQueryHandler(main_menu, pattern="main"))
    app.add_handler(CallbackQueryHandler(char_begin, pattern="char_begin"))
    app.add_handler(CallbackQueryHandler(char_confirm_yes, pattern="char_confirm_yes"))
    app.add_handler(CallbackQueryHandler(char_confirm_no, pattern="char_confirm_no"))

    app.add_handler(CallbackQueryHandler(char_pick_top, pattern="char_pick_top"))
    app.add_handler(CallbackQueryHandler(char_top_prev, pattern="char_top_prev"))
    app.add_handler(CallbackQueryHandler(char_top_next, pattern="char_top_next"))
    app.add_handler(CallbackQueryHandler(char_set_top, pattern="char_set_top_"))

    app.add_handler(CallbackQueryHandler(char_pick_bottom, pattern="char_pick_bottom"))
    app.add_handler(CallbackQueryHandler(char_bottom_prev, pattern="char_bottom_prev"))
    app.add_handler(CallbackQueryHandler(char_bottom_next, pattern="char_bottom_next"))
    app.add_handler(CallbackQueryHandler(char_set_bottom, pattern="char_set_bottom_"))

    app.add_handler(CallbackQueryHandler(char_pick_hair, pattern="char_pick_hair"))
    app.add_handler(CallbackQueryHandler(char_hair_prev, pattern="char_hair_prev"))
    app.add_handler(CallbackQueryHandler(char_hair_next, pattern="char_hair_next"))
    app.add_handler(CallbackQueryHandler(char_set_hair, pattern="char_set_hair_"))

    app.add_handler(CallbackQueryHandler(profile_menu, pattern="profile_menu"))
    app.add_handler(CallbackQueryHandler(inventory_menu, pattern="inventory_menu"))

    app.add_handler(CallbackQueryHandler(work_menu, pattern="work_menu"))
    app.add_handler(CallbackQueryHandler(city_menu, pattern="city_menu"))
    app.add_handler(CallbackQueryHandler(travel_menu, pattern="travel_menu"))
    app.add_handler(CallbackQueryHandler(travel_to_city, pattern="travel_"))

    app.add_handler(CallbackQueryHandler(taxi_call_menu, pattern="taxi_call_menu"))
    app.add_handler(CallbackQueryHandler(taxi_call_to_city, pattern="taxicall_"))
    app.add_handler(CallbackQueryHandler(taxi_passenger_refresh, pattern="taxi_passenger_refresh_"))
    app.add_handler(CallbackQueryHandler(taxi_driver_menu, pattern="taxi_driver_menu"))
    app.add_handler(CallbackQueryHandler(taxi_rental_menu, pattern="taxi_rental_menu"))
    app.add_handler(CallbackQueryHandler(taxi_rent_next, pattern="taxi_rent_next"))
    app.add_handler(CallbackQueryHandler(taxi_rent_prev, pattern="taxi_rent_prev"))
    app.add_handler(CallbackQueryHandler(taxi_rent_pick, pattern="rent_pick_"))
    app.add_handler(CallbackQueryHandler(taxi_own_car_menu, pattern="taxi_own_car_menu"))
    app.add_handler(CallbackQueryHandler(taxi_use_own_car, pattern="taxi_use_own_"))
    app.add_handler(CallbackQueryHandler(taxi_orders_menu, pattern="taxi_orders_menu"))
    app.add_handler(CallbackQueryHandler(taxi_take_order, pattern="taxi_take_"))
    app.add_handler(CallbackQueryHandler(taxi_current_trip, pattern="taxi_current_trip"))

    app.add_handler(CallbackQueryHandler(starter_jobs, pattern="starter_jobs"))
    app.add_handler(CallbackQueryHandler(mine_start, pattern="mine_start"))
    app.add_handler(CallbackQueryHandler(mine_stop, pattern="mine_stop"))
    app.add_handler(CallbackQueryHandler(factory_start, pattern="factory_start"))
    app.add_handler(CallbackQueryHandler(factory_cell, pattern=r"factory_cell_"))
    app.add_handler(CallbackQueryHandler(factory_repair, pattern="factory_repair"))

    app.add_handler(CallbackQueryHandler(dealership, pattern="dealership"))
    app.add_handler(CallbackQueryHandler(dealer_next, pattern="dealer_next"))
    app.add_handler(CallbackQueryHandler(dealer_prev, pattern="dealer_prev"))
    app.add_handler(CallbackQueryHandler(buy_car, pattern="buy_"))

    app.add_handler(CallbackQueryHandler(garage, pattern="garage"))
    app.add_handler(CallbackQueryHandler(sell, pattern="sell_"))
    app.add_handler(CallbackQueryHandler(confirm_sell, pattern="confirm_sell"))

    app.add_handler(CallbackQueryHandler(market, pattern="market"))
    app.add_handler(CallbackQueryHandler(market_next, pattern="market_next"))
    app.add_handler(CallbackQueryHandler(market_prev, pattern="market_prev"))
    app.add_handler(CallbackQueryHandler(market_buy, pattern="market_buy_"))

    app.add_handler(CallbackQueryHandler(placeholder, pattern=r"placeholder_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, price_input))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
