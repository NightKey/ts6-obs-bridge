import json
from sys import argv

lines = []
with open(argv[1], "r") as fp:
    lines.extend(fp.read().split("\n"))

versions = {}
for line in lines:
    if "Requirement already satisfied: " in line:
        versions[line.replace("Requirement already satisfied: ", "").split(" ")[0]] = line.split(") (")[1].replace(")", "")
    elif "Successfully installed" in line:
        for item in line.replace("Successfully installed ", "").split(" "):
            data = item.split('-')
            version = data[-1]
            name = "-".join(data[0:-1])
            versions[name] = version

with open("manifest.json", "w") as fp:
    json.dump(versions, fp)
