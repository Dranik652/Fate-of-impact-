import random
import sqlite3
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# ========== КОНФИГУРАЦИЯ ИГРЫ ==========
DUNGEON_ENERGY_MAX = 120
DUNGEON_ENERGY_COST = 20
GACHA_COST = 100
GACHA_10_COST = 900
GACHA_4STAR_GUARANTEE = 10
GACHA_5STAR_GUARANTEE = 50

# Персонажи
CHARACTERS = {
    "Сосата Комисата": {
        "rarity": 5,
        "element": "⚡ Электро",
        "abilities": ["Временной разрез", "Песочный щит", "Казнь Кроноса"],
        "stats": {"base_attack": 30, "base_hp": 150},
        "emoji": "👑",
        "ascension": ["Слеза времени", "Песок вечности", "Механическое ядро"]
    },
    "Лайт Коши": {
        "rarity": 5,
        "element": "🌪️ Анемо",
        "abilities": ["Мираж клинков", "Обман судьбы", "Фальшивый удар"],
        "stats": {"base_attack": 28, "base_hp": 130},
        "emoji": "🎭",
        "ascension": ["Обманчивый узор", "Фрагмент иллюзии", "Крыло бабочки"]
    },
    "Каса Эбардов": {
        "rarity": 4,
        "element": "💧 Гидро",
        "abilities": ["Запоздалый удар", "Жалоба богам", "Случайный блок"],
        "stats": {"base_attack": 20, "base_hp": 180},
        "emoji": "🛡️",
        "ascension": ["Капля росы", "Раковина моллюска", "Коралл"]
    }
}

# Монстры
MONSTERS = [
    {"name": "Песочный червь", "hp": 50, "attack": 5, "emoji": "🪱"},
    {"name": "Хроно-призрак", "hp": 120, "attack": 8, "emoji": "👻"},
    {"name": "Разрушитель времен", "hp": 300, "attack": 15, "emoji": "🤖"},
    {"name": "Тень Кроноса", "hp": 1000, "attack": 25, "emoji": "👤"}
]

