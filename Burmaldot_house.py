
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

DEBUG_ADMIN_ID = 123456789

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
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bank_operations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_number TEXT,
        user_id INTEGER,
        city TEXT,
        op_type TEXT,
        amount REAL,
        fee REAL DEFAULT 0,
        note TEXT DEFAULT '',
        created_at INTEGER
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT UNIQUE,
        owner_id INTEGER DEFAULT 0,
        name TEXT DEFAULT '',
        level INTEGER DEFAULT 0,
        processed_total INTEGER DEFAULT 0,
        stored_1060 INTEGER DEFAULT 0,
        stored_1660 INTEGER DEFAULT 0,
        stored_2060 INTEGER DEFAULT 0,
        stored_3060 INTEGER DEFAULT 0,
        stored_4060 INTEGER DEFAULT 0,
        stored_5060 INTEGER DEFAULT 0,
        warehouse_bonus_percent INTEGER DEFAULT 0,
        pending_profit INTEGER DEFAULT 0,
        is_processing INTEGER DEFAULT 0,
        processing_started_at INTEGER DEFAULT 0,
        processing_duration INTEGER DEFAULT 0,
        processing_amount INTEGER DEFAULT 0,
        ad_salary_percent INTEGER DEFAULT 0,
        ad_slots_target INTEGER DEFAULT 0,
        ad_description TEXT DEFAULT '',
        ad_bumped_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factory_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT,
        factory_id INTEGER,
        owner_id INTEGER,
        order_code TEXT UNIQUE,
        resource_key TEXT,
        units INTEGER,
        resource_cost INTEGER,
        delivery_cost INTEGER DEFAULT 0,
        eta_seconds INTEGER DEFAULT 3600,
        status TEXT DEFAULT 'pending',
        created_at INTEGER,
        delivered_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factory_employees(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factory_id INTEGER,
        employee_user_id INTEGER DEFAULT 0,
        employee_name TEXT DEFAULT '',
        employee_type TEXT DEFAULT 'npc',
        salary_percent INTEGER DEFAULT 0,
        created_at INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factory_applications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factory_id INTEGER,
        applicant_user_id INTEGER,
        applicant_name TEXT,
        status TEXT DEFAULT 'pending',
        created_at INTEGER
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factory_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factory_id INTEGER,
        created_at INTEGER,
        produced_1060 INTEGER DEFAULT 0,
        produced_1660 INTEGER DEFAULT 0,
        produced_2060 INTEGER DEFAULT 0,
        produced_3060 INTEGER DEFAULT 0,
        produced_4060 INTEGER DEFAULT 0,
        produced_5060 INTEGER DEFAULT 0,
        sent_prices_json TEXT DEFAULT ''
    )
    """)


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_shops(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city TEXT UNIQUE,
        owner_id INTEGER DEFAULT 0,
        name TEXT DEFAULT '',
        markup_percent INTEGER DEFAULT 18,
        pending_profit INTEGER DEFAULT 0,
        supplier_factory_city TEXT DEFAULT ''
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_shop_inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER,
        gpu_key TEXT,
        qty INTEGER DEFAULT 0,
        base_price INTEGER DEFAULT 0,
        UNIQUE(shop_id, gpu_key)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_shop_sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_id INTEGER,
        created_at INTEGER,
        gpu_key TEXT,
        unit_price INTEGER,
        buyer_name TEXT DEFAULT ''
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gpu_factory_shipments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        factory_id INTEGER,
        city TEXT,
        created_at INTEGER,
        gpu_key TEXT,
        qty INTEGER DEFAULT 0,
        remaining_qty INTEGER DEFAULT 0,
        unit_price INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS houses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER UNIQUE,
        city TEXT,
        level INTEGER DEFAULT 1,
        base_price INTEGER DEFAULT 0,
        house_code TEXT UNIQUE,
        street TEXT DEFAULT '',
        mining_progress_btc REAL DEFAULT 0,
        last_mining_update INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS house_storage(
        house_id INTEGER,
        item_key TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY(house_id, item_key)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS house_gpus(
        house_id INTEGER,
        slot_index INTEGER,
        gpu_key TEXT,
        PRIMARY KEY(house_id, slot_index)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS house_guests(
        house_id INTEGER,
        guest_user_id INTEGER UNIQUE,
        joined_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS friend_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user_id INTEGER,
        from_name TEXT DEFAULT '',
        to_user_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS friends(
        user_id INTEGER,
        friend_user_id INTEGER,
        created_at INTEGER DEFAULT 0,
        PRIMARY KEY(user_id, friend_user_id)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS house_invites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        house_id INTEGER,
        owner_id INTEGER,
        owner_name TEXT DEFAULT '',
        target_user_id INTEGER,
        status TEXT DEFAULT 'pending',
        created_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS house_chat_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        house_id INTEGER,
        sender_id INTEGER,
        sender_name TEXT DEFAULT '',
        message TEXT DEFAULT '',
        created_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        house_id INTEGER,
        user1_id INTEGER,
        user2_id INTEGER,
        status TEXT DEFAULT 'pending',
        user1_ready INTEGER DEFAULT 0,
        user2_ready INTEGER DEFAULT 0,
        user1_confirmed INTEGER DEFAULT 0,
        user2_confirmed INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_offers(
        session_id INTEGER,
        user_id INTEGER,
        slot_index INTEGER,
        item_key TEXT,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY(session_id, user_id, slot_index)
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_money(
        session_id INTEGER,
        user_id INTEGER,
        amount INTEGER DEFAULT 0,
        PRIMARY KEY(session_id, user_id)
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
ensure_column("players", "bank_balance INTEGER DEFAULT 90000000")
ensure_column("players", "bank_btc REAL DEFAULT 0")
ensure_column("players", "account_number TEXT DEFAULT ''")
ensure_column("car_market", "seller_name TEXT DEFAULT ''")
ensure_column("players", "current_house_id INTEGER DEFAULT 0")

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

BANK_IMAGES = {
    "Новоград": "https://files.catbox.moe/st449j.png",
    "Инд-Сити": "https://files.catbox.moe/9lu2bf.png",
    "Форс-Сити": "https://files.catbox.moe/uzbm85.png",
    "Вегаспорт": "https://files.catbox.moe/23qqre.png",
}
BTC_RATE = 5000
BANK_TRANSFER_FEE = 0.02
BANK_CRYPTO_FEE = 0.05
ADMIN_IDS = set()

PROPERTY_FEES = {
    "Новоград": {"garage": 0.01, "warehouse": 0.01, "home": 0.02, "business": 0.02, "gpu_factory": 0.04, "gpu_shop": 0.03, "special": 0.04, "casino": 0.04},
    "Инд-Сити": {"garage": 0.02, "warehouse": 0.02, "home": 0.03, "business": 0.03, "gpu_factory": 0.05, "gpu_shop": 0.04, "special": 0.05, "casino": 0.05},
    "Форс-Сити": {"garage": 0.03, "warehouse": 0.03, "home": 0.04, "business": 0.04, "gpu_factory": 0.06, "gpu_shop": 0.05, "special": 0.06, "casino": 0.06},
    "Вегаспорт": {"garage": 0.04, "warehouse": 0.04, "home": 0.05, "business": 0.05, "gpu_factory": 0.07, "gpu_shop": 0.06, "special": 0.07, "casino": 0.09},
}


FACTORY_IMAGE = "https://files.catbox.moe/btfvzj.jpg"
FACTORY_MANAGEMENT_IMAGE = "https://files.catbox.moe/q1rkea.jpg"
FACTORY_STORAGE_IMAGE = "https://files.catbox.moe/s2r0rj.jpg"
GPU_SHOP_IMAGE = "https://files.catbox.moe/4y98f1.jpg"

GPU_FACTORY_PRICES = {
    "Новоград": 1200000,
    "Инд-Сити": 1800000,
    "Форс-Сити": 2500000,
    "Вегаспорт": 3500000,
}


GPU_SHOP_PRICES = {
    "Новоград": 900000,
    "Инд-Сити": 1400000,
    "Форс-Сити": 1900000,
    "Вегаспорт": 2600000,
}

GPU_KEY_TO_LABEL = {
    "1060": "GTX 1060",
    "1660": "GTX 1660",
    "2060": "RTX 2060",
    "3060": "RTX 3060",
    "4060": "RTX 4060",
    "5060": "RTX 5060",
}

GPU_KEY_TO_ITEM = {
    "1060": "gpu_1060",
    "1660": "gpu_1660",
    "2060": "gpu_2060",
    "3060": "gpu_3060",
    "4060": "gpu_4060",
    "5060": "gpu_5060",
}

GPU_MINING_RATES = {
    "1060": 0.40,
    "1660": 0.55,
    "2060": 0.75,
    "3060": 1.00,
    "4060": 1.35,
    "5060": 1.80,
}

GPU_RAW_DATA = {
    "raw_1060": {"name": "Сырье для GTX 1060", "units_per_card": 100, "unit_price": 800, "sell_price": 100000, "weight": 40},
    "raw_1660": {"name": "Сырье для GTX 1660", "units_per_card": 140, "unit_price": 950, "sell_price": 170000, "weight": 30},
    "raw_2060": {"name": "Сырье для RTX 2060", "units_per_card": 220, "unit_price": 1100, "sell_price": 320000, "weight": 15},
    "raw_3060": {"name": "Сырье для RTX 3060", "units_per_card": 350, "unit_price": 1300, "sell_price": 600000, "weight": 8},
    "raw_4060": {"name": "Сырье для RTX 4060", "units_per_card": 500, "unit_price": 1500, "sell_price": 950000, "weight": 5},
    "raw_5060": {"name": "Сырье для RTX 5060", "units_per_card": 700, "unit_price": 1800, "sell_price": 1600000, "weight": 2},
}

GPU_FACTORY_LEVEL_THRESHOLDS = [15000, 25000, 50000]
GPU_FACTORY_BASE_SLOTS = 5
GPU_FACTORY_WAREHOUSE_BASE = 5000
GPU_FACTORY_BUMP_PRICE = 35000

STATE_PREFIXES = {
    "factory_buy_name": "factory_buy_name:",
    "factory_order_units": "factory_order_units:",
    "factory_post_slots": "factory_post_slots:",
    "factory_post_salary": "factory_post_salary:",
    "factory_post_desc": "factory_post_desc:",
    "shop_buy_name": "shop_buy_name:",
    "shop_markup": "shop_markup:",
    "friend_add_manual": "friend_add_manual",
    "house_invite_id": "house_invite_id:",
    "house_chat": "house_chat:",
    "house_store_move": "house_store_move:",
    "house_store_take": "house_store_take:",
    "trade_money": "trade_money:",
    "trade_add_item": "trade_add_item:",
    "trade_add_item_amount": "trade_add_item_amount:",
}


HOUSE_IMAGES = {
    "Новоград": "https://files.catbox.moe/xh5xi9.jpg",
    "Инд-Сити": "https://files.catbox.moe/bewlc5.jpg",
    "Форс-Сити": "https://files.catbox.moe/e6gylg.jpg",
    "Вегаспорт": "https://files.catbox.moe/43vcs7.jpg",
}
HOUSE_PRICES = {
    "Новоград": 800000,
    "Инд-Сити": 1400000,
    "Форс-Сити": 2200000,
    "Вегаспорт": 3500000,
}
HOUSE_STREET_WORDS = ["Элджеевка", "Мурино", "Друновка", "Габелло", "Жмуркино", "Рофлянская", "Базарная", "Шишкарево"]
HOUSE_STOREABLE_ITEMS = [
    "sharpening_stones", "zatocka", "super_zatocka", "garage_upgrade", "warehouse_upgrade",
    "gpu_1060", "gpu_1660", "gpu_2060", "gpu_3060", "gpu_4060", "gpu_5060"
]
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
    "gpu_1060",
    "gpu_1660",
    "gpu_2060",
    "gpu_3060",
    "gpu_4060",
    "gpu_5060",
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

def cached_download(url: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1] or ".img"
    name = hashlib.md5(url.encode("utf-8")).hexdigest() + ext
    path = os.path.join(CACHE_DIR, name)

    if os.path.exists(path):
        return path

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for attempt in range(3):
        try:
            response = requests.get(url, timeout=20, headers=headers)
            response.raise_for_status()

            with open(path, "wb") as f:
                f.write(response.content)

            return path

        except Exception as e:
            logging.warning(f"Download failed {url} attempt {attempt+1}: {e}")
            time.sleep(1)

    raise Exception(f"Failed to download image: {url}")

def open_rgba(url: str) -> Image.Image:
    try:
        path = cached_download(url)
        return Image.open(path).convert("RGBA")
    except Exception as e:
        logging.error(f"Image load failed: {url} {e}")
        return Image.new("RGBA", (512,512), (0,0,0,0))
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

def generate_account_number() -> str:
    while True:
        digits = "".join(random.choice("0123456789") for _ in range(4))
        letters = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(4))
        acc = digits + letters
        cursor.execute("SELECT 1 FROM players WHERE account_number=? LIMIT 1", (acc,))
        if cursor.fetchone() is None:
            return acc

def log_bank_operation(account_number: str, user_id: int, city: str, op_type: str, amount: float, fee: float = 0, note: str = ""):
    cursor.execute(
        "INSERT INTO bank_operations(account_number, user_id, city, op_type, amount, fee, note, created_at) VALUES(?,?,?,?,?,?,?,?)",
        (account_number, user_id, city, op_type, float(amount), float(fee), note, int(time.time())),
    )
    conn.commit()

def format_money(amount: float) -> str:
    amount = round(float(amount), 2)
    if amount.is_integer():
        return f"{int(amount)}$"
    return f"{amount:.2f}$"

def ensure_player_items(uid: int):
    for item_key in STARTER_ITEMS:
        cursor.execute(
            "INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)",
            (uid, item_key),
        )
    conn.commit()

def get_player(uid: int):
    cursor.execute("""
        SELECT user_id, city, money, taxi_level, taxi_rides, char_created, char_top, char_bottom, char_hair, bank_balance, bank_btc, account_number, current_house_id
        FROM players WHERE user_id=?
    """, (uid,))
    row = cursor.fetchone()
    if not row:
        account_number = generate_account_number()
        cursor.execute(
            "INSERT INTO players(user_id, city, money, taxi_level, taxi_rides, char_created, char_top, char_bottom, char_hair, bank_balance, bank_btc, account_number) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, "Новоград", 100000, 1, 0, 0, "", "", "", 0, 0, account_number),
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
            "bank_balance": 0,
            "bank_btc": 0.0,
            "account_number": account_number,
            "current_house_id": 0,
        }

    if not row[11]:
        account_number = generate_account_number()
        cursor.execute("UPDATE players SET account_number=? WHERE user_id=?", (account_number, uid))
        conn.commit()
        row = list(row)
        row[11] = account_number

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
        "bank_balance": row[9] or 0,
        "bank_btc": float(row[10] or 0),
        "account_number": row[11] or "",
        "current_house_id": row[12] if len(row) > 12 else 0,
    }

def get_money(uid: int) -> int:
    return get_player(uid)["money"]

def add_money(uid: int, amount: int):
    cursor.execute("UPDATE players SET money = money + ? WHERE user_id=?", (amount, uid))
    conn.commit()

def set_city(uid: int, city: str):
    cursor.execute("UPDATE players SET city=? WHERE user_id=?", (city, uid))
    conn.commit()

def set_bank_balance(uid: int, amount: float):
    cursor.execute("UPDATE players SET bank_balance=? WHERE user_id=?", (int(round(amount)), uid))
    conn.commit()

def add_bank_balance(uid: int, amount: float):
    cursor.execute("UPDATE players SET bank_balance = bank_balance + ? WHERE user_id=?", (int(round(amount)), uid))
    conn.commit()

def add_bank_btc(uid: int, amount: float):
    cursor.execute("UPDATE players SET bank_btc = bank_btc + ? WHERE user_id=?", (float(amount), uid))
    conn.commit()

def set_bank_btc(uid: int, amount: float):
    cursor.execute("UPDATE players SET bank_btc=? WHERE user_id=?", (float(amount), uid))
    conn.commit()

def find_player_by_account(account_number: str):
    cursor.execute("SELECT user_id FROM players WHERE account_number=?", (account_number.upper(),))
    row = cursor.fetchone()
    return row[0] if row else None

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



# ---------------- GPU FACTORY HELPERS ----------------

def ensure_gpu_factory_rows():
    for city in ["Новоград", "Инд-Сити", "Форс-Сити", "Вегаспорт"]:
        cursor.execute("INSERT OR IGNORE INTO gpu_factories(city) VALUES(?)", (city,))
    conn.commit()

ensure_gpu_factory_rows()

def ensure_gpu_shop_rows():
    for city in ["Новоград", "Инд-Сити", "Форс-Сити", "Вегаспорт"]:
        cursor.execute("INSERT OR IGNORE INTO gpu_shops(city) VALUES(?)", (city,))
    conn.commit()

ensure_gpu_shop_rows()

def gpu_shop_row(city: str):
    ensure_gpu_shop_rows()
    cursor.execute("SELECT id, city, owner_id, name, markup_percent, pending_profit, supplier_factory_city FROM gpu_shops WHERE city=?", (city,))
    row = cursor.fetchone()
    return {
        "id": row[0], "city": row[1], "owner_id": row[2], "name": row[3] or "",
        "markup_percent": row[4] or 18, "pending_profit": row[5] or 0,
        "supplier_factory_city": row[6] or "",
    }

def gpu_shop_display_name(shop: dict) -> str:
    return shop["name"] if shop["name"] else f"Магазин видеокарт | {shop['city']}"

def get_shop_inventory(shop_id: int):
    cursor.execute("SELECT gpu_key, qty, base_price FROM gpu_shop_inventory WHERE shop_id=? ORDER BY gpu_key", (shop_id,))
    return cursor.fetchall()

def upsert_shop_inventory(shop_id: int, gpu_key: str, qty_add: int, base_price: int):
    cursor.execute("SELECT qty, base_price FROM gpu_shop_inventory WHERE shop_id=? AND gpu_key=?", (shop_id, gpu_key))
    row = cursor.fetchone()
    if row:
        qty, old_base = row
        new_qty = qty + qty_add
        avg_base = base_price if qty == 0 else int(round(((qty * old_base) + (qty_add * base_price)) / max(1, new_qty)))
        cursor.execute("UPDATE gpu_shop_inventory SET qty=?, base_price=? WHERE shop_id=? AND gpu_key=?", (new_qty, avg_base, shop_id, gpu_key))
    else:
        cursor.execute("INSERT INTO gpu_shop_inventory(shop_id, gpu_key, qty, base_price) VALUES(?,?,?,?)", (shop_id, gpu_key, qty_add, base_price))
    conn.commit()

def add_player_gpu(uid: int, gpu_key: str, qty: int = 1):
    item_key = GPU_KEY_TO_ITEM[gpu_key]
    cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (uid, item_key))
    cursor.execute("UPDATE player_items SET amount = amount + ? WHERE user_id=? AND item_key=?", (qty, uid, item_key))
    conn.commit()

def shop_sell_price(base_price: int, markup_percent: int):
    return int(round(base_price * (1 + markup_percent / 100.0)))

def gpu_factory_row(city: str):
    ensure_gpu_factory_rows()

def ensure_gpu_shop_rows():
    for city in ["Новоград", "Инд-Сити", "Форс-Сити", "Вегаспорт"]:
        cursor.execute("INSERT OR IGNORE INTO gpu_shops(city) VALUES(?)", (city,))
    conn.commit()

ensure_gpu_shop_rows()

def gpu_shop_row(city: str):
    ensure_gpu_shop_rows()
    cursor.execute("SELECT id, city, owner_id, name, markup_percent, pending_profit, supplier_factory_city FROM gpu_shops WHERE city=?", (city,))
    row = cursor.fetchone()
    return {
        "id": row[0], "city": row[1], "owner_id": row[2], "name": row[3] or "",
        "markup_percent": row[4] or 18, "pending_profit": row[5] or 0,
        "supplier_factory_city": row[6] or "",
    }

def gpu_shop_display_name(shop: dict) -> str:
    return shop["name"] if shop["name"] else f"Магазин видеокарт | {shop['city']}"

def get_shop_inventory(shop_id: int):
    cursor.execute("SELECT gpu_key, qty, base_price FROM gpu_shop_inventory WHERE shop_id=? ORDER BY gpu_key", (shop_id,))
    return cursor.fetchall()

def upsert_shop_inventory(shop_id: int, gpu_key: str, qty_add: int, base_price: int):
    cursor.execute("SELECT qty, base_price FROM gpu_shop_inventory WHERE shop_id=? AND gpu_key=?", (shop_id, gpu_key))
    row = cursor.fetchone()
    if row:
        qty, old_base = row
        new_qty = qty + qty_add
        avg_base = base_price if qty == 0 else int(round(((qty * old_base) + (qty_add * base_price)) / max(1, new_qty)))
        cursor.execute("UPDATE gpu_shop_inventory SET qty=?, base_price=? WHERE shop_id=? AND gpu_key=?", (new_qty, avg_base, shop_id, gpu_key))
    else:
        cursor.execute("INSERT INTO gpu_shop_inventory(shop_id, gpu_key, qty, base_price) VALUES(?,?,?,?)", (shop_id, gpu_key, qty_add, base_price))
    conn.commit()

def add_player_gpu(uid: int, gpu_key: str, qty: int = 1):
    item_key = GPU_KEY_TO_ITEM[gpu_key]
    cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (uid, item_key))
    cursor.execute("UPDATE player_items SET amount = amount + ? WHERE user_id=? AND item_key=?", (qty, uid, item_key))
    conn.commit()

def shop_sell_price(base_price: int, markup_percent: int):
    return int(round(base_price * (1 + markup_percent / 100.0)))
    cursor.execute("""
        SELECT id, city, owner_id, name, level, processed_total,
               stored_1060, stored_1660, stored_2060, stored_3060, stored_4060, stored_5060,
               warehouse_bonus_percent, pending_profit, is_processing, processing_started_at,
               processing_duration, processing_amount, ad_salary_percent, ad_slots_target,
               ad_description, ad_bumped_at
        FROM gpu_factories WHERE city=?
    """, (city,))
    row = cursor.fetchone()
    if not row:
        raise ValueError("Factory row missing")
    return {
        "id": row[0], "city": row[1], "owner_id": row[2], "name": row[3] or "",
        "level": row[4], "processed_total": row[5],
        "stored_1060": row[6], "stored_1660": row[7], "stored_2060": row[8],
        "stored_3060": row[9], "stored_4060": row[10], "stored_5060": row[11],
        "warehouse_bonus_percent": row[12], "pending_profit": row[13],
        "is_processing": row[14], "processing_started_at": row[15],
        "processing_duration": row[16], "processing_amount": row[17],
        "ad_salary_percent": row[18], "ad_slots_target": row[19],
        "ad_description": row[20] or "", "ad_bumped_at": row[21] or 0,
    }

def factory_employee_limit(level: int) -> int:
    return GPU_FACTORY_BASE_SLOTS + (level * 5)

def factory_warehouse_limit(factory: dict) -> int:
    return int(GPU_FACTORY_WAREHOUSE_BASE * (1 + factory["warehouse_bonus_percent"] / 100))

def factory_total_raw(factory: dict) -> int:
    return (
        factory["stored_1060"] + factory["stored_1660"] + factory["stored_2060"] +
        factory["stored_3060"] + factory["stored_4060"] + factory["stored_5060"]
    )

def next_factory_level_remaining(factory: dict):
    level = factory["level"]
    if level >= 3:
        return None
    threshold = GPU_FACTORY_LEVEL_THRESHOLDS[level]
    return max(0, threshold - factory["processed_total"])

def generate_deli_code():
    letters = "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(4))
    digits = "".join(random.choice("0123456789") for _ in range(4))
    # tiny chance to be DELIVERY
    prefix = "DELIVERY" if random.randint(1, 100000) == 1 else "DELI"
    return f"{prefix}{letters}{digits}"

def get_factory_employee_count(factory_id: int):
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_employees WHERE factory_id=?", (factory_id,))
    return cursor.fetchone()[0]

def get_factory_player_employees(factory_id: int):
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_employees WHERE factory_id=? AND employee_type='player'", (factory_id,))
    return cursor.fetchone()[0]

def get_factory_npc_employees(factory_id: int):
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_employees WHERE factory_id=? AND employee_type='npc'", (factory_id,))
    return cursor.fetchone()[0]

def factory_speed_multiplier(factory_id: int):
    count = get_factory_employee_count(factory_id)
    return 1 + (0.05 * count)

def factory_display_name(factory: dict) -> str:
    return factory["name"] if factory["name"] else f"Завод видеокарт | {factory['city']}"

def gpu_factory_cards_from_raw(factory: dict):
    res = {}
    for key in GPU_RAW_DATA:
        suffix = key.split('_')[1]
        stored = factory[f"stored_{suffix}"]
        res[suffix] = stored // GPU_RAW_DATA[key]["units_per_card"]
    return res

def finalize_factory_production(city: str):
    factory = gpu_factory_row(city)
    if not factory["is_processing"]:
        return factory
    if time.time() < factory["processing_started_at"] + factory["processing_duration"]:
        return factory

    produced = {}
    total_profit = 0
    processed_delta = 0
    for key, meta in GPU_RAW_DATA.items():
        suffix = key.split('_')[1]
        stored_key = f"stored_{suffix}"
        units = factory[stored_key]
        cards = units // meta["units_per_card"]
        remain = units % meta["units_per_card"]
        produced[suffix] = cards
        processed_delta += units - remain
        total_profit += cards * meta["sell_price"]
        cursor.execute(f"UPDATE gpu_factories SET {stored_key}=? WHERE city=?", (remain, city))

    bonus_mult = 1.0
    if get_factory_player_employees(factory["id"]) > 0:
        bonus_mult = 2.0
    elif get_factory_npc_employees(factory["id"]) > 0:
        bonus_mult = 1.5
    total_profit = int(total_profit * bonus_mult)

    cursor.execute("""
        UPDATE gpu_factories
        SET is_processing=0,
            processing_started_at=0,
            processing_duration=0,
            processing_amount=0,
            processed_total=processed_total + ?,
            pending_profit=pending_profit + ?
        WHERE city=?
    """, (processed_delta, total_profit, city))

    sent_prices_json = json.dumps({
        "GTX 1060": GPU_RAW_DATA["raw_1060"]["sell_price"],
        "GTX 1660": GPU_RAW_DATA["raw_1660"]["sell_price"],
        "RTX 2060": GPU_RAW_DATA["raw_2060"]["sell_price"],
        "RTX 3060": GPU_RAW_DATA["raw_3060"]["sell_price"],
        "RTX 4060": GPU_RAW_DATA["raw_4060"]["sell_price"],
        "RTX 5060": GPU_RAW_DATA["raw_5060"]["sell_price"],
    }, ensure_ascii=False)

    for suffix, qty in produced.items():
        if qty > 0:
            cursor.execute(
                "INSERT INTO gpu_factory_shipments(factory_id, city, created_at, gpu_key, qty, remaining_qty, unit_price) VALUES(?,?,?,?,?,?,?)",
                (factory["id"], city, int(time.time()), suffix, qty, qty, GPU_RAW_DATA[f"raw_{suffix}"]["sell_price"])
            )

    cursor.execute("""
        INSERT INTO gpu_factory_history(
            factory_id, created_at, produced_1060, produced_1660, produced_2060,
            produced_3060, produced_4060, produced_5060, sent_prices_json
        ) VALUES(?,?,?,?,?,?,?,?,?)
    """, (
        factory["id"], int(time.time()), produced["1060"], produced["1660"], produced["2060"],
        produced["3060"], produced["4060"], produced["5060"], sent_prices_json
    ))
    conn.commit()

    # chance for warehouse bonus item
    if random.random() < 0.007 and factory["owner_id"]:
        cursor.execute(
            "INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)",
            (factory["owner_id"], "warehouse_upgrade")
        )
        cursor.execute(
            "UPDATE player_items SET amount = amount + 1 WHERE user_id=? AND item_key='warehouse_upgrade'",
            (factory["owner_id"],)
        )
        conn.commit()

    # auto level upgrades
    updated = gpu_factory_row(city)
    while updated["level"] < 3:
        rem = next_factory_level_remaining(updated)
        if rem is None or rem > 0:
            break
        cursor.execute("UPDATE gpu_factories SET level=level+1 WHERE city=?", (city,))
        conn.commit()
        updated = gpu_factory_row(city)

    return gpu_factory_row(city)

def seconds_until_factory_done(factory: dict):
    if not factory["is_processing"]:
        return 0
    return max(0, int(factory["processing_started_at"] + factory["processing_duration"] - time.time()))

def factory_ad_count(factory_id: int):
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_applications WHERE factory_id=? AND status='pending'", (factory_id,))
    return cursor.fetchone()[0]

def user_player_name(uid: int) -> str:
    cursor.execute("SELECT user_id FROM players WHERE user_id=?", (uid,))
    return str(uid)



# ---------------- FIXED FACTORY/SHOP HELPERS + HOUSE HELPERS ----------------

def gpu_factory_row(city: str):
    ensure_gpu_factory_rows()
    cursor.execute("""
        SELECT id, city, owner_id, name, level, processed_total,
               stored_1060, stored_1660, stored_2060, stored_3060, stored_4060, stored_5060,
               warehouse_bonus_percent, pending_profit, is_processing, processing_started_at,
               processing_duration, processing_amount, ad_salary_percent, ad_slots_target,
               ad_description, ad_bumped_at
        FROM gpu_factories WHERE city=?
    """, (city,))
    row = cursor.fetchone()
    if not row:
        raise ValueError("Factory row missing")
    return {
        "id": row[0], "city": row[1], "owner_id": row[2], "name": row[3] or "",
        "level": row[4], "processed_total": row[5],
        "stored_1060": row[6], "stored_1660": row[7], "stored_2060": row[8],
        "stored_3060": row[9], "stored_4060": row[10], "stored_5060": row[11],
        "warehouse_bonus_percent": row[12], "pending_profit": row[13],
        "is_processing": row[14], "processing_started_at": row[15],
        "processing_duration": row[16], "processing_amount": row[17],
        "ad_salary_percent": row[18], "ad_slots_target": row[19],
        "ad_description": row[20] or "", "ad_bumped_at": row[21] or 0,
    }

def ensure_gpu_shop_rows():
    for city in ["Новоград", "Инд-Сити", "Форс-Сити", "Вегаспорт"]:
        cursor.execute("INSERT OR IGNORE INTO gpu_shops(city) VALUES(?)", (city,))
    conn.commit()

def gpu_shop_row(city: str):
    ensure_gpu_shop_rows()
    cursor.execute("SELECT id, city, owner_id, name, markup_percent, pending_profit, supplier_factory_city FROM gpu_shops WHERE city=?", (city,))
    row = cursor.fetchone()
    return {
        "id": row[0], "city": row[1], "owner_id": row[2], "name": row[3] or "",
        "markup_percent": row[4] or 18, "pending_profit": row[5] or 0,
        "supplier_factory_city": row[6] or "",
    }

def gpu_shop_display_name(shop: dict) -> str:
    return shop["name"] if shop["name"] else f"Магазин видеокарт | {shop['city']}"

def get_shop_inventory(shop_id: int):
    cursor.execute("SELECT gpu_key, qty, base_price FROM gpu_shop_inventory WHERE shop_id=? ORDER BY gpu_key", (shop_id,))
    return cursor.fetchall()

def upsert_shop_inventory(shop_id: int, gpu_key: str, qty_add: int, base_price: int):
    cursor.execute("SELECT qty, base_price FROM gpu_shop_inventory WHERE shop_id=? AND gpu_key=?", (shop_id, gpu_key))
    row = cursor.fetchone()
    if row:
        qty, old_base = row
        new_qty = qty + qty_add
        avg_base = base_price if qty == 0 else int(round(((qty * old_base) + (qty_add * base_price)) / max(1, new_qty)))
        cursor.execute("UPDATE gpu_shop_inventory SET qty=?, base_price=? WHERE shop_id=? AND gpu_key=?", (new_qty, avg_base, shop_id, gpu_key))
    else:
        cursor.execute("INSERT INTO gpu_shop_inventory(shop_id, gpu_key, qty, base_price) VALUES(?,?,?,?)", (shop_id, gpu_key, qty_add, base_price))
    conn.commit()

def add_player_gpu(uid: int, gpu_key: str, qty: int = 1):
    item_key = GPU_KEY_TO_ITEM[gpu_key]
    cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (uid, item_key))
    cursor.execute("UPDATE player_items SET amount = amount + ? WHERE user_id=? AND item_key=?", (qty, uid, item_key))
    conn.commit()

def shop_sell_price(base_price: int, markup_percent: int):
    return int(round(base_price * (1 + markup_percent / 100.0)))

def house_gpu_limit(city: str, level: int) -> int:
    if city == "Новоград":
        return min(3, level)
    if city == "Инд-Сити":
        return min(4, level + 1)
    if city == "Форс-Сити":
        return 3 if level == 1 else 4
    if city == "Вегаспорт":
        return 5
    return 1

def house_storage_limit(level: int) -> int:
    return 500 + (level - 1) * 250

def generate_house_code() -> str:
    return random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + "".join(random.choice("0123456789") for _ in range(4)) + "".join(random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(3))

def house_upgrade_cost(base_price: int, next_level: int) -> int:
    return int(base_price * (next_level * 0.10))

def get_owned_house(uid: int):
    cursor.execute("SELECT id, owner_id, city, level, base_price, house_code, street, mining_progress_btc, last_mining_update, created_at FROM houses WHERE owner_id=?", (uid,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "owner_id": row[1], "city": row[2], "level": row[3], "base_price": row[4],
        "house_code": row[5], "street": row[6], "mining_progress_btc": float(row[7] or 0),
        "last_mining_update": row[8] or 0, "created_at": row[9] or 0
    }

def get_house_by_id(house_id: int):
    cursor.execute("SELECT id, owner_id, city, level, base_price, house_code, street, mining_progress_btc, last_mining_update, created_at FROM houses WHERE id=?", (house_id,))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "owner_id": row[1], "city": row[2], "level": row[3], "base_price": row[4],
        "house_code": row[5], "street": row[6], "mining_progress_btc": float(row[7] or 0),
        "last_mining_update": row[8] or 0, "created_at": row[9] or 0
    }

def active_house_for_user(uid: int):
    player = get_player(uid)
    if player.get("current_house_id", 0):
        house = get_house_by_id(player["current_house_id"])
        if house:
            return house
    return get_owned_house(uid)

def set_current_house(uid: int, house_id: int):
    cursor.execute("UPDATE players SET current_house_id=? WHERE user_id=?", (house_id, uid))
    conn.commit()

def clear_guest_presence(uid: int):
    cursor.execute("DELETE FROM house_guests WHERE guest_user_id=?", (uid,))
    cursor.execute("UPDATE players SET current_house_id=0 WHERE user_id=?", (uid,))
    conn.commit()

def get_house_guests(house_id: int):
    cursor.execute("SELECT guest_user_id FROM house_guests WHERE house_id=? ORDER BY joined_at ASC", (house_id,))
    ids = [r[0] for r in cursor.fetchall()]
    return ids

def get_house_guest_names(house_id: int):
    names = []
    for uid in get_house_guests(house_id):
        names.append(str(uid))
    return names

def add_house_guest(house_id: int, guest_user_id: int):
    clear_guest_presence(guest_user_id)
    cursor.execute("INSERT OR REPLACE INTO house_guests(house_id, guest_user_id, joined_at) VALUES(?,?,?)", (house_id, guest_user_id, int(time.time())))
    set_current_house(guest_user_id, house_id)
    conn.commit()

def house_owner_name(house: dict):
    return str(house["owner_id"])

def house_gpu_rows(house_id: int):
    cursor.execute("SELECT slot_index, gpu_key FROM house_gpus WHERE house_id=? ORDER BY slot_index", (house_id,))
    return cursor.fetchall()

def house_gpu_rate(house_id: int) -> float:
    total = 0.0
    for _, gpu_key in house_gpu_rows(house_id):
        total += GPU_MINING_RATES.get(gpu_key, 0.0)
    return total

def sync_house_mining(house_id: int):
    house = get_house_by_id(house_id)
    if not house:
        return None
    now = int(time.time())
    last = house["last_mining_update"] or now
    rate = house_gpu_rate(house_id)
    elapsed = max(0, now - last)
    total_btc = house["mining_progress_btc"] + rate * (elapsed / 3600.0)
    whole = int(total_btc)
    remainder = total_btc - whole
    if whole > 0:
        add_bank_btc(house["owner_id"], whole)
    cursor.execute("UPDATE houses SET mining_progress_btc=?, last_mining_update=? WHERE id=?", (remainder, now, house_id))
    conn.commit()
    house = get_house_by_id(house_id)
    return house

def next_btc_time_text(house_id: int):
    rate = house_gpu_rate(house_id)
    house = get_house_by_id(house_id)
    if not house or rate <= 0:
        return "—"
    remaining = 1.0 - house["mining_progress_btc"]
    seconds = int((remaining / rate) * 3600)
    return format_seconds(seconds)

def get_house_storage_amount(house_id: int, item_key: str) -> int:
    cursor.execute("SELECT amount FROM house_storage WHERE house_id=? AND item_key=?", (house_id, item_key))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_house_storage_total(house_id: int) -> int:
    cursor.execute("SELECT COALESCE(SUM(amount),0) FROM house_storage WHERE house_id=?", (house_id,))
    return cursor.fetchone()[0] or 0

def add_house_storage(house_id: int, item_key: str, amount: int):
    cursor.execute("INSERT OR IGNORE INTO house_storage(house_id, item_key, amount) VALUES(?,?,0)", (house_id, item_key))
    cursor.execute("UPDATE house_storage SET amount=amount+? WHERE house_id=? AND item_key=?", (amount, house_id, item_key))
    conn.commit()

def remove_house_storage(house_id: int, item_key: str, amount: int):
    cur = get_house_storage_amount(house_id, item_key)
    if cur < amount:
        return False
    cursor.execute("UPDATE house_storage SET amount=amount-? WHERE house_id=? AND item_key=?", (amount, house_id, item_key))
    cursor.execute("DELETE FROM house_storage WHERE house_id=? AND item_key=? AND amount<=0", (house_id, item_key))
    conn.commit()
    return True

def friend_exists(uid: int, friend_id: int) -> bool:
    cursor.execute("SELECT 1 FROM friends WHERE user_id=? AND friend_user_id=?", (uid, friend_id))
    return cursor.fetchone() is not None

def create_friendship(a: int, b: int):
    if a == b:
        return
    cursor.execute("INSERT OR IGNORE INTO friends(user_id, friend_user_id, created_at) VALUES(?,?,?)", (a, b, int(time.time())))
    cursor.execute("INSERT OR IGNORE INTO friends(user_id, friend_user_id, created_at) VALUES(?,?,?)", (b, a, int(time.time())))
    conn.commit()

def get_friend_ids(uid: int):
    cursor.execute("SELECT friend_user_id FROM friends WHERE user_id=? ORDER BY friend_user_id", (uid,))
    return [r[0] for r in cursor.fetchall()]

def get_active_trade_for_user(uid: int):
    cursor.execute("""
        SELECT id, house_id, user1_id, user2_id, status, user1_ready, user2_ready, user1_confirmed, user2_confirmed
        FROM trade_sessions
        WHERE status IN ('pending','active','locked') AND (user1_id=? OR user2_id=?)
        ORDER BY id DESC LIMIT 1
    """, (uid, uid))
    row = cursor.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "house_id": row[1], "user1_id": row[2], "user2_id": row[3], "status": row[4],
        "user1_ready": row[5], "user2_ready": row[6], "user1_confirmed": row[7], "user2_confirmed": row[8]
    }

def trade_partner(session: dict, uid: int) -> int:
    return session["user2_id"] if session["user1_id"] == uid else session["user1_id"]

def get_trade_offers(session_id: int, user_id: int):
    cursor.execute("SELECT slot_index, item_key, amount FROM trade_offers WHERE session_id=? AND user_id=? ORDER BY slot_index", (session_id, user_id))
    return cursor.fetchall()

def get_trade_money(session_id: int, user_id: int) -> int:
    cursor.execute("SELECT amount FROM trade_money WHERE session_id=? AND user_id=?", (session_id, user_id))
    row = cursor.fetchone()
    return row[0] if row else 0

def set_trade_money(session_id: int, user_id: int, amount: int):
    cursor.execute("INSERT OR REPLACE INTO trade_money(session_id, user_id, amount) VALUES(?,?,?)", (session_id, user_id, amount))
    conn.commit()

def reset_trade_ready(session_id: int):
    cursor.execute("UPDATE trade_sessions SET user1_ready=0, user2_ready=0, user1_confirmed=0, user2_confirmed=0, status='active' WHERE id=?", (session_id,))
    conn.commit()

def next_trade_slot(session_id: int, user_id: int):
    taken = {slot for slot, _, _ in get_trade_offers(session_id, user_id)}
    for i in range(16):
        if i not in taken:
            return i
    return None

def render_trade_grid(offers):
    cells = ["[]"] * 16
    for slot, item_key, amount in offers:
        label = item_key
        if item_key in GPU_KEY_TO_ITEM.values():
            label = GPU_KEY_TO_LABEL[item_key.split("_")[1]]
        elif item_key == "sharpening_stones":
            label = "Точильный камень"
        elif item_key == "zatocka":
            label = "Заточка"
        elif item_key == "super_zatocka":
            label = "Супер заточка"
        elif item_key == "garage_upgrade":
            label = "Расширение гаража"
        elif item_key == "warehouse_upgrade":
            label = "Пристройка склада"
        label = f"[{label} x{amount}]"
        cells[slot] = label
    lines = []
    for i in range(0, 16, 4):
        lines.append(" ".join(cells[i:i+4]))
    return "\n".join(lines)

def trade_user_status(session: dict, uid: int):
    if session["user1_id"] == uid:
        return session["user1_ready"], session["user1_confirmed"]
    return session["user2_ready"], session["user2_confirmed"]

def set_trade_ready(session_id: int, uid: int, value: int):
    session = get_active_trade_for_user(uid)
    col = "user1_ready" if session and session["user1_id"] == uid else "user2_ready"
    cursor.execute(f"UPDATE trade_sessions SET {col}=? WHERE id=?", (value, session_id))
    conn.commit()

def set_trade_confirm(session_id: int, uid: int, value: int):
    session = get_active_trade_for_user(uid)
    col = "user1_confirmed" if session and session["user1_id"] == uid else "user2_confirmed"
    cursor.execute(f"UPDATE trade_sessions SET {col}=? WHERE id=?", (value, session_id))
    conn.commit()

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
        [InlineKeyboardButton("👥 Друзья", callback_data="friends_menu")],
    ]
    player = get_player(uid)
    if has_any_car(uid):
        rows.append([InlineKeyboardButton("🚘 Гараж", callback_data="garage")])
    if get_owned_house(uid) or player.get("current_house_id", 0):
        rows.append([InlineKeyboardButton("🏠 Дом", callback_data="house_menu")])
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
        f"GTX 1060: {get_item_amount(uid, 'gpu_1060')}\n"
        f"GTX 1660: {get_item_amount(uid, 'gpu_1660')}\n"
        f"RTX 2060: {get_item_amount(uid, 'gpu_2060')}\n"
        f"RTX 3060: {get_item_amount(uid, 'gpu_3060')}\n"
        f"RTX 4060: {get_item_amount(uid, 'gpu_4060')}\n"
        f"RTX 5060: {get_item_amount(uid, 'gpu_5060')}\n"
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
    buttons.append([InlineKeyboardButton("🧑‍🏭 Трудоустройство", callback_data="factory_jobs_menu")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="main")])
    await render_text(query.message, "💼 Работа", reply_markup=InlineKeyboardMarkup(buttons))

async def city_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]

    if city == "Новоград":
        keyboard = [
            [InlineKeyboardButton("🏦 Банк Новограда", callback_data="bank_menu")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="agency_menu")],
            [InlineKeyboardButton("💼 Начальные работы", callback_data="starter_jobs")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            *([[InlineKeyboardButton("🏠 Дом", callback_data="house_menu")]] if (get_owned_house(query.from_user.id) and get_owned_house(query.from_user.id)["city"] == city) else []),
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Инд-Сити":
        keyboard = [
            [InlineKeyboardButton("🛒 Рынок", callback_data="placeholder_market")],
            [InlineKeyboardButton("💼 Работа", callback_data="work_menu")],
            [InlineKeyboardButton("🏦 Банк Инд-Сити", callback_data="bank_menu")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="agency_menu")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            *([[InlineKeyboardButton("🏠 Дом", callback_data="house_menu")]] if (get_owned_house(query.from_user.id) and get_owned_house(query.from_user.id)["city"] == city) else []),
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Форс-Сити":
        keyboard = [
            [InlineKeyboardButton("🚗 Автосалон", callback_data="dealership")],
            [InlineKeyboardButton("🏪 Авторынок", callback_data="market")],
            [InlineKeyboardButton("🏁 Гонки", callback_data="placeholder_race")],
            [InlineKeyboardButton("🔧 СТО", callback_data="placeholder_sto")],
            [InlineKeyboardButton("🏦 Банк Форс-Сити", callback_data="bank_menu")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="agency_menu")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            *([[InlineKeyboardButton("🏠 Дом", callback_data="house_menu")]] if (get_owned_house(query.from_user.id) and get_owned_house(query.from_user.id)["city"] == city) else []),
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    elif city == "Вегаспорт":
        keyboard = [
            [InlineKeyboardButton("🎰 Казино", callback_data="placeholder_casino")],
            [InlineKeyboardButton("🏛 Аукцион", callback_data="placeholder_auction")],
            [InlineKeyboardButton("⚙️ Крафт", callback_data="placeholder_craft")],
            [InlineKeyboardButton("🏦 Банк Вегаспорта", callback_data="bank_menu")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="agency_menu")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            *([[InlineKeyboardButton("🏠 Дом", callback_data="house_menu")]] if (get_owned_house(query.from_user.id) and get_owned_house(query.from_user.id)["city"] == city) else []),
            [InlineKeyboardButton("⬅️ Назад", callback_data="main")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🏦 Банк", callback_data="bank_menu")],
            [InlineKeyboardButton("🏢 Агентство недвижимости", callback_data="agency_menu")],
            [InlineKeyboardButton("🚕 Вызвать такси", callback_data="taxi_call_menu")],
            [InlineKeyboardButton("🌍 Отправиться в другой город", callback_data="travel_menu")],
            *([[InlineKeyboardButton("🏠 Дом", callback_data="house_menu")]] if (get_owned_house(query.from_user.id) and get_owned_house(query.from_user.id)["city"] == city) else []),
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




# ---------------- AGENCY / GPU FACTORY ----------------

def agency_keyboard(city: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏭 Бизнесы", callback_data="agency_businesses")],
        [InlineKeyboardButton("🏠 Дома", callback_data="agency_houses")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")],
    ])

async def agency_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    await render_text(query.message, f"🏢 Агентство недвижимости | {city}", reply_markup=agency_keyboard(city))

async def agency_businesses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    factory = finalize_factory_production(city)
    shop = gpu_shop_row(city)
    owner_text = "Свободен" if not factory["owner_id"] else "Занят"
    shop_owner_text = "Свободен" if not shop["owner_id"] else "Занят"
    factory_price = GPU_FACTORY_PRICES.get(city, 2000000)
    shop_price = GPU_SHOP_PRICES.get(city, 1200000)
    text = (
        f"🏭 Бизнесы | {city}\n\n"
        f"Завод видеокарт\n"
        f"Статус: {owner_text}\n"
        f"Цена: {factory_price}$\n\n"
        f"🛒 Магазин видеокарт\n"
        f"Статус: {shop_owner_text}\n"
        f"Цена: {shop_price}$"
    )
    kb = [
        [InlineKeyboardButton("Открыть завод видеокарт", callback_data="factory_open_city")],
        [InlineKeyboardButton("Открыть магазин видеокарт", callback_data="gpu_shop_open_city")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="agency_menu")]
    ]
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def factory_open_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    await factory_menu_common(query.message, query.from_user.id, query.from_user.first_name, city)

async def factory_menu_common(target_message, uid: int, first_name: str, city: str):
    factory = finalize_factory_production(city)
    if factory["owner_id"] == 0:
        price = GPU_FACTORY_PRICES.get(city, 2000000)
        text = (
            f"🏭 Завод видеокарт | {city}\n\n"
            f"Завод пока никем не куплен.\n"
            f"Цена покупки: {price}$\n\n"
            f"После покупки вам нужно будет задать название бизнесу."
        )
        kb = [[InlineKeyboardButton("Купить завод", callback_data=f"factory_buy_{city}")],
              [InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]
        await render_photo(target_message, FACTORY_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if factory["owner_id"] != uid:
        text = (
            f"🏭 Завод видеокарт | {city}\n\n"
            f"Владелец: другой игрок\n"
            f"Название: {factory_display_name(factory)}"
        )
        kb = [[InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]
        await render_photo(target_message, FACTORY_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    employee_count = get_factory_employee_count(factory["id"])
    limit = factory_employee_limit(factory["level"])
    text = (
        f"🏭 Завод видеокарт | {city}\n\n"
        f"Уровень завода: {factory['level']}\n"
        f"Сырьё: {factory_total_raw(factory)}\n"
        f"Готовых карт: {sum(gpu_factory_cards_from_raw(factory).values())}\n"
        f"Сотрудников: {employee_count}/{limit}\n"
        f"Прибыль не собрана: {factory['pending_profit']}$"
    )
    kb = [
        [InlineKeyboardButton("📦 Склад бизнеса", callback_data=f"factory_storage_{city}")],
        [InlineKeyboardButton("⚙️ Запустить производство", callback_data=f"factory_startprod_{city}")],
        [InlineKeyboardButton("💰 Собрать прибыль", callback_data=f"factory_collect_{city}")],
        [InlineKeyboardButton("🧑‍💼 Управление бизнесом", callback_data=f"factory_manage_{city}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")],
    ]
    await render_photo(target_message, FACTORY_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))

async def factory_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_buy_", "")
    uid = query.from_user.id
    factory = gpu_factory_row(city)
    if factory["owner_id"]:
        await query.answer("Завод уже куплен")
        return
    price = GPU_FACTORY_PRICES.get(city, 2000000)
    if get_money(uid) < price:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -price)
    cursor.execute("UPDATE gpu_factories SET owner_id=? WHERE city=?", (uid, city))
    conn.commit()
    context.user_data["text_state"] = STATE_PREFIXES["factory_buy_name"] + city
    await render_text(query.message, f"Вы купили завод видеокарт в городе {city}.\nВведите название бизнеса одним сообщением.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]))

async def factory_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_storage_", "")
    factory = finalize_factory_production(city)
    total_raw = factory_total_raw(factory)
    limit = factory_warehouse_limit(factory)
    pct = (total_raw / limit * 100) if limit else 0
    remain = next_factory_level_remaining(factory)
    remain_text = "Максимальный уровень" if remain is None else f"{remain}"
    eta = seconds_until_factory_done(factory)
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_orders WHERE city=? AND status='pending'", (city,))
    pending_deliveries = cursor.fetchone()[0]
    text = (
        f'📦 Склад твоего бизнеса "{factory_display_name(factory)}"\n\n'
        f"📦 сырья на складе: {total_raw}/{limit} ({pct:.2f}% заполнено)\n"
        f"🕚 переработка полностью завершится через {format_seconds(eta)}\n"
        f"🚚 доставляется сырья: {pending_deliveries if pending_deliveries else 'Не доставляется'}\n"
        f"⏫️ осталось переработать сырья до след. Уровня: {remain_text}\n\n"
        f"Сырье для GTX 1060: {factory['stored_1060']}\n"
        f"Сырье для GTX 1660: {factory['stored_1660']}\n"
        f"Сырье для RTX 2060: {factory['stored_2060']}\n"
        f"Сырье для RTX 3060: {factory['stored_3060']}\n"
        f"Сырье для RTX 4060: {factory['stored_4060']}\n"
        f"Сырье для RTX 5060: {factory['stored_5060']}"
    )
    kb = [
        [InlineKeyboardButton("Закупить сырьё", callback_data=f"factory_buyraw_menu_{city}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_open_{city}")]
    ]
    await render_photo(query.message, FACTORY_STORAGE_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))

async def factory_buyraw_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_buyraw_menu_", "")
    lines = [f"Закупить сырьё | {city}\n", "Имеется сырья:"]
    factory = gpu_factory_row(city)
    for key, meta in GPU_RAW_DATA.items():
        suffix = key.split("_")[1]
        lines.append(f"{meta['name']}: {factory[f'stored_{suffix}']}")
    kb = []
    for key, meta in GPU_RAW_DATA.items():
        kb.append([InlineKeyboardButton(meta["name"], callback_data=f"factory_order_{city}_{key}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_storage_{city}")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def factory_order_raw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, _, city, raw_key = query.data.split("_", 3)
    context.user_data["text_state"] = STATE_PREFIXES["factory_order_units"] + city + ":" + raw_key
    meta = GPU_RAW_DATA[raw_key]
    await render_text(query.message, f"Введите количество единиц для заказа.\n{meta['name']}\nЦена за 1 ед.: {meta['unit_price']}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_buyraw_menu_{city}")]]))

async def factory_startprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_startprod_", "")
    factory = finalize_factory_production(city)
    if factory["is_processing"]:
        await query.answer("Производство уже запущено")
        return
    total_raw = factory_total_raw(factory)
    if total_raw <= 0:
        await query.answer("Нет сырья для переработки")
        return
    speed = factory_speed_multiplier(factory["id"])
    duration = max(60, int((total_raw / 1000) * 3600 / speed))
    cursor.execute("""
        UPDATE gpu_factories
        SET is_processing=1, processing_started_at=?, processing_duration=?, processing_amount=?
        WHERE city=?
    """, (int(time.time()), duration, total_raw, city))
    conn.commit()
    await render_text(query.message, f"⚙️ Переработка запущена.\nПолностью завершится через {format_seconds(duration)}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📦 Склад бизнеса", callback_data=f"factory_storage_{city}")], [InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_open_{city}")]]))

async def factory_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_collect_", "")
    factory = finalize_factory_production(city)
    profit = factory["pending_profit"]
    if profit <= 0:
        await query.answer("Прибыль пока не собрана")
        return
    add_bank_balance(query.from_user.id, profit)
    cursor.execute("UPDATE gpu_factories SET pending_profit=0 WHERE city=?", (city,))
    conn.commit()
    player = get_player(query.from_user.id)
    log_bank_operation(player["account_number"], query.from_user.id, city, "factory_profit", profit, 0, f"Собрана прибыль с завода {factory_display_name(factory)}")
    await render_text(query.message, f"💰 Прибыль собрана и зачислена в банк: {profit}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_open_{city}")]]))

async def factory_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_manage_", "")
    factory = finalize_factory_production(city)
    text = (
        f"Управление бизнесом\n\n"
        f"Название: {factory_display_name(factory)}\n"
        f"Заявок: {factory_ad_count(factory['id'])}\n"
        f"Сотрудников: {get_factory_employee_count(factory['id'])}/{factory_employee_limit(factory['level'])}"
    )
    kb = [
        [InlineKeyboardButton("📢 Подать объявление", callback_data=f"factory_postad_{city}")],
        [InlineKeyboardButton("📨 Заявки", callback_data=f"factory_apps_{city}")],
        [InlineKeyboardButton("👷 Сотрудники", callback_data=f"factory_workers_{city}")],
        [InlineKeyboardButton("📜 История отправок видеокарт", callback_data=f"factory_history_{city}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_open_{city}")],
    ]
    await render_photo(query.message, FACTORY_MANAGEMENT_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))

async def factory_postad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_postad_", "")
    factory = finalize_factory_production(city)
    if factory["ad_slots_target"] > 0 and get_factory_employee_count(factory["id"]) < factory["ad_slots_target"]:
        kb = [[InlineKeyboardButton("Поднять", callback_data=f"factory_bumpad_{city}"), InlineKeyboardButton("Назад", callback_data=f"factory_manage_{city}")]]
        await render_text(query.message, "Вы уже подали объявление на трудоустройство, вы можете его поднять, что бы оно было в самом начале списка!", reply_markup=InlineKeyboardMarkup(kb))
        return
    kb = [[InlineKeyboardButton("Нанять бота", callback_data=f"factory_hirenpc_{city}")],
          [InlineKeyboardButton("Подать обьявление о поиске сотрудников", callback_data=f"factory_postad_flow_{city}")],
          [InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]
    await render_text(query.message, "Подать объявление.\nЭта кнопка позволяет нанимать нпс и давать заявки на свою работу.", reply_markup=InlineKeyboardMarkup(kb))

async def factory_hirenpc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_hirenpc_", "")
    factory = gpu_factory_row(city)
    count = get_factory_employee_count(factory["id"])
    if count >= factory_employee_limit(factory["level"]):
        await query.answer("Нет свободных слотов сотрудников")
        return
    salary = random.randint(0, 49)
    cursor.execute("""
        INSERT INTO gpu_factory_employees(factory_id, employee_user_id, employee_name, employee_type, salary_percent, created_at)
        VALUES(?,?,?,?,?,?)
    """, (factory["id"], 0, f"NPC #{count+1}", "npc", salary, int(time.time())))
    conn.commit()
    await render_text(query.message, f"🤖 Нанят бот-сотрудник.\nЕго зарплата: {salary}%", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))

async def factory_postad_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_postad_flow_", "")
    context.user_data["text_state"] = STATE_PREFIXES["factory_post_slots"] + city
    await render_text(query.message, 'Ваше обьявление появится в вкладке "трудоустройство"\nВам нужно указать процент заработной платы и сколько сотрудников вы ищете\n\nУкажите искомое количество сотрудников', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))

async def factory_bumpad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_bumpad_", "")
    uid = query.from_user.id
    if get_money(uid) < GPU_FACTORY_BUMP_PRICE:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -GPU_FACTORY_BUMP_PRICE)
    cursor.execute("UPDATE gpu_factories SET ad_bumped_at=? WHERE city=?", (int(time.time()), city))
    conn.commit()
    await render_text(query.message, f"Объявление поднято за {GPU_FACTORY_BUMP_PRICE}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))

async def factory_jobs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cursor.execute("""
        SELECT city, name, ad_slots_target, ad_salary_percent, owner_id, id, ad_description, ad_bumped_at
        FROM gpu_factories
        WHERE owner_id != 0 AND ad_slots_target > 0
        ORDER BY ad_bumped_at DESC, id ASC
    """)
    ads = cursor.fetchall()
    if not ads:
        await render_text(query.message, "Вот все контракты на найм:\n\nСейчас объявлений нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="work_menu")]]))
        return
    page = context.user_data.get("factory_jobs_page", 0)
    total_pages = max(1, math.ceil(len(ads) / 9))
    page = max(0, min(page, total_pages - 1))
    context.user_data["factory_jobs_page"] = page
    chunk = ads[page*9:(page+1)*9]
    lines = ["Вот все контракты на найм:"]
    kb = []
    for i, row in enumerate(chunk, start=1 + page*9):
        city, name, slots_target, _, _, factory_id, _, _ = row
        hired = get_factory_employee_count(factory_id)
        label = name if name else "Завод видеокарт"
        lines.append(f"#{i} {label} {hired}/{slots_target}")
        kb.append([InlineKeyboardButton(f"#{i} {label} {hired}/{slots_target}", callback_data=f"factory_jobview_{factory_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data="factory_jobs_prev"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data="factory_jobs_next"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="work_menu")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def factory_jobs_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["factory_jobs_page"] = max(0, context.user_data.get("factory_jobs_page", 0) - 1)
    await factory_jobs_menu(update, context)

async def factory_jobs_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["factory_jobs_page"] = context.user_data.get("factory_jobs_page", 0) + 1
    await factory_jobs_menu(update, context)

async def factory_jobview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    factory_id = int(query.data.replace("factory_jobview_", ""))
    cursor.execute("""
        SELECT city, name, owner_id, ad_description, ad_salary_percent, ad_slots_target
        FROM gpu_factories WHERE id=?
    """, (factory_id,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Объявление не найдено")
        return
    city, name, owner_id, desc, salary, slots_target = row
    hired = get_factory_employee_count(factory_id)
    approx_salary = "Зависит от выручки"
    text = (
        f"Заявка\n"
        f"Бизнесс: {name if name else 'Завод видеокарт'}\n"
        f"Тип бизнеса: Завод видеокарт\n"
        f"Владелец: {owner_id}\n"
        f"Описание: {desc}\n"
        f"Зарплата в %: {salary}%\n"
        f"Зарплата в $: {approx_salary}\n"
        f"Нанято: {hired}/{slots_target}"
    )
    kb = [
        [InlineKeyboardButton("Отправить свою кандидатуру", callback_data=f"factory_apply_{factory_id}")],
        [InlineKeyboardButton("Назад", callback_data="factory_jobs_menu")]
    ]
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def factory_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    factory_id = int(query.data.replace("factory_apply_", ""))
    uid = query.from_user.id
    cursor.execute("SELECT 1 FROM gpu_factory_applications WHERE factory_id=? AND applicant_user_id=? AND status='pending'", (factory_id, uid))
    if cursor.fetchone():
        await query.answer("Вы уже подали заявку")
        return
    cursor.execute("SELECT COUNT(*) FROM gpu_factory_applications WHERE factory_id=? AND status='pending'", (factory_id,))
    pending = cursor.fetchone()[0]
    if pending >= 30:
        await query.answer("Ящик заявок заполнен")
        return
    cursor.execute("""
        INSERT INTO gpu_factory_applications(factory_id, applicant_user_id, applicant_name, status, created_at)
        VALUES(?,?,?,?,?)
    """, (factory_id, uid, query.from_user.first_name, "pending", int(time.time())))
    conn.commit()
    await render_text(query.message, "Кандидатура отправлена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="factory_jobs_menu")]]))

async def factory_apps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_apps_", "")
    factory = gpu_factory_row(city)
    cursor.execute("""
        SELECT id, applicant_name FROM gpu_factory_applications
        WHERE factory_id=? AND status='pending'
        ORDER BY id ASC
    """, (factory["id"],))
    apps = cursor.fetchall()
    if not apps:
        await render_text(query.message, "Кандидаты:\n\nЗаявок нет", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))
        return
    page = context.user_data.get(f"factory_apps_page_{city}", 0)
    total_pages = max(1, math.ceil(len(apps) / 9))
    page = max(0, min(page, total_pages - 1))
    context.user_data[f"factory_apps_page_{city}"] = page
    chunk = apps[page*9:(page+1)*9]
    lines = ["Кандидаты:"]
    kb = []
    for n, (app_id, applicant_name) in enumerate(chunk, start=1 + page*9):
        lines.append(f"#{n} {applicant_name}")
        kb.append([InlineKeyboardButton(f"#{n} {applicant_name}", callback_data=f"factory_appopen_{city}_{app_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"factory_apps_prev_{city}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"factory_apps_next_{city}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def factory_apps_prev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_apps_prev_", "")
    key = f"factory_apps_page_{city}"
    context.user_data[key] = max(0, context.user_data.get(key, 0) - 1)
    await factory_apps(update, context)

async def factory_apps_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_apps_next_", "")
    key = f"factory_apps_page_{city}"
    context.user_data[key] = context.user_data.get(key, 0) + 1
    await factory_apps(update, context)

async def factory_appopen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"factory_appopen_(.+)_(\d+)", query.data)
    city, app_id = m.group(1), int(m.group(2))
    cursor.execute("SELECT applicant_name FROM gpu_factory_applications WHERE id=? AND status='pending'", (app_id,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Заявка не найдена")
        return
    name = row[0]
    kb = [
        [InlineKeyboardButton("✅ Принять", callback_data=f"factory_app_accept_{city}_{app_id}")],
        [InlineKeyboardButton("❌ Отказать", callback_data=f"factory_app_decline_{city}_{app_id}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_apps_{city}")]
    ]
    await render_text(query.message, f"Кандидат: {name}", reply_markup=InlineKeyboardMarkup(kb))

async def factory_app_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"factory_app_accept_(.+)_(\d+)", query.data)
    city, app_id = m.group(1), int(m.group(2))
    factory = gpu_factory_row(city)
    if get_factory_employee_count(factory["id"]) >= factory_employee_limit(factory["level"]):
        await query.answer("Нет свободных слотов")
        return
    cursor.execute("SELECT applicant_user_id, applicant_name FROM gpu_factory_applications WHERE id=? AND status='pending'", (app_id,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Заявка уже обработана")
        return
    applicant_user_id, applicant_name = row
    cursor.execute("""
        INSERT INTO gpu_factory_employees(factory_id, employee_user_id, employee_name, employee_type, salary_percent, created_at)
        VALUES(?,?,?,?,?,?)
    """, (factory["id"], applicant_user_id, applicant_name, "player", factory["ad_salary_percent"], int(time.time())))
    cursor.execute("UPDATE gpu_factory_applications SET status='accepted' WHERE id=?", (app_id,))
    conn.commit()
    try:
        await context.bot.send_message(chat_id=applicant_user_id, text=f'Владелец "{factory_display_name(factory)}" принял вашу заявку на трудоустройство')
    except Exception:
        pass
    await render_text(query.message, "Заявка принята", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_apps_{city}")]]))

async def factory_app_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"factory_app_decline_(.+)_(\d+)", query.data)
    city, app_id = m.group(1), int(m.group(2))
    factory = gpu_factory_row(city)
    cursor.execute("SELECT applicant_user_id FROM gpu_factory_applications WHERE id=? AND status='pending'", (app_id,))
    row = cursor.fetchone()
    if row:
        applicant_user_id = row[0]
        try:
            await context.bot.send_message(chat_id=applicant_user_id, text=f'Владелец "{factory_display_name(factory)}" отклонил вашу заявку на трудоустройство')
        except Exception:
            pass
    cursor.execute("UPDATE gpu_factory_applications SET status='declined' WHERE id=?", (app_id,))
    conn.commit()
    await render_text(query.message, "Заявка отклонена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_apps_{city}")]]))

async def factory_workers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_workers_", "")
    factory = gpu_factory_row(city)
    cursor.execute("""
        SELECT employee_name, employee_type, salary_percent
        FROM gpu_factory_employees WHERE factory_id=?
        ORDER BY id ASC
    """, (factory["id"],))
    rows = cursor.fetchall()
    if not rows:
        text = "Сотрудников пока нет"
    else:
        lines = [f"Сотрудники ({len(rows)}/{factory_employee_limit(factory['level'])}):"]
        for name, e_type, salary in rows[:30]:
            lines.append(f"{name} | {e_type} | {salary}%")
        text = "\n".join(lines)
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))

async def factory_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_history_", "")
    factory = gpu_factory_row(city)
    cursor.execute("""
        SELECT created_at, produced_1060, produced_1660, produced_2060, produced_3060, produced_4060, produced_5060, sent_prices_json
        FROM gpu_factory_history WHERE factory_id=? ORDER BY id DESC LIMIT 10
    """, (factory["id"],))
    rows = cursor.fetchall()
    if not rows:
        text = "История отправки видеокарт пуста"
    else:
        lines = []
        for row in rows:
            created_at, p1060, p1660, p2060, p3060, p4060, p5060, sent_prices_json = row
            prices = json.loads(sent_prices_json or "{}")
            lines.append(f"Дата и время: {time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))}")
            for label, qty in [("GTX 1060", p1060), ("GTX 1660", p1660), ("RTX 2060", p2060), ("RTX 3060", p3060), ("RTX 4060", p4060), ("RTX 5060", p5060)]:
                if qty:
                    lines.append(f"{label} x{qty} - {prices.get(label, 0)}$")
            lines.append("")
        text = "\n".join(lines[:50]).strip()
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"factory_manage_{city}")]]))

async def factory_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("factory_open_", "")
    await factory_menu_common(query.message, query.from_user.id, query.from_user.first_name, city)


# ---------------- GPU SHOP ----------------

async def gpu_shop_open_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    await gpu_shop_menu_common(query.message, query.from_user.id, query.from_user.first_name, city)

async def gpu_shop_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_open_", "")
    await gpu_shop_menu_common(query.message, query.from_user.id, query.from_user.first_name, city)

async def gpu_shop_menu_common(target_message, uid: int, first_name: str, city: str):
    shop = gpu_shop_row(city)
    if shop["owner_id"] == 0:
        price = GPU_SHOP_PRICES.get(city, 1200000)
        text = (
            f"🛒 Магазин видеокарт | {city}\n\n"
            f"Магазин пока никем не куплен.\n"
            f"Цена покупки: {price}$\n\n"
            f"После покупки вам нужно будет задать название бизнесу."
        )
        kb = [[InlineKeyboardButton("Купить магазин", callback_data=f"gpu_shop_buy_{city}")],
              [InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]
        await render_photo(target_message, GPU_SHOP_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    if shop["owner_id"] == uid:
        inv = get_shop_inventory(shop["id"])
        inv_lines = []
        for gpu_key, qty, _ in inv:
            if qty > 0:
                inv_lines.append(f"{GPU_KEY_TO_LABEL[gpu_key]} x{qty}")
        stock_text = "\n".join(inv_lines) if inv_lines else "Сейчас товара нет в наличии."
        text = (
            f"🛒 Магазин видеокарт | {city}\n\n"
            f"Название: {gpu_shop_display_name(shop)}\n"
            f"Владелец: {first_name}\n\n"
            f"{stock_text}\n\n"
            f"Текущая наценка: {shop['markup_percent']}%\n"
            f"Несобранная прибыль: {shop['pending_profit']}$"
        )
        kb = [
            [InlineKeyboardButton("♻️ Каталог", callback_data=f"gpu_shop_catalog_{city}")],
            [InlineKeyboardButton("📦 Склад", callback_data=f"gpu_shop_storage_{city}")],
            [InlineKeyboardButton("📝 Изменить наценку", callback_data=f"gpu_shop_markup_{city}")],
            [InlineKeyboardButton("💰 Собрать прибыль", callback_data=f"gpu_shop_collect_{city}")],
            [InlineKeyboardButton("📊 Статистика продаж", callback_data=f"gpu_shop_stats_{city}")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")],
        ]
        await render_photo(target_message, GPU_SHOP_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    inv = get_shop_inventory(shop["id"])
    total = sum(qty for _, qty, _ in inv)
    if total <= 0:
        text = f"🛒 Магазин видеокарт | {city}\n\nНазвание: {gpu_shop_display_name(shop)}\nВладелец: игрок\n\nСейчас товара нет в наличии."
        kb = [[InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]
        await render_photo(target_message, GPU_SHOP_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))
        return

    text = (
        f"🛒 Магазин видеокарт | {city}\n\n"
        f"Название: {gpu_shop_display_name(shop)}\n"
        f"Владелец: игрок"
    )
    kb = [
        [InlineKeyboardButton("♻️ Каталог", callback_data=f"gpu_shop_catalog_{city}")],
        [InlineKeyboardButton("📊 Статистика продаж", callback_data=f"gpu_shop_stats_{city}")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")],
    ]
    await render_photo(target_message, GPU_SHOP_IMAGE, text, reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_buy_", "")
    uid = query.from_user.id
    shop = gpu_shop_row(city)
    if shop["owner_id"]:
        await query.answer("Магазин уже куплен")
        return
    price = GPU_SHOP_PRICES.get(city, 1200000)
    if get_money(uid) < price:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -price)
    cursor.execute("UPDATE gpu_shops SET owner_id=? WHERE city=?", (uid, city))
    conn.commit()
    context.user_data["text_state"] = STATE_PREFIXES["shop_buy_name"] + city
    await render_text(query.message, f"Вы купили магазин видеокарт в городе {city}.\nВведите название бизнеса одним сообщением.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="agency_businesses")]]))

async def gpu_shop_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_storage_", "")
    shop = gpu_shop_row(city)
    supplier = shop["supplier_factory_city"] if shop["supplier_factory_city"] else "Не выбран"
    text = (
        "Склад:\n"
        "Выберите поставщика:\n"
        f"Выбран: {supplier}\n\n"
        "Отправленные видеокарты:"
    )
    kb = [[InlineKeyboardButton("Выбрать поставщика", callback_data=f"gpu_shop_supplier_{city}")],
          [InlineKeyboardButton("Открыть поставки", callback_data=f"gpu_shop_shipments_{city}_0")],
          [InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")]]
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_supplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_supplier_", "")
    cursor.execute("SELECT city, name FROM gpu_factories WHERE owner_id != 0")
    rows = cursor.fetchall()
    if not rows:
        await render_text(query.message, "Доступных заводов нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))
        return
    kb = []
    for fcity, fname in rows:
        label = fname if fname else f"Завод видеокарт | {fcity}"
        kb.append([InlineKeyboardButton(label, callback_data=f"gpu_shop_selectsupplier_{city}_{fcity}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")])
    await render_text(query.message, "Выберите поставщика:", reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_selectsupplier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_selectsupplier_(.+)_(.+)", query.data)
    city, supplier_city = m.group(1), m.group(2)
    cursor.execute("UPDATE gpu_shops SET supplier_factory_city=? WHERE city=?", (supplier_city, city))
    conn.commit()
    await render_text(query.message, f"Поставщик выбран: {supplier_city}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))

async def gpu_shop_shipments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_shipments_(.+)_(\d+)", query.data)
    city, page = m.group(1), int(m.group(2))
    shop = gpu_shop_row(city)
    if not shop["supplier_factory_city"]:
        await render_text(query.message, "Сначала выберите поставщика.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))
        return
    factory = gpu_factory_row(shop["supplier_factory_city"])
    cursor.execute("""
        SELECT id, gpu_key, remaining_qty, unit_price
        FROM gpu_factory_shipments
        WHERE factory_id=? AND remaining_qty>0
        ORDER BY id DESC
    """, (factory["id"],))
    rows = cursor.fetchall()
    if not rows:
        await render_text(query.message, "Поставок нет.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))
        return
    total_pages = max(1, math.ceil(len(rows) / 8))
    page = max(0, min(page, total_pages - 1))
    chunk = rows[page*8:(page+1)*8]
    lines = ["Когда нажимают купить вылезает список присланных видеокарт:"]
    kb = []
    total_page_cost = 0
    labels = []
    for ship_id, gpu_key, qty, unit_price in chunk:
        cost = qty * unit_price
        total_page_cost += cost
        labels.append(f"{GPU_KEY_TO_LABEL[gpu_key]} x{qty}")
        lines.append(f"{GPU_KEY_TO_LABEL[gpu_key]} x{qty} - {cost}$")
        kb.append([InlineKeyboardButton(f"Купить {GPU_KEY_TO_LABEL[gpu_key]} x{qty}", callback_data=f"gpu_shop_buyship_{city}_{ship_id}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"gpu_shop_shipments_{city}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"gpu_shop_shipments_{city}_{page+1}"))
    kb.append([InlineKeyboardButton(f"Купить все видеокарты на странице за {total_page_cost}$", callback_data=f"gpu_shop_buyall_{city}_{page}")])
    kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_buyship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_buyship_(.+)_(\d+)", query.data)
    city, ship_id = m.group(1), int(m.group(2))
    shop = gpu_shop_row(city)
    cursor.execute("SELECT gpu_key, remaining_qty, unit_price, city FROM gpu_factory_shipments WHERE id=?", (ship_id,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Поставка не найдена")
        return
    gpu_key, qty, unit_price, source_city = row
    total_cost = qty * unit_price
    if get_money(query.from_user.id) < total_cost:
        await query.answer("Недостаточно денег")
        return
    add_money(query.from_user.id, -total_cost)
    upsert_shop_inventory(shop["id"], gpu_key, qty, unit_price)
    cursor.execute("UPDATE gpu_factory_shipments SET remaining_qty=0 WHERE id=?", (ship_id,))
    supplier_factory = gpu_factory_row(source_city)
    if supplier_factory["owner_id"]:
        add_bank_balance(supplier_factory["owner_id"], total_cost)
    conn.commit()
    await render_text(query.message, f"Купить {GPU_KEY_TO_LABEL[gpu_key]} за {total_cost}$?\nПокупка выполнена.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))

async def gpu_shop_buyall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_buyall_(.+)_(\d+)", query.data)
    city, page = m.group(1), int(m.group(2))
    shop = gpu_shop_row(city)
    if not shop["supplier_factory_city"]:
        await query.answer("Нет поставщика")
        return
    factory = gpu_factory_row(shop["supplier_factory_city"])
    cursor.execute("""
        SELECT id, gpu_key, remaining_qty, unit_price
        FROM gpu_factory_shipments
        WHERE factory_id=? AND remaining_qty>0
        ORDER BY id DESC
    """, (factory["id"],))
    rows = cursor.fetchall()
    total_pages = max(1, math.ceil(len(rows) / 8))
    page = max(0, min(page, total_pages - 1))
    chunk = rows[page*8:(page+1)*8]
    total_cost = sum(qty * unit_price for _, _, qty, unit_price in chunk)
    if get_money(query.from_user.id) < total_cost:
        await query.answer("Недостаточно денег")
        return
    add_money(query.from_user.id, -total_cost)
    for ship_id, gpu_key, qty, unit_price in chunk:
        upsert_shop_inventory(shop["id"], gpu_key, qty, unit_price)
        cursor.execute("UPDATE gpu_factory_shipments SET remaining_qty=0 WHERE id=?", (ship_id,))
    if factory["owner_id"]:
        add_bank_balance(factory["owner_id"], total_cost)
    conn.commit()
    await render_text(query.message, f"Купить видеокарты на странице за {total_cost}$?\nПокупка выполнена.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_storage_{city}")]]))

async def gpu_shop_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_catalog_", "")
    shop = gpu_shop_row(city)
    inv = [row for row in get_shop_inventory(shop["id"]) if row[1] > 0]
    if not inv:
        await render_text(query.message, f"🛒 Магазин видеокарт | {city}\n\nСейчас товара нет в наличии.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")]]))
        return
    page = context.user_data.get(f"gpu_shop_catalog_page_{city}", 0)
    total_pages = max(1, math.ceil(len(inv) / 8))
    page = max(0, min(page, total_pages - 1))
    context.user_data[f"gpu_shop_catalog_page_{city}"] = page
    chunk = inv[page*8:(page+1)*8]
    lines = ["Доступные видеокарты:"]
    kb = []
    for gpu_key, qty, base_price in chunk:
        sell_price = shop_sell_price(base_price, shop["markup_percent"])
        lines.append(f"{GPU_KEY_TO_LABEL[gpu_key]} - {sell_price}$")
        kb.append([InlineKeyboardButton(f"{GPU_KEY_TO_LABEL[gpu_key]}", callback_data=f"gpu_shop_item_{city}_{gpu_key}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"gpu_shop_catprev_{city}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"gpu_shop_catnext_{city}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_catprev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_catprev_", "")
    key = f"gpu_shop_catalog_page_{city}"
    context.user_data[key] = max(0, context.user_data.get(key, 0) - 1)
    query.data = f"gpu_shop_catalog_{city}"
    await gpu_shop_catalog(update, context)

async def gpu_shop_catnext(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_catnext_", "")
    key = f"gpu_shop_catalog_page_{city}"
    context.user_data[key] = context.user_data.get(key, 0) + 1
    query.data = f"gpu_shop_catalog_{city}"
    await gpu_shop_catalog(update, context)

async def gpu_shop_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_item_(.+)_(\d+)", query.data)
    city, gpu_key = m.group(1), m.group(2)
    shop = gpu_shop_row(city)
    cursor.execute("SELECT qty, base_price FROM gpu_shop_inventory WHERE shop_id=? AND gpu_key=?", (shop["id"], gpu_key))
    row = cursor.fetchone()
    if not row or row[0] <= 0:
        await query.answer("Товара нет")
        return
    qty, base_price = row
    sell_price = shop_sell_price(base_price, shop["markup_percent"])
    text = (
        f"🖥 {GPU_KEY_TO_LABEL[gpu_key]}\n\n"
        f"Цена: {sell_price}$\n"
        f"В наличии: {qty}\n\n"
        f"Майнинг:\n"
        f"{GPU_MINING_RATES[gpu_key]:.2f} BTC/час"
    )
    kb = [[InlineKeyboardButton("Купить", callback_data=f"gpu_shop_buyitem_{city}_{gpu_key}")],
          [InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_catalog_{city}")]]
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def gpu_shop_buyitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"gpu_shop_buyitem_(.+)_(\d+)", query.data)
    city, gpu_key = m.group(1), m.group(2)
    uid = query.from_user.id
    shop = gpu_shop_row(city)
    cursor.execute("SELECT qty, base_price FROM gpu_shop_inventory WHERE shop_id=? AND gpu_key=?", (shop["id"], gpu_key))
    row = cursor.fetchone()
    if not row or row[0] <= 0:
        await query.answer("Товара нет")
        return
    qty, base_price = row
    sell_price = shop_sell_price(base_price, shop["markup_percent"])
    if get_money(uid) < sell_price:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -sell_price)
    cursor.execute("UPDATE gpu_shop_inventory SET qty=qty-1 WHERE shop_id=? AND gpu_key=?", (shop["id"], gpu_key))
    cursor.execute("UPDATE gpu_shops SET pending_profit=pending_profit+? WHERE city=?", (sell_price, city))
    cursor.execute("INSERT INTO gpu_shop_sales(shop_id, created_at, gpu_key, unit_price, buyer_name) VALUES(?,?,?,?,?)", (shop["id"], int(time.time()), gpu_key, sell_price, query.from_user.first_name))
    conn.commit()
    add_player_gpu(uid, gpu_key, 1)
    await render_text(query.message, f"✅ Вы купили:\n{GPU_KEY_TO_LABEL[gpu_key]} x1\n\nСписано: {sell_price}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_catalog_{city}")]]))

async def gpu_shop_markup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_markup_", "")
    shop = gpu_shop_row(city)
    context.user_data["text_state"] = STATE_PREFIXES["shop_markup"] + city
    await render_text(query.message, f"Изменить наценку магазина\nТекущая наценка: {shop['markup_percent']}%\nВведите новое значение от 5 до 30%", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")]]))

async def gpu_shop_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_collect_", "")
    shop = gpu_shop_row(city)
    amount = shop["pending_profit"]
    if amount <= 0:
        await query.answer("Прибыль пока не собрана")
        return
    add_bank_balance(query.from_user.id, amount)
    player = get_player(query.from_user.id)
    log_bank_operation(player["account_number"], query.from_user.id, city, "gpu_shop_profit", amount, 0, f"Собрана прибыль с магазина {gpu_shop_display_name(shop)}")
    cursor.execute("UPDATE gpu_shops SET pending_profit=0 WHERE city=?", (city,))
    conn.commit()
    await render_text(query.message, f"💰 Прибыль собрана и зачислена в банк: {amount}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")]]))

async def gpu_shop_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("gpu_shop_stats_", "")
    shop = gpu_shop_row(city)
    cursor.execute("SELECT created_at, gpu_key, unit_price, buyer_name FROM gpu_shop_sales WHERE shop_id=? ORDER BY id DESC LIMIT 30", (shop["id"],))
    rows = cursor.fetchall()
    if not rows:
        text = "Статистика продаж пуста"
    else:
        lines = []
        for created_at, gpu_key, price, buyer_name in rows:
            lines.append(f"Дата и время: {time.strftime('%d.%m.%Y %H:%M', time.localtime(created_at))}")
            lines.append(f"{GPU_KEY_TO_LABEL[gpu_key]} - {price}$ - {buyer_name}")
        text = "\n".join(lines)
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"gpu_shop_open_{city}")]]))



# ---------------- HOUSES / FRIENDS / TRADE ----------------

async def agency_houses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    owned = get_owned_house(query.from_user.id)
    price = HOUSE_PRICES.get(city, 1000000)
    if owned and owned["city"] == city:
        next_level = owned["level"] + 1
        upgrade_text = "Максимальный уровень" if next_level > 5 else f"Прокачка до {next_level} уровня: {house_upgrade_cost(owned['base_price'], next_level)}$"
        text = (
            f"🏠 Дом | {city}\n\n"
            f"У вас уже есть дом в этом городе.\n"
            f"Уровень: {owned['level']}\n"
            f"{upgrade_text}"
        )
        kb = [[InlineKeyboardButton("Прокачать дом", callback_data="house_upgrade")],
              [InlineKeyboardButton("Открыть дом", callback_data="house_menu")],
              [InlineKeyboardButton("⬅️ Назад", callback_data="agency_menu")]]
    elif owned:
        text = (
            f"🏠 Дом | {city}\n\n"
            f"У вас уже есть дом в городе {owned['city']}.\n"
            f"Сейчас можно владеть только одним домом."
        )
        kb = [[InlineKeyboardButton("Открыть свой дом", callback_data="house_menu")],
              [InlineKeyboardButton("⬅️ Назад", callback_data="agency_menu")]]
    else:
        text = (
            f"🏠 Дом | {city}\n\n"
            f"Цена дома: {price}$\n"
            f"Прокачка дома стоит 10% от цены за уровень.\n"
            f"2 уровень = 20% от цены дома\n"
            f"3 уровень = 30% от цены дома и т.д."
        )
        kb = [[InlineKeyboardButton("Купить дом", callback_data=f"house_buy_{city}")],
              [InlineKeyboardButton("⬅️ Назад", callback_data="agency_menu")]]
    await render_photo(query.message, HOUSE_IMAGES.get(city, HOUSE_IMAGES["Новоград"]), text, reply_markup=InlineKeyboardMarkup(kb))

async def house_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = query.data.replace("house_buy_", "")
    uid = query.from_user.id
    if get_owned_house(uid):
        await query.answer("У вас уже есть дом")
        return
    price = HOUSE_PRICES.get(city, 1000000)
    if get_money(uid) < price:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -price)
    street = f"{random.choice(HOUSE_STREET_WORDS)} {random.randint(1,99)}"
    house_code = generate_house_code()
    cursor.execute("""
        INSERT INTO houses(owner_id, city, level, base_price, house_code, street, mining_progress_btc, last_mining_update, created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
    """, (uid, city, 1, price, house_code, street, 0, int(time.time()), int(time.time())))
    conn.commit()
    house = get_owned_house(uid)
    set_current_house(uid, house["id"])
    await render_text(query.message, f"✅ Вы купили дом в городе {city}\nНомер дома: {house_code}\nУлица: {street}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть дом", callback_data="house_menu")]]))

async def house_upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        await query.answer("У вас нет дома")
        return
    next_level = house["level"] + 1
    if next_level > 5:
        await query.answer("Максимальный уровень")
        return
    cost = house_upgrade_cost(house["base_price"], next_level)
    if get_money(uid) < cost:
        await query.answer("Недостаточно денег")
        return
    add_money(uid, -cost)
    cursor.execute("UPDATE houses SET level=level+1 WHERE id=?", (house["id"],))
    conn.commit()
    await render_text(query.message, f"🏠 Дом улучшен до {next_level} уровня.\nСтоимость: {cost}$", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть дом", callback_data="house_menu")]]))

def house_menu_keyboard(house: dict, uid: int):
    is_owner = house["owner_id"] == uid
    rows = []
    if is_owner:
        rows.append([InlineKeyboardButton("⛏ Майнинг", callback_data="house_mining")])
        rows.append([InlineKeyboardButton("📦 Склад", callback_data="house_storage")])
    rows.append([InlineKeyboardButton("👥 Гости", callback_data="house_guests")])
    if is_owner:
        rows.append([InlineKeyboardButton("👕 Гардероб", callback_data="house_wardrobe")])
        rows.append([InlineKeyboardButton("🚘 Гараж", callback_data="garage")])
    rows.append([InlineKeyboardButton("🚪 Выйти из дома", callback_data="house_exit")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(rows)

async def house_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = active_house_for_user(uid)
    if not house:
        await render_text(query.message, "У вас нет дома и вы не находитесь в чужом доме.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))
        return
    set_current_house(uid, house["id"])
    house = sync_house_mining(house["id"])
    guest_count = len(get_house_guests(house["id"]))
    text = (
        f"🏠 Дом | {house['city']}\n\n"
        f"Владелец: {house_owner_name(house)}\n"
        f"Уровень дома: {house['level']}\n\n"
        f"📦 Склад: {get_house_storage_total(house['id'])}/{house_storage_limit(house['level'])}\n"
        f"⛏ Слоты видеокарт: {len(house_gpu_rows(house['id']))}/{house_gpu_limit(house['city'], house['level'])}\n"
        f"👥 Гостей в доме: {guest_count}/4"
    )
    await render_photo(query.message, HOUSE_IMAGES.get(house["city"], HOUSE_IMAGES["Новоград"]), text, reply_markup=house_menu_keyboard(house, uid))

async def house_mining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        await query.answer("Майнинг доступен только владельцу дома")
        return
    house = sync_house_mining(house["id"])
    gpu_rows = house_gpu_rows(house["id"])
    limit = house_gpu_limit(house["city"], house["level"])
    lines = ["⛏ Комната для майнинга\n", f"В работе: {len(gpu_rows)}/{limit} видеокарт", ""]
    for _, gpu_key in gpu_rows:
        lines.append(GPU_KEY_TO_LABEL[gpu_key])
    lines.append("")
    lines.append(f"Скорость майнинга: {house_gpu_rate(house['id']):.2f} BTC/час")
    lines.append(f"След. BTC через: {next_btc_time_text(house['id'])}")
    kb = []
    row = []
    for slot_index in range(limit):
        installed = next((g for s, g in gpu_rows if s == slot_index), None)
        label = GPU_KEY_TO_LABEL[installed] if installed else "Добавить"
        cb = f"house_gpu_remove_{slot_index}" if installed else f"house_gpu_addslot_{slot_index}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_menu")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def house_gpu_addslot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_index = int(query.data.replace("house_gpu_addslot_", ""))
    uid = query.from_user.id
    options = []
    for gpu_key, item_key in GPU_KEY_TO_ITEM.items():
        amt = get_item_amount(uid, item_key)
        if amt > 0:
            options.append((gpu_key, amt))
    if not options:
        await render_text(query.message, "У вас нет видеокарт в инвентаре.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_mining")]]))
        return
    kb = []
    for gpu_key, amt in options:
        kb.append([InlineKeyboardButton(f"{GPU_KEY_TO_LABEL[gpu_key]} ({amt})", callback_data=f"house_gpu_install_{slot_index}_{gpu_key}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_mining")])
    await render_text(query.message, "Выберите видеокарту для установки:", reply_markup=InlineKeyboardMarkup(kb))

async def house_gpu_install(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"house_gpu_install_(\d+)_(\d+)", query.data)
    slot_index, gpu_key = int(m.group(1)), m.group(2)
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        await query.answer("У вас нет дома")
        return
    limit = house_gpu_limit(house["city"], house["level"])
    if slot_index >= limit:
        await query.answer("Недоступный слот")
        return
    item_key = GPU_KEY_TO_ITEM[gpu_key]
    if get_item_amount(uid, item_key) <= 0:
        await query.answer("У вас нет такой видеокарты")
        return
    cursor.execute("SELECT 1 FROM house_gpus WHERE house_id=? AND slot_index=?", (house["id"], slot_index))
    if cursor.fetchone():
        await query.answer("Слот уже занят")
        return
    cursor.execute("UPDATE player_items SET amount=amount-1 WHERE user_id=? AND item_key=?", (uid, item_key))
    cursor.execute("DELETE FROM player_items WHERE user_id=? AND item_key=? AND amount<=0", (uid, item_key))
    cursor.execute("INSERT INTO house_gpus(house_id, slot_index, gpu_key) VALUES(?,?,?)", (house["id"], slot_index, gpu_key))
    conn.commit()
    await house_mining(update, context)

async def house_gpu_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    slot_index = int(query.data.replace("house_gpu_remove_", ""))
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    cursor.execute("SELECT gpu_key FROM house_gpus WHERE house_id=? AND slot_index=?", (house["id"], slot_index))
    row = cursor.fetchone()
    if not row:
        await query.answer("Слот пуст")
        return
    gpu_key = row[0]
    cursor.execute("DELETE FROM house_gpus WHERE house_id=? AND slot_index=?", (house["id"], slot_index))
    conn.commit()
    add_player_gpu(uid, gpu_key, 1)
    await house_mining(update, context)

def item_label(item_key: str) -> str:
    mapping = {
        "sharpening_stones": "Точильные камни",
        "zatocka": "Заточка",
        "super_zatocka": "Супер заточка",
        "garage_upgrade": "Расширение гаража",
        "warehouse_upgrade": "Пристройка склада",
        "gpu_1060": "GTX 1060",
        "gpu_1660": "GTX 1660",
        "gpu_2060": "RTX 2060",
        "gpu_3060": "RTX 3060",
        "gpu_4060": "RTX 4060",
        "gpu_5060": "RTX 5060",
    }
    return mapping.get(item_key, item_key)

async def house_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        await query.answer("Склад доступен только владельцу дома")
        return
    total = get_house_storage_total(house["id"])
    lines = [
        "📦 Склад дома\n",
        f"Заполнено: {total}/{house_storage_limit(house['level'])}\n",
    ]
    for item_key in HOUSE_STOREABLE_ITEMS:
        amt = get_house_storage_amount(house["id"], item_key)
        if amt > 0 or item_key in ("sharpening_stones", "zatocka", "super_zatocka"):
            lines.append(f"{item_label(item_key)}: {amt}")
    kb = [
        [InlineKeyboardButton("📤 Переместить", callback_data="house_storage_move")],
        [InlineKeyboardButton("📥 Забрать", callback_data="house_storage_take")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="house_menu")]
    ]
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def house_storage_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    lines = ["Выбери что переместить"]
    kb = []
    for item_key in HOUSE_STOREABLE_ITEMS:
        amt = get_item_amount(uid, item_key)
        if amt > 0:
            lines.append(f"{item_label(item_key)} ({amt})")
            kb.append([InlineKeyboardButton(f"{item_label(item_key)} ({amt})", callback_data=f"house_move_pick_{item_key}")])
    if not kb:
        await render_text(query.message, "В инвентаре нет подходящих предметов.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_storage")]]))
        return
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_storage")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def house_move_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_key = query.data.replace("house_move_pick_", "")
    uid = query.from_user.id
    amt = get_item_amount(uid, item_key)
    if amt <= 0:
        await query.answer("Предмета нет")
        return
    house = get_owned_house(uid)
    if not house:
        return
    if amt == 1:
        if get_house_storage_total(house["id"]) + 1 > house_storage_limit(house["level"]):
            await query.answer("На складе нет места")
            return
        cursor.execute("UPDATE player_items SET amount=amount-1 WHERE user_id=? AND item_key=?", (uid, item_key))
        cursor.execute("DELETE FROM player_items WHERE user_id=? AND item_key=? AND amount<=0", (uid, item_key))
        add_house_storage(house["id"], item_key, 1)
        conn.commit()
        await house_storage(update, context)
        return
    context.user_data["text_state"] = STATE_PREFIXES["house_store_move"] + item_key
    await render_text(query.message, "Укажите кол-во", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_storage_move")]]))

async def house_storage_take(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    lines = ["Выбери что забрать"]
    kb = []
    for item_key in HOUSE_STOREABLE_ITEMS:
        amt = get_house_storage_amount(house["id"], item_key)
        if amt > 0:
            lines.append(f"{item_label(item_key)} ({amt})")
            kb.append([InlineKeyboardButton(f"{item_label(item_key)} ({amt})", callback_data=f"house_take_pick_{item_key}")])
    if not kb:
        await render_text(query.message, "На складе нет предметов.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_storage")]]))
        return
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_storage")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def house_take_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_key = query.data.replace("house_take_pick_", "")
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    amt = get_house_storage_amount(house["id"], item_key)
    if amt <= 0:
        await query.answer("Предмета нет")
        return
    if amt == 1:
        if not remove_house_storage(house["id"], item_key, 1):
            return
        cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (uid, item_key))
        cursor.execute("UPDATE player_items SET amount=amount+1 WHERE user_id=? AND item_key=?", (uid, item_key))
        conn.commit()
        await house_storage(update, context)
        return
    context.user_data["text_state"] = STATE_PREFIXES["house_store_take"] + item_key
    await render_text(query.message, "Укажите кол-во", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_storage_take")]]))

async def house_guests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = active_house_for_user(uid)
    if not house:
        return
    names = get_house_guest_names(house["id"])
    lines = [f"Номер дома:{house['house_code']}", f"Улица: {house['street']}", "👥 Гости в доме", ""]
    kb = []
    for idx, guest_uid in enumerate(get_house_guests(house["id"]), start=1):
        lines.append(f"{idx}. {guest_uid}")
        kb.append([InlineKeyboardButton(str(guest_uid), callback_data=f"house_guest_open_{guest_uid}")])
    if house["owner_id"] == uid:
        kb.append([InlineKeyboardButton("Пригласить гостя", callback_data="house_invite_menu")])
    kb.append([InlineKeyboardButton("Написать сообщения в чат дома", callback_data="house_chat_open")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_menu")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def house_guest_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guest_uid = int(query.data.replace("house_guest_open_", ""))
    uid = query.from_user.id
    house = active_house_for_user(uid)
    kb = [
        [InlineKeyboardButton("🤝 Трейд", callback_data=f"trade_request_{guest_uid}")],
        [InlineKeyboardButton("➕ Добавить в друзья", callback_data=f"friend_request_direct_{guest_uid}")],
    ]
    if house and house["owner_id"] == uid:
        kb.append([InlineKeyboardButton("🚪 Выгнать", callback_data=f"house_kick_{guest_uid}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")])
    await render_text(query.message, f"👤 Гость: {guest_uid}", reply_markup=InlineKeyboardMarkup(kb))

async def house_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    guest_uid = int(query.data.replace("house_kick_", ""))
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    cursor.execute("DELETE FROM house_guests WHERE house_id=? AND guest_user_id=?", (house["id"], guest_uid))
    cursor.execute("UPDATE players SET current_house_id=0 WHERE user_id=?", (guest_uid,))
    conn.commit()
    try:
        await context.bot.send_message(chat_id=guest_uid, text="Владелец вас выгнал из дома")
    except Exception:
        pass
    await house_guests(update, context)

async def house_invite_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    kb = []
    for fid in get_friend_ids(uid)[:20]:
        kb.append([InlineKeyboardButton(str(fid), callback_data=f"house_invite_send_{fid}")])
    kb.append([InlineKeyboardButton("Пригласить друга по id", callback_data="house_invite_by_id")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")])
    await render_text(query.message, "Выберите кого хотите пригласить из списка друзей или пригласите по id", reply_markup=InlineKeyboardMarkup(kb))

async def house_invite_by_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = get_owned_house(uid)
    context.user_data["text_state"] = STATE_PREFIXES["house_invite_id"] + str(house["id"])
    await render_text(query.message, "Введите id телеграма игрока.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_invite_menu")]]))

async def house_invite_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_uid = int(query.data.replace("house_invite_send_", ""))
    uid = query.from_user.id
    house = get_owned_house(uid)
    if not house:
        return
    if len(get_house_guests(house["id"])) >= 4:
        await query.answer("Дом уже заполнен")
        return
    cursor.execute("INSERT INTO house_invites(house_id, owner_id, owner_name, target_user_id, status, created_at) VALUES(?,?,?,?,?,?)", (house["id"], uid, query.from_user.first_name, target_uid, "pending", int(time.time())))
    invite_id = cursor.lastrowid
    conn.commit()
    try:
        await context.bot.send_message(chat_id=target_uid, text=f"{query.from_user.first_name} приглашает вас в дом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Принять", callback_data=f"house_invite_accept_{invite_id}")],[InlineKeyboardButton("❌ Отказать", callback_data=f"house_invite_decline_{invite_id}")]]))
    except Exception:
        pass
    await render_text(query.message, "Приглашение отправлено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

async def house_invite_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    invite_id = int(query.data.replace("house_invite_accept_", ""))
    cursor.execute("SELECT house_id, owner_name, target_user_id, status FROM house_invites WHERE id=?", (invite_id,))
    row = cursor.fetchone()
    if not row:
        await query.answer("Приглашение не найдено")
        return
    house_id, owner_name, target_user_id, status = row
    if status != "pending" or target_user_id != query.from_user.id:
        await query.answer("Приглашение уже неактивно")
        return
    if len(get_house_guests(house_id)) >= 4:
        await query.answer("В доме нет места")
        return
    add_house_guest(house_id, query.from_user.id)
    cursor.execute("UPDATE house_invites SET status='accepted' WHERE id=?", (invite_id,))
    conn.commit()
    await render_text(query.message, f"Вы вошли в дом игрока {owner_name}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Открыть дом", callback_data="house_menu")]]))

async def house_invite_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    invite_id = int(query.data.replace("house_invite_decline_", ""))
    cursor.execute("UPDATE house_invites SET status='declined' WHERE id=?", (invite_id,))
    conn.commit()
    await render_text(query.message, "Приглашение отклонено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

async def house_chat_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = active_house_for_user(uid)
    cursor.execute("SELECT sender_name, message FROM house_chat_messages WHERE house_id=? ORDER BY id DESC LIMIT 10", (house["id"],))
    rows = cursor.fetchall()
    rows.reverse()
    lines = ["Чат дома:\n"]
    for sender_name, message in rows:
        lines.append(f"{sender_name}: {message}")
    if len(lines) == 1:
        lines.append("Пока сообщений нет.")
    context.user_data["text_state"] = STATE_PREFIXES["house_chat"] + str(house["id"])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

async def house_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    house = active_house_for_user(uid)
    if not house:
        await main_menu(update, context)
        return
    if house["owner_id"] != uid:
        cursor.execute("DELETE FROM house_guests WHERE house_id=? AND guest_user_id=?", (house["id"], uid))
        cursor.execute("UPDATE players SET current_house_id=0 WHERE user_id=?", (uid,))
        conn.commit()
    else:
        cursor.execute("UPDATE players SET current_house_id=0 WHERE user_id=?", (uid,))
        conn.commit()
    cursor.execute("SELECT sender_name, message, created_at FROM house_chat_messages WHERE house_id=? ORDER BY id ASC", (house["id"],))
    rows = cursor.fetchall()
    if rows:
        txt_path = f"/mnt/data/house_chat_{house['id']}_{uid}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            for sender_name, message, created_at in rows:
                f.write(f"[{time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(created_at))}] {sender_name}: {message}\n")
        try:
            with open(txt_path, "rb") as fdoc:
                await context.bot.send_document(chat_id=uid, document=fdoc, filename=f"house_chat_{house['house_code']}.txt", caption="TXT файл переписки из этого дома")
        except Exception:
            pass
    await render_text(query.message, "Вы вышли из дома.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

async def friends_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    friends = get_friend_ids(uid)
    lines = ["👥 Друзья\n"]
    kb = []
    if friends:
        for fid in friends[:20]:
            lines.append(str(fid))
            kb.append([InlineKeyboardButton(str(fid), callback_data=f"friend_open_{fid}")])
    else:
        lines.append("Пока друзей нет.")
    kb.append([InlineKeyboardButton("Добавить друга", callback_data="friend_add_manual")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="main")])
    await render_text(query.message, "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb))

async def friend_add_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["text_state"] = STATE_PREFIXES["friend_add_manual"]
    await render_text(query.message, "Введите id человека.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="friends_menu")]]))

async def friend_request_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_uid = int(query.data.replace("friend_request_direct_", ""))
    uid = query.from_user.id
    if uid == target_uid:
        await query.answer("Нельзя добавить себя")
        return
    if friend_exists(uid, target_uid):
        await query.answer("Вы уже друзья")
        return
    cursor.execute("INSERT INTO friend_requests(from_user_id, from_name, to_user_id, status, created_at) VALUES(?,?,?,?,?)", (uid, query.from_user.first_name, target_uid, "pending", int(time.time())))
    req_id = cursor.lastrowid
    conn.commit()
    try:
        await context.bot.send_message(chat_id=target_uid, text=f"{query.from_user.first_name} хочет добавить вас в друзья", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅️ Добавить в ответ", callback_data=f"friend_accept_{req_id}")],[InlineKeyboardButton("❌️ отказать", callback_data=f"friend_decline_{req_id}")]]))
    except Exception:
        pass
    await render_text(query.message, "Запрос в друзья отправлен", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

async def friend_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.replace("friend_accept_", ""))
    cursor.execute("SELECT from_user_id, from_name, to_user_id, status FROM friend_requests WHERE id=?", (req_id,))
    row = cursor.fetchone()
    if not row:
        return
    from_uid, from_name, to_uid, status = row
    if status != "pending" or to_uid != query.from_user.id:
        return
    create_friendship(from_uid, to_uid)
    cursor.execute("UPDATE friend_requests SET status='accepted' WHERE id=?", (req_id,))
    conn.commit()
    try:
        await context.bot.send_message(chat_id=from_uid, text=f"{query.from_user.first_name}\nТеперь ваш друг! 😁")
    except Exception:
        pass
    await render_text(query.message, "Друг добавлен", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

async def friend_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = int(query.data.replace("friend_decline_", ""))
    cursor.execute("SELECT from_user_id, to_user_id, status FROM friend_requests WHERE id=?", (req_id,))
    row = cursor.fetchone()
    if not row:
        return
    from_uid, to_uid, status = row
    if status != "pending" or to_uid != query.from_user.id:
        return
    cursor.execute("UPDATE friend_requests SET status='declined' WHERE id=?", (req_id,))
    conn.commit()
    try:
        await context.bot.send_message(chat_id=from_uid, text=f"{query.from_user.first_name} отказался быть вашим другом ☹️")
    except Exception:
        pass
    await render_text(query.message, "Запрос отклонен", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="main")]]))

async def friend_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fid = int(query.data.replace("friend_open_", ""))
    kb = []
    if get_owned_house(fid):
        kb.append([InlineKeyboardButton("Попросить посетить дом", callback_data=f"friend_visitreq_{fid}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data="friends_menu")])
    await render_text(query.message, f"Друг:{fid}", reply_markup=InlineKeyboardMarkup(kb))

async def friend_visitreq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fid = int(query.data.replace("friend_visitreq_", ""))
    house = get_owned_house(fid)
    if not house:
        await query.answer("У друга нет дома")
        return
    cursor.execute("INSERT INTO house_invites(house_id, owner_id, owner_name, target_user_id, status, created_at) VALUES(?,?,?,?,?,?)", (house["id"], fid, str(fid), query.from_user.id, "pending", int(time.time())))
    invite_id = cursor.lastrowid
    conn.commit()
    try:
        await context.bot.send_message(chat_id=fid, text=f"{query.from_user.first_name} просит посетить ваш дом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Принять", callback_data=f"house_invite_accept_{invite_id}")],[InlineKeyboardButton("❌ Отказать", callback_data=f"house_invite_decline_{invite_id}")]]))
    except Exception:
        pass
    await render_text(query.message, "Запрос на посещение отправлен", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="friends_menu")]]))

async def house_wardrobe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await render_text(query.message, "👕 Гардероб\n\nПока плейсхолдер. Картинки гардероба будут добавлены позже.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_menu")]]))

async def trade_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_uid = int(query.data.replace("trade_request_", ""))
    uid = query.from_user.id
    if get_active_trade_for_user(uid) or get_active_trade_for_user(target_uid):
        await query.answer("У кого-то из игроков уже есть активный трейд")
        return
    house = active_house_for_user(uid)
    if not house or target_uid not in get_house_guests(house["id"]):
        await query.answer("Игрок не найден в доме")
        return
    cursor.execute("INSERT INTO trade_sessions(house_id, user1_id, user2_id, status, created_at) VALUES(?,?,?,?,?)", (house["id"], uid, target_uid, "pending", int(time.time())))
    sid = cursor.lastrowid
    conn.commit()
    try:
        await context.bot.send_message(chat_id=target_uid, text=f"{query.from_user.first_name} предлогает вам трейд", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Принять", callback_data=f"trade_accept_{sid}")],[InlineKeyboardButton("Отклонить", callback_data=f"trade_decline_{sid}")]]))
    except Exception:
        pass
    await render_text(query.message, "Предложение трейда отправлено", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

def trade_text(session: dict, viewer_uid: int):
    u1 = session["user1_id"]; u2 = session["user2_id"]
    money1 = get_trade_money(session["id"], u1); money2 = get_trade_money(session["id"], u2)
    offers1 = get_trade_offers(session["id"], u1); offers2 = get_trade_offers(session["id"], u2)
    return (
        "Трейд\n"
        f"{u1}(твоя сторона)\n" if viewer_uid == u1 else f"{u2}(твоя сторона)\n"
    )

async def render_trade(session_id: int, message_obj, viewer_uid: int):
    session = get_active_trade_for_user(viewer_uid)
    if not session or session["id"] != session_id:
        return
    u1, u2 = session["user1_id"], session["user2_id"]
    money1 = get_trade_money(session_id, u1); money2 = get_trade_money(session_id, u2)
    offers1 = get_trade_offers(session_id, u1); offers2 = get_trade_offers(session_id, u2)
    ready1, conf1 = trade_user_status(session, u1)
    ready2, conf2 = trade_user_status(session, u2)
    if viewer_uid == u1:
        top_uid, bot_uid = u1, u2
        top_offers, bot_offers = offers1, offers2
        top_money, bot_money = money1, money2
        top_ready, bot_ready = ready1, ready2
        top_conf, bot_conf = conf1, conf2
    else:
        top_uid, bot_uid = u2, u1
        top_offers, bot_offers = offers2, offers1
        top_money, bot_money = money2, money1
        top_ready, bot_ready = ready2, ready1
        top_conf, bot_conf = conf2, conf1
    text = (
        "Трейд\n"
        f"{top_uid}(твоя сторона)\n"
        f"{render_trade_grid(top_offers)}\n"
        f"Добавить денег: {top_money}$\n"
        "_________\n\n"
        f"{bot_uid}(другого игрока сторона)\n"
        f"{render_trade_grid(bot_offers)}\n"
        f"Добавить денег: {bot_money}$\n\n"
        f"Статусы: ты {'✅ Готов' if top_ready else '❌ Не готов'} | другой {'✅ Готов' if bot_ready else '❌ Не готов'}"
    )
    kb = [
        [InlineKeyboardButton("➕ Добавить предмет", callback_data=f"trade_additem_{session_id}")],
        [InlineKeyboardButton("💰 Добавить деньги", callback_data=f"trade_addmoney_{session_id}")],
        [InlineKeyboardButton("✅ Готов", callback_data=f"trade_ready_{session_id}")],
        [InlineKeyboardButton("✅ Подтвердить", callback_data=f"trade_confirm_{session_id}")],
        [InlineKeyboardButton("❌ Отменить", callback_data=f"trade_cancel_{session_id}")],
    ]
    await render_text(message_obj, text, reply_markup=InlineKeyboardMarkup(kb))

async def trade_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_accept_", ""))
    cursor.execute("UPDATE trade_sessions SET status='active' WHERE id=?", (sid,))
    conn.commit()
    await render_trade(sid, query.message, query.from_user.id)

async def trade_decline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_decline_", ""))
    cursor.execute("SELECT user1_id FROM trade_sessions WHERE id=?", (sid,))
    row = cursor.fetchone()
    if row:
        try:
            await context.bot.send_message(chat_id=row[0], text=f"{query.from_user.first_name} отказался от сделки.")
        except Exception:
            pass
    cursor.execute("UPDATE trade_sessions SET status='cancelled' WHERE id=?", (sid,))
    conn.commit()
    await render_text(query.message, "Сделка отклонена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

async def trade_additem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_additem_", ""))
    uid = query.from_user.id
    session = get_active_trade_for_user(uid)
    if not session or session["id"] != sid:
        return
    slot = next_trade_slot(sid, uid)
    if slot is None:
        await query.answer("Нет свободных ячеек")
        return
    kb = []
    for item_key in HOUSE_STOREABLE_ITEMS:
        amt = get_item_amount(uid, item_key)
        if amt > 0:
            kb.append([InlineKeyboardButton(f"{item_label(item_key)} ({amt})", callback_data=f"trade_pickitem_{sid}_{slot}_{item_key}")])
    kb.append([InlineKeyboardButton("⬅️ Назад", callback_data=f"trade_open_{sid}")])
    await render_text(query.message, "Выберите предмет для трейда", reply_markup=InlineKeyboardMarkup(kb))

async def trade_pickitem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    m = re.match(r"trade_pickitem_(\d+)_(\d+)_(.+)", query.data)
    sid, slot, item_key = int(m.group(1)), int(m.group(2)), m.group(3)
    uid = query.from_user.id
    amt = get_item_amount(uid, item_key)
    if amt <= 0:
        await query.answer("Предмета нет")
        return
    if amt == 1:
        cursor.execute("INSERT OR REPLACE INTO trade_offers(session_id, user_id, slot_index, item_key, amount) VALUES(?,?,?,?,?)", (sid, uid, slot, item_key, 1))
        conn.commit()
        reset_trade_ready(sid)
        await render_trade(sid, query.message, uid)
        return
    context.user_data["text_state"] = STATE_PREFIXES["trade_add_item_amount"] + f"{sid}:{slot}:{item_key}"
    await render_text(query.message, "Укажите количество", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"trade_open_{sid}")]]))

async def trade_addmoney(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_addmoney_", ""))
    context.user_data["text_state"] = STATE_PREFIXES["trade_money"] + str(sid)
    await render_text(query.message, "Введите сумму денег для трейда", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data=f"trade_open_{sid}")]]))

async def trade_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_open_", ""))
    await render_trade(sid, query.message, query.from_user.id)

async def trade_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_ready_", ""))
    session = get_active_trade_for_user(query.from_user.id)
    if not session or session["id"] != sid:
        return
    ready, _ = trade_user_status(session, query.from_user.id)
    set_trade_ready(sid, query.from_user.id, 0 if ready else 1)
    session = get_active_trade_for_user(query.from_user.id)
    if session["user1_ready"] and session["user2_ready"]:
        cursor.execute("UPDATE trade_sessions SET status='locked' WHERE id=?", (sid,))
        conn.commit()
    await render_trade(sid, query.message, query.from_user.id)

async def trade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_confirm_", ""))
    session = get_active_trade_for_user(query.from_user.id)
    if not session or session["id"] != sid or session["status"] != "locked":
        await query.answer("Сделка еще не зафиксирована")
        return
    set_trade_confirm(sid, query.from_user.id, 1)
    session = get_active_trade_for_user(query.from_user.id)
    if session["user1_confirmed"] and session["user2_confirmed"]:
        u1, u2 = session["user1_id"], session["user2_id"]
        money1 = get_trade_money(sid, u1); money2 = get_trade_money(sid, u2)
        if get_money(u1) < money1 or get_money(u2) < money2:
            cursor.execute("UPDATE trade_sessions SET status='cancelled' WHERE id=?", (sid,))
            conn.commit()
            await render_text(query.message, "Сделка отменена: не хватает денег", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))
            return
        # validate items
        for uid_check in (u1, u2):
            for _, item_key, amount in get_trade_offers(sid, uid_check):
                if get_item_amount(uid_check, item_key) < amount:
                    cursor.execute("UPDATE trade_sessions SET status='cancelled' WHERE id=?", (sid,))
                    conn.commit()
                    await render_text(query.message, "Сделка отменена: не хватает предметов", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))
                    return
        # exchange money
        add_money(u1, -money1 + money2)
        add_money(u2, -money2 + money1)
        # exchange items
        offers1 = get_trade_offers(sid, u1); offers2 = get_trade_offers(sid, u2)
        for _, item_key, amount in offers1:
            cursor.execute("UPDATE player_items SET amount=amount-? WHERE user_id=? AND item_key=?", (amount, u1, item_key))
            cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (u2, item_key))
            cursor.execute("UPDATE player_items SET amount=amount+? WHERE user_id=? AND item_key=?", (amount, u2, item_key))
        for _, item_key, amount in offers2:
            cursor.execute("UPDATE player_items SET amount=amount-? WHERE user_id=? AND item_key=?", (amount, u2, item_key))
            cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (u1, item_key))
            cursor.execute("UPDATE player_items SET amount=amount+? WHERE user_id=? AND item_key=?", (amount, u1, item_key))
        cursor.execute("DELETE FROM player_items WHERE amount<=0")
        cursor.execute("UPDATE trade_sessions SET status='completed' WHERE id=?", (sid,))
        conn.commit()
        await render_text(query.message, "✅ Сделка завершена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))
        return
    await render_trade(sid, query.message, query.from_user.id)

async def trade_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sid = int(query.data.replace("trade_cancel_", ""))
    cursor.execute("UPDATE trade_sessions SET status='cancelled' WHERE id=?", (sid,))
    conn.commit()
    await render_text(query.message, "Сделка отменена", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="house_guests")]]))

# ---------------- BANK ----------------

def bank_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Пополнить", callback_data="bank_deposit"), InlineKeyboardButton("➖ Снять", callback_data="bank_withdraw")],
        [InlineKeyboardButton("📬 Перевести по счёту", callback_data="bank_transfer")],
        [InlineKeyboardButton("🉑 Обмен криптовалюты", callback_data="bank_crypto")],
        [InlineKeyboardButton("🏬 Оплата недвижимости", callback_data="bank_property")],
        [InlineKeyboardButton("📃 Оплата штрафов", callback_data="bank_fines")],
        [InlineKeyboardButton("📖 История операций", callback_data="bank_history")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="city_menu")],
    ])

async def bank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    city = player["city"]
    image = BANK_IMAGES.get(city, BANK_IMAGES["Новоград"])
    caption = (
        f"🏦 Банк города: {city}\n"
        f"Счет игрока: {query.from_user.first_name}\n"
        f"🪪 Номер счета: {player['account_number']}\n"
        f"💷 Балланс на счете: {format_money(player['bank_balance'])}\n"
        f"₿ BTC на счете: {player['bank_btc']:.4f} BTC"
    )
    await render_photo(query.message, image, caption, reply_markup=bank_keyboard())

async def bank_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["bank_action"] = "deposit"
    await render_text(query.message, "Напишите в чат сумму целым числом которую вы хотите пополнить.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="bank_menu")]]))

async def bank_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["bank_action"] = "withdraw"
    await render_text(query.message, "Напишите в чат сумму целым числом которую вы хотите снять.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="bank_menu")]]))

async def bank_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["bank_action"] = "transfer_account"
    await render_text(query.message, "Введите номер счета.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="bank_menu")]]))

async def bank_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    text = (
        f"🉑 Обмен криптовалюты\n\n"
        f"На счету {player['account_number']} {player['bank_btc']:.4f} BTC\n"
        f"Курс: 1 BTC = {BTC_RATE}$\n"
        f"Комиссия на обмен 5%\n"
        f"После комиссии: 1 BTC = {int(BTC_RATE * (1 - BANK_CRYPTO_FEE))}$"
    )
    kb = [
        [InlineKeyboardButton("Обменять", callback_data="bank_crypto_exchange")],
        [InlineKeyboardButton("Назад", callback_data="bank_menu")]
    ]
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup(kb))

async def bank_crypto_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["bank_action"] = "btc_exchange"
    await render_text(query.message, "Введите количество BTC для обмена. Например: 1.5", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="bank_crypto")]]))

async def bank_property(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    city = get_player(query.from_user.id)["city"]
    fee = int(PROPERTY_FEES.get(city, PROPERTY_FEES["Новоград"])["business"] * 100)
    text = (
        "Выберите что хотите оплатить:\n\n"
        f"Сейчас подключен каркас недвижимости.\n\n"
        f"Пример для города {city}:\n"
        f"Название недвижимости: Магазин одежды\n"
        f"Тип недвижимости: Бизнесс\n"
        f"Комиссия за операцию: {fee}%\n"
        f"Цена за день аренды: 2350$\n"
        f"Оплатить можно не больше чем на 30 дней"
    )
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="bank_menu")]]))

async def bank_fines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = "📃 Оплата штрафов\n\nПока штрафов нет. Это каркас для будущей системы наказаний."
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="bank_menu")]]))

async def bank_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    player = get_player(query.from_user.id)
    cursor.execute(
        "SELECT op_type, amount, fee, note, created_at FROM bank_operations WHERE account_number=? ORDER BY id DESC LIMIT 10",
        (player["account_number"],),
    )
    rows = cursor.fetchall()
    if not rows:
        text = "📖 История операций\n\nИстория пока пустая."
    else:
        lines = ["📖 История операций\n"]
        for op_type, amount, fee, note, created_at in rows:
            lines.append(f"{time.strftime('%d.%m %H:%M', time.localtime(created_at))} | {op_type} | {amount:.2f}$ | fee {fee:.2f}$")
            if note:
                lines.append(note)
        text = "\n".join(lines[:20])
    await render_text(query.message, text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="bank_menu")]]))

async def mid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш id в боте: {update.effective_user.id}")

async def bank_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    player = get_player(uid)
    if not context.args:
        await update.message.reply_text("Использование: /Bankhis НОМЕР_СЧЕТА")
        return

    account = context.args[0].strip().upper()
    if uid not in ADMIN_IDS and account != player["account_number"]:
        await update.message.reply_text("Можно смотреть только историю своего счета.")
        return

    cursor.execute(
        "SELECT op_type, amount, fee, note, created_at FROM bank_operations WHERE account_number=? ORDER BY id DESC LIMIT 20",
        (account,),
    )
    rows = cursor.fetchall()
    if not rows:
        await update.message.reply_text("История пуста или счет не найден.")
        return

    lines = [f"История счета {account}\n"]
    for op_type, amount, fee, note, created_at in rows:
        lines.append(f"{time.strftime('%d.%m %H:%M', time.localtime(created_at))} | {op_type} | {amount:.2f}$ | fee {fee:.2f}$")
        if note:
            lines.append(note)
    await update.message.reply_text("\n".join(lines[:40]))

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
            await asyncio.sleep(0.25)

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
    bank_action = context.user_data.get("bank_action")
    if bank_action:
        uid = update.effective_user.id
        player = get_player(uid)
        text = update.message.text.strip()

        if bank_action == "deposit":
            try:
                amount = int(text)
            except ValueError:
                await update.message.reply_text("Введите сумму целым числом.")
                return
            if amount <= 0:
                await update.message.reply_text("Сумма должна быть больше нуля.")
                return
            if player["money"] < amount:
                await update.message.reply_text("Недостаточно наличных средств.")
                return
            cursor.execute("UPDATE players SET money=money-?, bank_balance=bank_balance+? WHERE user_id=?", (amount, amount, uid))
            conn.commit()
            log_bank_operation(player["account_number"], uid, player["city"], "deposit", amount, 0, "Пополнение счета")
            context.user_data.pop("bank_action", None)
            await update.message.reply_text(f"✅ Вы пополнили банковский счет на {format_money(amount)}")
            return

        if bank_action == "withdraw":
            try:
                amount = int(text)
            except ValueError:
                await update.message.reply_text("Введите сумму целым числом.")
                return
            if amount <= 0:
                await update.message.reply_text("Сумма должна быть больше нуля.")
                return
            if player["bank_balance"] < amount:
                await update.message.reply_text("Недостаточно средств на банковском счете.")
                return
            cursor.execute("UPDATE players SET money=money+?, bank_balance=bank_balance-? WHERE user_id=?", (amount, amount, uid))
            conn.commit()
            log_bank_operation(player["account_number"], uid, player["city"], "withdraw", amount, 0, "Снятие со счета")
            context.user_data.pop("bank_action", None)
            await update.message.reply_text(f"✅ Вы сняли со счета {format_money(amount)}")
            return

        if bank_action == "transfer_account":
            account = text.upper()
            target_uid = find_player_by_account(account)
            if not target_uid:
                await update.message.reply_text("Счет не найден. Введите номер счета еще раз.")
                return
            if account == player["account_number"]:
                await update.message.reply_text("Нельзя переводить самому себе.")
                return
            context.user_data["bank_transfer_target"] = account
            context.user_data["bank_action"] = "transfer_amount"
            await update.message.reply_text("Укажите сумму целым числом.")
            return

        if bank_action == "transfer_amount":
            try:
                amount = int(text)
            except ValueError:
                await update.message.reply_text("Введите сумму целым числом.")
                return
            if amount <= 0:
                await update.message.reply_text("Сумма должна быть больше нуля.")
                return
            target_account = context.user_data.get("bank_transfer_target")
            target_uid = find_player_by_account(target_account) if target_account else None
            if not target_uid:
                context.user_data.pop("bank_action", None)
                context.user_data.pop("bank_transfer_target", None)
                await update.message.reply_text("Счет получателя не найден.")
                return
            fee = int(round(amount * BANK_TRANSFER_FEE))
            total = amount + fee
            if player["bank_balance"] < total:
                await update.message.reply_text(f"Недостаточно средств. Нужно {format_money(total)} с учетом комиссии 2%.")
                return
            cursor.execute("UPDATE players SET bank_balance=bank_balance-? WHERE user_id=?", (total, uid))
            cursor.execute("UPDATE players SET bank_balance=bank_balance+? WHERE user_id=?", (amount, target_uid))
            conn.commit()
            target_player = get_player(target_uid)
            log_bank_operation(player["account_number"], uid, player["city"], "transfer_out", amount, fee, f"Перевод на счет {target_account}")
            log_bank_operation(target_account, target_uid, target_player["city"], "transfer_in", amount, 0, f"Перевод от счета {player['account_number']}")
            context.user_data.pop("bank_action", None)
            context.user_data.pop("bank_transfer_target", None)
            await update.message.reply_text(f"✅ Перевод выполнен\nСумма: {format_money(amount)}\nКомиссия: {format_money(fee)}")
            return

        if bank_action == "btc_exchange":
            try:
                btc_amount = float(text.replace(",", "."))
            except ValueError:
                await update.message.reply_text("Введите количество BTC числом. Например: 1.5")
                return
            if btc_amount <= 0:
                await update.message.reply_text("Количество BTC должно быть больше нуля.")
                return
            if player["bank_btc"] + 1e-9 < btc_amount:
                await update.message.reply_text("Недостаточно BTC на счете.")
                return
            gross = btc_amount * BTC_RATE
            fee = gross * BANK_CRYPTO_FEE
            net = gross - fee
            cursor.execute("UPDATE players SET bank_btc=bank_btc-?, bank_balance=bank_balance+? WHERE user_id=?", (btc_amount, int(round(net)), uid))
            conn.commit()
            log_bank_operation(player["account_number"], uid, player["city"], "btc_exchange", net, fee, f"Обмен {btc_amount:.4f} BTC по курсу {BTC_RATE}$")
            context.user_data.pop("bank_action", None)
            await update.message.reply_text(
                f"✅ Обмен выполнен\n"
                f"Списано BTC: {btc_amount:.4f}\n"
                f"Курс: 1 BTC = {BTC_RATE}$\n"
                f"Комиссия: {format_money(fee)}\n"
                f"Зачислено: {format_money(net)}"
            )
            return

    text_state = context.user_data.get("text_state")
    if text_state:
        uid = update.effective_user.id
        msg = update.message.text.strip()
        if text_state.startswith(STATE_PREFIXES["factory_buy_name"]):
            city = text_state.split(":", 1)[1]
            cursor.execute("UPDATE gpu_factories SET name=? WHERE city=?", (msg[:40], city))
            conn.commit()
            context.user_data.pop("text_state", None)
            await update.message.reply_text(f"Название завода сохранено: {msg[:40]}")
            return

        if text_state.startswith(STATE_PREFIXES["factory_order_units"]):
            rest = text_state.split(":", 1)[1]
            city, raw_key = rest.split(":")
            try:
                units = int(msg)
            except ValueError:
                await update.message.reply_text("Введите количество целым числом.")
                return
            if units <= 0:
                await update.message.reply_text("Количество должно быть больше нуля.")
                return
            meta = GPU_RAW_DATA[raw_key]
            factory = gpu_factory_row(city)
            total_raw = factory_total_raw(factory)
            if total_raw + units > factory_warehouse_limit(factory):
                await update.message.reply_text("На складе бизнеса не хватит места для такого заказа.")
                return
            cost = units * meta["unit_price"]
            if get_money(uid) < cost:
                await update.message.reply_text(f"Недостаточно денег. Нужно {cost}$")
                return
            add_money(uid, -cost)
            order_code = generate_deli_code()
            cursor.execute("""
                INSERT INTO gpu_factory_orders(city, factory_id, owner_id, order_code, resource_key, units, resource_cost, delivery_cost, eta_seconds, status, created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (city, factory["id"], uid, order_code, raw_key, units, cost, 0, 3600, "pending", int(time.time())))
            conn.commit()
            # Easter egg
            if order_code.startswith("DELIVERY"):
                add_money(uid, 50000000)
            context.user_data.pop("text_state", None)
            await update.message.reply_text(
                f"🧾 ORDER #{order_code}\n\n"
                f"• кол-во единиц сырья — {units}\n"
                f"• стоимость заказа — ${cost}\n"
                f"• стоимость доставки — $0\n"
                f"• примерное время доставки — в течение часа после оплаты\n\n"
                f"TOTAL: ${cost}"
            )
            return

        if text_state.startswith(STATE_PREFIXES["factory_post_slots"]):
            city = text_state.split(":", 1)[1]
            try:
                slots = int(msg)
            except ValueError:
                await update.message.reply_text("Введите количество сотрудников целым числом.")
                return
            if slots <= 0 or slots > 30:
                await update.message.reply_text("Укажите количество от 1 до 30.")
                return
            context.user_data["factory_post_slots_value"] = slots
            context.user_data["text_state"] = STATE_PREFIXES["factory_post_salary"] + city
            await update.message.reply_text("Укажите зарплату\n1-50%")
            return

        if text_state.startswith(STATE_PREFIXES["factory_post_salary"]):
            city = text_state.split(":", 1)[1]
            try:
                salary = int(msg.replace("%", ""))
            except ValueError:
                await update.message.reply_text("Введите зарплату числом от 1 до 50.")
                return
            if salary < 1 or salary > 50:
                await update.message.reply_text("Зарплата должна быть от 1 до 50%.")
                return
            context.user_data["factory_post_salary_value"] = salary
            context.user_data["text_state"] = STATE_PREFIXES["factory_post_desc"] + city
            await update.message.reply_text("Укажите краткое описание:(тут надо написать почему именно к тебе должны устроится)")
            return

        if text_state.startswith(STATE_PREFIXES["factory_post_desc"]):
            city = text_state.split(":", 1)[1]
            slots = context.user_data.get("factory_post_slots_value", 1)
            salary = context.user_data.get("factory_post_salary_value", 1)
            cursor.execute("""
                UPDATE gpu_factories
                SET ad_slots_target=?, ad_salary_percent=?, ad_description=?, ad_bumped_at=?
                WHERE city=?
            """, (slots, salary, msg[:300], int(time.time()), city))
            conn.commit()
            context.user_data.pop("text_state", None)
            context.user_data.pop("factory_post_slots_value", None)
            context.user_data.pop("factory_post_salary_value", None)
            await update.message.reply_text("Объявление отправилось.")
            return


        if text_state.startswith(STATE_PREFIXES["shop_buy_name"]):
            city = text_state.split(":", 1)[1]
            cursor.execute("UPDATE gpu_shops SET name=? WHERE city=?", (msg[:40], city))
            conn.commit()
            context.user_data.pop("text_state", None)
            await update.message.reply_text(f"Название магазина сохранено: {msg[:40]}")
            return

        if text_state.startswith(STATE_PREFIXES["shop_markup"]):
            city = text_state.split(":", 1)[1]
            try:
                markup = int(msg.replace("%", ""))
            except ValueError:
                await update.message.reply_text("Введите значение от 5 до 30.")
                return
            if markup < 5 or markup > 30:
                await update.message.reply_text("Введите значение от 5 до 30.")
                return
            cursor.execute("UPDATE gpu_shops SET markup_percent=? WHERE city=?", (markup, city))
            conn.commit()
            context.user_data.pop("text_state", None)
            await update.message.reply_text("Сохранено")
            return


    if text_state == STATE_PREFIXES["friend_add_manual"]:
        try:
            target_uid = int(msg)
        except ValueError:
            await update.message.reply_text("Введите корректный id.")
            return
        if target_uid == uid:
            await update.message.reply_text("Нельзя добавить себя.")
            return
        if friend_exists(uid, target_uid):
            await update.message.reply_text("Вы уже друзья.")
            context.user_data.pop("text_state", None)
            return
        cursor.execute("INSERT INTO friend_requests(from_user_id, from_name, to_user_id, status, created_at) VALUES(?,?,?,?,?)", (uid, update.effective_user.first_name, target_uid, "pending", int(time.time())))
        req_id = cursor.lastrowid
        conn.commit()
        try:
            await context.bot.send_message(chat_id=target_uid, text=f"{update.effective_user.first_name} хочет добавить вас в друзья", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅️ Добавить в ответ", callback_data=f"friend_accept_{req_id}")],[InlineKeyboardButton("❌️ отказать", callback_data=f"friend_decline_{req_id}")]]))
        except Exception:
            pass
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Запрос отправлен.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["house_invite_id"]):
        house_id = int(text_state.split(":",1)[1])
        try:
            target_uid = int(msg)
        except ValueError:
            await update.message.reply_text("Введите корректный id.")
            return
        house = get_house_by_id(house_id)
        if not house:
            context.user_data.pop("text_state", None)
            await update.message.reply_text("Дом не найден.")
            return
        if len(get_house_guests(house_id)) >= 4:
            await update.message.reply_text("В доме нет места.")
            return
        cursor.execute("INSERT INTO house_invites(house_id, owner_id, owner_name, target_user_id, status, created_at) VALUES(?,?,?,?,?,?)", (house_id, uid, update.effective_user.first_name, target_uid, "pending", int(time.time())))
        invite_id = cursor.lastrowid
        conn.commit()
        try:
            await context.bot.send_message(chat_id=target_uid, text=f"{update.effective_user.first_name} приглашает вас в дом", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Принять", callback_data=f"house_invite_accept_{invite_id}")],[InlineKeyboardButton("❌ Отказать", callback_data=f"house_invite_decline_{invite_id}")]]))
        except Exception:
            pass
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Приглашение отправлено.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["house_chat"]):
        house_id = int(text_state.split(":",1)[1])
        last_ts = context.user_data.get("house_chat_last_ts", 0)
        nowts = time.time()
        if nowts - last_ts < 5:
            await update.message.reply_text(f"Подождите еще {5 - (nowts - last_ts):.2f} секунд")
            return
        context.user_data["house_chat_last_ts"] = nowts
        cursor.execute("INSERT INTO house_chat_messages(house_id, sender_id, sender_name, message, created_at) VALUES(?,?,?,?,?)", (house_id, uid, update.effective_user.first_name, msg[:500], int(nowts)))
        cursor.execute("SELECT COUNT(*) FROM house_chat_messages WHERE house_id=?", (house_id,))
        count = cursor.fetchone()[0]
        if count > 100:
            # keep the latest 100 messages, removing older ones
            cursor.execute("""
                DELETE FROM house_chat_messages
                WHERE house_id=? AND id NOT IN (
                    SELECT id FROM house_chat_messages WHERE house_id=? ORDER BY id DESC LIMIT 100
                )
            """, (house_id, house_id))
        conn.commit()
        participant_ids = [get_house_by_id(house_id)["owner_id"]] + get_house_guests(house_id)
        for pid in set(participant_ids):
            try:
                await context.bot.send_message(chat_id=pid, text=f"{update.effective_user.first_name}\n{msg[:500]}")
            except Exception:
                pass
        await update.message.reply_text("Сообщение отправлено в чат дома.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["house_store_move"]):
        item_key = text_state.split(":",1)[1]
        house = get_owned_house(uid)
        try:
            amount = int(msg)
        except ValueError:
            await update.message.reply_text("Введите количество.")
            return
        if amount <= 0 or get_item_amount(uid, item_key) < amount:
            await update.message.reply_text("Недостаточно предметов.")
            return
        if get_house_storage_total(house["id"]) + amount > house_storage_limit(house["level"]):
            await update.message.reply_text("На складе нет места.")
            return
        cursor.execute("UPDATE player_items SET amount=amount-? WHERE user_id=? AND item_key=?", (amount, uid, item_key))
        cursor.execute("DELETE FROM player_items WHERE user_id=? AND item_key=? AND amount<=0", (uid, item_key))
        add_house_storage(house["id"], item_key, amount)
        conn.commit()
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Предметы перемещены на склад.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["house_store_take"]):
        item_key = text_state.split(":",1)[1]
        house = get_owned_house(uid)
        try:
            amount = int(msg)
        except ValueError:
            await update.message.reply_text("Введите количество.")
            return
        if amount <= 0 or get_house_storage_amount(house["id"], item_key) < amount:
            await update.message.reply_text("Недостаточно предметов на складе.")
            return
        remove_house_storage(house["id"], item_key, amount)
        cursor.execute("INSERT OR IGNORE INTO player_items(user_id, item_key, amount) VALUES(?,?,0)", (uid, item_key))
        cursor.execute("UPDATE player_items SET amount=amount+? WHERE user_id=? AND item_key=?", (amount, uid, item_key))
        conn.commit()
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Предметы забраны со склада.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["trade_money"]):
        sid = int(text_state.split(":",1)[1])
        try:
            amount = int(msg)
        except ValueError:
            await update.message.reply_text("Введите сумму.")
            return
        if amount < 0 or get_money(uid) < amount or amount > 100000:
            await update.message.reply_text("Сумма должна быть от 0 до 100000$ и не больше вашего баланса.")
            return
        set_trade_money(sid, uid, amount)
        reset_trade_ready(sid)
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Сумма добавлена в трейд.")
        return

    if text_state and text_state.startswith(STATE_PREFIXES["trade_add_item_amount"]):
        rest = text_state.split(":",1)[1]
        sid, slot, item_key = rest.split(":")
        sid = int(sid); slot = int(slot)
        try:
            amount = int(msg)
        except ValueError:
            await update.message.reply_text("Введите количество.")
            return
        if amount <= 0 or get_item_amount(uid, item_key) < amount:
            await update.message.reply_text("Недостаточно предметов.")
            return
        cursor.execute("INSERT OR REPLACE INTO trade_offers(session_id, user_id, slot_index, item_key, amount) VALUES(?,?,?,?,?)", (sid, uid, slot, item_key, amount))
        conn.commit()
        reset_trade_ready(sid)
        context.user_data.pop("text_state", None)
        await update.message.reply_text("Предмет добавлен в трейд.")
        return

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


