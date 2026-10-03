import asyncio

from src.messaging.broker import Broker

GUIAS = {"id": 1, "topic": "ronda.1.rama.guias", "title": "Salida el sábado"}


def test_matching_subscriber_receives_the_message():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        sub = broker.subscribe(["ronda.1.rama.guias", "ronda.1.all"])
        broker.publish(GUIAS)
        return await asyncio.wait_for(sub.queue.get(), timeout=1)

    assert asyncio.run(scenario())["title"] == "Salida el sábado"


def test_non_matching_subscriber_gets_nothing():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        sub = broker.subscribe(["ronda.1.rama.alitas"])
        broker.publish(GUIAS)
        await asyncio.sleep(0.05)      # give the loop time to run _fan_out
        return sub.queue.empty()

    assert asyncio.run(scenario())


def test_kraal_wildcard_receives_every_rama():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        sub = broker.subscribe(["ronda.1.#"])
        broker.publish(GUIAS)
        return await asyncio.wait_for(sub.queue.get(), timeout=1)

    assert asyncio.run(scenario())["id"] == 1


def test_unsubscribed_listener_stops_receiving():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        sub = broker.subscribe(["ronda.1.#"])
        broker.unsubscribe(sub)
        broker.publish(GUIAS)
        await asyncio.sleep(0.05)
        return sub.queue.empty(), broker.subscriber_count

    assert asyncio.run(scenario()) == (True, 0)


def test_publish_from_a_worker_thread_is_delivered():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        sub = broker.subscribe(["ronda.1.#"])
        await asyncio.to_thread(broker.publish, GUIAS)    # same situation as a sync FastAPI route
        return await asyncio.wait_for(sub.queue.get(), timeout=1)

    assert asyncio.run(scenario())["id"] == 1


def test_close_wakes_every_subscriber_with_none():
    async def scenario():
        broker = Broker(asyncio.get_running_loop())
        a, b = broker.subscribe(["ronda.1.all"]), broker.subscribe(["ronda.2.all"])
        broker.close()
        return await a.queue.get(), await b.queue.get()

    assert asyncio.run(scenario()) == (None, None)