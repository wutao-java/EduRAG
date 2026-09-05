class MySQLConversationRepository:
    """使用现有 MySQLClient 持久化会话和最近对话。"""

    def __init__(self, mysql_client):
        self.mysql_client = mysql_client

    def initialize(self):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    INDEX idx_session_id (session_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id VARCHAR(36) PRIMARY KEY,
                    title VARCHAR(80) NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_updated_at (updated_at)
                )
            """)

    def create_session(self, session_id, title):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            cursor.execute("""
                INSERT INTO conversation_sessions (session_id, title)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE title = VALUES(title), updated_at = NOW()
            """, (session_id, title))
            cursor.execute("""
                SELECT updated_at
                FROM conversation_sessions
                WHERE session_id = %s
            """, (session_id,))
            updated_at = cursor.fetchone()[0]
        return {
            "session_id": session_id,
            "title": title,
            "updated_at": updated_at.isoformat(timespec="seconds"),
        }

    def list_sessions(self):
        with self.mysql_client.cursor_context() as cursor:
            cursor.execute("""
                SELECT session_id, title, updated_at
                FROM conversation_sessions
                ORDER BY updated_at DESC
                LIMIT 20
            """)
            return [
                {
                    "session_id": row[0],
                    "title": row[1],
                    "updated_at": row[2].isoformat(timespec="seconds"),
                }
                for row in cursor.fetchall()
            ]

    def rename_session(self, session_id, title):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            cursor.execute("""
                UPDATE conversation_sessions
                SET title = %s, updated_at = NOW()
                WHERE session_id = %s
            """, (title, session_id))
            return cursor.rowcount > 0

    def delete_session(self, session_id):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            cursor.execute(
                "DELETE FROM conversations WHERE session_id = %s",
                (session_id,),
            )
            cursor.execute(
                "DELETE FROM conversation_sessions WHERE session_id = %s",
                (session_id,),
            )
        return True

    def get_history(self, session_id, limit):
        with self.mysql_client.cursor_context() as cursor:
            return self._read_recent_history(cursor, session_id, limit)

    def append_history(self, session_id, question, answer, limit):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            self._touch_session(cursor, session_id, question)
            cursor.execute("""
                INSERT INTO conversations (session_id, question, answer, timestamp)
                VALUES (%s, %s, %s, NOW())
            """, (session_id, question, answer))
            history = self._read_recent_history(cursor, session_id, limit)
            cursor.execute("""
                DELETE FROM conversations
                WHERE session_id = %s AND id NOT IN (
                    SELECT id FROM (
                        SELECT id
                        FROM conversations
                        WHERE session_id = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    ) AS recent_conversations
                )
            """, (session_id, session_id, limit))
        return history

    def clear_history(self, session_id):
        with self.mysql_client.cursor_context(commit=True) as cursor:
            cursor.execute(
                "DELETE FROM conversations WHERE session_id = %s",
                (session_id,),
            )
        return True

    @staticmethod
    def _touch_session(cursor, session_id, title):
        cursor.execute("""
            INSERT INTO conversation_sessions (session_id, title)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE updated_at = NOW()
        """, (session_id, title[:80] or "新的学习问题"))

    @staticmethod
    def _read_recent_history(cursor, session_id, limit):
        cursor.execute("""
            SELECT question, answer
            FROM conversations
            WHERE session_id = %s
            ORDER BY timestamp DESC
            LIMIT %s
        """, (session_id, limit))
        history = [
            {"question": row[0], "answer": row[1]}
            for row in cursor.fetchall()
        ]
        return history[::-1]
