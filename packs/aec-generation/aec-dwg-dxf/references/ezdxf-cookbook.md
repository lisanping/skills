# ezdxf 操作速查 (Cookbook)

> 何时读取:写脚本前需要回忆 ezdxf 的常见 API 时。

## 1. 打开 / 保存

```python
import ezdxf
doc = ezdxf.readfile("input.dxf")          # 读取
doc = ezdxf.read("file.dxf", errors="ignore")  # 容错读取损坏文件
doc.saveas("output.dxf")                   # 另存
```

如版本不兼容:`ezdxf.recover.readfile("input.dxf")` 自动恢复。

## 2. 实体查询

```python
msp = doc.modelspace()
for line in msp.query("LINE"):              # 所有直线
    print(line.dxf.start, line.dxf.end)

# 多类型 + 过滤
walls = msp.query('LWPOLYLINE[layer=="WALL"]')
```

支持的实体类型常见:`LINE`, `LWPOLYLINE`, `POLYLINE`, `CIRCLE`, `ARC`, `TEXT`, `MTEXT`,
`INSERT`, `DIMENSION`, `HATCH`, `SPLINE`, `ELLIPSE`, `3DFACE`, `MESH`, `SOLID`。

## 3. 图层

```python
for layer in doc.layers:
    print(layer.dxf.name, layer.dxf.color, layer.dxf.linetype, layer.is_off())

# 新建图层
doc.layers.add("NEW_LAYER", color=3, linetype="DASHED")
```

## 4. 块 (Block) 与属性 (Attrib)

```python
# 遍历所有块定义
for block in doc.blocks:
    print(block.name)

# 块引用 (INSERT) 的属性
for insert in msp.query("INSERT"):
    print(insert.dxf.name)                  # 块名
    for attrib in insert.attribs:           # ATTRIB 实体
        print(attrib.dxf.tag, "=", attrib.dxf.text)
```

> 注意:`insert.attribs` 是属性实体的迭代器,不是字典。
> 若同 tag 多次出现,需要自己处理 (通常取第一个或后者覆盖前者)。

## 5. 文字

```python
for text in msp.query("TEXT MTEXT"):
    content = text.dxf.text if text.dxftype() == "TEXT" else text.text
    print(content)
```

`MTEXT` 的 `text` 属性可能含格式控制码 (`\\P` 换行、`{\\fSimSun;...}` 字体),
如需纯文本用 `ezdxf.tools.text.MTextEditor` 或正则清洗。

## 6. 几何边界

```python
from ezdxf import bbox
extents = bbox.extents(msp)                # 整个模型空间
print(extents.extmin, extents.extmax)

# 单个实体
ent_box = bbox.extents([entity])
```

## 7. 单位

```python
print(doc.header["$INSUNITS"])              # 0=未指定 1=英寸 4=毫米 6=米
doc.header["$INSUNITS"] = 4                 # 设置为毫米
```

## 8. 中文字体

ezdxf 默认不嵌入字体。生成中文时:

```python
doc = ezdxf.new(dxfversion="R2018", setup=True)
doc.styles.add("CHINESE", font="simsun.ttf")
msp.add_text("中文", dxfattribs={"style": "CHINESE", "height": 250})
```

下游 CAD 打开时若提示缺字体,提供 `simsun.ttf` 或映射到 `gbcbig.shx`。

## 9. 容错与恢复

```python
from ezdxf import recover
try:
    doc, auditor = recover.readfile("broken.dxf")
    if auditor.has_errors:
        for err in auditor.errors:
            print(err)
except IOError:
    print("文件不存在")
except ezdxf.DXFStructureError:
    print("DXF 结构损坏,无法恢复")
```

## 10. 常见坑

| 坑                                          | 解法                                                 |
| ------------------------------------------- | ---------------------------------------------------- |
| 中文图层名乱码                              | 文件保存时 `encoding="utf-8"`;ezdxf ≥ 1.0 默认 UTF-8 |
| INSERT 缩放未应用到子实体                   | 用 `insert.virtual_entities()` 取得实际几何          |
| 块定义被多个 INSERT 引用,修改块影响所有引用 | 需要独立时先 `doc.blocks.new(...)` 复制              |
| `LWPOLYLINE` 与 `POLYLINE` 不同             | LW 是轻量版 (2D),POLYLINE 兼容 3D                    |
| DWG 格式不支持                              | 必须先转 DXF (ODA File Converter)                    |
