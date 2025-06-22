import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2
import numpy as np
from math import sqrt, ceil, floor
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
        ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY,
                image TEXT,
                used INTEGER DEFAULT 0
            )
        ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id)
            )
        ''')

            conn.commit()

    def add_user(self, user_id, user_name):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.execute('INSERT OR IGNORE INTO users VALUES (?, ?)', (user_id, user_name))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя: {e}")

    def add_prize(self, data):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.executemany('''INSERT INTO prizes (image) VALUES (?)''', data)
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при добавлении приза: {e}")

    def add_winner(self, user_id, prize_id):
        try:
            win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor() 
                cur.execute("SELECT * FROM winners WHERE user_id = ? AND prize_id = ?", (user_id, prize_id))
                if cur.fetchone():
                    return 0
                else:
                    conn.execute('''INSERT INTO winners (user_id, prize_id, win_time) VALUES (?, ?, ?)''', (user_id, prize_id, win_time))
                    conn.commit()
                    return 1
        except Exception as e:
            logger.error(f"Ошибка при добавлении победителя: {e}")
            return 0

    def get_winners_img(self, user_id):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute('''
                    SELECT image FROM winners 
                    INNER JOIN prizes ON winners.prize_id = prizes.prize_id
                    WHERE user_id = ?
                ''', (user_id,))
                return cur.fetchall()
        except Exception as e:
            logger.error(f"Ошибка при получении изображений победителя: {e}")
            return []

    def get_users(self):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM users")
                return [row[0] for row in cur.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при получении пользователей: {e}")
            return []

    def get_random_prize(self):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT prize_id, image FROM prizes WHERE used = 0 ORDER BY RANDOM() LIMIT 1")
                return cur.fetchone()
        except Exception as e:
            logger.error(f"Ошибка при получении случайного приза: {e}")
            return None

    def get_prize_img(self, prize_id):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT image FROM prizes WHERE prize_id = ?", (prize_id,))
                result = cur.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при получении изображения приза: {e}")
            return None

    def mark_prize_used(self, prize_id):
        try:
            conn = sqlite3.connect(self.database)
            with conn:
                conn.execute("UPDATE prizes SET used = 1 WHERE prize_id = ?", (prize_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Ошибка при отметке приза как использованного: {e}")

def create_collage(image_paths):
    try:
        if not image_paths:
            return None
            
        images = []
        for path in image_paths:
            if os.path.exists(path):
                image = cv2.imread(path)
                if image is not None:
                    # Изменяем размер изображения для единообразия
                    image = cv2.resize(image, (200, 200))
                    images.append(image)
        
        if not images:
            return None
        
        num_images = len(images)
        num_cols = max(1, floor(sqrt(num_images)))  # Поиск количество картинок по горизонтали
        num_rows = ceil(num_images/num_cols)  # Поиск количество картинок по вертикали
        
        # Создание пустого коллажа
        collage = np.zeros((num_rows * images[0].shape[0], num_cols * images[0].shape[1], 3), dtype=np.uint8)
        
        # Размещение изображений на коллаже
        for i, image in enumerate(images):
            row = i // num_cols
            col = i % num_cols
            collage[row*image.shape[0]:(row+1)*image.shape[0], col*image.shape[1]:(col+1)*image.shape[1], :] = image
        
        return collage
    except Exception as e:
        logger.error(f"Ошибка при создании коллажа: {e}")
        return None

def hide_img(img_name):
    try:
        if not os.path.exists('hidden_img'):
            os.makedirs('hidden_img')
        
        img_path = f'img/{img_name}'
        hidden_path = f'hidden_img/{img_name}'
        
        if os.path.exists(img_path) and not os.path.exists(hidden_path):
            image = cv2.imread(img_path)
            if image is not None:
                # Применяем эффект размытия для "шифрования"
                blurred = cv2.GaussianBlur(image, (51, 51), 0)
                cv2.imwrite(hidden_path, blurred)
    except Exception as e:
        logger.error(f"Ошибка при создании скрытого изображения: {e}")
