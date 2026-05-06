# CSI 三段式技术规格书 — 模板骨架

> 何时读取:为国际项目或 EPC 项目生成 CSI MasterFormat 技术规格书章节(Section)时。

## Section 编号

按 CSI MasterFormat 2020 六位编号,例如:
- `03 30 00` Cast-in-Place Concrete
- `08 11 13` Hollow Metal Doors and Frames
- `09 29 00` Gypsum Board

## 三段式骨架

```
SECTION 09 29 00 — GYPSUM BOARD

PART 1 — GENERAL

1.1  SUMMARY
     A. Section Includes:
        1. ...
     B. Related Sections:
        1. Section 09 22 16 — Non-Structural Metal Framing

1.2  REFERENCES
     A. ASTM International:
        1. ASTM C 1396 / C 1396M — Standard Specification for Gypsum Board

1.3  SUBMITTALS
     A. Product Data
     B. Samples
     C. Manufacturer's Installation Instructions

1.4  QUALITY ASSURANCE
     A. Mockups
     B. Pre-installation Conference

1.5  DELIVERY, STORAGE, AND HANDLING

1.6  WARRANTY

PART 2 — PRODUCTS

2.1  MANUFACTURERS
     A. Acceptable Manufacturers:
        1. [Manufacturer A]
        2. [Manufacturer B]

2.2  MATERIALS
     A. Gypsum Board: ASTM C 1396, Type X, 5/8 inch (15.9 mm) thick

2.3  ACCESSORIES
     A. Joint Tape
     B. Joint Compound
     C. Fasteners

2.4  FABRICATION  (if applicable)

2.5  SOURCE QUALITY CONTROL  (if applicable)

PART 3 — EXECUTION

3.1  EXAMINATION

3.2  PREPARATION

3.3  INSTALLATION
     A. General: Install in accordance with GA-216
     B. Single-Layer Application
     C. Fastening

3.4  FIELD QUALITY CONTROL

3.5  CLEANING

3.6  PROTECTION

END OF SECTION
```

## 书写约定

1. **三段不可合并、不可重排**——审图与采购按 Part 编号定位
2. 每一条用 **A. / B. / C.** 一级,**1. / 2. / 3.** 二级,**a. / b. / c.** 三级
3. 引用标准用全称 + 编号,例如 `ASTM C 1396 / C 1396M — Standard Specification for Gypsum Board`
4. 单位采用 **英制(公制)** 双标注:`5/8 inch (15.9 mm)`
5. 厂商名 / 产品型号若未确定,用 `[Specifier to confirm]` 占位

## 常用 Division 速查

| Division | 主题                                                                      |
| -------- | ------------------------------------------------------------------------- |
| 03       | Concrete                                                                  |
| 04       | Masonry                                                                   |
| 05       | Metals                                                                    |
| 06       | Wood, Plastics, and Composites                                            |
| 07       | Thermal and Moisture Protection                                           |
| 08       | Openings (Doors, Windows, Curtain Walls)                                  |
| 09       | Finishes                                                                  |
| 10       | Specialties                                                               |
| 21–28    | Fire Suppression / Plumbing / HVAC / Electrical / Communications / Safety |
| 31–35    | Sitework / Exterior Improvements / Utilities                              |
