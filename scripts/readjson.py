import json

with open("emner.json", encoding="utf-8") as f:
    data = json.load(f)
    print(data[0]["IMAT2022"])

    '''
    for item in data:
        if "IMAT2022" in item:
            for topic in item["IMAT2022"]:
                print(topic)
                '''