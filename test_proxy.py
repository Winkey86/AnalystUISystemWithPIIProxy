import asyncio
import httpx
import json

async def main():
    payload = {
        "model": "yandex-private",
        "messages": [
            {
                "role": "user",
                "content": "**Наименование оператора: полное наименование** - Общество с ограниченной ответственностью «Коммерсант плюс»\n**Адрес оператора:** г. Симферополь, ул. Ленина, д. 1\n**ИНН:** 9109999999;"
            }
        ],
        "stream": False
    }
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "http://localhost:8081/v1/chat/completions",
            json=payload,
            headers={"Authorization": "Bearer local-dev-key"}
        )
        print("Status:", res.status_code)
        try:
            print(json.dumps(res.json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print("Response:", res.text)

asyncio.run(main())
