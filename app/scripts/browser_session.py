"""Open a dedicated browser for a human to establish and save a source session."""
import argparse
from pathlib import Path

from app.collectors.browser import browser_fetcher
from app.collectors.cookie_import import cookies_from_header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--channel', choices=('chromium', 'chrome'), default='chromium',
                        help='chrome uses installed Google Chrome in a separate browser context')
    parser.add_argument('--wait-selector', required=True, help='Selector identifying actual news content')
    parser.add_argument('--cookies-file', type=Path,
                        help='Private file with the Cookie request header copied from a successful browser request')
    args = parser.parse_args()
    cookies = None
    if args.cookies_file is not None:
        cookies = cookies_from_header(args.cookies_file.read_text(), args.url)
    config = {
        'fetch_mode': 'browser', 'browser_state_name': args.name,
        'browser_channel': args.channel,
    }
    with browser_fetcher(config, headless=False) as fetcher:
        if cookies is not None:
            fetcher.context.clear_cookies()
            fetcher.context.add_cookies(cookies)
            print(f'Импортировано cookies: {len(cookies)}. Проверяем доступ к странице.')
        else:
            page = fetcher.context.new_page()
            page.goto(args.url, wait_until='domcontentloaded', timeout=45000)
            input('Откройте новости в окне браузера. Когда они доступны, нажмите Enter здесь. При отказе прервите Ctrl+C. ')
        # Verify a fresh navigation in the same context before saving; never export a denial page.
        fetcher.fetch(args.url, wait_selector=args.wait_selector)
        print(f'Сессия {args.name} сохранена в .browser-state/{args.name}.json')


if __name__ == '__main__':
    main()
