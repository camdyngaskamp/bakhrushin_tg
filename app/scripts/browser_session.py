"""Open a dedicated browser for a human to establish and save a source session."""
import argparse

from app.collectors.browser import browser_fetcher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--wait-selector', required=True, help='Selector identifying actual news content')
    args = parser.parse_args()
    config = {'fetch_mode': 'browser', 'browser_state_name': args.name}
    with browser_fetcher(config, headless=False) as fetcher:
        page = fetcher.context.new_page()
        page.goto(args.url, wait_until='domcontentloaded', timeout=45000)
        input('Откройте новости в окне браузера. Когда они доступны, нажмите Enter здесь. При отказе прервите Ctrl+C. ')
        # Verify a fresh navigation in the same context before saving; never export a denial page.
        fetcher.fetch(args.url, wait_selector=args.wait_selector)
        print(f'Сессия {args.name} сохранена в .browser-state/{args.name}.json')


if __name__ == '__main__':
    main()