# Артефакты (Диковины)
ARTIFACT_SETS = {
    "Песочные Часы": {
        "emoji": "⏳",
        "2pc": "HP +15%",
        "4pc": "Урон +25% если HP > 70%",
        "main_stats": {
            "chain": ["HP%", "ATK%"],
            "crown": ["CRIT Rate%", "CRIT DMG%"],
            "boots": ["Elemental DMG%"]
        },
        "sub_stats": ["HP", "ATK", "CRIT Rate%", "CRIT DMG%"]
    },
    "Обманный Мираж": {
        "emoji": "🌪️",
        "2pc": "CRIT Rate +12%",
        "4pc": "CRIT DMG +30% после способности (10сек)",
        "main_stats": {
            "chain": ["ATK%", "HP%"],
            "crown": ["CRIT DMG%", "CRIT Rate%"],
            "boots": ["Elemental DMG%"]
        },
        "sub_stats": ["ATK%", "HP", "CRIT Rate%", "CRIT DMG%"]
    },
    "Клыки Вечности": {
        "emoji": "🔱",
        "2pc": "Elemental DMG +15%",
        "4pc": "ATK +25% против 2+ врагов",
        "main_stats": {
            "chain": ["ATK%", "HP%"],
            "crown": ["CRIT Rate%", "CRIT DMG%"],
            "boots": ["Elemental DMG%"]
        },
        "sub_stats": ["ATK", "HP%", "CRIT Rate%", "CRIT DMG%"]
    }
}

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('battle_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY,
                   username TEXT,
                   currency INTEGER DEFAULT 0,
                   energy INTEGER DEFAULT 120,
                   energy_time INTEGER DEFAULT 0,
                   characters TEXT DEFAULT '{}',
                   artifacts TEXT DEFAULT '[]',
                   equipped TEXT DEFAULT '{}',
                   stats TEXT DEFAULT '{"attack": 10, "hp": 100, "crit_rate": 5, "crit_dmg": 50}',
                   dungeon_progress TEXT DEFAULT '{"sands": 1, "mirage": 0, "fangs": 0}',
                   pity_4star INTEGER DEFAULT 0,
                   pity_5star INTEGER DEFAULT 0,
                   is_guaranteed BOOLEAN DEFAULT FALSE)''')
    
    conn.commit()
    conn.close()

init_db()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_user_data(user_id):
    conn = sqlite3.connect('battle_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        default_data = (
            user_id, "", 0, 120, int(time.time()), 
            '{}', '[]', '{}', 
            '{"attack": 10, "hp": 100, "crit_rate": 5, "crit_dmg": 50}',
            '{"sands": 1, "mirage": 0, "fangs": 0}',
            0, 0, False
        )
        conn = sqlite3.connect('battle_bot.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', default_data)
        conn.commit()
        conn.close()
        return default_data
    return user

def update_user_data(user_id, **kwargs):
    conn = sqlite3.connect('battle_bot.db')
    cursor = conn.cursor()
    
    # Получаем текущие данные
    current_data = dict(zip(
        ['user_id', 'username', 'currency', 'energy', 'energy_time', 
         'characters', 'artifacts', 'equipped', 'stats', 
         'dungeon_progress', 'pity_4star', 'pity_5star', 'is_guaranteed'],
        get_user_data(user_id)
    ))
    
    # Обновляем данные
    for key, value in kwargs.items():
        if key in current_data:
            current_data[key] = value
    
    # Сохраняем
    cursor.execute('''UPDATE users SET
                   username = ?,
                   currency = ?,
                   energy = ?,
                   energy_time = ?,
                   characters = ?,
                   artifacts = ?,
                   equipped = ?,
                   stats = ?,
                   dungeon_progress = ?,
                   pity_4star = ?,
                   pity_5star = ?,
                   is_guaranteed = ?
                   WHERE user_id = ?''',
                   (current_data['username'], current_data['currency'], 
                    current_data['energy'], current_data['energy_time'],
                    current_data['characters'], current_data['artifacts'],
                    current_data['equipped'], current_data['stats'],
                    current_data['dungeon_progress'], current_data['pity_4star'],
                    current_data['pity_5star'], current_data['is_guaranteed'],
                    user_id))
    
    conn.commit()
    conn.close()

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    update_user_data(user.id, username=user.username)
    
    text = (
        "⚔️ *Добро пожаловать в Fates of Kronos!*\n\n"
        "Вы - Безликий, воин с пробудившимся Хроно-Клинком.\n"
        "Сражайтесь с монстрами, находите союзников и собирайте мощные Диковины!\n\n"
        "Используйте кнопки ниже для навигации:"
    )
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Начать бой", callback_data="battle")],
        [InlineKeyboardButton("🏰 Подземелья Диковин", callback_data="dungeon_menu")],
        [InlineKeyboardButton("🔎 Поиск помощи", callback_data="gacha_menu")],
        [InlineKeyboardButton("📦 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("👥 Галерея персонажей", callback_data="characters")]
    ]
    
    update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== СИСТЕМА БОЯ ==========
def start_battle(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    # Выбираем монстра
    dungeon_progress = eval(user_data[8])
    monster_level = dungeon_progress['sands'] + dungeon_progress['mirage'] + dungeon_progress['fangs']
    monster = random.choice(MONSTERS)
    monster_hp = monster['hp'] * (1 + monster_level * 0.2)
    
    # Сохраняем текущего монстра в контексте
    context.user_data['current_monster'] = {
        'name': monster['name'],
        'hp': monster_hp,
        'max_hp': monster_hp,
        'attack': monster['attack'],
        'emoji': monster['emoji']
    }
    
    text = (
        f"Вы встретили *{monster['name']}* {monster['emoji']}!\n"
        f"HP: {int(monster_hp)}/{int(monster_hp)}\n\n"
        "Выберите действие:"
    )
    
    keyboard = [
        [InlineKeyboardButton("⚔️ Атаковать", callback_data="attack")],
        [InlineKeyboardButton("🛡️ Использовать способность", callback_data="skill")],
        [InlineKeyboardButton("🏃‍♂️ Бежать", callback_data="run")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def attack_monster(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    stats = eval(user_data[7])
    monster = context.user_data['current_monster']
    
    # Расчет урона
    crit_roll = random.randint(1, 100)
    is_crit = crit_roll <= stats['crit_rate']
    damage = stats['attack'] * (2 if is_crit else 1) * (1 + stats.get('crit_dmg', 0)/100 if is_crit else 1)
    
    # Наносим урон
    monster['hp'] -= damage
    context.user_data['current_monster'] = monster
    
    # Проверяем победу
    if monster['hp'] <= 0:
        reward = random.randint(20, 50)
        update_user_data(
            user_id,
            currency=user_data[2] + reward
        )
        
        text = (
            f"⚔️ Вы нанесли *{int(damage)}* урона ({'КРИТ!' if is_crit else ''})\n"
            f"*{monster['name']}* повержен!\n\n"
            f"Получено: *{reward}* валюты\n\n"
            "Выберите следующее действие:"
        )
        
        keyboard = [
            [InlineKeyboardButton("⚔️ Новый бой", callback_data="battle")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
        ]
    else:
        # Ответный удар монстра
        player_hp = stats['hp'] - monster['attack']
        stats['hp'] = max(0, player_hp)
        update_user_data(user_id, stats=str(stats))
        
        if stats['hp'] <= 0:
            text = (
                f"⚔️ Вы нанесли *{int(damage)}* урона\n"
                f"💀 *{monster['name']}* убил вас!\n\n"
                "Вы проиграли все неполученные награды."
            )
            
            keyboard = [
                [InlineKeyboardButton("⚔️ Новый бой", callback_data="battle")],
                [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
            ]
        else:
            text = (
                f"⚔️ Вы нанесли *{int(damage)}* урона ({'КРИТ!' if is_crit else ''})\n"
                f"❤️ Ваше HP: *{int(stats['hp'])}*/{int(stats.get('max_hp', 100))}\n"
                f"🐾 {monster['name']} HP: *{int(monster['hp'])}*/{int(monster['max_hp'])}\n\n"
                "Выберите действие:"
            )
            
            keyboard = [
                [InlineKeyboardButton("⚔️ Атаковать", callback_data="attack")],
                [InlineKeyboardButton("🛡️ Использовать способность", callback_data="skill")],
                [InlineKeyboardButton("🏃‍♂️ Бежать", callback_data="run")]
            ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== ПОДЗЕМЕЛЬЯ И ДИКОВИНЫ ==========
def dungeon_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    dungeon_progress = eval(user_data[8])
    
    text = (
        "🏰 *Подземелья Диковин*\n\n"
        "Исследуйте подземелья для получения мощных артефактов.\n"
        f"🔋 Энергия: *{user_data[3]}/{DUNGEON_ENERGY_MAX}*\n\n"
        "Доступные подземелья:"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"⏳ Песочные Часы (Ур. {dungeon_progress['sands']})", callback_data="dungeon_sands")],
        [InlineKeyboardButton(f"🌪️ Обманный Мираж (Ур. {dungeon_progress['mirage']})", callback_data="dungeon_mirage")],
        [InlineKeyboardButton(f"🔱 Клыки Вечности (Ур. {dungeon_progress['fangs']})", callback_data="dungeon_fangs")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def run_dungeon(update: Update, context: CallbackContext, dungeon_type):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    if user_data[3] < DUNGEON_ENERGY_COST:
        query.answer("Недостаточно энергии!", show_alert=True)
        return
    
    # Получаем артефакт
    artifact_set = ARTIFACT_SETS[dungeon_type]
    piece_type = random.choice(["chain", "crown", "boots"])
    main_stat = random.choice(artifact_set["main_stats"][piece_type])
    
    # Создаем артефакт
    new_artifact = {
        "set": dungeon_type,
        "type": piece_type,
        "main_stat": main_stat,
        "sub_stats": random.sample(artifact_set["sub_stats"], 2),
        "level": 0
    }
    
    # Добавляем в инвентарь
    artifacts = eval(user_data[6])
    artifacts.append(new_artifact)
    
    # Обновляем прогресс
    dungeon_progress = eval(user_data[8])
    if dungeon_type == "Песочные Часы":
        dungeon_progress['sands'] += 1
    elif dungeon_type == "Обманный Мираж":
        dungeon_progress['mirage'] += 1
    else:
        dungeon_progress['fangs'] += 1
    
    update_user_data(
        user_id,
        energy=user_data[3] - DUNGEON_ENERGY_COST,
        artifacts=str(artifacts),
        dungeon_progress=str(dungeon_progress)
    )
    
    # Формируем сообщение
    text = (
        f"🏆 *Вы получили:*\n"
        f"{artifact_set['emoji']} *{dungeon_type}*\n"
        f"Тип: *{piece_type}*\n"
        f"Основной стат: *{main_stat}*\n"
        f"Доп. статы: *{', '.join(new_artifact['sub_stats'])}*\n\n"
        f"🔋 Энергия: *{user_data[3] - DUNGEON_ENERGY_COST}/{DUNGEON_ENERGY_MAX}*"
    )
    
    keyboard = [
        [InlineKeyboardButton("🏰 Ещё заход", callback_data=f"dungeon_{dungeon_type}")],
        [InlineKeyboardButton("📦 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== ГАЧА СИСТЕМА ==========
def gacha_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    text = (
        "🔎 *Поиск помощи*\n\n"
        "Призывайте новых союзников, тратя валюту.\n"
        f"💰 Валюта: *{user_data[2]}*\n\n"
        f"Гарант 4★ через: *{GACHA_4STAR_GUARANTEE - user_data[10]} круток*\n"
        f"Гарант 5★ через: *{GACHA_5STAR_GUARANTEE - user_data[11]} круток*"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔎 Крутить 1 раз (100)", callback_data="gacha_1")],
        [InlineKeyboardButton("🎉 Крутить 10 раз (900)", callback_data="gacha_10")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def gacha_pull(update: Update, context: CallbackContext, pulls=1):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    if user_data[2] < (GACHA_COST * pulls if pulls == 1 else GACHA_10_COST):
        query.answer("Недостаточно валюты!", show_alert=True)
        return
    
    results = []
    pity_4star = user_data[10]
    pity_5star = user_data[11]
    is_guaranteed = user_data[12]
    
    for _ in range(pulls):
        pity_4star += 1
        pity_5star += 1
        
        # Гарантированный 4★
        if pity_4star >= GACHA_4STAR_GUARANTEE:
            char_name = "Каса Эбардов"
            rarity = 4
            pity_4star = 0
        # Гарантированный 5★
        elif pity_5star >= GACHA_5STAR_GUARANTEE:
            char_name = "Сосата Комисата" if not is_guaranteed or random.random() < 0.5 else "Лайт Коши"
            rarity = 5
            pity_5star = 0
            is_guaranteed = not is_guaranteed if char_name == "Лайт Коши" else is_guaranteed
        else:
            roll = random.random() * 100
            if roll < 0.6:  # 5★
                char_name = "Сосата Комисата" if not is_guaranteed or random.random() < 0.5 else "Лайт Коши"
                rarity = 5
                pity_5star = 0
                is_guaranteed = not is_guaranteed if char_name == "Лайт Коши" else is_guaranteed
            elif roll < 5.7:  # 4★
                char_name = "Каса Эбардов"
                rarity = 4
                pity_4star = 0
            else:  # 3★ (предмет)
                char_name = "Сломанный клинок"
                rarity = 3
        
        # Добавляем результат
        results.append({
            "name": char_name,
            "rarity": rarity,
            "emoji": CHARACTERS.get(char_name, {}).get("emoji", "🗡️")
        })
        
        # Обновляем инвентарь
        characters = eval(user_data[5])
        if char_name in CHARACTERS:
            characters[char_name] = characters.get(char_name, 0) + 1
            update_user_data(user_id, characters=str(characters))
    
    # Обновляем данные пользователя
    update_user_data(
        user_id,
        currency=user_data[2] - (GACHA_COST * pulls if pulls == 1 else GACHA_10_COST),
        pity_4star=pity_4star,
        pity_5star=pity_5star,
        is_guaranteed=is_guaranteed
    )
    
    # Формируем результат
    text = "🎉 *Результаты круток:*\n"
    for result in results:
        stars = "⭐" * result["rarity"]
        text += f"{result['emoji']} {result['name']} {stars}\n"
    
    text += f"\n💰 Осталось валюты: *{user_data[2] - (GACHA_COST * pulls if pulls == 1 else GACHA_10_COST)}*"
    
    keyboard = [
        [InlineKeyboardButton("🔎 Крутить ещё", callback_data="gacha_1")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== ИНВЕНТАРЬ И ГАЛЕРЕЯ ==========
def inventory_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    
    text = (
        "📦 *Инвентарь*\n\n"
        f"💰 Валюта: *{user_data[2]}*\n"
        f"🔋 Энергия: *{user_data[3]}/{DUNGEON_ENERGY_MAX}*\n\n"
        "Выберите раздел:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎒 Диковины", callback_data="artifacts_list")],
        [InlineKeyboardButton("👥 Персонажи", callback_data="characters")],
        [InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def characters_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    characters = eval(user_data[5])
    
    text = "👥 *Галерея персонажей*\n\n"
    keyboard = []
    
    for char_name, char_data in CHARACTERS.items():
        count = characters.get(char_name, 0)
        if count > 0:
            text += f"{char_data['emoji']} *{char_name}* (Ур. {count})\n"
            keyboard.append([InlineKeyboardButton(
                f"{char_data['emoji']} {char_name}",
                callback_data=f"character_{char_name}"
            )])
    
    keyboard.append([InlineKeyboardButton("🏠 В главное меню", callback_data="main_menu")])
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def show_character(update: Update, context: CallbackContext, character_name):
    query = update.callback_query
    update.callback_query
    user_id = query.from_user.id
    user_data = get_user_data(user_id)
    char_data = CHARACTERS[character_name]
    characters = eval(user_data[5])
    count = characters.get(character_name, 0)
    
    text = (
        f"{char_data['emoji']} *{character_name}*\n"
        f"★ {'⭐' * char_data['rarity']}\n"
        f"Элемент: {char_data['element']}\n"
        f"Уровень наложения: *{count}*\n\n"
        "*Способности:*\n"
        f"- {char_data['abilities'][0]}\n"
        f"- {char_data['abilities'][1]}\n"
        f"- {char_data['abilities'][2]}\n\n"
        "*Базовые статы:*\n"
        f"- ATK: {char_data['stats']['base_attack'] * count}\n"
        f"- HP: {char_data['stats']['base_hp'] * count}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎒 Экипировать", callback_data=f"equip_{character_name}")],
        [InlineKeyboardButton("👥 Назад к персонажам", callback_data="characters")]
    ]
    
    query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ========== ОБРАБОТЧИКИ КОМАНД ==========
def main_menu(update: Update, context: CallbackContext):
    query = update.callback_query
    query.edit_message_text(
        "⚔️ *Главное меню*\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚔️ Начать бой", callback_data="battle")],
            [InlineKeyboardButton("🏰 Подземелья Диковин", callback_data="dungeon_menu")],
            [InlineKeyboardButton("🔎 Поиск помощи", callback_data="gacha_menu")],
            [InlineKeyboardButton("📦 Инвентарь", callback_data="inventory")],
            [InlineKeyboardButton("👥 Галерея персонажей", callback_data="characters")]
        ]),
        parse_mode="Markdown"
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data
    
    if data == "main_menu":
        main_menu(update, context)
    elif data == "battle":
        start_battle(update, context)
    elif data == "attack":
        attack_monster(update, context)
    elif data == "dungeon_menu":
        dungeon_menu(update, context)
    elif data.startswith("dungeon_"):
        dungeon_type = data.split("_")[1]
        if dungeon_type == "sands":
            run_dungeon(update, context, "Песочные Часы")
        elif dungeon_type == "mirage":
            run_dungeon(update, context, "Обманный Мираж")
        else:
            run_dungeon(update, context, "Клыки Вечности")
    elif data == "gacha_menu":
        gacha_menu(update, context)
    elif data == "gacha_1":
        gacha_pull(update, context, 1)
    elif data == "gacha_10":
        gacha_pull(update, context, 10)
    elif data == "inventory":
        inventory_menu(update, context)
    elif data == "characters":
        characters_menu(update, context)
    elif data.startswith("character_"):
        char_name = data.split("_")[1]
        show_character(update, context, char_name)

# ========== ЗАПУСК БОТА ==========
def main():
    updater = Updater("8068561650:AAFVlqaX1BiJRfSIqTNQ3DxzR6EAEYSOC0w", use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button_handler))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
