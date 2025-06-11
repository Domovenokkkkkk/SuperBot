import telebot
from telebot import types
import re
import logging
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Конфигурация (рекомендуется вынести в отдельный config.py или переменные окружения)
TOKEN = "7725975541:AAEZ1KbmqfeyTE5IMXZaGP97aQfR3EiaGwI"
CHAT_ID = -1002575550846
CREDS_FILE = "wise-philosophy-459302-d2-1402aa2b7daf.json"

bot = telebot.TeleBot(TOKEN)

# Варианты работ
WORK_OPTIONS = ["Гравировка", "Система", "Office", "Adobe", "Autocad", "Замена комплектующих"]
WORK_MAPPING = {
    "Гравировка": "Гравировка",
    "Система": "Система",
    "Office": "Офис",
    "Adobe": "Адоб",
    "Autocad": "Автокад",
    "Замена комплектующих": "Замена"
}

# Варианты доставки
DELIVERY_OPTIONS = [
    "СДЭК к двери",
    "СДЭК к ПВЗ",
    "Курьер Герман",
    "Курьер Яндекс",
    "Самовывоз",
    "Экспресс-Л",
    "Озон",
    "Почта РФ",
    "Авито",
    "Другое"
]

AVITO_SUBTYPES = {
    "Почта": "Авито (Почта)",
    "Яндекс": "Авито (Яндекс)"
}

DELIVERY_MAPPING = {
    "СДЭК к двери": "СДЭК к двери",
    "СДЭК к ПВЗ": "СДЭК к ПВЗ",
    "Курьер Герман": "Курьер Герман",
    "Курьер Яндекс": "Курьер Яндекс",
    "Самовывоз": "Самовывоз",
    "Экспресс-Л": "Экспресс-Л",
    "Озон": "Озон",
    "Почта РФ": "Почта РФ",
    "Авито (Почта)": "Авито (Почта)",
    "Авито (Яндекс)": "Авито (Яндекс)",
    "Другое": "Другое"
}

DELIVERY_WITH_PRICE = ["СДЭК к двери", "СДЭК к ПВЗ", "Курьер Герман", "Почта РФ"]

# Состояния бота
STATE_DEAL_NUM = 1
STATE_WORK = 2
STATE_REPLACEMENT = 3
STATE_DELIVERY = 4
STATE_ADDRESS = 5
STATE_CLIENT_NAME = 6
STATE_CLIENT_PHONE = 7
STATE_AMOUNT = 8
STATE_DELIVERY_PAYER = 9
STATE_COMMENT = 10
STATE_CONFIRM = 11
STATE_AVITO_SUBTYPE = 12

user_data = {}

def create_main_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Создать заявку", callback_data="create_order"))
    return markup

def create_cancel_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def create_back_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Назад", callback_data="back"))
    return markup

def create_cancel_back_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Назад", callback_data="back"),
        types.InlineKeyboardButton("Отменить", callback_data="cancel")
    )
    return markup

def create_work_keyboard(selected_works):
    markup = types.InlineKeyboardMarkup(row_width=2)
    for work in WORK_OPTIONS:
        text = f"✓ {work}" if work in selected_works else work
        markup.add(types.InlineKeyboardButton(text, callback_data=f"work_{work}"))
    markup.row(
        types.InlineKeyboardButton("Готово", callback_data="work_done"),
        types.InlineKeyboardButton("Пропустить", callback_data="work_skip")
    )
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def create_delivery_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    regular_options = [opt for opt in DELIVERY_OPTIONS if opt != "Авито"]
    for i in range(0, len(regular_options), 2):
        row = regular_options[i:i+2]
        markup.row(*[types.InlineKeyboardButton(opt, callback_data=f"delivery_{opt}") for opt in row])
    markup.add(types.InlineKeyboardButton("Авито", callback_data="delivery_Авито"))
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def create_avito_subtype_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Почта", callback_data="avito_subtype_Почта"),
        types.InlineKeyboardButton("Яндекс", callback_data="avito_subtype_Яндекс")
    )
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def create_delivery_payer_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("Мы", callback_data="payer_Мы"),
        types.InlineKeyboardButton("Клиент", callback_data="payer_Клиент")
    )
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def create_comment_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Пропустить", callback_data="comment_skip"),
        types.InlineKeyboardButton("Отменить", callback_data="cancel")
    )
    return markup