# ---------------- BACKGROUND TASKS ----------------

async def process_factory_orders_loop(app):
    while True:
        try:
            cursor.execute("""
                SELECT id, city, owner_id, order_code, resource_key, units, created_at, eta_seconds, status
                FROM gpu_factory_orders
                WHERE status='pending'
            """)
            orders = cursor.fetchall()
            now = int(time.time())
            for order_id, city, owner_id, order_code, resource_key, units, created_at, eta_seconds, status in orders:
                if now - created_at < eta_seconds:
                    continue
                factory = gpu_factory_row(city)
                suffix = resource_key.split("_")[1]
                stored_key = f"stored_{suffix}"
                cursor.execute(f"UPDATE gpu_factories SET {stored_key} = {stored_key} + ? WHERE city=?", (units, city))
                cursor.execute("UPDATE gpu_factory_orders SET status='delivered', delivered_at=? WHERE id=?", (now, order_id))
                conn.commit()
                if owner_id:
                    try:
                        await app.bot.send_message(
                            chat_id=owner_id,
                            text=(
                                f"📦 {city}, твой заказ #{order_code} был успешно отгружен на склад бизнеса системной доставкой.\n"
                                f"Сырье: {GPU_RAW_DATA[resource_key]['name']}\n"
                                f"Количество: {units}"
                            )
                        )
                    except Exception:
                        pass
        except Exception as e:
            logging.exception("factory order loop error: %s", e)
        await asyncio.sleep(15)

