from __future__ import annotations

import logging

from src.config import Config, WatchItem
from src.nga import NgaReply, fetch_thread, page_for_lou
from src.notify import format_message, send_webhook
from src.store import PostRecord, StoreData, load, save

logger = logging.getLogger(__name__)


def process_thread(config: Config, item: WatchItem) -> None:
    try:
        latest_resp = fetch_thread(item.tid, "e", config.nga_cookie)
    except Exception as e:
        logger.error("Failed to fetch tid=%d: %s", item.tid, e)
        return

    if latest_resp.thread_info is None:
        logger.error("No thread info returned for tid=%d", item.tid)
        return

    uids = item.uids or [latest_resp.thread_info.authorid]

    # Load stored data for each user and determine page range
    stored_map: dict[int, StoreData | None] = {}
    earliest_page = latest_resp.current_page
    for uid in uids:
        stored = load(item.tid, uid)
        stored_map[uid] = stored
        if stored is not None:
            sp = page_for_lou(stored.last_page)
            earliest_page = min(earliest_page, sp)

    # Fetch intermediate pages only if at least one user has history
    need_intermediate = any(v is not None for v in stored_map.values())
    all_replies: list[NgaReply] = []
    if need_intermediate:
        for p in range(earliest_page, latest_resp.current_page):
            try:
                r = fetch_thread(item.tid, p, config.nga_cookie)
                all_replies.extend(r.replies)
            except Exception as e:
                logger.error("Failed to fetch tid=%d page=%d: %s", item.tid, p, e)
    all_replies.extend(latest_resp.replies)

    # First-run: search backwards for uids not found on the latest page
    first_run_uids = {uid for uid in uids if stored_map[uid] is None}
    found_on_latest = {r.authorid for r in latest_resp.replies} & first_run_uids
    missing_uids = first_run_uids - found_on_latest
    MAX_BACKWARD_PAGES = 10
    if missing_uids:
        floor = max(latest_resp.current_page - MAX_BACKWARD_PAGES, 1)
        for p in range(latest_resp.current_page - 1, floor - 1, -1):
            if not missing_uids:
                break
            try:
                r = fetch_thread(item.tid, p, config.nga_cookie)
                found_here = {reply.authorid for reply in r.replies} & missing_uids
                if found_here:
                    all_replies.extend(r.replies)
                    missing_uids -= found_here
            except Exception as e:
                logger.error("Failed to fetch tid=%d page=%d: %s", item.tid, p, e)

    all_replies.sort(key=lambda x: x.lou)

    for uid in uids:
        stored = stored_map[uid]
        user_replies = [r for r in all_replies if r.authorid == uid]

        if stored is None:
            new_replies = user_replies
        else:
            new_replies = [r for r in user_replies if str(r.pid) not in stored.posts]

        if not new_replies:
            continue

        username_obj = latest_resp.users.get(uid)
        username_str = username_obj.username if username_obj else str(uid)

        msg = format_message(latest_resp.thread_info.subject, username_str, new_replies)
        success = send_webhook(config.feishu_webhook_url, msg)

        if success:
            if stored is None:
                stored = StoreData(last_page=0, username=username_str, posts={})
            for r in new_replies:
                stored.posts[str(r.pid)] = PostRecord(
                    content=r.content, postdate=r.postdate, lou=r.lou
                )
            stored.last_page = max(stored.last_page, max(r.lou for r in new_replies))
            stored.username = username_str
            save(item.tid, uid, stored)
            logger.info(
                "Sent %d new replies for tid=%d uid=%d",
                len(new_replies),
                item.tid,
                uid,
            )
        else:
            logger.warning(
                "Feishu send failed, will retry next run: tid=%d uid=%d",
                item.tid,
                uid,
            )


def main() -> None:
    from src.config import load_config

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    config = load_config()
    for item in config.watch_list:
        process_thread(config, item)


if __name__ == "__main__":
    main()
