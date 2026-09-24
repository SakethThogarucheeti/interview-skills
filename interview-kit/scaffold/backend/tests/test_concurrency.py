# Regression test for the graded write race: concurrent PATCHes to different
# fields of one item must BOTH survive. A read -> modify -> save implementation
# fails this; the atomic update_fields passes. Copy this shape for any new
# mutating endpoint (counters, quotas, balances).
import threading
from concurrent.futures import ThreadPoolExecutor

from app.models import ItemCreate, ItemUpdate
from app.repository import InMemoryItemRepository
from app.service import ItemService


def test_concurrent_patches_do_not_lose_updates():
    svc = ItemService(InMemoryItemRepository())
    for trial in range(25):
        item = svc.create_item(ItemCreate(title="t0", body="b0"))
        start = threading.Barrier(2)

        def patch(update: ItemUpdate, item_id=item.id, start=start):
            start.wait()
            svc.update_item(item_id, update)

        with ThreadPoolExecutor(2) as pool:
            list(pool.map(patch, [ItemUpdate(title=f"t{trial}"), ItemUpdate(body=f"b{trial}")]))
        final = svc.get_item(item.id)
        assert (final.title, final.body) == (f"t{trial}", f"b{trial}")
