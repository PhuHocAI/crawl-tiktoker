import asyncio
import csv
import re
from typing import Callable, Optional
from urllib.parse import quote_plus
from playwright.async_api import async_playwright

# Đổi từ khóa tìm kiếm trực tiếp tại đây
SEARCH_QUERY = "Nhà đất Hà Nội"
OUTPUT_CSV = "tiktok_users.csv"
MAX_IDLE_SCROLL_ROUNDS = 5
SCROLL_PAUSE_MS = 1200
BROWSER_ARGS = [
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--window-size=1366,2200",
]


def normalize_metric(value: str) -> int:
    text = (value or "").strip().replace(",", "")
    if not text:
        return 0

    match = re.match(r"^(\d+(?:\.\d+)?)\s*([KMBkmb]?)$", text)
    if not match:
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else 0

    number = float(match.group(1))
    suffix = match.group(2).upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[suffix]
    return int(number * multiplier)


async def auto_scroll(page, pause_ms: int) -> tuple[bool, str]:
    item_selector = "div[class*='DivSearchUserItemContainer']"
    items = page.locator(item_selector)
    count_before = await items.count()
    if count_before == 0:
        await page.wait_for_timeout(pause_ms)
        return False, "no-items"

    last_item = items.nth(count_before - 1)
    try:
        top_before = await last_item.evaluate("el => el.getBoundingClientRect().top")
    except Exception:
        top_before = None

    try:
        await last_item.scroll_into_view_if_needed(timeout=0)
        await page.wait_for_timeout(max(200, pause_ms // 2))
        top_after = await last_item.evaluate("el => el.getBoundingClientRect().top")
        moved_by_geometry = (
            top_before is not None
            and top_after is not None
            and abs(float(top_after) - float(top_before)) > 2
        )
        if moved_by_geometry:
            await page.wait_for_timeout(max(200, pause_ms // 2))
            return True, "scroll-into-view"
    except Exception:
        pass

    moved_by_ancestors = await page.evaluate(
        """() => {
            const last = document.querySelectorAll("div[class*='DivSearchUserItemContainer']");
            if (!last.length) return false;

            const target = last[last.length - 1];
            const step = 900;
            let current = target;
            while (current) {
                if (current.scrollHeight > current.clientHeight + 4) {
                    const before = current.scrollTop;
                    current.scrollTop = Math.min(before + step, current.scrollHeight);
                    if (current.scrollTop > before) return true;
                }
                current = current.parentElement;
            }

            const doc = document.scrollingElement || document.documentElement;
            const before = doc.scrollTop;
            window.scrollBy(0, step);
            return doc.scrollTop > before;
        }"""
    )

    await page.wait_for_timeout(pause_ms)
    return bool(moved_by_ancestors), "ancestor-scroll"


async def crawl_tiktok_users(
    search_query: str,
    output_csv: str = OUTPUT_CSV,
    max_idle_scroll_rounds: int = MAX_IDLE_SCROLL_ROUNDS,
    scroll_pause_ms: int = SCROLL_PAUSE_MS,
    headless: bool = False,
    auto_scroll_enabled: bool = True,
    stop_event=None,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> int:
    def report(message: str) -> None:
        print(message)
        if progress_callback:
            try:
                progress_callback(message)
            except Exception:
                pass

    async with async_playwright() as p:
        if headless:
            # Headless ổn định hơn khi dùng Chromium mặc định.
            browser = await p.chromium.launch(headless=True, args=BROWSER_ARGS)
        else:
            try:
                # Ưu tiên dùng Chrome thường (channel="chrome"). Nếu thiếu, fallback Chromium.
                browser = await p.chromium.launch(channel="chrome", headless=False, args=BROWSER_ARGS)
            except Exception:
                report("Không tìm thấy Chrome channel, dùng Chromium đi kèm Playwright.")
                browser = await p.chromium.launch(headless=False, args=BROWSER_ARGS)

        context = await browser.new_context(
            viewport={"width": 1366, "height": 2200},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page.set_default_timeout(0)
        page.set_default_navigation_timeout(0)

        search_query = (search_query or "").strip()
        if not search_query:
            report("Search query đang rỗng, dừng chương trình.")
            await context.close()
            await browser.close()
            return 0

        try:
            encoded_query = quote_plus(search_query)
            search_url = f"https://www.tiktok.com/search/user?q={encoded_query}"
            report(f"--- Đang mở TikTok Search: {search_query} ---")
            await page.goto(search_url, wait_until="domcontentloaded")
            await page.wait_for_selector("div[class*='DivSearchUserItemContainer']", timeout=0)
            report(f"--- Auto scroll: {'BẬT' if auto_scroll_enabled else 'TẮT'} ---")

            users_by_username = {}
            idle_rounds = 0
            previous_total = 0

            while True:
                if stop_event is not None and stop_event.is_set():
                    report("--- Đã nhận yêu cầu dừng crawl ---")
                    break

                rows = await page.evaluate(
                    """() => {
                        const items = Array.from(document.querySelectorAll("div[class*='DivSearchUserItemContainer']"));
                        return items.map((row) => {
                            const texts = Array.from(row.querySelectorAll("p"))
                                .map((p) => (p.textContent || "").trim())
                                .filter(Boolean);

                            const name = texts[0] || "";
                            const username = texts[1] || "";

                            const followersIndex = texts.findIndex((t) => t.toLowerCase() === "followers");
                            const likesIndex = texts.findIndex((t) => t.toLowerCase() === "likes");

                            const followers = followersIndex > 0 ? texts[followersIndex - 1] : "";
                            const likes = likesIndex > 0 ? texts[likesIndex - 1] : "";

                            return { name, username, followers, likes };
                        }).filter((item) => item.username);
                    }"""
                )

                total_before = len(users_by_username)
                for item in rows:
                    username = item.get("username", "").strip()
                    username_key = username.lower()
                    if username:
                        users_by_username[username_key] = {
                            "name": item.get("name", "").strip(),
                            "username": username,
                            "followers": item.get("followers", "").strip(),
                            "likes": item.get("likes", "").strip(),
                        }

                total_after = len(users_by_username)
                if total_after == total_before == previous_total:
                    idle_rounds += 1
                else:
                    idle_rounds = 0
                previous_total = total_after

                report(
                    f"Đang lướt... thu được {total_after} user (idle {idle_rounds}/{max_idle_scroll_rounds})"
                )

                if idle_rounds >= max_idle_scroll_rounds:
                    break

                if auto_scroll_enabled:
                    moved, source = await auto_scroll(page, scroll_pause_ms)
                    report(f"↳ Auto-scroll: {'OK' if moved else 'không đổi vị trí'} ({source})")
                else:
                    await page.wait_for_timeout(scroll_pause_ms)

            with open(output_csv, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(["Tên", "Username", "NumOfFollower", "NumOfLike"])

                for item in users_by_username.values():
                    writer.writerow(
                        [
                            item.get("name", ""),
                            item.get("username", ""),
                            normalize_metric(item.get("followers", "")),
                            normalize_metric(item.get("likes", "")),
                        ]
                    )
            
            report(f"--- Đã cào {len(users_by_username)} user và lưu vào {output_csv} ---")
            await page.wait_for_timeout(3000)
            return len(users_by_username)
            
        except Exception as e:
            report(f"Có lỗi xảy ra: {e}")
            return 0
        finally:
            await context.close()
            await browser.close()


async def tiktok_search_tool():
    return await crawl_tiktok_users(search_query=SEARCH_QUERY)

if __name__ == "__main__":
    # Chạy thẳng bằng asyncio.run để đảm bảo script không thoát sớm
    try:
        asyncio.run(tiktok_search_tool())
    except KeyboardInterrupt:
        print("Đã dừng theo yêu cầu (Ctrl+C)")