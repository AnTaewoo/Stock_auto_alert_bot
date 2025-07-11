import os
import requests
import time
import mysql.connector
from datetime import datetime
from zoneinfo import ZoneInfo

from crawl_stock import Crawler

from dotenv import load_dotenv

load_dotenv(override=True)
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_URL = f"https://api.telegram.org/bot{API_TOKEN}"
LAST_UPDATE_ID = 0


class AlertBot:
    def __init__(self):
        db_config = {
            "host": os.getenv("HOST"),
            "user": os.getenv("USER"),  # MySQL 사용자 이름
            "password": os.getenv("PASSWORD"),  # MySQL 비밀번호
        }

        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()

        # 데이터베이스 생성 (없으면 생성)
        cursor.execute("CREATE DATABASE IF NOT EXISTS web_data;")
        connection.commit()

        # 데이터베이스 연결 갱신
        db_config["database"] = "web_data"
        connection.close()
        self.connection = mysql.connector.connect(**db_config)
        self.cursor = self.connection.cursor()

        # 7. 테이블 생성
        table_creation_query = """
            CREATE TABLE IF NOT EXISTS telegram_alerts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE NOT NULL UNIQUE,
            alerted TINYINT(1) NOT NULL DEFAULT 0
        );
        """
        self.cursor.execute(table_creation_query)

        table_creation_query = """
        CREATE TABLE IF NOT EXISTS chat_id (
            chat_id BIGINT NOT NULL PRIMARY KEY,
            name VARCHAR(255) NOT NULL
        );
        """
        self.cursor.execute(table_creation_query)

    def run(self):
        def insert_chat_id(chat_id, name):
            insert_query = "INSERT INTO chat_id (chat_id, name) VALUES (%s, %s)"
            self.cursor.execute(insert_query, (chat_id, name))
            self.connection.commit()

        def select_chat_id():
            select_query = "SELECT * FROM chat_id"

            self.cursor.execute(select_query)
            result = self.cursor.fetchall()

            return result

        def listen_for_command():
            global LAST_UPDATE_ID

            data_chat_id_db = select_chat_id()
            chat_id_list = [data[0] for data in data_chat_id_db]

            params = {
                "offset": LAST_UPDATE_ID + 1,
                "limit": 1,
                "allowed_updates": ["message"],
            }
            response = requests.get(f"{API_URL}/getUpdates", params=params)

            if response.status_code != 200:
                print(f"❌ 전송 실패: {chat_id} - {response.text}")
            elif response.json()["result"]:
                result = response.json()["result"][0]

                update_id = result["update_id"]
                msg = result["message"]
                chat_id = msg["from"]["id"]
                name = msg["from"]["first_name"]
                command = msg["text"]

                LAST_UPDATE_ID = update_id

                if command:
                    message = ""
                    if chat_id_list and chat_id in chat_id_list:
                        if command == "/start":
                            message = f"📈주식알림봇 입니다. 반갑습니다!"
                        elif command == "/방어2소대":
                            message = f"❌이미 등록된 사용자 입니다."
                        elif command[0] == "/":
                            message = f"❌암호가 틀렸습니다."
                        else:
                            message = "/를 통해 명령어를 검색하세요!"
                    else:
                        if command == "/start":
                            message = (
                                f"📈주식알림봇 입니다. /를 붙이고 암호를 입력해주세요."
                            )
                        elif command == "/방어2소대":
                            message = f"✅등록되었습니다!"
                            insert_chat_id(chat_id, name)
                        elif command[0] == "/":
                            message = f"❌암호가 틀렸습니다."
                        else:
                            message = "/를 통해 명령어를 검색하세요!"

                    telegram_bot_send(chat_id, message)

        def alert_bot():
            now = datetime.now(ZoneInfo("Asia/Seoul"))
            current_time = now.strftime("%H:%M")
            current_date = now.strftime("%Y-%m-%d")
            if current_time == "20:49":
                select_query = (
                    "SELECT id FROM telegram_alerts WHERE date = %s AND alerted = TRUE"
                )
                self.cursor.execute(select_query, (current_date,))
                result = self.cursor.fetchone()

                if not result:
                    data_chat_id_db = select_chat_id()
                    chat_id_list = [data[0] for data in data_chat_id_db]

                    crawler = Crawler()
                    crawl_result = crawler.crawl_stock_info()
                    crawler.quit()

                    fear_and_score = crawl_result["fear_and_greed_score"]
                    news_data = crawl_result["news_data"]

                    if len(news_data) > 5:
                        news_data = news_data[4:]

                    is_alert = True

                    fear_msg = (
                        f"📊 *공포탐욕 지수*\n"
                        f"✅ *{fear_and_score[0]['label']}*: {fear_and_score[0]['score']}\n"
                    )
                    for item in fear_and_score[1:]:
                        fear_msg += f"🔹 {item['label']}: {item['score']}\n"

                    for chat_id in chat_id_list:
                        if not telegram_bot_send(
                            chat_id,
                            (
                                f"📅 날짜: {current_date} 🕰 시간: {current_time}\n\n"
                                f"{fear_msg}\n"
                            ),
                        ):
                            is_alert = False

                    for chat_id in chat_id_list:
                        for news in news_data:
                            news_msg = "📰 *오늘의 뉴스 요약*\n"
                            tags_text = (
                                ", ".join(news["tags"]) if news["tags"] else "No tags"
                            )
                            summary_text = (
                                f"\n{news['summary']}" if news["summary"] else ""
                            )
                            news_msg += (
                                f"\n📌 *{news['title']}*\n"
                                f"🏷 분류: {tags_text}"
                                f"{summary_text}\n"
                                # f"🔗 [더 읽어보기]({news['link']})\n" # 나중에 필요하면 추가
                            )

                            if not telegram_bot_send(
                                chat_id,
                                (f"{news_msg}\n"),
                            ):
                                is_alert = False

                    if is_alert:
                        print(f"✅ {current_date}날짜로 공지 완료 했습니다.")

                        insert_query = "INSERT INTO telegram_alerts (date, alerted) VALUES (%s, TRUE)"
                        self.cursor.execute(insert_query, (current_date,))
                        self.connection.commit()
                    else:
                        print(f"❌ 공지 실패했습니다")

        def telegram_bot_send(chat_id, message):
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
            }
            response = requests.post(f"{API_URL}/sendMessage", data=payload)

            if response.status_code != 200:
                print(f"❌ 전송 실패: {chat_id} - {response.text}")
                return False
            else:
                print(f"✅ 전송 완료: {chat_id}")
                return True

        while True:
            listen_for_command()
            alert_bot()
            time.sleep(5)


if __name__ == "__main__":
    bot = AlertBot()
    bot.run()
