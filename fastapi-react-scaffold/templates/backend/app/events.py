# Observer pattern over Redis pub/sub (see lld-design-patterns) -- use when one
# write should fan out to independent reactions (e.g. "notify all connected
# clients a new item was created" via a websocket relay, or "invalidate caches
# in other app instances"). Only wire this in if the prompt actually needs
# live/multi-consumer updates -- most CRUD prompts don't, and a plain function
# call is simpler and correct for a single-process demo.

import json
import redis


class EventPublisher:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def publish(self, channel: str, payload: dict) -> None:
        self._client.publish(channel, json.dumps(payload))


class EventSubscriber:
    """Run in a background task (e.g. FastAPI startup event / asyncio task) to
    react to published events -- e.g. push to a websocket, update a live counter."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def listen(self, channel: str):
        pubsub = self._client.pubsub()
        pubsub.subscribe(channel)
        for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
