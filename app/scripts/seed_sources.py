from __future__ import annotations

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models import Source, SourceType

START_SOURCES = [
    # --- Official Bakhrushin Museum ---
    {
        "name": "Бахрушинский музей — Новости (официальный сайт)",
        "type": "html",
        "url": "https://www.bakhrushinmuseum.ru/news/",
        "parser_config": {
            "include_regex": [r"bakhrushinmuseum\.ru/\d{4}/\d{2}/\d{2}/"],
            "exclude_regex": [r"/news/?$"],
            "same_domain": True,
            "max_items": 50,
        },
    },

    # --- Major theatres (official sites) ---
    {
        "name": "Большой театр — Новости",
        "type": "html",
        "url": "https://bolshoi.ru/news",
        "parser_config": {
            "include_regex": [r"bolshoi\.ru/(ru/|en/)?news/"],
            "exclude_regex": [r"/news/?$"],
            "same_domain": True,
            "max_items": 60,
        },
    },
    {
        "name": "Малый театр — Новости",
        "type": "html",
        "url": "https://www.maly.ru/news",
        "parser_config": {
            "include_regex": [r"maly\.ru/news/\d+"],
            "exclude_regex": [r"/news/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Александринский театр — Новости",
        "type": "html",
        "url": "https://alexandrinsky.ru/novosti/",
        "parser_config": {
            "include_regex": [r"alexandrinsky\.ru/novosti/"],
            "exclude_regex": [r"/novosti/?$", r"/novosti/arhiv/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Мариинский театр — Новости",
        "type": "html",
        "url": "https://www.mariinsky.ru/news1/",
        "parser_config": {
            "include_regex": [r"mariinsky\.ru/news1/"],
            "exclude_regex": [r"/news1/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Театр Наций — Посты/новости",
        "type": "html",
        "url": "https://theatreofnations.ru/posts/",
        "parser_config": {
            "include_regex": [r"theatreofnations\.ru/posts/"],
            "exclude_regex": [r"/posts/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Театр им. Евгения Вахтангова — Новости",
        "type": "html",
        "url": "https://vakhtangov.ru/media/news/theatre/",
        "parser_config": {
            "include_regex": [r"vakhtangov\.ru/media/news/"],
            "exclude_regex": [r"/media/news/theatre/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Ленком Марка Захарова — Новости",
        "type": "html",
        "url": "https://lenkom.ru/news",
        "parser_config": {
            "include_regex": [r"lenkom\.ru/news/"],
            "exclude_regex": [r"/news/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Театр «Современник» — Новости",
        "type": "html",
        "url": "https://sovremennik.ru/news",
        "parser_config": {
            "include_regex": [r"sovremennik\.ru/news/"],
            "exclude_regex": [r"/news/?$"],
            "same_domain": True,
            "max_items": 120,
        },
    },
    {
        "name": "РАМТ — Новости",
        "type": "html",
        "url": "https://ramt.ru/news/",
        "parser_config": {
            "include_regex": [r"ramt\.ru/news/"],
            "exclude_regex": [r"/news/?$", r"\?year="],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "МХТ им. А.П. Чехова — Новости",
        "type": "html",
        "url": "https://mxat.ru/o-teatre/novosti/",
        "parser_config": {
            "include_regex": [r"mxat\.ru/o-teatre/novosti/"],
            "exclude_regex": [r"/o-teatre/novosti/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },
    {
        "name": "Театр им. А.С. Пушкина (Москва) — Новости",
        "type": "html",
        "url": "https://teatrpushkin.ru/press_centr/novosti/",
        "parser_config": {
            "include_regex": [r"teatrpushkin\.ru/press_centr/novosti/"],
            "exclude_regex": [r"/press_centr/novosti/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },

    # --- Awards / festivals ---
    {
        "name": "«Золотая Маска» — Новости (СТД РФ)",
        "type": "html",
        "url": "https://goldenmask.stdrf.ru/novosti/",
        "parser_config": {
            "include_regex": [r"goldenmask\.stdrf\.ru/novosti/"],
            "exclude_regex": [r"/novosti/?$"],
            "same_domain": True,
            "max_items": 80,
        },
    },

    # --- Culture / arts institutions (official) ---
    {
        "name": "Минкульт РФ — Новости Министерства",
        "type": "html",
        "url": "https://culture.gov.ru/press/news/",
        "parser_config": {
            "include_regex": [r"culture\.gov\.ru/press/news/"],
            "exclude_regex": [r"/press/news/?$"],
            "same_domain": True,
            "max_items": 100,
        },
    },

    # --- RSS sources (international) ---
    {"name": "Playbill — News (RSS)", "type": "rss", "url": "https://playbill.com/rss/news", "parser_config": {}},
    {
        "name": "Playbill — Combined feed (RSS)",
        "type": "rss",
        "url": "https://playbill.com/rss/combined-feed-news-features-celebrity-buzz",
        "parser_config": {},
    },
    {"name": "Theatre-News.com — News (RSS)", "type": "rss", "url": "https://www.theatre-news.com/rss/UK/news", "parser_config": {}},
    {"name": "Theatre-News.com — Reviews/Theatre (RSS)", "type": "rss", "url": "https://www.theatre-news.com/rss/UK/reviews/theatre", "parser_config": {}},

    # --- RSS sources (general; filter by keywords later) ---
    {"name": "Interfax.ru — RSS (общая лента; фильтрация по ключевым словам)", "type": "rss", "url": "https://www.interfax.ru/rss.asp", "parser_config": {}},
    {"name": "РИА Новости — RSS index (общая лента; фильтрация по ключевым словам)", "type": "rss", "url": "https://ria.ru/export/rss2/index.xml", "parser_config": {}},
]

def main():
    with SessionLocal() as db:
        created = 0
        updated = 0

        for s in START_SOURCES:
            src = db.scalar(select(Source).where(Source.url == s["url"]))
            if src:
                # keep name/type/parser_config in sync (idempotent seed)
                new_type = SourceType(s["type"])
                if src.name != s["name"] or src.type != new_type or (src.parser_config or {}) != (s.get("parser_config") or {}):
                    src.name = s["name"]
                    src.type = new_type
                    src.parser_config = s.get("parser_config") or {}
                    updated += 1
                continue

            db.add(
                Source(
                    name=s["name"],
                    type=SourceType(s["type"]),
                    url=s["url"],
                    enabled=True,
                    parser_config=s.get("parser_config") or {},
                )
            )
            created += 1

        db.commit()
        print(f"Seeded sources: created={created}, updated={updated}, total={len(START_SOURCES)}")

if __name__ == "__main__":
    main()
