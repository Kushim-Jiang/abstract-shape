"""验证重构后的 ob.json"""

import json

with open("backend/data/ob.json", "r", encoding="utf-8") as f:
    d = json.load(f)
obs = d.get("ob", [])
print("条目数:", len(obs))

# 看前几条
for i, o in enumerate(obs):
    if i < 5:
        annos = o.get("annotations", [])
        print(f'[{o["num"]}] glyph={repr(o["glyph"])} annos={annos}')
    else:
        break

print("...")

# 看最后几条
for o in obs[-3:]:
    annos = o.get("annotations", [])
    print(f'[{o["num"]}] glyph={repr(o["glyph"])} annos={[a for a in annos[:2]]}')
