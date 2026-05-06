# aec-spec-writer scripts

| Script                    | Purpose                                                   |
| ------------------------- | --------------------------------------------------------- |
| `finish_schedule_xlsx.py` | Export a finish schedule (装修做法表) to a styled `.xlsx` |

## Quick test

```bash
python finish_schedule_xlsx.py \
  ../references/finish-schedule-example.json \
  --output /tmp/finish.xlsx \
  --project "杭州办公楼"
```

## Input JSON shape

```jsonc
[
  {
    "id": "L01",                       // 楼地面 L / 内墙面 W / 外墙面 EW / 顶棚 C / 屋面 R / 踢脚 B
    "location": "大堂地面",
    "layers": ["20 厚石材", "30 厚水泥砂浆", "100 厚 C20 混凝土"],
    "thickness_mm": 150,
    "fire_rating": "A",                // 必须是 A / B1 / B2 / B3 (GB 8624-2012)
    "remark": "房间号 101-105"
  }
]
```

## Validation

The script validates inputs and prints warnings (without failing) for:

- 缺失 `id` 或重复 `id`
- `id` 前缀不在 `{L, W, EW, C, R, B}` 范围
- 缺失 `layers`
- `fire_rating` 不在 GB 8624-2012 规定的 `{A, B1, B2, B3}` 范围

Warnings are reminders for the human author — the file is still produced.

## Dependencies

```bash
pip install openpyxl
```
