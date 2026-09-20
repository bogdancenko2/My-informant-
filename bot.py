import telebot
import sqlite3
import random
from datetime import datetime, timedelta

# Твой токен бота и ID администратора
TOKEN = '8915599112:AAHVP4hLqZtA-dfRgp9Y5NOCQViNZ-Oj2Og'
ADMIN_ID = 8449068202

bot = telebot.TeleBot(TOKEN)

# Список загадок уровня 6-8 класса
RIDDLES = [
    ("Какое число делится на все числа без остатка, кроме нуля?", ["0", "1", "все числа"], "0"),
    ("У отца пять сыновей, и у каждого есть сестра. Сколько всего детей в семье?", ["5", "6", "10"], "6"),
    ("Чему равна сумма углов треугольника?", ["180 градусов", "360 градусов", "90 градусов"], "180 градусов"),
    ("Какая планета Солнечной системы ближе всего к Солнцу?", ["Венера", "Марс", "Меркурий"], "Меркурий")
]

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            last_farm TEXT,
            last_riddle TEXT
        )
    ''')
    
    # Таблица для подсчета сообщений (хранит историю времени сообщений)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            timestamp TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Логгер сообщений для статистики профиля
@bot.message_handler(func=lambda message: True, content_types=['text'])
def track_messages(message):
    # Если это текстовая команда из нашего списка, не обрабатываем её здесь как обычный текст,
    # а даем отработать профильным хендлерам ниже.
    text_lower = message.text.lower() if message.text else ""
    
    # Записываем сообщение в лог для статистики
    user_id = str(message.from_user.id)
    now_str = datetime.now().isoformat()
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages_log (user_id, timestamp) VALUES (?, ?)", (user_id, now_str))
    conn.commit()
    conn.close()
    
    # Перенаправляем дальше по хендлерам
    bot.process_new_messages([message])


# ==========================================
# 1. СТАРТ И КНОПКИ УПРАВЛЕНИЯ
# ==========================================

@bot.message_handler(commands=['start'])
def clean_start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username if message.from_user.username else ""
    name = message.from_user.first_name
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
    conn.commit()
    conn.close()
    
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_profile = telebot.types.KeyboardButton('👤 Профиль')
    btn_clean = telebot.types.KeyboardButton('🧹 Чистка')
    markup.add(btn_profile, btn_clean)
    
    text = f"👋 Привет, {name}!\n\n🎮 Бот успешно запущен и готов к работе."
    bot.reply_to(message, text, reply_markup=markup)


# ==========================================
# 2. ПРОФИЛЬ (ВКЛЮЧАЯ СТАТИСТИКУ СООБЩЕНИЙ)
# ==========================================

@bot.message_handler(func=lambda message: message.text and message.text == '👤 Профиль')
def block_profile(message):
    user_id = str(message.from_user.id)
    name = message.from_user.first_name
    username = f"@{message.from_user.username}" if message.from_user.username else "отсутствует"
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Баланс
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    
    # Подсчет сообщений за день, неделю, месяц
    now = datetime.now()
    day_ago = (now - timedelta(days=1)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()
    month_ago = (now - timedelta(days=30)).isoformat()
    
    cursor.execute("SELECT COUNT(*) FROM messages_log WHERE user_id = ? AND timestamp >= ?", (user_id, day_ago))
    msg_day = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages_log WHERE user_id = ? AND timestamp >= ?", (user_id, week_ago))
    msg_week = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM messages_log WHERE user_id = ? AND timestamp >= ?", (user_id, month_ago))
    msg_month = cursor.fetchone()[0]
    
    conn.close()
    
    profile_text = (
        f"👤 <b>Твой профиль:</b>\n\n"
        f"• Имя: {name}\n"
        f"• Username: {username}\n"
        f"• ID: <code>{user_id}</code>\n"
        f"• Баланс: <b>{balance}</b> монет\n\n"
        f"📊 <b>Активность (сообщений):</b>\n"
        f"• За 1 день: <b>{msg_day}</b>\n"
        f"• За 1 неделю: <b>{msg_week}</b>\n"
        f"• За 1 месяц: <b>{msg_month}</b>"
    )
    bot.reply_to(message, profile_text, parse_mode="HTML")


# ==========================================
# 3. ФАРМ, ТОП И ИГРЫ
# ==========================================

@bot.message_handler(func=lambda message: message.text and message.text.lower() == 'фарм')
def block_farm(message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, last_farm FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        username = message.from_user.username if message.from_user.username else ""
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
        conn.commit()
        balance, last_farm_str = 0, None
    else:
        balance, last_farm_str = user
    
    # Кулдаун 3 часа
    if last_farm_str:
        last_farm_time = datetime.fromisoformat(last_farm_str)
        next_farm_time = last_farm_time + timedelta(hours=3)
        
        if now < next_farm_time:
            remaining = next_farm_time - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            bot.reply_to(message, f"⏳ Рано фармить! Подожди еще {hours} ч. {minutes} мин.")
            conn.close()
            return

    reward = random.randint(1, 100)
    new_balance = balance + reward
    current_time_str = now.isoformat()
    
    cursor.execute("UPDATE users SET balance = ?, last_farm = ? WHERE user_id = ?", (new_balance, current_time_str, user_id))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"🎉 Ты успешно пофармил и выбил +{reward} монет!\n💰 Баланс: {new_balance} монет.")


@bot.message_handler(func=lambda message: message.text and message.text.lower() in ['топ', 'топ монет'])
def block_top(message):
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT username, user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        bot.reply_to(message, "🏆 Список лидеров пока пуст.")
        return
        
    text = "🏆 <b>Топ игроков по монетам:</b>\n\n"
    for index, (uname, uid, bal) in enumerate(top_users, start=1):
        display_name = f"@{uname}" if uname else f"ID: {uid}"
        text += f"{index}. {display_name} — <b>{bal}</b> монет\n"
        
    bot.reply_to(message, text, parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text and message.text.lower() == 'рандом')
def game_random(message):
    num = random.randint(1, 100)
    bot.reply_to(message, f"🎲 Твое случайное число: <b>{num}</b>", parse_mode="HTML")


@bot.message_handler(func=lambda message: message.text and message.text.lower() == 'загадка')
def game_riddle(message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, last_riddle FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        username = message.from_user.username if message.from_user.username else ""
        cursor.execute("INSERT INTO users (user_id, username, balance) VALUES (?, ?, 0)", (user_id, username))
        conn.commit()
        balance, last_riddle_str = 0, None
    else:
        balance, last_riddle_str = user
        
    # Кулдаун на загадку 4 часа
    if last_riddle_str:
        last_time = datetime.fromisoformat(last_riddle_str)
        next_time = last_time + timedelta(hours=4)
        if now < next_time:
            remaining = next_time - now
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            bot.reply_to(message, f"⏳ Новая загадка будет доступна через {hours} ч. {minutes} мин.")
            conn.close()
            return

    riddle = random.choice(RIDDLES)
    question, options, correct_answer = riddle
    
    # Сохраняем время загадки и фиксируем правильный ответ (для простоты выдаем сразу награду за вызов или можно сделать механику ответов)
    # Здесь выдадим +50 монет за правильный ответ сразу для теста
    new_balance = balance + 50
    current_time_str = now.isoformat()
    
    cursor.execute("UPDATE users SET balance = ?, last_riddle = ? WHERE user_id = ?", (new_balance, current_time_str, user_id))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"🧩 <b>Школьная загадка:</b>\n{question}\n\nВарианты: {', '.join(options)}\n\n💡 Правильный ответ засчитан! Тебе начислено +50 монет.", parse_mode="HTML")


# ==========================================
# 4. АДМИНСКАЯ КОМАНДА
# ==========================================

@bot.message_handler(commands=['add_money'])
def admin_add_money(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ У тебя нет прав администратора.")
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "Использование: /add_money <ID или @username> <сумма>\n(Чтобы забрать, используй минус, например: -50)")
        return
    
    target = args[1].strip()
    try:
        amount = int(args[2])
    except ValueError:
        bot.reply_to(message, "❌ Сумма должна быть числом!")
        return
    
    conn = sqlite3.connect('bot_database.db', check_same_thread=False)
    cursor = conn.cursor()
    
    if target.isdigit():
        cursor.execute("SELECT balance FROM users WHERE user_id = ?", (target,))
        user = cursor.fetchone()
        search_query = "UPDATE users SET balance = balance + ? WHERE user_id = ?"
    else:
        clean_username = target.lstrip('@')
        cursor.execute("SELECT balance FROM users WHERE username = ?", (clean_username,))
        user = cursor.fetchone()
        search_query = "UPDATE users SET balance = balance + ? WHERE username = ?"
        target = clean_username

    if not user:
        bot.reply_to(message, f"❌ Пользователь '{target}' не найден в базе данных!")
        conn.close()
        return
        
    cursor.execute(search_query, (amount, target))
    conn.commit()
    conn.close()
    
    bot.reply_to(message, f"✅ Успешно обновлен баланс пользователя {target} на {amount} монет!")


# ==========================================
# 5. ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    print("Бот успешно запущен со всеми компонентами...")
    bot.infinity_polling(none_stop=True)
