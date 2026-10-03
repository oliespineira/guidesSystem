| Date/commit | Tool | Prompt | | Date/commit | Tool | Prompt | Disposition | What changed & why | In my own words, how this works |
|---|---|---|---|---|---|
| 2026-09-19 / <hash> | Claude | "Difference between Flask and FastAPI, and which fits my app" | Accepted | N/A. I first leaned toward Flask, but after the comparison and a chat with my teacher (who said neither is clearly better for this scope) I chose FastAPI. | I chose FastAPI because request bodies are validated from type hints (Pydantic models like `RondaCreate`), the database connection is opened and closed per request with `Depends(get_db)`, and `/docs` is generated automatically. Flask would have needed manual validation code. |
|3/10|claude|explain in this case whether i would need an observer architecture or a subscriber|modified|created a new segment so that subscribers listen to notices|ok so when the broker notifies, each individual has a queue, if the message is related to that specific queue, it will be sent there. all messages reeach all individuals, but only the ones whose characteristics match are stoerd in the queue, for example, if i belong to guias, a message qith the slug guias will stay in my queue| 


