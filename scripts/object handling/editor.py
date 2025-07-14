import json

# Example object to write
obj = {
    "exam": "INGX1002",
    {
        "version": "H24"
    }
}

# Path to objects.json
json_path = "objects.json"

# Write the object to objects.json
with open(json_path, "w") as f:
    json.dump(obj, f, indent=4)