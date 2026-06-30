import telebot
import random
import sqlite3
import time
import os
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN не найден! Добавьте его в переменные окружения Render.")

bot = telebot.TeleBot(TOKEN, timeout=60)
app = Flask(__name__)

ADMIN_ID = 6522832492
DB_FILE = "users.db"

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            balance INTEGER DEFAULT 0,
            username TEXT,
            last_open TEXT,
            total_cards INTEGER DEFAULT 0,
            total_sold INTEGER DEFAULT 0,
            total_upgrades INTEGER DEFAULT 0,
            total_failed INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            user_id INTEGER,
            card_name TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, card_name)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова")

def get_user(uid):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT balance, username, last_open, total_cards, total_sold, total_upgrades, total_failed FROM users WHERE user_id = ?', (uid,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            "balance": result[0],
            "username": result[1] or "",
            "last_open": result[2],
            "stats": {
                "total_cards": result[3] or 0,
                "total_sold": result[4] or 0,
                "total_upgrades": result[5] or 0,
                "total_failed": result[6] or 0
            }
        }
    return None

def create_user(uid, username=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (user_id, balance, username) VALUES (?, 0, ?)', (uid, username))
    conn.commit()
    conn.close()

def update_user(uid, data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET 
            balance = ?,
            username = ?,
            last_open = ?,
            total_cards = ?,
            total_sold = ?,
            total_upgrades = ?,
            total_failed = ?
        WHERE user_id = ?
    ''', (
        data.get("balance", 0),
        data.get("username", ""),
        data.get("last_open"),
        data.get("stats", {}).get("total_cards", 0),
        data.get("stats", {}).get("total_sold", 0),
        data.get("stats", {}).get("total_upgrades", 0),
        data.get("stats", {}).get("total_failed", 0),
        uid
    ))
    conn.commit()
    conn.close()

def get_inventory(uid):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT card_name, count FROM inventory WHERE user_id = ? AND count > 0', (uid,))
    result = cursor.fetchall()
    conn.close()
    return {card: count for card, count in result}

def update_inventory(uid, card_name, change):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inventory (user_id, card_name, count)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, card_name) DO UPDATE SET count = count + ?
    ''', (uid, card_name, change, change))
    cursor.execute('DELETE FROM inventory WHERE user_id = ? AND card_name = ? AND count <= 0', (uid, card_name))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, balance, username FROM users')
    result = cursor.fetchall()
    conn.close()
    return result

def get_user_by_username(username):
    username = username.lower().replace('@', '')
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, balance, username FROM users WHERE LOWER(username) = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    return result

# ========== ПОДАРКИ ==========
CARDS = [
    {"name": "Мишка", "rarity": "Обычный", "price": 5, "emoji": "🧸", "weight": 100, "upgrade_chance": 0.80},
    {"name": "Сердце", "rarity": "Обычный", "price": 4, "emoji": "💝", "weight": 95, "upgrade_chance": 0.80},
    {"name": "Роза", "rarity": "Обычный", "price": 5, "emoji": "🌹", "weight": 90, "upgrade_chance": 0.78},
    {"name": "Торт", "rarity": "Обычный", "price": 6, "emoji": "🎂", "weight": 85, "upgrade_chance": 0.78},
    {"name": "Кубок", "rarity": "Обычный", "price": 5, "emoji": "🏆", "weight": 80, "upgrade_chance": 0.75},
    {"name": "Ракета", "rarity": "Обычный", "price": 6, "emoji": "🚀", "weight": 75, "upgrade_chance": 0.75},
    {"name": "Кольцо", "rarity": "Обычный", "price": 7, "emoji": "💍", "weight": 70, "upgrade_chance": 0.72},
    {"name": "Алмаз", "rarity": "Обычный", "price": 8, "emoji": "💎", "weight": 65, "upgrade_chance": 0.70},
    {"name": "Шампанское", "rarity": "Обычный", "price": 6, "emoji": "🍾", "weight": 60, "upgrade_chance": 0.70},
    {"name": "Букет", "rarity": "Обычный", "price": 5, "emoji": "💐", "weight": 55, "upgrade_chance": 0.68},
    {"name": "Подарок", "rarity": "Обычный", "price": 5, "emoji": "🎁", "weight": 50, "upgrade_chance": 0.68},
    {"name": "Леденец", "rarity": "Редкий", "price": 25, "emoji": "🍭", "weight": 35, "upgrade_chance": 0.50},
    {"name": "Сакура", "rarity": "Редкий", "price": 30, "emoji": "🌸", "weight": 30, "upgrade_chance": 0.48},
    {"name": "Пряник", "rarity": "Редкий", "price": 28, "emoji": "🍪", "weight": 28, "upgrade_chance": 0.45},
    {"name": "Глинтвейн", "rarity": "Редкий", "price": 35, "emoji": "🍷", "weight": 25, "upgrade_chance": 0.43},
    {"name": "Шапка Санты", "rarity": "Редкий", "price": 30, "emoji": "🎅", "weight": 22, "upgrade_chance": 0.40},
    {"name": "Кролик", "rarity": "Редкий", "price": 40, "emoji": "🐰", "weight": 20, "upgrade_chance": 0.38},
    {"name": "Замок из песка", "rarity": "Редкий", "price": 45, "emoji": "🏰", "weight": 18, "upgrade_chance": 0.35},
    {"name": "Доска для серфинга", "rarity": "Редкий", "price": 40, "emoji": "🏄", "weight": 16, "upgrade_chance": 0.33},
    {"name": "Розовый фламинго", "rarity": "Редкий", "price": 50, "emoji": "🦩", "weight": 15, "upgrade_chance": 0.30},
    {"name": "Домашний торт", "rarity": "Коллекционный", "price": 80, "emoji": "🧁", "weight": 12, "upgrade_chance": 0.25},
    {"name": "Желейный кролик", "rarity": "Коллекционный", "price": 90, "emoji": "🐇", "weight": 10, "upgrade_chance": 0.22},
    {"name": "Снежные варежки", "rarity": "Коллекционный", "price": 75, "emoji": "🧤", "weight": 9, "upgrade_chance": 0.20},
    {"name": "Волшебный кот", "rarity": "Коллекционный", "price": 100, "emoji": "🐱", "weight": 8, "upgrade_chance": 0.18},
    {"name": "Бабочка", "rarity": "Коллекционный", "price": 85, "emoji": "🦋", "weight": 7, "upgrade_chance": 0.17},
    {"name": "Магический шар", "rarity": "Коллекционный", "price": 110, "emoji": "🔮", "weight": 6, "upgrade_chance": 0.15},
    {"name": "Снежный ком", "rarity": "Коллекционный", "price": 70, "emoji": "❄️", "weight": 5, "upgrade_chance": 0.14},
    {"name": "Шляпа ведьмы", "rarity": "Коллекционный", "price": 120, "emoji": "🧙", "weight": 4, "upgrade_chance": 0.12},
    {"name": "Коллекционная карта", "rarity": "Коллекционный", "price": 130, "emoji": "🃏", "weight": 3, "upgrade_chance": 0.10},
    {"name": "Очки Дурова", "rarity": "Эксклюзивный", "price": 500, "emoji": "🕶️", "weight": 2.5, "upgrade_chance": 0.08},
    {"name": "Собака Сопротивления", "rarity": "Эксклюзивный", "price": 600, "emoji": "🐕", "weight": 2.0, "upgrade_chance": 0.07},
    {"name": "Redo", "rarity": "Эксклюзивный", "price": 700, "emoji": "🐶", "weight": 1.5, "upgrade_chance": 0.06},
    {"name": "Snoop Dogg", "rarity": "Эксклюзивный", "price": 800, "emoji": "🎤", "weight": 1.2, "upgrade_chance": 0.05},
    {"name": "Золотой проигрыватель", "rarity": "Эксклюзивный", "price": 900, "emoji": "📀", "weight": 1.0, "upgrade_chance": 0.04},
    {"name": "Винтажная сигара", "rarity": "Эксклюзивный", "price": 750, "emoji": "🚬", "weight": 0.8, "upgrade_chance": 0.035},
    {"name": "Швейцарские часы", "rarity": "Эксклюзивный", "price": 1000, "emoji": "⌚", "weight": 0.6, "upgrade_chance": 0.03},
    {"name": "Плюшевая лягушка", "rarity": "Эксклюзивный", "price": 850, "emoji": "🐸", "weight": 0.4, "upgrade_chance": 0.02},
    {"name": "Драгоценный персик", "rarity": "Эксклюзивный", "price": 1200, "emoji": "🍑", "weight": 0.2, "upgrade_chance": 0.015},
]

# ========== ЛОГИ ==========
def log_action(uid, action, details="", extra=""):
    try:
        user = bot.get_chat(uid)
        username = user.username or user.first_name or str(uid)
    except:
        username = str(uid)
    
    time_now = datetime.now().strftime("%H:%M:%S")
    log_text = f"[{time_now}] 👤 @{username} (ID: {uid}) → {action}"
    if details:
        log_text += f" | {details}"
    if extra:
        log_text += f" | {extra}"
    print(log_text)

# ========== ФУНКЦИИ ==========
def get_random_card():
    total = sum(c["weight"] for c in CARDS)
    r = random.uniform(0, total)
    cur = 0
    for c in CARDS:
        cur += c["weight"]
        if r <= cur:
            return c
    return CARDS[-1]

def get_user_info(uid):
    user = get_user(uid)
    if not user:
        create_user(uid)
        user = get_user(uid)
    return user

def get_balance_display(uid):
    user = get_user_info(uid)
    return f"💰 Баланс: {user['balance']} TGGifts"

def get_main_menu(uid, text=""):
    balance_text = get_balance_display(uid)
    user = get_user_info(uid)
    stats = user.get("stats", {})
    
    if text:
        full_text = f"{text}\n\n{balance_text}"
    else:
        full_text = f"🎰 **Gifts Cards Bot**\n\n{balance_text}\n\n📊 **Статистика:**\n"
        full_text += f"📦 Выбито: {stats.get('total_cards', 0)}\n"
        full_text += f"💲 Продано: {stats.get('total_sold', 0)}\n"
        full_text += f"⬆️ Улучшений: {stats.get('total_upgrades', 0)}\n"
        full_text += f"💥 Неудач: {stats.get('total_failed', 0)}\n\n"
        full_text += "📌 **Команды:**\n"
        full_text += "/TGCard — получить подарок (1 раз/мин)\n"
        full_text += "/inventory — посмотреть инвентарь\n"
        full_text += "/balance — проверить баланс\n"
        full_text += "/start — показать это меню"
    
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"),
        InlineKeyboardButton("🏆 Топ игроков", callback_data="show_leaderboard")
    )
    markup.row(InlineKeyboardButton("📖 Как играть?", callback_data="how_to_play"))
    return full_text, markup

