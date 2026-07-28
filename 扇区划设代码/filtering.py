import re
import sys

with open(sys.argv[1], 'r') as file:
    text = file.read()

matches = re.findall(r'transfer grid (.*?) from section .*? to section 2', text)
matches = [int(match) for match in matches]
print(matches)