def create_confirmation_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Отправить", callback_data="confirm_send"),
        types.InlineKeyboardButton("Редактировать", callback_data="confirm_edit"),
    )
    markup.row(
        types.InlineKeyboardButton("Отменить", callback_data="cancel")
    )
    return markup

def create_edit_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        ("Номер сделки", "edit_deal"),
        ("Работы", "edit_work"),
        ("Доставка", "edit_delivery"),
        ("Адрес", "edit_address"),
        ("Клиент", "edit_client"),
        ("Телефон", "edit_phone"),
        ("Сумма", "edit_amount"),
        ("Оплата доставки", "edit_payer"),
        ("Комментарий", "edit_comment")
    ]
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.row(*[types.InlineKeyboardButton(text, callback_data=data) for text, data in row])
    markup.add(types.InlineKeyboardButton("Отменить", callback_data="cancel"))
    return markup

def init_google_sheets(sheet_name, max_retries=3):
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']

    for attempt in range(max_retries):
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
            client = gspread.authorize(creds)
            return client.open("Заявки").worksheet(sheet_name)
        except gspread.exceptions.APIError as e:
            logger.error(f"Ошибка Google Sheets (попытка {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
        except Exception as e:
            logger.error(f"Неожиданная ошибка Google Sheets: {e}")
            raise

def find_first_empty_row(sheet):
    col_a = sheet.col_values(1)
    row_num = 3
    while row_num <= len(col_a) + 1:
        if row_num > len(col_a) or not col_a[row_num-1]:
            break
        row_num += 1
    return row_num

def format_order_message(data, for_confirmation=False):
    works = data['selected_works'].copy()
    if "Замена комплектующих" in works and data.get('replacement_details'):
        works.remove("Замена комплектующих")
        works.append(f"Замена: {data['replacement_details']}")

    work_str = "\n".join(f"- {WORK_MAPPING.get(w, w)}" for w in works) if works else "- Не указано"
    delivery_display = DELIVERY_MAPPING.get(data.get('delivery_method', ''), data.get('delivery_method', ''))

    msg = (
        f"📋 Номер сделки: {data.get('deal_number', 'Не указан')}\n\n"
        f"🔧 Работы:\n{work_str}\n\n"
        f"🚚 Доставка: {delivery_display}\n"
    )

    if data.get('delivery_method') != "Самовывоз":
        msg += f"📍 Адрес: {data.get('address', 'Не указан')}\n\n"

    if data.get('delivery_method') not in ["Озон", "Самовывоз"]:
        msg += (
            f"👤 Клиент: {data.get('client_name', 'Не указан')}\n"
            f"📞 Телефон: {data.get('phone', 'Не указан')}\n"
        )

    if data.get('delivery_method') in DELIVERY_WITH_PRICE:
        msg += (
            f"\n💰 Сумма: {data.get('amount', 'Не указана')}\n"
            f"💳 Оплата доставки: {data.get('delivery_payer', 'Не указано')}\n"
        )

    if data.get('delivery_method', '').startswith("Авито"):
        msg += f"\n📦 Подтип доставки: {data.get('delivery_subtype', 'Не указан')}\n"

    msg += f"\n📝 Комментарий: {data.get('comment', 'Без комментария')}"

    if not for_confirmation:
        msg += f"\n\n👨‍💼 Менеджер: @{data.get('username', 'неизвестен')}"
        if data.get('delivery_method', '').startswith("Авито"):
            msg += "\n#Авито"
        elif "СДЭК" in data.get('delivery_method', ''):
            msg += "\n#СДЭК"

    return msg

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "Добро пожаловать! Нажмите кнопку ниже для создания заявки.",
        reply_markup=create_main_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data == "create_order")
def start_order(call):
    chat_id = call.message.chat.id
    user_data[chat_id] = {
        'state': STATE_DEAL_NUM,
        'selected_works': [],
        'user_id': call.from_user.id,
        'username': call.from_user.username
    }
    bot.edit_message_text(
        "Введите номер сделки:",
        chat_id,
        call.message.message_id,
        reply_markup=create_cancel_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data in ["cancel", "back"])
def handle_cancel_back(call):
    chat_id = call.message.chat.id
    if call.data == "cancel":
        cancel_order(chat_id, call.message.message_id)
    elif call.data == "back":
        handle_back(chat_id, call.message.message_id)