def card_buttons(card_name):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("💲 Продать", callback_data=f"confirm_sell_{card_name}"),
        InlineKeyboardButton("⬆️ Улучшить", callback_data=f"confirm_upgrade_{card_name}")
    )
    markup.row(
        InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"),
        InlineKeyboardButton("🏠 Меню", callback_data="main_menu")
    )
    return markup

def confirm_buttons(action, card_name):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Да, точно", callback_data=f"do_{action}_{card_name}"),
        InlineKeyboardButton("❌ Отмена", callback_data="main_menu")
    )
    return markup

def inventory_buttons(uid):
    inv = get_inventory(uid)
    if not inv:
        return None
    
    markup = InlineKeyboardMarkup()
    for card_name, count in inv.items():
        if count > 0:
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if card:
                btn_text = f"{card['emoji']} {card_name} ×{count}"
                markup.row(InlineKeyboardButton(btn_text, callback_data=f"card_{card_name}"))
    
    markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
    return markup

# ========== АДМИНКА ==========
def admin_panel(chat_id, text=""):
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("➕ Выдать деньги", callback_data="admin_add"),
        InlineKeyboardButton("➖ Забрать деньги", callback_data="admin_remove")
    )
    markup.row(
        InlineKeyboardButton("💰 Баланс игрока", callback_data="admin_balance"),
        InlineKeyboardButton("📋 Список игроков", callback_data="admin_list")
    )
    markup.row(InlineKeyboardButton("🔙 Назад", callback_data="main_menu"))
    
    if not text:
        text = "🔐 **Админ-панель**\n\nВыбери действие:"
    
    try:
        bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)
    except:
        bot.send_message(chat_id, text, parse_mode='Markdown')

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(m):
    uid = m.from_user.id
    create_user(uid, m.from_user.username or "")
    log_action(uid, "ИСПОЛЬЗОВАЛ /start", "")
    text, markup = get_main_menu(uid)
    bot.send_message(m.chat.id, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['TGCard', 'tgcard', 'getcard'])
