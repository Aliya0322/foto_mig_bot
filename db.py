import sqlite3



class Database:
    def __init__(self, db_file):
        self.connection = sqlite3.connect(db_file)
        self.cursor = self.connection.cursor()
        self._init_db()

    def _init_db(self):
        """Initialize database tables if they don't exist"""
        with self.connection:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    order_name TEXT NOT NULL,
                    tournament_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

    def user_exists(self, user_id):
        with self.connection:
            result = self.cursor.execute("SELECT * FROM `users` WHERE `user_id` = ?", (user_id,)).fetchone()
            return result is not None

    def add_user(self, user_id, full_name=None):
        with self.connection:
            self.cursor.execute("INSERT INTO `users` (`user_id`, `full_name`) VALUES (?, ?)", (user_id, full_name))
            return True

    def update_user_name(self, user_id, full_name):
        """Update user's full name in the database"""
        with self.connection:
            self.cursor.execute("UPDATE `users` SET `full_name` = ? WHERE `user_id` = ?", (full_name, user_id))
            return True

    def get_user_name(self, user_id):
        """Get user's full name from the database"""
        with self.connection:
            result = self.cursor.execute("SELECT `full_name` FROM `users` WHERE `user_id` = ?", (user_id,)).fetchone()
            return result[0] if result and result[0] else None

    def delete_user(self, user_id):
        with self.connection:
            self.cursor.execute("DELETE FROM `users` WHERE `user_id` = ?", (user_id,))
            return True

    def add_order(self, user_id, order_name, tournament_name):
        """Add a new order to the database"""
        with self.connection:
            self.cursor.execute(
                "INSERT INTO `orders` (`user_id`, `order_name`, `tournament_name`) VALUES (?, ?, ?)",
                (user_id, order_name, tournament_name)
            )
            return True

    def get_user_orders(self, user_id):
        """Get all orders for a specific user"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT `order_id`, `order_name`, `tournament_name`, `created_at` FROM `orders` WHERE `user_id` = ? ORDER BY `created_at` DESC",
                (user_id,)
            ).fetchall()
            return result

    def get_order_by_id(self, order_id):
        """Get order by order_id"""
        with self.connection:
            result = self.cursor.execute(
                "SELECT `order_id`, `user_id`, `order_name`, `tournament_name`, `created_at` FROM `orders` WHERE `order_id` = ?",
                (order_id,)
            ).fetchone()
            return result

    def close(self):
        self.connection.close()