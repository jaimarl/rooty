import sqlite3
import datetime
from core import config

class SQLiteMemory:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS interactions 
                USING fts5(timestamp, user_msg, ai_msg)
            ''')
            conn.commit()

    def save_interaction(self, user_msg: str, ai_msg: str):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO interactions (timestamp, user_msg, ai_msg) 
                VALUES (?, ?, ?)
            ''', (timestamp, user_msg, ai_msg))
            conn.commit()

    def search_relevant_context(self, query: str, limit: int = config.MEMORY_SEARCH_LIMIT) -> str:
        clean_query = "".join(char for char in query if char.isalnum() or char.isspace())
        words = clean_query.split()
        
        if not words:
            return ""

        match_query = " OR ".join(words)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    SELECT timestamp, user_msg, ai_msg 
                    FROM interactions 
                    WHERE interactions MATCH ? 
                    ORDER BY rank 
                    LIMIT ?
                ''', (match_query, limit))
                results = cursor.fetchall()
            except sqlite3.OperationalError:
                return ""

        if not results:
            return ""

        context_block = "\n--- INFORMATION FROM PAST DIALOGS ---\n"
        for row in results:
            context_block += f"[{row[0]}]\nUser: {row[1]}\nAssistant: {row[2]}\n\n"
        context_block += "----------------------------------------\n" 

        return context_block
