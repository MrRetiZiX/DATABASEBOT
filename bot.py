from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *
import cv2
import os
import logging
from requests.exceptions import ConnectionError, ReadTimeout
from telebot.apihelper import ApiTelegramException

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = TeleBot(API_TOKEN)

def gen_markup(id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=id))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    try:
        prize_id = call.data
        user_id = call.message.chat.id

        # Добавляем пользователя как победителя
        result = manager.add_winner(user_id, prize_id)
        
        if result:
            img = manager.get_prize_img(prize_id)
            if img and os.path.exists(f'img/{img}'):
                with open(f'img/{img}', 'rb') as photo:
                    bot.send_photo(user_id, photo, caption="Поздравляем! Вы получили приз!")
            else:
                bot.answer_callback_query(call.id, "Приз недоступен!")
        else:
            bot.answer_callback_query(call.id, "Вы уже получили этот приз!")
    except Exception as e:
        logger.error(f"Ошибка в callback_query: {e}")
        try:
            bot.answer_callback_query(call.id, "Произошла ошибка!")
        except:
            pass

def send_message():
    try:
        result = manager.get_random_prize()
        if result:
            prize_id, img = result
            manager.mark_prize_used(prize_id)
            hide_img(img)
            
            users = manager.get_users()
            for user in users:
                try:
                    if os.path.exists(f'hidden_img/{img}'):
                        with open(f'hidden_img/{img}', 'rb') as photo:
                            bot.send_photo(user, photo, reply_markup=gen_markup(id=prize_id))
                        time.sleep(0.1)  # Небольшая задержка между отправками
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения пользователю {user}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Ошибка в send_message: {e}")

def shedule_thread():
    schedule.every(10).minutes.do(send_message)
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка в shedule_thread: {e}")
            time.sleep(5)

@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user_id = message.chat.id
        if user_id in manager.get_users():
            bot.reply_to(message, "Ты уже зарегестрирован!")
        else:
            username = message.from_user.username if message.from_user.username else f"user_{user_id}"
            manager.add_user(user_id, username)
            bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждые 10 минут тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Используй команду /get_my_score чтобы посмотреть свои достижения!""")
    except Exception as e:
        logger.error(f"Ошибка в handle_start: {e}")
        try:
            bot.reply_to(message, "Произошла ошибка при регистрации. Попробуйте позже.")
        except:
            pass

@bot.message_handler(commands=['get_my_score'])
def handle_get_my_score(message):
    try:
        user_id = message.chat.id
        
        # Проверяем, зарегистрирован ли пользователь
        if user_id not in manager.get_users():
            bot.reply_to(message, "Сначала зарегистрируйтесь с помощью команды /start")
            return
        
        # Получаем картинки пользователя
        user_prizes_info = manager.get_winners_img(user_id)
        user_prizes = [x[0] for x in user_prizes_info]
        
        # Получаем все доступные картинки
        if not os.path.exists('img'):
            bot.reply_to(message, "Папка с изображениями не найдена!")
            return
            
        all_images = os.listdir('img')
        
        if not all_images:
            bot.reply_to(message, "Изображения не найдены!")
            return
        
        # Создаем пути к изображениям (полученные - обычные, неполученные - зашифрованные)
        image_paths = []
        for img_name in all_images:
            if img_name in user_prizes:
                image_paths.append(f'img/{img_name}')
            else:
                hidden_path = f'hidden_img/{img_name}'
                if os.path.exists(hidden_path):
                    image_paths.append(hidden_path)
                else:
                    # Если зашифрованной версии нет, создаем её
                    hide_img(img_name)
                    if os.path.exists(hidden_path):
                        image_paths.append(hidden_path)
        
        if not image_paths:
            bot.reply_to(message, "Нет доступных изображений для создания коллажа!")
            return
        
        # Создаем коллаж
        collage = create_collage(image_paths)
        
        if collage is None:
            bot.reply_to(message, "Не удалось создать коллаж!")
            return
        
        # Сохраняем коллаж
        collage_path = f'collages/user_{user_id}_collage.jpg'
        os.makedirs('collages', exist_ok=True)
        cv2.imwrite(collage_path, collage)
        
        # Отправляем коллаж пользователю
        try:
            with open(collage_path, 'rb') as photo:
                caption = f"Ваши достижения!\nПолучено призов: {len(user_prizes)}/{len(all_images)}"
                bot.send_photo(user_id, photo, caption=caption)
        except Exception as e:
            logger.error(f"Ошибка при отправке коллажа: {e}")
            bot.reply_to(message, "Ошибка при отправке коллажа. Попробуйте позже.")
        finally:
            # Удаляем временный файл коллажа
            if os.path.exists(collage_path):
                try:
                    os.remove(collage_path)
                except:
                    pass
                    
    except Exception as e:
        logger.error(f"Ошибка в handle_get_my_score: {e}")
        try:
            bot.reply_to(message, "Произошла ошибка. Попробуйте позже.")
        except:
            pass

def polling_thread():
    while True:
        try:
            logger.info("Запуск polling...")
            bot.polling(none_stop=True, interval=1, timeout=20)
        except ConnectionError as e:
            logger.error(f"Ошибка соединения: {e}")
            logger.info("Переподключение через 15 секунд...")
            time.sleep(15)
        except ReadTimeout as e:
            logger.error(f"Таймаут чтения: {e}")
            logger.info("Переподключение через 10 секунд...")
            time.sleep(10)
        except ApiTelegramException as e:
            logger.error(f"Ошибка Telegram API: {e}")
            logger.info("Переподключение через 10 секунд...")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            logger.info("Переподключение через 20 секунд...")
            time.sleep(20)

if __name__ == '__main__':
    try:
        manager = DatabaseManager(DATABASE)
        manager.create_tables()
        
        # Создаем необходимые папки
        os.makedirs('img', exist_ok=True)
        os.makedirs('hidden_img', exist_ok=True)
        os.makedirs('collages', exist_ok=True)

        logger.info("Запуск потоков...")
        
        polling_thread_obj = threading.Thread(target=polling_thread, daemon=True)
        shedule_thread_obj = threading.Thread(target=shedule_thread, daemon=True)
        
        polling_thread_obj.start()
        shedule_thread_obj.start()
        
        # Основной поток остается активным
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Остановка бота...")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
