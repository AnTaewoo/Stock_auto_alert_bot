import os
import time
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv(override=True)


class Crawler:
    def __init__(self):
        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--headless")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )

        self.service = Service(executable_path="/usr/local/bin/chromedriver")
        self.driver = webdriver.Chrome(service=self.service, options=options)
        time.sleep(3)

    def fear_and_greed_score(self):
        URL = os.getenv("FEAR_AND_GREED_SCORE_URL")
        self.driver.get(URL)
        html_content = self.driver.page_source

        soup = BeautifulSoup(html_content, "html.parser")
        data = soup.find_all("div", class_="market-fng-gauge__overview")
        crawling_result = {}

        for div_tag in data:
            fear_and_greed_score = int(
                div_tag.find("div", class_="market-fng-gauge__dial-number").get_text(
                    strip=True
                )
            )

            history_fear_and_greed_score_tag = div_tag.find(
                "div", class_="market-fng-gauge__historical"
            )

        history_fear_and_greed_score = [
            int(value.text.strip())
            for value in history_fear_and_greed_score_tag.find_all(
                "div", class_="market-fng-gauge__historical-item-index-value"
            )
        ]

        history_fear_and_greed_score_label = [
            value.text.strip()
            for value in history_fear_and_greed_score_tag.find_all(
                "div", class_="market-fng-gauge__historical-item-label"
            )
        ]

        history_fear_and_greed_score_data = [
            {"label": "Now", "score": fear_and_greed_score}
        ]
        for label, score in zip(
            history_fear_and_greed_score_label, history_fear_and_greed_score
        ):
            history_fear_and_greed_score_data.append(
                {
                    "label": label,
                    "score": score,
                }
            )

        return history_fear_and_greed_score_data

    def crawl_live_news_feed(self):
        URL = os.getenv("NEWS_URL")
        self.driver.get(URL)

        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")

        feed = soup.select_one("#live-news-feed")

        if not feed:
            print("live-news-feed not found")
            return

        direct_divs = feed.find_all("div", recursive=False)

        if len(direct_divs) < 2:
            print("두 번째 div가 없음")
            return

        target_div = direct_divs[1]

        content_divs = target_div.find_all(
            lambda tag: tag.name == "div" and "adv-feed" not in (tag.get("class") or [])
        )

        href_list = []
        data_list = []

        for div in content_divs:
            impact_bar = div.find("div", class_="impact-bar")
            if impact_bar:
                # segment full 클래스가 포함된 div 들만 찾기
                full_segments = impact_bar.find_all(
                    "div",
                    class_=lambda classes: classes
                    and "segment" in classes
                    and "full" in classes,
                )
                full_count = len(full_segments)

                if full_count >= 5:
                    a_tags = div.find_all(
                        "a", class_=lambda classes: classes and "feed-link" in classes
                    )
                    for a in a_tags:
                        href = a.get("href")
                        if href:
                            href_list.append("https://www.stocktitan.net" + href)

        data_list = self.parse_articles(href_list)

        return data_list

    def parse_articles(self, link_list):
        articles_data = []

        for url in link_list:
            self.driver.get(url)
            html_content = self.driver.page_source
            soup = BeautifulSoup(html_content, "html.parser")

            # 1) 제목
            title_tag = soup.find("h1", class_="article-title")
            title = title_tag.get_text(strip=True) if title_tag else None

            # 2) 태그
            tags = []
            tags_container = soup.find("div", class_="tags-list-container d-flex")
            if tags_container:
                tag_spans = tags_container.find_all("span", class_="badge tag")
                tags = [tag.get_text(strip=True) for tag in tag_spans]

            # 3) 요약
            summary = ""
            summary_div = soup.find("div", id="summary-kr")
            if summary_div:
                p_tags = summary_div.find_all("p")
                summary = "\n".join(p.get_text(strip=True) for p in p_tags)

                articles_data.append(
                    {"link": url, "title": title, "tags": tags, "summary": summary}
                )

        return articles_data

    def crawl_stock_info(self):
        fear_and_greed_score = self.fear_and_greed_score()
        news_data = self.crawl_live_news_feed()

        return {
            "fear_and_greed_score": fear_and_greed_score,
            "news_data": news_data,
        }

    def quit(self):
        self.driver.quit()


if __name__ == "__main__":
    crawler = Crawler()
    crawler.fear_and_greed_score()
    crawler.crawl_live_news_feed()
    crawler.quit()


def investing_news(self):
    URL = os.getenv("INVESTING_DOTCOM_URL")
    self.driver.get(URL)

    html_content = self.driver.page_source

    soup = BeautifulSoup(html_content, "html.parser")
    ul_tag = soup.find("ul", {"data-test": "news-list"})

    li_tags = ul_tag.find_all("li", recursive=False)[:5]

    href_list = []
    for li in li_tags:
        a_tag = li.find("a", {"data-test": "article-title-link"})
        if a_tag and a_tag.has_attr("href"):
            href_list.append(a_tag["href"])

    news_data_list = []
    for news_url in href_list:
        self.driver.get(news_url)
        html_content = self.driver.page_source
        soup = BeautifulSoup(html_content, "html.parser")
        target_div = soup.find(
            "div",
            class_=lambda classes: classes and "article_WYSIWYG__O0uhw" in classes,
        )

        first_inner_div = target_div.find("div")

        p_tags = first_inner_div.find_all("p")

        text_content = "\n".join(p.get_text(strip=True) for p in p_tags)

        news_data_list["link"] = news_url
        news_data_list["article"] = text_content