def tg_card(m):
    uid = m.from_user.id
    create_user(uid, m.from_user.username or "")
    user = get_user(uid)
    
    log_action(uid, "ИСПОЛЬЗОВАЛ /TGCard", "")
    
    now = datetime.now().isoformat()
    if user and user.get("last_open"):
        last = datetime.fromisoformat(user["last_open"])
        diff = datetime.now() - last
        if diff.total_seconds() < 60:
            sec = int(60 - diff.total_seconds())
            log_action(uid, "ПОПЫТКА ДО ТАЙМЕРА", f"осталось {sec} сек")
            text, markup = get_main_menu(uid, f"⏳ Подожди {sec} секунд до следующего подарка!")
            bot.reply_to(m, text, parse_mode='Markdown', reply_markup=markup)
            return
    
    card = get_random_card()
    
    update_inventory(uid, card["name"], 1)
    
    user_data = get_user(uid)
    stats = user_data.get("stats", {})
    stats["total_cards"] = stats.get("total_cards", 0) + 1
    user_data["stats"] = stats
    user_data["last_open"] = datetime.now().isoformat()
    update_user(uid, user_data)
    
    log_action(uid, "ВЫБИЛ ПОДАРОК", f"{card['emoji']} {card['name']} ({card['rarity']})")
    
    msg = f"🎴 **Тебе выпал подарок!**\n\n"
    msg += f"{card['emoji']} **{card['name']}**\n"
    msg += f"📊 Редкость: {card['rarity']}\n"
    msg += f"💰 Продажа: {card['price']} TGGifts\n"
    msg += f"⬆️ Шанс улучшения: {int(card['upgrade_chance']*100)}%\n"
    msg += f"\n{get_balance_display(uid)}\n\n"
    msg += f"👇 Выбери действие:"
    
    if card["rarity"] in ["Эксклюзивный"]:
        msg = f"🔥 **ЭКСКЛЮЗИВ!!!** 🔥\n\n" + msg
    elif card["rarity"] in ["Коллекционный"]:
        msg = f"✨ **Коллекционный подарок!** ✨\n\n" + msg
    
    bot.send_message(m.chat.id, msg, parse_mode='Markdown', 
                     reply_markup=card_buttons(card["name"]))

