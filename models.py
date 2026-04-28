import requests

response = requests.get("https://openrouter.ai/api/v1/models")
all_models = response.json().get('data', [])

# Фильтруем модели, у которых цена за вход и выход равна 0
free_models = [
    model['id'] for model in all_models
    if float(model.get('pricing', {}).get('prompt', 0)) == 0
]

for model in free_models:
    print(model)