def handle_back(chat_id, message_id):
    if chat_id not in user_data:
        bot.edit_message_text(
            "Добро пожаловать! Нажмите кнопку ниже для создания заявки.",
            chat_id,
            message_id,
            reply_markup=create_main_keyboard()
        )
        return

    data = user_data[chat_id]

    if data.get('edit_state'):
        show_order_confirmation(chat_id)
        return

    if data['state'] == STATE_WORK:
        data['state'] = STATE_DEAL_NUM
        bot.edit_message_text(
            "Введите номер сделки:",
            chat_id,
            message_id,
            reply_markup=create_cancel_keyboard()
        )
    elif data['state'] == STATE_REPLACEMENT:
        ask_work_selection(chat_id)
    elif data['state'] == STATE_DELIVERY:
        if "Замена комплектующих" in data['selected_works']:
            data['state'] = STATE_REPLACEMENT
            bot.edit_message_text(
                "Опишите, что на что нужно заменить:",
                chat_id,
                message_id,
                reply_markup=create_cancel_back_keyboard()
            )
        else:
            ask_work_selection(chat_id)
    elif data['state'] == STATE_ADDRESS:
        ask_delivery_method(chat_id)
    elif data['state'] == STATE_CLIENT_NAME:
        ask_address(chat_id)
    elif data['state'] == STATE_CLIENT_PHONE:
        ask_client_name(chat_id)
    elif data['state'] == STATE_AMOUNT:
        ask_client_phone(chat_id)
    elif data['state'] == STATE_DELIVERY_PAYER:
        ask_amount(chat_id)
    elif data['state'] == STATE_COMMENT:
        if data['delivery_method'] in DELIVERY_WITH_PRICE:
            ask_delivery_payer(chat_id)
        else:
            ask_client_phone(chat_id)
    elif data['state'] == STATE_CONFIRM:
        ask_comment(chat_id)
    elif data['state'] == STATE_AVITO_SUBTYPE:
        ask_delivery_method(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_text(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if chat_id not in user_data:
        bot.send_message(chat_id, "Пожалуйста, начните с создания заявки", reply_markup=create_main_keyboard())
        return

    data = user_data[chat_id]

    if data.get('edit_state'):
        handle_edit_text(message)
        return

    if data['state'] == STATE_DEAL_NUM:
        data['deal_number'] = text
        ask_work_selection(chat_id)

    elif data['state'] == STATE_REPLACEMENT:
        data['replacement_details'] = text
        ask_delivery_method(chat_id)

    elif data['state'] == STATE_ADDRESS:
        data['address'] = text
        if data['delivery_method'] in ["Озон", "Самовывоз"]:
            data['client_name'] = "Не требуется"
            data['phone'] = "Не требуется"
            if data['delivery_method'] in DELIVERY_WITH_PRICE:
                ask_amount(chat_id)
            else:
                data['amount'] = "Не указана"
                data['delivery_payer'] = "Не требуется"
                ask_comment(chat_id)
        else:
            ask_client_name(chat_id)

    elif data['state'] == STATE_CLIENT_NAME:
        if len(text.split()) < 2:
            bot.send_message(
                chat_id,
                "ФИО должно содержать минимум 2 слова! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['client_name'] = text
        ask_client_phone(chat_id)

    elif data['state'] == STATE_CLIENT_PHONE:
        phone = format_phone_number(text)
        if not phone:
            bot.send_message(
                chat_id,
                "Неверный формат телефона! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['phone'] = phone

        if data['delivery_method'] in DELIVERY_WITH_PRICE:
            ask_amount(chat_id)
        else:
            data['amount'] = "Не указана"
            data['delivery_payer'] = "Не требуется"
            ask_comment(chat_id)

    elif data['state'] == STATE_AMOUNT:
        if not text.isdigit():
            bot.send_message(
                chat_id,
                "Сумма должна быть числом! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['amount'] = text
        ask_delivery_payer(chat_id)

    elif data['state'] == STATE_DELIVERY_PAYER:
        data['delivery_payer'] = text
        ask_comment(chat_id)

    elif data['state'] == STATE_COMMENT:
        data['comment'] = text if text.lower() != "нет" else "Без комментария"
        show_order_confirmation(chat_id)

def ask_work_selection(chat_id):
    user_data[chat_id]['state'] = STATE_WORK
    selected = user_data[chat_id]['selected_works']
    bot.send_message(
        chat_id,
        "Выберите перечень работ:\nВыбрано: " + (", ".join(selected) if selected else "пока ничего"),
        reply_markup=create_work_keyboard(selected)
    )

def ask_delivery_method(chat_id):
    user_data[chat_id]['state'] = STATE_DELIVERY
    bot.send_message(
        chat_id,
        "Выберите способ доставки:",
        reply_markup=create_delivery_keyboard()
    )

def ask_address(chat_id):
    user_data[chat_id]['state'] = STATE_ADDRESS
    bot.send_message(
        chat_id,
        "Введите полный адрес:",
        reply_markup=create_cancel_back_keyboard()
    )

def ask_client_name(chat_id):
    user_data[chat_id]['state'] = STATE_CLIENT_NAME
    if user_data[chat_id].get('delivery_method') in ["Озон", "Самовывоз"]:
        user_data[chat_id]['client_name'] = "Не требуется"
        ask_client_phone(chat_id)
        return

    bot.send_message(
        chat_id,
        "Введите ФИО клиента (минимум 2 слова):",
        reply_markup=create_cancel_back_keyboard()
    )

def ask_client_phone(chat_id):
    user_data[chat_id]['state'] = STATE_CLIENT_PHONE
    if user_data[chat_id].get('delivery_method') in ["Озон", "Самовывоз"]:
        user_data[chat_id]['phone'] = "Не требуется"
        if user_data[chat_id]['delivery_method'] in DELIVERY_WITH_PRICE:
            ask_amount(chat_id)
        else:
            user_data[chat_id]['amount'] = "Не указана"
            user_data[chat_id]['delivery_payer'] = "Не требуется"
            ask_comment(chat_id)
        return

    bot.send_message(
        chat_id,
        "Введите телефон клиента:",
        reply_markup=create_cancel_back_keyboard()
    )

def ask_amount(chat_id):
    user_data[chat_id]['state'] = STATE_AMOUNT
    bot.send_message(
        chat_id,
        "Введите сумму за товар:",
        reply_markup=create_cancel_back_keyboard()
    )

def ask_delivery_payer(chat_id):
    user_data[chat_id]['state'] = STATE_DELIVERY_PAYER
    if user_data[chat_id].get('delivery_method') == "Курьер Герман":
        user_data[chat_id]['delivery_payer'] = "Не требуется"
        ask_comment(chat_id)
        return

    bot.send_message(
        chat_id,
        "Кто оплачивает доставку?",
        reply_markup=create_delivery_payer_keyboard()
    )

def ask_comment(chat_id):
    user_data[chat_id]['state'] = STATE_COMMENT
    bot.send_message(
        chat_id,
        "Добавьте комментарий (или нажмите 'Пропустить'):",
        reply_markup=create_comment_keyboard()
    )

def show_order_confirmation(chat_id):
    user_data[chat_id]['state'] = STATE_CONFIRM
    data = user_data[chat_id]
    try:
        msg = format_order_message(data, for_confirmation=True)
        bot.send_message(
            chat_id,
            f"Проверьте заявку:\n\n{msg}\n\nПодтвердите отправку:",
            reply_markup=create_confirmation_keyboard()
        )
    except KeyError as e:
        logger.error(f"Ошибка формирования заявки: {e}")
        bot.send_message(
            chat_id,
            "Произошла ошибка при формировании заявки. Пожалуйста, начните заново.",
            reply_markup=create_main_keyboard()
        )
        if chat_id in user_data:
            del user_data[chat_id]

@bot.callback_query_handler(func=lambda call: call.data.startswith("work_"))
def handle_work_selection(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    action = call.data[5:]

    if action == "done":
        if not data['selected_works']:
            bot.answer_callback_query(call.id, "Выберите хотя бы один вариант или нажмите 'Пропустить'")
            return

        if "Замена комплектующих" in data['selected_works']:
            data['state'] = STATE_REPLACEMENT
            bot.edit_message_text(
                "Опишите, что на что нужно заменить:",
                chat_id,
                call.message.message_id,
                reply_markup=create_cancel_back_keyboard()
            )
        else:
            ask_delivery_method(chat_id)
            bot.delete_message(chat_id, call.message.message_id)

    elif action == "skip":
        data['selected_works'] = []
        ask_delivery_method(chat_id)
        bot.delete_message(chat_id, call.message.message_id)

    else:
        work = action
        if work in data['selected_works']:
            data['selected_works'].remove(work)
        else:
            data['selected_works'].append(work)

        selected = data['selected_works']
        try:
            bot.edit_message_text(
                f"Выберите перечень работ:\nВыбрано: {', '.join(selected) if selected else 'пока ничего'}",
                chat_id,
                call.message.message_id,
                reply_markup=create_work_keyboard(selected)
            )
        except:
            bot.answer_callback_query(call.id, "Обновление...")

@bot.callback_query_handler(func=lambda call: call.data.startswith("delivery_"))
def handle_delivery_selection(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    delivery_method = call.data[9:]

    if delivery_method == "Авито":
        data['state'] = STATE_AVITO_SUBTYPE
        bot.edit_message_text(
            "Выберите способ доставки для Авито:",
            chat_id,
            call.message.message_id,
            reply_markup=create_avito_subtype_keyboard()
        )
        return

    data['delivery_method'] = delivery_method

    if delivery_method == "Озон":
        data['client_name'] = "Не требуется"
        data['phone'] = "Не требуется"
        ask_comment(chat_id)
    elif delivery_method == "Курьер Герман":
        data['delivery_payer'] = "Не требуется"
        ask_address(chat_id)
    elif delivery_method == "Самовывоз":
        data['address'] = "Самовывоз"
        data['client_name'] = "Не требуется"
        data['phone'] = "Не требуется"
        data['delivery_payer'] = "Не требуется"
        ask_comment(chat_id)
    else:
        ask_address(chat_id)

    bot.delete_message(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("avito_subtype_"))
def handle_avito_subtype(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    subtype = call.data[13:]

    data['delivery_method'] = AVITO_SUBTYPES[subtype]
    data['delivery_subtype'] = subtype
    data['delivery_payer'] = "Не требуется"  # Для Авито не запрашиваем оплату
    bot.delete_message(chat_id, call.message.message_id)
    ask_comment(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("payer_"))
def handle_payer_selection(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    payer = call.data[6:]

    data['delivery_payer'] = payer
    bot.delete_message(chat_id, call.message.message_id)
    ask_comment(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "comment_skip")
def handle_comment_skip(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    data['comment'] = "Без комментария"
    bot.delete_message(chat_id, call.message.message_id)
    show_order_confirmation(chat_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_"))
def handle_confirmation(call):
    chat_id = call.message.chat.id
    data = user_data[chat_id]
    action = call.data[8:]

    if action == "send":
        try:
            formatted_msg = format_order_message(data)
            bot.send_message(CHAT_ID, f"НОВАЯ ЗАЯВКА\n\n{formatted_msg}")

            # Запись в основную таблицу
            sheet = init_google_sheets("Заявки")
            row_num = find_first_empty_row(sheet)

            works = [WORK_MAPPING.get(w, w) for w in data.get('selected_works', [])]
            delivery = DELIVERY_MAPPING.get(data.get('delivery_method', ''), '')

            sheet.update_cell(row_num, 1, data.get('deal_number', ''))
            sheet.update_cell(row_num, 3, ", ".join(works))
            sheet.update_cell(row_num, 5, data.get('comment', ''))
            sheet.update_cell(row_num, 6, delivery)

            # Запись в таблицу СДЭК (если нужно)
            if "СДЭК" in data.get('delivery_method', ''):
                sdek_sheet = init_google_sheets("Заполнение запроса СДЭК")
                sdek_row_num = find_first_empty_row(sdek_sheet)

                updates = {
                    'A': data.get('deal_number', ''),
                    'E': data.get('address', ''),
                    'F': data.get('client_name', ''),
                    'G': data.get('phone', ''),
                    'L': data.get('amount', ''),
                    'M': "Отправитель" if data.get('delivery_payer') == "Мы" else "Получатель"
                }

                for col, value in updates.items():
                    sdek_sheet.update_acell(f'{col}{sdek_row_num}', value)

            bot.edit_message_text(
                "Заявка успешно отправлена!",
                chat_id,
                call.message.message_id
            )

            del user_data[chat_id]
            send_welcome(call.message)
        except Exception as e:
            logger.error(f"Ошибка отправки заявки: {e}")
            bot.answer_callback_query(call.id, "Ошибка отправки заявки")

    elif action == "edit":
        ask_what_to_edit(chat_id, call.message.message_id)

def ask_what_to_edit(chat_id, message_id):
    bot.edit_message_text(
        "Что вы хотите изменить?",
        chat_id,
        message_id,
        reply_markup=create_edit_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def handle_edit_selection(call):
    chat_id = call.message.chat.id
    if chat_id not in user_data:
        return

    edit_type = call.data[5:]
    data = user_data[chat_id]
    data['edit_state'] = edit_type

    if edit_type == "deal":
        bot.edit_message_text(
            "Введите новый номер сделки:",
            chat_id,
            call.message.message_id,
            reply_markup=create_cancel_back_keyboard()
        )
    elif edit_type == "work":
        ask_work_selection(chat_id)
    elif edit_type == "delivery":
        ask_delivery_method(chat_id)
    elif edit_type == "address":
        bot.edit_message_text(
            "Введите новый адрес:",
            chat_id,
            call.message.message_id,
            reply_markup=create_cancel_back_keyboard()
        )
    elif edit_type == "client":
        bot.edit_message_text(
            "Введите новые ФИО клиента (минимум 2 слова):",
            chat_id,
            call.message.message_id,
            reply_markup=create_cancel_back_keyboard()
        )
    elif edit_type == "phone":
        bot.edit_message_text(
            "Введите новый телефон клиента:",
            chat_id,
            call.message.message_id,
            reply_markup=create_cancel_back_keyboard()
        )
    elif edit_type == "amount":
        bot.edit_message_text(
            "Введите новую сумму:",
            chat_id,
            call.message.message_id,
            reply_markup=create_cancel_back_keyboard()
        )
    elif edit_type == "payer":
        bot.edit_message_text(
            "Выберите, кто оплачивает доставку:",
            chat_id,
            call.message.message_id,
            reply_markup=create_delivery_payer_keyboard()
        )
    elif edit_type == "comment":
        bot.edit_message_text(
            "Введите новый комментарий (или 'нет'):",
            chat_id,
            call.message.message_id,
            reply_markup=create_comment_keyboard()
        )

def handle_edit_text(message):
    chat_id = message.chat.id
    data = user_data[chat_id]
    edit_state = data.get('edit_state')
    text = message.text.strip()

    if not edit_state:
        return

    if edit_state == "deal":
        data['deal_number'] = text
    elif edit_state == "address":
        data['address'] = text
    elif edit_state == "client":
        if len(text.split()) < 2:
            bot.send_message(
                chat_id,
                "ФИО должно содержать минимум 2 слова! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['client_name'] = text
    elif edit_state == "phone":
        phone = format_phone_number(text)
        if not phone:
            bot.send_message(
                chat_id,
                "Неверный формат телефона! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['phone'] = phone
    elif edit_state == "amount":
        if not text.isdigit():
            bot.send_message(
                chat_id,
                "Сумма должна быть числом! Введите еще раз:",
                reply_markup=create_cancel_back_keyboard()
            )
            return
        data['amount'] = text
    elif edit_state == "comment":
        data['comment'] = text if text.lower() != "нет" else "Без комментария"

    data.pop('edit_state', None)
    show_order_confirmation(chat_id)

def format_phone_number(phone):
    cleaned = re.sub(r'[^0-9]', '', phone)

    if not cleaned:
        return None

    if len(cleaned) == 11:
        if cleaned.startswith('8'):
            return '+7' + cleaned[1:]
        if cleaned.startswith('7'):
            return '+' + cleaned
    elif len(cleaned) == 10:
        return '+7' + cleaned

    return None

def cancel_order(chat_id, message_id=None):
    if chat_id in user_data:
        del user_data[chat_id]

    if message_id:
        bot.edit_message_text(
            "Заявка отменена.",
            chat_id,
            message_id,
            reply_markup=create_main_keyboard()
        )
    else:
        bot.send_message(
            chat_id,
            "Заявка отменена.",
            reply_markup=create_main_keyboard()
        )

def run_bot():
    while True:
        try:
            print("Бот запущен!")
            bot.polling(none_stop=True, interval=1, timeout=20)
        except requests.exceptions.ProxyError as e:
            logger.error(f"Proxy error: {e}. Перезапуск бота через 10 секунд...")
            time.sleep(10)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {e}. Перезапуск бота через 10 секунд...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Перезапуск бота через 30 секунд...")
            time.sleep(30)

if __name__ == '__main__':
    while True:
        try:
            run_bot()
        except KeyboardInterrupt:
            print("Бот остановлен")
            break
        except Exception as e:
            print(f"Критическая ошибка: {e}. Перезапуск через 60 секунд...")
            time.sleep(60)