@bot.message_handler(commands=['balance'])
def balance(m):
    uid = m.from_user.id
    create_user(uid, m.from_user.username or "")
    log_action(uid, "ИСПОЛЬЗОВАЛ /balance", "")
    text, markup = get_main_menu(uid, get_balance_display(uid))
    bot.reply_to(m, text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['inventory'])
def inventory(m):
    uid = m.from_user.id
    create_user(uid, m.from_user.username or "")
    log_action(uid, "ИСПОЛЬЗОВАЛ /inventory", "")
    show_inventory_menu(uid, m.chat.id)

@bot.message_handler(commands=['admin'])
def admin_command(m):
    uid = m.from_user.id
    if uid != ADMIN_ID:
        log_action(uid, "ПОПЫТКА ВЗЛОМА АДМИНКИ", "")
        bot.reply_to(m, "❌ У тебя нет доступа!")
        return
    
    log_action(uid, "ОТКРЫЛ АДМИН-ПАНЕЛЬ", "")
    
    # Отправляем в личные сообщения
    try:
        admin_panel(uid)
        bot.reply_to(m, "🔐 Админ-панель отправлена в личные сообщения!")
    except:
        bot.reply_to(m, "❌ Не могу отправить в ЛС! Напиши боту первым в личку.")
        admin_panel(m.chat.id)

