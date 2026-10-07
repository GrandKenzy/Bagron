from core.processor.objects.base import Object

def process(content: dict[Object, str]):
    for item, name in content.items():
        print(name, '|', item)
        