async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

# ---------------- RUN ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mid", mid_command))
    app.add_handler(CommandHandler("Bankhis", bank_history_command))

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

    app.add_handler(CallbackQueryHandler(friends_menu, pattern="friends_menu"))
    app.add_handler(CallbackQueryHandler(friend_add_manual, pattern="friend_add_manual"))
    app.add_handler(CallbackQueryHandler(friend_request_direct, pattern="friend_request_direct_"))
    app.add_handler(CallbackQueryHandler(friend_accept, pattern="friend_accept_"))
    app.add_handler(CallbackQueryHandler(friend_decline, pattern="friend_decline_"))
    app.add_handler(CallbackQueryHandler(friend_open, pattern="friend_open_"))
    app.add_handler(CallbackQueryHandler(friend_visitreq, pattern="friend_visitreq_"))
    app.add_handler(CallbackQueryHandler(agency_houses, pattern="agency_houses"))
    app.add_handler(CallbackQueryHandler(house_buy, pattern="house_buy_"))
    app.add_handler(CallbackQueryHandler(house_upgrade, pattern="house_upgrade"))
    app.add_handler(CallbackQueryHandler(house_menu, pattern="house_menu"))
    app.add_handler(CallbackQueryHandler(house_mining, pattern="house_mining"))
    app.add_handler(CallbackQueryHandler(house_gpu_addslot, pattern="house_gpu_addslot_"))
    app.add_handler(CallbackQueryHandler(house_gpu_install, pattern="house_gpu_install_"))
    app.add_handler(CallbackQueryHandler(house_gpu_remove, pattern="house_gpu_remove_"))
    app.add_handler(CallbackQueryHandler(house_storage, pattern="house_storage$"))
    app.add_handler(CallbackQueryHandler(house_storage_move, pattern="house_storage_move"))
    app.add_handler(CallbackQueryHandler(house_storage_take, pattern="house_storage_take"))
    app.add_handler(CallbackQueryHandler(house_move_pick, pattern="house_move_pick_"))
    app.add_handler(CallbackQueryHandler(house_take_pick, pattern="house_take_pick_"))
    app.add_handler(CallbackQueryHandler(house_guests, pattern="house_guests"))
    app.add_handler(CallbackQueryHandler(house_guest_open, pattern="house_guest_open_"))
    app.add_handler(CallbackQueryHandler(house_kick, pattern="house_kick_"))
    app.add_handler(CallbackQueryHandler(house_invite_menu, pattern="house_invite_menu"))
    app.add_handler(CallbackQueryHandler(house_invite_by_id, pattern="house_invite_by_id"))
    app.add_handler(CallbackQueryHandler(house_invite_send, pattern="house_invite_send_"))
    app.add_handler(CallbackQueryHandler(house_invite_accept, pattern="house_invite_accept_"))
    app.add_handler(CallbackQueryHandler(house_invite_decline, pattern="house_invite_decline_"))
    app.add_handler(CallbackQueryHandler(house_chat_open, pattern="house_chat_open"))
    app.add_handler(CallbackQueryHandler(house_wardrobe, pattern="house_wardrobe"))
    app.add_handler(CallbackQueryHandler(house_exit, pattern="house_exit"))
    app.add_handler(CallbackQueryHandler(trade_request, pattern="trade_request_"))
    app.add_handler(CallbackQueryHandler(trade_accept, pattern="trade_accept_"))
    app.add_handler(CallbackQueryHandler(trade_decline, pattern="trade_decline_"))
    app.add_handler(CallbackQueryHandler(trade_open, pattern="trade_open_"))
    app.add_handler(CallbackQueryHandler(trade_additem, pattern="trade_additem_"))
    app.add_handler(CallbackQueryHandler(trade_pickitem, pattern="trade_pickitem_"))
    app.add_handler(CallbackQueryHandler(trade_addmoney, pattern="trade_addmoney_"))
    app.add_handler(CallbackQueryHandler(trade_ready, pattern="trade_ready_"))
    app.add_handler(CallbackQueryHandler(trade_confirm, pattern="trade_confirm_"))
    app.add_handler(CallbackQueryHandler(trade_cancel, pattern="trade_cancel_"))
    app.add_handler(CallbackQueryHandler(inventory_menu, pattern="inventory_menu"))
    app.add_handler(CallbackQueryHandler(bank_menu, pattern="bank_menu"))
    app.add_handler(CallbackQueryHandler(bank_deposit, pattern="bank_deposit"))
    app.add_handler(CallbackQueryHandler(bank_withdraw, pattern="bank_withdraw"))
    app.add_handler(CallbackQueryHandler(bank_transfer, pattern="bank_transfer"))
    app.add_handler(CallbackQueryHandler(bank_crypto_exchange, pattern="bank_crypto_exchange"))
    app.add_handler(CallbackQueryHandler(bank_crypto, pattern="bank_crypto"))
    app.add_handler(CallbackQueryHandler(bank_property, pattern="bank_property"))
    app.add_handler(CallbackQueryHandler(bank_fines, pattern="bank_fines"))
    app.add_handler(CallbackQueryHandler(bank_history, pattern="bank_history"))
    app.add_handler(CallbackQueryHandler(agency_menu, pattern="agency_menu"))
    app.add_handler(CallbackQueryHandler(agency_businesses, pattern="agency_businesses"))
    app.add_handler(CallbackQueryHandler(factory_open_city, pattern="factory_open_city"))
    app.add_handler(CallbackQueryHandler(factory_buy, pattern="factory_buy_"))
    app.add_handler(CallbackQueryHandler(factory_open, pattern="factory_open_"))
    app.add_handler(CallbackQueryHandler(factory_storage, pattern="factory_storage_"))
    app.add_handler(CallbackQueryHandler(factory_buyraw_menu, pattern="factory_buyraw_menu_"))
    app.add_handler(CallbackQueryHandler(factory_order_raw, pattern="factory_order_"))
    app.add_handler(CallbackQueryHandler(factory_startprod, pattern="factory_startprod_"))
    app.add_handler(CallbackQueryHandler(factory_collect, pattern="factory_collect_"))
    app.add_handler(CallbackQueryHandler(factory_manage, pattern="factory_manage_"))
    app.add_handler(CallbackQueryHandler(factory_postad, pattern="factory_postad_"))
    app.add_handler(CallbackQueryHandler(factory_hirenpc, pattern="factory_hirenpc_"))
    app.add_handler(CallbackQueryHandler(factory_postad_flow, pattern="factory_postad_flow_"))
    app.add_handler(CallbackQueryHandler(factory_bumpad, pattern="factory_bumpad_"))
    app.add_handler(CallbackQueryHandler(factory_jobs_menu, pattern="factory_jobs_menu"))
    app.add_handler(CallbackQueryHandler(factory_jobs_prev, pattern="factory_jobs_prev"))
    app.add_handler(CallbackQueryHandler(factory_jobs_next, pattern="factory_jobs_next"))
    app.add_handler(CallbackQueryHandler(factory_jobview, pattern="factory_jobview_"))
    app.add_handler(CallbackQueryHandler(factory_apply, pattern="factory_apply_"))
    app.add_handler(CallbackQueryHandler(factory_apps_prev, pattern="factory_apps_prev_"))
    app.add_handler(CallbackQueryHandler(factory_apps_next, pattern="factory_apps_next_"))
    app.add_handler(CallbackQueryHandler(factory_apps, pattern="factory_apps_"))
    app.add_handler(CallbackQueryHandler(factory_appopen, pattern="factory_appopen_"))
    app.add_handler(CallbackQueryHandler(factory_app_accept, pattern="factory_app_accept_"))
    app.add_handler(CallbackQueryHandler(factory_app_decline, pattern="factory_app_decline_"))
    app.add_handler(CallbackQueryHandler(factory_workers, pattern="factory_workers_"))
    app.add_handler(CallbackQueryHandler(factory_history, pattern="factory_history_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_open_city, pattern="gpu_shop_open_city"))
    app.add_handler(CallbackQueryHandler(gpu_shop_buy, pattern="gpu_shop_buy_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_open, pattern="gpu_shop_open_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_storage, pattern="gpu_shop_storage_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_supplier, pattern="gpu_shop_supplier_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_selectsupplier, pattern="gpu_shop_selectsupplier_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_shipments, pattern="gpu_shop_shipments_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_buyship, pattern="gpu_shop_buyship_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_buyall, pattern="gpu_shop_buyall_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_catalog, pattern="gpu_shop_catalog_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_catprev, pattern="gpu_shop_catprev_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_catnext, pattern="gpu_shop_catnext_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_item, pattern="gpu_shop_item_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_buyitem, pattern="gpu_shop_buyitem_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_markup, pattern="gpu_shop_markup_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_collect, pattern="gpu_shop_collect_"))
    app.add_handler(CallbackQueryHandler(gpu_shop_stats, pattern="gpu_shop_stats_"))
    app.add_handler(CallbackQueryHandler(noop, pattern="noop"))

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

    async def _post_init(app_):
        app_.create_task(process_factory_orders_loop(app_))
    app.post_init = _post_init
    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