# ========== ТОП ==========
def show_leaderboard(uid, chat_id):
    try:
        users = get_all_users()
        if not users:
            text, markup = get_main_menu(uid, "📊 Пока нет игроков!")
            bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)
            return
        
        sorted_users = sorted(users, key=lambda x: x[1], reverse=True)
        top_10 = sorted_users[:10]
        
        msg = "🏆 **Топ игроков:**\n\n"
        for i, (user_id, balance, username) in enumerate(top_10, 1):
            username = username or str(user_id)
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            inv = get_inventory(user_id)
            card_count = sum(inv.values())
            msg += f"{medal} @{username} — {balance} TGGifts (подарков: {card_count})\n"
        
        msg += f"\n{get_balance_display(uid)}"
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
        
        bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
        log_action(uid, "ПОКАЗАЛ ТОП", f"всего игроков: {len(users)}")
    except Exception as e:
        log_action(uid, "ОШИБКА ТОПА", str(e))

def show_inventory_menu(uid, chat_id, edit_msg=False, message_id=None):
    try:
        inv = get_inventory(uid)
        
        if not inv:
            msg = f"📭 У тебя пока нет подарков! Используй /TGCard\n\n{get_balance_display(uid)}"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            if edit_msg and message_id:
                bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            return
        
        markup = inventory_buttons(uid)
        if not markup:
            msg = f"📭 Инвентарь пуст!\n\n{get_balance_display(uid)}"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            if edit_msg and message_id:
                bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
            return
        
        msg = f"📦 **Твой инвентарь:**\nНажми на подарок для действий\n\n{get_balance_display(uid)}"
        
        if edit_msg and message_id:
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.send_message(chat_id, msg, parse_mode='Markdown', reply_markup=markup)
    except Exception as e:
        log_action(uid, "ОШИБКА ИНВЕНТАРЯ", str(e))

