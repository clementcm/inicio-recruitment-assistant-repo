curl -X POST http://127.0.0.1:8000/api/chat \
-H "Content-Type: application/json" \
-d '{
    "messages": [
        {"role": "user", "content": "Find me 5 Java developers in GTA"}
    ]
}'