# ========== ОБРАБОТЧИК КНОПОК ==========
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    uid = call.from_user.id
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data
    
    create_user(uid)
    
    log_action(uid, "НАЖАЛ КНОПКУ", f"{data}")
    
    try:
        # ===== ГЛАВНОЕ МЕНЮ =====
        if data == "main_menu":
            text, markup = get_main_menu(uid)
            bot.edit_message_text(text, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        
        # ===== КАК ИГРАТЬ =====
        if data == "how_to_play":
            msg = "📖 **Как играть:**\n\n"
            msg += "🎯 **Цель:** Собрать все подарки!\n\n"
            msg += "📌 **Команды:**\n"
            msg += "`/TGCard` — получить подарок (1 раз/мин)\n"
            msg += "`/inventory` — посмотреть подарки\n"
            msg += "`/balance` — баланс\n\n"
            msg += "💡 **Как заработать:**\n"
            msg += "• Продавай подарки\n"
            msg += "• Улучшай подарки (рискни!)\n\n"
            msg += "⬆️ **Улучшение:**\n"
            msg += "• При неудаче подарок сгорает!\n\n"
            msg += f"{get_balance_display(uid)}"
            
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        
        # ===== ИНВЕНТАРЬ =====
        if data == "show_inventory":
            show_inventory_menu(uid, chat_id, True, message_id)
            bot.answer_callback_query(call.id)
            return
        
        # ===== ТОП =====
        if data == "show_leaderboard":
            bot.delete_message(chat_id, message_id)
            show_leaderboard(uid, chat_id)
            bot.answer_callback_query(call.id)
            return
        
        # ===== ВЫБОР ПОДАРКА =====
        if data.startswith("card_"):
            card_name = data.replace("card_", "")
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if not card:
                bot.answer_callback_query(call.id, "❌ Подарок не найден!")
                return
            
            inv = get_inventory(uid)
            if card_name not in inv or inv[card_name] < 1:
                bot.answer_callback_query(call.id, "❌ Нет такого подарка!")
                return
            
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("💲 Продать", callback_data=f"confirm_sell_{card_name}"),
                InlineKeyboardButton("⬆️ Улучшить", callback_data=f"confirm_upgrade_{card_name}")
            )
            markup.row(InlineKeyboardButton("◀️ Назад", callback_data="show_inventory"))
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            
            msg = f"📦 **{card['emoji']} {card_name}**\n"
            msg += f"📊 Редкость: {card['rarity']}\n"
            msg += f"💰 Продажа: {card['price']} TGGifts\n"
            msg += f"⬆️ Шанс улучшения: {int(card['upgrade_chance']*100)}%\n"
            msg += f"📦 В наличии: {inv[card_name]} шт.\n\n"
            msg += f"{get_balance_display(uid)}\n\n"
            msg += f"👇 Выбери действие:"
            
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        
        # ===== ПОДТВЕРЖДЕНИЕ =====
        if data.startswith("confirm_sell_"):
            card_name = data.replace("confirm_sell_", "")
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if not card:
                bot.answer_callback_query(call.id, "❌ Ошибка!")
                return
            
            inv = get_inventory(uid)
            if card_name not in inv or inv[card_name] < 1:
                bot.answer_callback_query(call.id, "❌ Нет подарка!")
                return
            
            markup = confirm_buttons("sell", card_name)
            msg = f"⚠️ **Продать {card['emoji']} {card_name} за {card['price']} TGGifts?**"
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        
        if data.startswith("confirm_upgrade_"):
            card_name = data.replace("confirm_upgrade_", "")
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if not card:
                bot.answer_callback_query(call.id, "❌ Ошибка!")
                return
            
            if card["rarity"] == "Эксклюзивный":
                bot.answer_callback_query(call.id, "🌟 Максимальная редкость!")
                return
            
            inv = get_inventory(uid)
            if card_name not in inv or inv[card_name] < 1:
                bot.answer_callback_query(call.id, "❌ Нет подарка!")
                return
            
            chance = int(card['upgrade_chance']*100)
            markup = confirm_buttons("upgrade", card_name)
            msg = f"⚠️ **Улучшить {card['emoji']} {card_name}?**\n"
            msg += f"📊 Шанс: {chance}%\n"
            msg += f"💥 При неудаче сгорит!"
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        
        # ===== ВЫПОЛНЕНИЕ =====
        if data.startswith("do_sell_"):
            card_name = data.replace("do_sell_", "")
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if not card:
                bot.answer_callback_query(call.id, "❌ Ошибка!")
                return
            
            inv = get_inventory(uid)
            if card_name not in inv or inv[card_name] < 1:
                bot.answer_callback_query(call.id, "❌ Нет подарка!")
                return
            
            update_inventory(uid, card_name, -1)
            user_data = get_user(uid)
            user_data["balance"] += card["price"]
            stats = user_data.get("stats", {})
            stats["total_sold"] = stats.get("total_sold", 0) + 1
            user_data["stats"] = stats
            update_user(uid, user_data)
            
            log_action(uid, "ПРОДАЛ", f"{card['emoji']} {card_name} за {card['price']}")
            
            msg = f"💲 **Продано!**\n{card['emoji']} {card_name} +{card['price']} TGGifts\n{get_balance_display(uid)}"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"))
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id, f"✅ +{card['price']} TGGifts!")
            return
        
        if data.startswith("do_upgrade_"):
            card_name = data.replace("do_upgrade_", "")
            card = next((c for c in CARDS if c["name"] == card_name), None)
            if not card:
                bot.answer_callback_query(call.id, "❌ Ошибка!")
                return
            
            if card["rarity"] == "Эксклюзивный":
                bot.answer_callback_query(call.id, "🌟 Максимальная редкость!")
                return
            
            inv = get_inventory(uid)
            if card_name not in inv or inv[card_name] < 1:
                bot.answer_callback_query(call.id, "❌ Нет подарка!")
                return
            
            chance = card["upgrade_chance"]
            roll = random.random()
            
            if roll > chance:
                update_inventory(uid, card_name, -1)
                user_data = get_user(uid)
                stats = user_data.get("stats", {})
                stats["total_failed"] = stats.get("total_failed", 0) + 1
                user_data["stats"] = stats
                update_user(uid, user_data)
                
                log_action(uid, "НЕУДАЧНОЕ УЛУЧШЕНИЕ", f"{card['emoji']} {card_name}")
                
                msg = f"💥 **Провал!**\n{card['emoji']} {card_name} сгорел!\n{get_balance_display(uid)}"
                markup = InlineKeyboardMarkup()
                markup.row(InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"))
                markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
                
                bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
                bot.answer_callback_query(call.id, "❌ Карта сгорела!")
                return
            
            # УСПЕХ
            current_index = CARDS.index(card)
            next_card = CARDS[current_index + 1]
            
            update_inventory(uid, card_name, -1)
            update_inventory(uid, next_card["name"], 1)
            
            user_data = get_user(uid)
            stats = user_data.get("stats", {})
            stats["total_upgrades"] = stats.get("total_upgrades", 0) + 1
            user_data["stats"] = stats
            update_user(uid, user_data)
            
            log_action(uid, "УСПЕШНОЕ УЛУЧШЕНИЕ", f"{card['emoji']} {card_name} → {next_card['emoji']} {next_card['name']}")
            
            msg = f"⬆️ **Успех!**\n{card['emoji']} {card_name} → {next_card['emoji']} {next_card['name']}\n{get_balance_display(uid)}"
            markup = InlineKeyboardMarkup()
            markup.row(InlineKeyboardButton("📦 Инвентарь", callback_data="show_inventory"))
            markup.row(InlineKeyboardButton("🏠 Меню", callback_data="main_menu"))
            
            bot.edit_message_text(msg, chat_id, message_id, parse_mode='Markdown', reply_markup=markup)
            bot.answer_callback_query(call.id, f"✅ Улучшено до {next_card['name']}!")
            return
        
        # ===== АДМИН-КНОПКИ =====
        if data.startswith("admin_"):
            if uid != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Нет доступа!")
                return
            
            if data == "admin_list":
                users = get_all_users()
                if not users:
                    admin_panel(chat_id, "📋 Нет игроков")
                    bot.answer_callback_query(call.id)
                    return
                
                msg = "📋 **Список игроков:**\n\n"
                for i, (user_id, balance, username) in enumerate(sorted(users, key=lambda x: x[1], reverse=True), 1):
                    username = username or str(user_id)
                    msg += f"{i}. @{username} — {balance} TGGifts\n"
                    if len(msg) > 3500:
                        msg += "\n... и ещё"
                        break
                
                admin_panel(chat_id, msg)
                bot.answer_callback_query(call.id)
                return
            
            if data == "admin_add" or data == "admin_remove" or data == "admin_balance":
                bot.answer_callback_query(call.id, "ℹ️ Используй команду в чате:\n"
                                          f"`/{data.replace('admin_', 'admin_')} @username 100`", show_alert=True)
                return
    
    except Exception as e:
        log_action(uid, "ОШИБКА", str(e))
        try:
            bot.answer_callback_query(call.id, "❌ Ошибка! Попробуй ещё раз")
        except:
            pass

# ========== НЕИЗВЕСТНЫЕ КОМАНДЫ ==========
@bot.message_handler(func=lambda m: True)
def unknown(m):
    uid = m.from_user.id
    create_user(uid, m.from_user.username or "")
    log_action(uid, "НЕИЗВЕСТНАЯ КОМАНДА", f"'{m.text}'")
    text, markup = get_main_menu(uid, f"❌ Неизвестно: `{m.text}`\nИспользуй /start")
    bot.reply_to(m, text, parse_mode='Markdown', reply_markup=markup)

# ========== FLASK ОБЁРТКА ДЛЯ RENDER ==========
@app.route('/')
def index():
    """Health check для Render"""
    return "🤖 Gifts Cards Bot is running!", 200

@app.route('/health')
def health():
    """Дополнительный эндпоинт для мониторинга"""
    return {"status": "ok", "bot": "Gifts Cards Bot"}, 200

# ========== ЗАПУСК ==========
def start_bot():
    """Запуск бота в отдельном потоке"""
    init_db()
    print("="*60)
    print("🎰 Gifts Cards Bot ЗАПУЩЕН!")
    print("="*60)
    print("👤 Админ ID:", ADMIN_ID)
    print("💡 /start - меню")
    print("💡 /TGCard - получить подарок")
    print("💡 /admin - админ-панель (в ЛС)")
    print("="*60)
    
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Ошибка в боте: {e}")
            time.sleep(5)

if __name__ == "__main__":
    import threading
    
    # Запускаем бота в фоновом потоке
    bot_thread = threading.Thread(target=start_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Запускаем Flask для Render
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Веб-сервер запущен на порту {port}")
    app.run(host='0.0.0.0', port=port)